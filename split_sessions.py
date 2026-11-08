#!/usr/bin/env python3
"""
Step 3 — 两场拍摄拆分检查。

一次导入里照片/视频的时间轴如果中间出现很大的空档，很可能其实是两场不同的
拍摄（比如上午一场、晚上一场，或跨天两场）。本脚本按「最大空档」把这一批
拆成两个文件夹（至多两场），并在 cmd 里询问 y/n 后再执行。

时间来源（按优先级）：
  1. 文件名已经按时间重命名过（YYYY-MM-DD_HH-MM-SS）→ 直接从文件名读，最快；
  2. 未重命名的照片 → EXIF DateTimeOriginal / DateTime；
  3. 未重命名的视频 → ffprobe 的 creation_time（转北京时间）。

拆分结果（示例，原目录结构保留）:
  E:/_Photo/temp/0924/
  ├── 2026-09-24/            ← 第一场
  │   ├── <照片>
  │   ├── CLIP/              ← 该场次的 CLIP 视频
  │   └── DJI/               ← 该场次的 DJI 视频
  └── 2026-09-25/            ← 第二场

用法:
  python split_sessions.py --dry                   # 只检测并报告，不改动任何文件
  python split_sessions.py --go                    # 检测 → 询问 y/n → 拆分
  python split_sessions.py --yes                   # 检测 → 直接拆分（不询问）
  python split_sessions.py --dir <文件夹> --go      # 对指定文件夹操作
  python split_sessions.py --gap-minutes 180 --go  # 自定义空档阈值（默认取 config）
  python split_sessions.py --go --no-db            # 不更新导入指纹库
"""

import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from config import (
        TARGET_DIR, SESSION_GAP_MINUTES, SESSION_MIN_FILES, IMPORT_DB_PATH,
    )
except ImportError as e:
    raise SystemExit("✗ 找不到 config.py，请在项目根目录下运行本脚本。") from e

from import_db import ImportDB, partial_md5
from rename_photos import get_exif_datetime, parse_exif_date   # 复用 EXIF 读取
from rename_videos import get_creation_time_utc, UTC8          # 复用 creation_time

DATE_FORMAT = "%Y-%m-%d_%H-%M-%S"
# 已重命名的文件：2026-09-10_18-58-48.jpg / 2026-09-10_18-58-48_01.jpg
RENAMED_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})(?:_\d{2})?$")

PHOTO_SUFFIXES = {".jpg", ".jpeg"}
MEDIA_SUFFIXES = PHOTO_SUFFIXES | {".mp4"}

SUB_DIRS = ("CLIP", "DJI")


def arg_value(args: list[str], name: str) -> str | None:
    """取 `--name value` 形式参数的值，缺值返回 None。"""
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def fmt_gap(td: timedelta) -> str:
    """把空档时长写成人话：2 天 3 小时 / 5 小时 20 分钟 / 45 分钟"""
    minutes = int(td.total_seconds() // 60)
    days, rest = divmod(minutes, 60 * 24)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} 天 {hours} 小时"
    if hours:
        return f"{hours} 小时 {mins} 分钟"
    return f"{mins} 分钟"


# ── 收集文件 & 读取时间 ───────────────────────────────────
def collect_files(folder: Path) -> list[Path]:
    """收集本批照片/视频：根目录 + CLIP/ + DJI/（XML 等附属文件不算）"""
    files = [p for p in sorted(folder.iterdir())
             if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES]
    for sub in SUB_DIRS:
        d = folder / sub
        if d.is_dir():
            files += [p for p in sorted(d.iterdir())
                      if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES]
    return files


def timestamp_of(path: Path) -> datetime | None:
    """取拍摄时间：先看文件名（已重命名过），再退回 EXIF / ffprobe。"""
    m = RENAMED_RE.match(path.stem)
    if m:
        try:
            return datetime.strptime(m.group(1), DATE_FORMAT)
        except ValueError:
            pass

    ext = path.suffix.lower()
    if ext in PHOTO_SUFFIXES:
        exif_str = get_exif_datetime(path)
        return parse_exif_date(exif_str) if exif_str else None
    if ext == ".mp4":
        dt_utc = get_creation_time_utc(path)
        return dt_utc.astimezone(UTC8).replace(tzinfo=None) if dt_utc else None
    return None


def analyze(folder: Path) -> tuple[list[tuple[datetime, Path]], list[Path]]:
    """按拍摄时间排序本批文件；返回 ([(时间, 文件)], [读不出时间的文件])"""
    items: list[tuple[datetime, Path]] = []
    unknown: list[Path] = []
    for p in collect_files(folder):
        dt = timestamp_of(p)
        if dt is None:
            unknown.append(p)
        else:
            items.append((dt, p))
    items.sort(key=lambda it: it[0])
    return items, unknown


# ── 找最大空档 ────────────────────────────────────────────
def best_split(items: list[tuple[datetime, Path]], gap_minutes: int,
               min_files: int) -> tuple[int, timedelta] | None:
    """在时间轴上找最大的空档，返回 (拆分下标, 空档时长)；不满足阈值返回 None。

    拆分下标 i 表示 items[:i] 为第一场、items[i:] 为第二场；
    每场至少 min_files 个文件，避免把零星几个文件拆出去。
    """
    if len(items) < min_files * 2:
        return None
    best: tuple[int, timedelta] | None = None
    for i in range(min_files, len(items) - min_files + 1):
        gap = items[i][0] - items[i - 1][0]
        if best is None or gap > best[1]:
            best = (i, gap)
    if best is not None and best[1] >= timedelta(minutes=gap_minutes):
        return best
    return None


# ── 目标文件夹命名 ────────────────────────────────────────
def _unique_dir(folder: Path, name: str) -> Path:
    """目录已存在时加 _1、_2… 后缀，避免和已有文件混在一起。"""
    d = folder / name
    if not d.exists():
        return d
    n = 1
    while (folder / f"{name}_{n}").exists():
        n += 1
    return folder / f"{name}_{n}"


def session_dirs(folder: Path, items: list[tuple[datetime, Path]],
                 idx: int) -> list[Path]:
    """按每场第一张的日期命名文件夹；同一天两场时用 -1 / -2 区分。"""
    names = [items[0][0].strftime("%Y-%m-%d"), items[idx][0].strftime("%Y-%m-%d")]
    if names[0] == names[1]:
        names = [f"{names[0]}-1", f"{names[1]}-2"]
    return [_unique_dir(folder, n) for n in names]


def _unique_file(dst_dir: Path, name: str) -> Path:
    """目标文件重名时加 _1、_2… 后缀。"""
    dst = dst_dir / name
    if not dst.exists():
        return dst
    stem, suffix = dst.stem, dst.suffix
    n = 1
    while (dst_dir / f"{stem}_{n}{suffix}").exists():
        n += 1
    return dst_dir / f"{stem}_{n}{suffix}"


# ── 执行拆分 ──────────────────────────────────────────────
def split_batch(folder: Path, items: list[tuple[datetime, Path]], idx: int,
                dirs: list[Path]) -> list[tuple[Path, Path]]:
    """把两场文件分别移入 dirs[0] / dirs[1]，保留 CLIP/、DJI/ 子结构。

    返回 [(原路径, 新路径)]，供之后修正指纹库用。
    """
    moves: list[tuple[Path, Path]] = []
    for i, (_dt, src) in enumerate(items):
        target_root = dirs[0] if i < idx else dirs[1]
        rel = src.parent.relative_to(folder)          # 根目录 → Path('.')
        dst_dir = target_root / rel if rel.parts else target_root
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = _unique_file(dst_dir, src.name)
        shutil.move(str(src), str(dst))
        print(f"  → {src.name}  →  {dst_dir.relative_to(folder).as_posix()}/")
        moves.append((src, dst))
    return moves


def prune_empty_dirs(folder: Path):
    """拆分后清掉空出来的 CLIP/、DJI/（只删空目录，不动任何文件）。"""
    for sub in SUB_DIRS:
        d = folder / sub
        if d.is_dir() and not any(d.iterdir()):
            try:
                d.rmdir()
                print(f"  🧹 已清理空目录: {sub}/")
            except OSError:
                pass


# ── 修正导入指纹库里的目标目录 ────────────────────────────
def _match_record(records: list[dict], path: Path, size: int) -> dict | None:
    """在旧目录的记录里按大小找对应条目；大小撞车时用内容指纹确认。"""
    same_size = [r for r in records if r["size"] == size]
    if len(same_size) == 1:
        return same_size[0]
    if not same_size:
        return None
    fp = partial_md5(path)
    for r in same_size:
        if r["partial_md5"] == fp:
            return r
    return None


def update_db(moves: list[tuple[Path, Path]]) -> None:
    """拆分后把指纹库里记录的 dst_dir 改到新位置（只改库里的路径文字，不动文件）。"""
    if not IMPORT_DB_PATH.exists():
        return
    db = ImportDB(IMPORT_DB_PATH)
    try:
        cache: dict[str, list[dict]] = {}
        updated = 0
        for old, new in moves:
            old_dir = str(old.parent)
            if old_dir not in cache:
                cache[old_dir] = db.by_dst_dir(old_dir)
            try:
                size = new.stat().st_size
            except OSError:
                continue
            rec = _match_record(cache[old_dir], new, size)
            if rec is None:
                continue
            updated += db.set_dst_dir(rec["partial_md5"], new.parent)
        if updated:
            print(f"  📚 指纹库已更新 {updated} 条记录的目标目录")
    finally:
        db.close()


def ask_yes_no(prompt: str) -> bool:
    """在 cmd 里问 y/n；回车、EOF 或 Ctrl+C 都按「不拆分」处理。"""
    try:
        ans = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return ans in ("y", "yes")


def main():
    args = sys.argv[1:]
    dry_run = "--dry" in args
    go_mode = "--go" in args
    yes_mode = "--yes" in args
    use_db = "--no-db" not in args

    if not dry_run and not go_mode and not yes_mode:
        print(__doc__.strip())
        sys.exit(1)

    override = arg_value(args, "--dir")
    folder = Path(override) if override else TARGET_DIR
    if not folder.is_dir():
        if override:
            print(f"❌  目录不存在: {folder}")
            sys.exit(1)
        # 默认目录不存在 = 本次没有导入任何文件，属于正常情况，直接跳过。
        print(f"⏭  目录不存在，跳过: {folder}")
        sys.exit(0)

    gap_minutes = SESSION_GAP_MINUTES
    raw_gap = arg_value(args, "--gap-minutes")
    if raw_gap:
        try:
            gap_minutes = int(raw_gap)
        except ValueError:
            print(f"⚠  --gap-minutes 需要整数，已用默认值 {SESSION_GAP_MINUTES}")

    print(f"📁  {folder}")
    items, unknown = analyze(folder)
    if not items:
        print("⚠  没有找到能读出时间的照片/视频，无需拆分。")
        sys.exit(0)

    print(f"🕒  {len(items)} 个文件，时间范围 "
          f"{items[0][0].strftime('%Y-%m-%d %H:%M')} ~ "
          f"{items[-1][0].strftime('%Y-%m-%d %H:%M')}")
    if unknown:
        names = "、".join(p.name for p in unknown[:5])
        more = "…" if len(unknown) > 5 else ""
        print(f"⚠  {len(unknown)} 个文件读不出拍摄时间，保持原位：{names}{more}")

    split = best_split(items, gap_minutes, SESSION_MIN_FILES)
    if split is None:
        print(f"✓  时间轴上没有 ≥ {gap_minutes} 分钟的空档"
              f"（两场各需至少 {SESSION_MIN_FILES} 个文件），判定为同一场拍摄，不拆分。")
        sys.exit(0)

    idx, gap = split
    dirs = session_dirs(folder, items, idx)
    first, second = items[:idx], items[idx:]
    print(f"⏱  发现最大空档 {fmt_gap(gap)}："
          f"{items[idx - 1][0].strftime('%m-%d %H:%M')} → "
          f"{items[idx][0].strftime('%m-%d %H:%M')}")
    print("💡  很可能是两场摄影，可以拆成两个文件夹（至多拆两场）：")
    for d, part in zip(dirs, (first, second)):
        print(f"    {d.name}/   {len(part)} 个文件   "
              f"{part[0][0].strftime('%Y-%m-%d %H:%M')} ~ "
              f"{part[-1][0].strftime('%Y-%m-%d %H:%M')}")
    print()

    if dry_run:
        print("🔍  预览模式 — 不会修改任何文件")
        sys.exit(0)

    if not yes_mode and not ask_yes_no("是否拆分成两个文件夹？(y/n): "):
        print("已按「不拆分」处理，文件保持原样。")
        sys.exit(0)

    print()
    moves = split_batch(folder, items, idx, dirs)
    prune_empty_dirs(folder)
    if use_db:
        update_db(moves)
    print(f"\n✅  已拆分为 {dirs[0].name}/（{len(first)} 个）"
          f" 和 {dirs[1].name}/（{len(second)} 个）")
    print(f"    {folder}")


if __name__ == "__main__":
    main()

