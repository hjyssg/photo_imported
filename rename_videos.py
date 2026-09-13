#!/usr/bin/env python3
"""
Step 2b — 按 creation_time 重命名 CLIP 视频。

扫描 TARGET_DIR/CLIP/ 下的 Cxxxx.MP4，读取 MP4 元数据中的
creation_time（UTC），转换为北京时间后重命名。
配套的 CxxxxM01.XML 文件同步改名（复制阶段已不再复制 XML，
此分支仅兼容历史残留的 XML）。

用法:
  python rename_videos.py --dry     # 预览
  python rename_videos.py --go      # 执行
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from config import CLIP_DIR
except ImportError:
    CLIP_DIR = Path("E:/_Photo2/temp/0910/CLIP")

PATTERN_MP4 = re.compile(r"^C(\d+)\.MP4$", re.IGNORECASE)
DATE_FORMAT = "%Y-%m-%d_%H-%M-%S"
UTC8 = timezone(timedelta(hours=8))


def get_creation_time_utc(filepath: Path) -> datetime | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(filepath)],
            capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        ct = data.get("format", {}).get("tags", {}).get("creation_time")
        if ct:
            dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc)
    except Exception:
        return None
    return None


def rename_file(src: Path, dry: bool) -> str | None:
    if src.suffix.upper() == ".XML":
        return None  # XML 跟随同名的 MP4

    dt_utc = get_creation_time_utc(src)
    if dt_utc is None:
        return f"⚠  {src.name}  →  无 creation_time，跳过"

    dt_local = dt_utc.astimezone(UTC8)
    base_name = dt_local.strftime(DATE_FORMAT)
    ext = src.suffix.lower()
    dst_name = base_name + ext
    dst = src.with_name(dst_name)

    counter = 1
    while dst.exists() and dst.name != src.name:
        stem = f"{base_name}_{counter:02d}"
        dst_name = stem + ext
        dst = src.with_name(dst_name)
        counter += 1

    results = []
    if dst.name == src.name:
        results.append(f"✓  {src.name}  →  已是正确命名")
    else:
        if not dry:
            src.rename(dst)
        results.append(f"→  {src.name}  →  {dst_name}")

    # 处理配套的 XML 文件
    companion = src.with_name(src.stem + "M01.XML")
    if companion.exists():
        xml_stem = dst.stem
        xml_dst = dst.with_name(xml_stem + ".XML")
        xml_counter = 1
        while xml_dst.exists() and xml_dst.name != companion.name:
            xml_stem = f"{dst.stem}_{xml_counter:02d}"
            xml_dst = dst.with_name(xml_stem + ".XML")
            xml_counter += 1
        if xml_dst.name == companion.name:
            results.append(f"✓  {companion.name}  →  已是正确命名")
        else:
            if not dry:
                companion.rename(xml_dst)
            results.append(f"→  {companion.name}  →  {xml_dst.name}")

    return "\n".join(results)


def main():
    dry_run = "--dry" in sys.argv
    go_mode = "--go" in sys.argv or "--yes" in sys.argv

    if not dry_run and not go_mode:
        print("用法:")
        print("  python rename_videos.py --dry      # 预览")
        print("  python rename_videos.py --go       # 执行")
        sys.exit(1)

    folder = CLIP_DIR
    if not folder.is_dir():
        print(f"❌  目录不存在: {folder}")
        sys.exit(1)

    mp4_files = sorted(f for f in folder.iterdir() if PATTERN_MP4.match(f.name))
    if not mp4_files:
        print(f"📁  {folder}")
        print("未找到 Cxxxx.MP4 文件。")
        sys.exit(0)

    print(f"📁  {folder}")
    print(f"🎬  找到 {len(mp4_files)} 个 MP4 文件")
    print("🔍  预览模式 — 不会实际修改" if dry_run else "⚡  执行重命名 — 不可撤销！")
    print()

    all_results = []
    for f in mp4_files:
        r = rename_file(f, dry=dry_run)
        if r:
            print(f"  {r}")
            all_results.append(r)

    rename_count = sum(1 for r in all_results
                       for line in r.split("\n") if line.startswith("→"))
    skip_count = sum(1 for r in all_results
                     for line in r.split("\n") if line.startswith("✓"))
    print(f"\n✅  重命名 {rename_count} 个，{skip_count} 个已正确")


if __name__ == "__main__":
    main()