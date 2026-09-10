#!/usr/bin/env python3
"""
Step 3 — 连拍照片分组。

将同1秒内拍摄的多张照片（如 2026-09-10_20-15-52.jpg + _01~_05）
移入以该时间戳命名的子文件夹中，方便管理和挑选。

用法:
  python group_bursts.py            # 预览 + 执行
  python group_bursts.py --dry      # 仅预览
  python group_bursts.py --force    # 强制执行（不询问）
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from config import TARGET_DIR
except ImportError:
    TARGET_DIR = Path("E:/_Photo2/temp/0910")

# 匹配已重命名的照片文件
PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})(?:_(\d+))?\.(jpg|jpeg)$",
    re.IGNORECASE
)


def main():
    dry_run = "--dry" in sys.argv
    force = "--force" in sys.argv

    folder = TARGET_DIR
    if not folder.is_dir():
        print(f"❌  目录不存在: {folder}")
        sys.exit(1)

    # 分组
    groups = defaultdict(list)
    singles = []
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        m = PATTERN.match(f.name)
        if m:
            base = m.group(1)
            if m.group(2) is None:  # 不带 _NN 后缀
                singles.append(f)
                groups[base].append(f)  # 以不带后缀的文件作为锚点
            else:
                groups[base].append(f)
        elif f.suffix.lower() in (".jpg", ".jpeg"):
            singles.append(f)  # 未匹配到命名模式的，仍保留统计

    # 筛选连拍组（≥2 张）
    burst_groups = {k: v for k, v in groups.items() if len(v) >= 2}

    if not burst_groups:
        print("没有发现连拍照片。")
        return

    total_burst = sum(len(v) for v in burst_groups.values())
    print(f"📸  发现 {len(burst_groups)} 组连拍，共 {total_burst} 张照片")
    print()

    for base, files in sorted(burst_groups.items()):
        print(f"  📁 {base}/  ({len(files)} 张)")
        for f in files:
            print(f"       {f.name}")

    print()
    print(f"  根目录将保留 {len(singles) - len(burst_groups)} 张单张照片")
    print(f"  将创建 {len(burst_groups)} 个连拍子文件夹")

    if dry_run:
        print("\n🔍  预览模式 — 未做任何修改")
        return

    if not force:
        try:
            ans = input(f"\n确定移动这 {total_burst} 张照片？(Y/n): ")
            if ans and ans.lower() != "y":
                print("已取消。")
                return
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            return

    # 执行移动
    moved = 0
    for base, files in sorted(burst_groups.items()):
        subdir = folder / base
        subdir.mkdir(exist_ok=True)
        for f in files:
            dst = subdir / f.name
            if dst.exists():
                continue  # 已在子文件夹中
            f.rename(dst)
            moved += 1

    print(f"\n✅  已移动 {moved} 张连拍照片 → {len(burst_groups)} 个子文件夹")


if __name__ == "__main__":
    main()