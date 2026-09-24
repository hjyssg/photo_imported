#!/usr/bin/env python3
"""
Step 1 — 从 SD 卡/相机复制文件到目标文件夹。--dry 预览，不实际复制。

来源（按文件夹自动定位，只检查 G/H 两盘第一层，找不到则跳过）：
  - 照片     ：DCIM 下第一层子目录中的 DSC*.JPG（索尼）
  - DJI 无人机 ：DCIM/DJI_xxxx 下的 MP4
  - CLIP     ：PRIVATE/M4ROOT/CLIP 下的 MP4（DJI CLIP；配套 XML 不再复制）

目标：
  E:/_Photo2/temp/<mmdd>/
  ├── CLIP/        ← CLIP 视频
  └── DJI/         ← DJI 无人机视频（独立文件夹）

去重（import_db.py）：
  复制前计算源文件的部分 MD5（大小 + 头尾各 1MB），命中 SQLite 里已导入记录
  就跳过，避免换卡/改名后同一内容被重复导入；复制成功后再登记指纹。
  参数：--no-db 关闭去重；--allow-dup 只登记不跳过；--db-stats 查看库状态。
"""
from pathlib import Path
import shutil
import sys
import time

from config import (
    PHOTO_SOURCE, DJI_SOURCE, CLIP_SOURCE,
    TARGET_DIR, CLIP_DIR, DJI_DIR,
    IMPORT_DB_PATH, SKIP_DUPLICATE_IMPORT,
)
from import_db import ImportDB, partial_md5, fmt_size



def fmt_dur(seconds: float) -> str:
    seconds = int(seconds)
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def progress_str(done: int, total: int, t0: float) -> str:
    elapsed = time.time() - t0
    pct = (done / total * 100) if total else 100.0
    eta = (elapsed / done * (total - done)) if done else 0.0
    return (f"{done}/{total} ({pct:3.0f}%)  ·  已用 {fmt_dur(elapsed)}"
            f"  ·  预计剩余 {fmt_dur(eta)}")


def print_progress(done: int, total: int, t0: float, indent: str = "    "):
    print(f"\r{indent}{progress_str(done, total, t0)}", end="", flush=True)


def _remove_quiet(p: Path):
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def copy_one(src: Path, dst: Path, dry: bool) -> bool:
    """复制 src -> dst 并校验大小；dry 时只预览。失败时清理不完整的目标文件。"""
    if dry:
        print(f"    → [预览] {src.name}  →  {dst.parent.name}/{dst.name}")
        return True
    if dst.exists():
        dst.unlink()  # 先清理旧目标，避免新旧混杂（仅影响目标，不影响源）
    try:
        shutil.copy2(src, dst)
    except Exception as e:
        print(f"    ✗ 复制失败 {src.name}: {e}")
        _remove_quiet(dst)
        return False
    try:
        same_size = dst.stat().st_size == src.stat().st_size
    except Exception as e:
        print(f"    ✗ 大小校验失败 {src.name}: {e}")
        _remove_quiet(dst)
        return False
    if not same_size:
        print(f"    ✗ 大小不一致 {src.name}，已移除不完整副本")
        _remove_quiet(dst)
        return False
    return True


def import_file(src: Path, dst: Path, dry: bool, db: ImportDB | None,
                allow_dup: bool = False) -> str:
    """导入单个文件并登记部分 MD5。

    返回 'copied'（已复制）| 'resumed'（同名同大小已存在，跳过复制）
        | 'dup'（内容已导入过，跳过）| 'failed'（复制失败）。
    """
    fp = partial_md5(src) if db is not None else None

    # 断点续传：目标已存在同名同大小文件 → 不再复制，但要补登记指纹
    if not dry and dst.exists() and dst.stat().st_size == src.stat().st_size:
        _remember(db, fp, src, dst, dry)
        return "resumed"

    # 内容去重：同一份内容之前已导入过（可能换了卡/改了名）→ 跳过
    if fp is not None and not allow_dup:
        rec = db.find(fp)
        if rec is not None:
            print(f"    ⏭  跳过重复 {src.name}（已导入于 {rec['imported_at']}，"
                  f"原文件 {rec['name']} → {rec['dst_dir']}）")
            return "dup"

    if not copy_one(src, dst, dry):
        return "failed"
    _remember(db, fp, src, dst, dry)
    return "copied"


def _remember(db: ImportDB | None, fp: str | None, src: Path, dst: Path, dry: bool):
    """把成功的导入登记进指纹库（dry 模式只预览不落库）。"""
    if db is None or fp is None:
        return
    if dry:
        return
    try:
        size = src.stat().st_size
    except OSError:
        return
    db.add(fp, size, src.name, src, dst.parent)


def summarize(kind: str, copied: int, dup: int, failed: int, resumed: int, total: int):
    parts = [f"复制 {copied}"]
    if resumed:
        parts.append(f"续传跳过 {resumed}")
    if dup:
        parts.append(f"重复跳过 {dup}")
    if failed:
        parts.append(f"失败 {failed}")
    print(f"✅  {kind}：共 {total} 个文件 — " + "，".join(parts))


def copy_photos(dry: bool = False, db: ImportDB | None = None,
                allow_dup: bool = False) -> int:
    """扫描照片源下所有第一层子目录，复制 DSC*.JPG"""
    if PHOTO_SOURCE is None or not PHOTO_SOURCE.is_dir():
        print(f"⚠  照片源未找到/不存在: {PHOTO_SOURCE}")
        return 0

    print(f"📷  照片源: {PHOTO_SOURCE}")
    subdirs = sorted(d for d in PHOTO_SOURCE.iterdir() if d.is_dir())
    if not subdirs:
        print(f"⚠  {PHOTO_SOURCE} 下没有子目录")
        return 0

    if not dry:
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
    stats = {"copied": 0, "dup": 0, "failed": 0, "resumed": 0}
    total_files = 0
    for sub in subdirs:
        jpgs = sorted(sub.glob("DSC*.JPG")) or sorted(sub.glob("DSC*.jpg"))
        if not jpgs:
            continue
        print(f"    📂 处理文件夹: {sub.name}")
        n = len(jpgs)
        total_files += n
        t0 = time.time()
        for i, src in enumerate(jpgs, 1):
            dst = TARGET_DIR / src.name
            r = import_file(src, dst, dry, db, allow_dup)
            stats[r] += 1
            if not dry:
                print_progress(i, n, t0)
        print()
    summarize("照片", stats["copied"], stats["dup"], stats["failed"],
              stats["resumed"], total_files)
    return stats["copied"]


def copy_dji_videos(dry: bool = False, db: ImportDB | None = None,
                    allow_dup: bool = False) -> int:
    """复制 DJI 无人机视频到独立文件夹 DJI_DIR"""
    if DJI_SOURCE is None or not DJI_SOURCE.is_dir():
        print(f"⚠  DJI 源未找到/不存在: {DJI_SOURCE}")
        return 0

    print(f"🎬  DJI 源: {DJI_SOURCE}  →  {DJI_DIR.name}/")
    if not dry:
        DJI_DIR.mkdir(parents=True, exist_ok=True)
    mp4s = sorted(DJI_SOURCE.glob("*.MP4"))
    if not mp4s:
        print("⚠  DJI 目录中无 MP4")
        return 0

    n = len(mp4s)
    t0 = time.time()
    stats = {"copied": 0, "dup": 0, "failed": 0, "resumed": 0}
    for i, src in enumerate(mp4s, 1):
        dst = DJI_DIR / src.name
        r = import_file(src, dst, dry, db, allow_dup)
        stats[r] += 1
        if not dry:
            print_progress(i, n, t0)
    print()
    summarize(f"DJI（→ {DJI_DIR.name}/）", stats["copied"], stats["dup"],
              stats["failed"], stats["resumed"], n)
    return stats["copied"]


def copy_clip_videos(dry: bool = False, db: ImportDB | None = None,
                     allow_dup: bool = False) -> int:
    """复制 CLIP 目录下的 MP4（XML 不再复制）"""
    if CLIP_SOURCE is None or not CLIP_SOURCE.is_dir():
        print(f"⚠  CLIP 源未找到/不存在: {CLIP_SOURCE}")
        return 0

    mp4s = sorted(CLIP_SOURCE.glob("*.MP4"))
    if not mp4s:
        print(f"⚠  CLIP 目录 {CLIP_SOURCE} 中无 MP4")
        return 0

    print(f"🎬  CLIP 源: {CLIP_SOURCE}  →  {CLIP_DIR.name}/")
    if not dry:
        CLIP_DIR.mkdir(parents=True, exist_ok=True)
    n = len(mp4s)
    t0 = time.time()
    stats = {"copied": 0, "dup": 0, "failed": 0, "resumed": 0}
    for i, src in enumerate(mp4s, 1):
        dst = CLIP_DIR / src.name
        r = import_file(src, dst, dry, db, allow_dup)
        stats[r] += 1
        if not dry:
            print_progress(i, n, t0)
    print()
    summarize(f"CLIP（→ {CLIP_DIR.name}/）", stats["copied"], stats["dup"],
              stats["failed"], stats["resumed"], n)
    return stats["copied"]


def main():
    args = sys.argv[1:]
    dry_run = "--dry" in args
    allow_dup = ("--allow-dup" in args) or (not SKIP_DUPLICATE_IMPORT)
    use_db = "--no-db" not in args

    if "--db-stats" in args:                      # 只看指纹库，不复制
        with ImportDB(IMPORT_DB_PATH) as _db:
            s = _db.stats()
        print(f"📚  指纹库: {IMPORT_DB_PATH}")
        print(f"    已登记 {s['count']} 个文件，合计 {fmt_size(s['bytes'])}")
        return

    mode = "预览模式（不实际复制）" if dry_run else "复制文件到目标目录"

    print("=" * 56)
    print(f"  Step 1 — {mode}")
    print(f"  目标: {TARGET_DIR}")
    if use_db:
        print(f"  去重: 部分 MD5 指纹库 {IMPORT_DB_PATH}"
              + ("（仅登记不跳过）" if allow_dup else ""))
    else:
        print("  去重: 已关闭（--no-db）")
    print("=" * 56)
    print()

    db = ImportDB(IMPORT_DB_PATH) if use_db else None
    try:
        if db is not None:
            s = db.stats()
            print(f"📚  指纹库已有 {s['count']} 条记录（{fmt_size(s['bytes'])}）")
            print()
        copy_dji_videos(dry_run, db, allow_dup)
        print()
        copy_photos(dry_run, db, allow_dup)
        print()
        copy_clip_videos(dry_run, db, allow_dup)
        print()
    finally:
        if db is not None:
            db.close()

    if TARGET_DIR.exists():
        print(f"📁  目标目录结构:")
        print(f"    {TARGET_DIR}/")
        for p in sorted(TARGET_DIR.iterdir()):
            if p.is_dir():
                children = list(p.iterdir())
                print(f"    ├── {p.name}/")
                for f in children[:5]:
                    print(f"    │   ├── {f.name}")
                if len(children) > 5:
                    print(f"    │   └── ... 共 {len(children)} 个文件")
            else:
                print(f"    ├── {p.name}")
    print()


if __name__ == "__main__":
    main()