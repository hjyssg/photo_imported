#!/usr/bin/env python3
"""
Step 2a — 按 EXIF 拍摄时间重命名照片。

扫描目标目录下的 DSC*.JPG，读取 EXIF DateTime 字段，
重命名为 YYYY-MM-DD_HH-MM-SS[_NN].jpg 格式。

用法:
  python rename_photos.py --dry     # 预览
  python rename_photos.py --go      # 执行
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS

try:
    from config import TARGET_DIR
except ImportError as e:
    raise SystemExit("✗ 找不到 config.py，请在项目根目录下运行本脚本。") from e

PATTERN = re.compile(r"^DSC\d+\.(JPG|jpg|jpeg)$", re.IGNORECASE)
DATE_FORMAT = "%Y-%m-%d_%H-%M-%S"


def get_exif_datetime(filepath: Path) -> str | None:
    """读取 EXIF DateTime 字段"""
    try:
        img = Image.open(filepath)
        exif_data = img.getexif()
        if exif_data is None:
            return None
        tag_map = {TAGS.get(tag_id, tag_id): str(value)
                   for tag_id, value in exif_data.items()}
        for tag in ("DateTimeOriginal", "DateTime"):
            if tag in tag_map:
                return tag_map[tag]
    except Exception:
        return None
    return None


def parse_exif_date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s.strip(), "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def rename_file(src: Path, dry: bool) -> str:
    exif_str = get_exif_datetime(src)
    if exif_str is None:
        return f"⚠  {src.name}  →  无 EXIF，跳过"

    dt = parse_exif_date(exif_str)
    if dt is None:
        return f"⚠  {src.name}  →  EXIF 日期格式异常 '{exif_str}'，跳过"

    base_name = dt.strftime(DATE_FORMAT)
    ext = src.suffix.lower()
    dst_name = base_name + ext
    dst = src.with_name(dst_name)

    counter = 1
    while dst.exists() and dst.name != src.name:
        stem = f"{base_name}_{counter:02d}"
        dst_name = stem + ext
        dst = src.with_name(dst_name)
        counter += 1

    if dst.name == src.name:
        return f"✓  {src.name}  →  已是正确命名"

    if not dry:
        src.rename(dst)

    return f"→  {src.name}  →  {dst_name}"


def main():
    dry_run = "--dry" in sys.argv
    go_mode = "--go" in sys.argv or "--yes" in sys.argv

    if not dry_run and not go_mode:
        print("用法:")
        print("  python rename_photos.py --dry      # 预览")
        print("  python rename_photos.py --go       # 执行")
        sys.exit(1)

    folder = TARGET_DIR
    if not folder.is_dir():
        print(f"❌  目录不存在: {folder}")
        sys.exit(1)

    files = sorted(f for f in folder.iterdir() if PATTERN.match(f.name))
    if not files:
        print(f"📁  {folder}")
        print("未找到 DSC*.JPG 文件。")
        sys.exit(0)

    print(f"📁  {folder}")
    print(f"📸  找到 {len(files)} 个文件")
    print("🔍  预览模式 — 不会实际修改" if dry_run else "⚡  执行重命名 — 不可撤销！")
    print()

    results = [rename_file(f, dry=dry_run) for f in files]

    renamed = sum(1 for r in results if r.startswith("→"))
    skipped = sum(1 for r in results if r.startswith("✓"))
    failed = sum(1 for r in results if r.startswith("⚠"))

    for r in results:
        print(f"  {r}")

    print(f"\n✅  重命名 {renamed} 个，{skipped} 个已正确，{failed} 个跳过")


if __name__ == "__main__":
    main()