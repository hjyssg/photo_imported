#!/usr/bin/env python3
"""
Step 1 — 从 SD 卡/相机复制文件到目标文件夹。

来源：
  - G:/DCIM/ 下所有子目录中的 DSC*.JPG 照片
  - G:/PRIVATE/M4ROOT/CLIP/ 下的 MP4+XML（DJI CLIP 视频）
  - H:/DCIM/DJI_001/ 下的 MP4（DJI 无人机视频）

目标：
  E:/_Photo2/temp/<mmdd>/
  └── CLIP/
"""

import shutil
import sys
from pathlib import Path

# 导入配置
try:
    from config import (
        PHOTO_SOURCE, CLIP_SOURCE, DJI_SOURCE,
        TARGET_DIR, CLIP_DIR,
    )
except ImportError:
    # 直接运行本文件时使用默认路径
    from config_defaults import *


def copy_photos():
    """扫描 PHOTO_SOURCE 下所有子目录，复制 DSC*.JPG"""
    if not PHOTO_SOURCE.is_dir():
        print(f"⚠  照片源目录不存在: {PHOTO_SOURCE}")
        return 0

    subdirs = sorted([d for d in PHOTO_SOURCE.iterdir() if d.is_dir()])
    if not subdirs:
        print(f"⚠  照片源目录下没有子目录: {PHOTO_SOURCE}")
        return 0

    total = 0
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for sub in subdirs:
        jpgs = sorted(sub.glob("DSC*.JPG"))
        if not jpgs:
            jpgs = sorted(sub.glob("DSC*.jpg"))
        if not jpgs:
            continue
        print(f"📷  {sub.name}  →  {len(jpgs)} 张照片")
        for src in jpgs:
            dst = TARGET_DIR / src.name
            shutil.copy2(src, dst)
            total += 1

    print(f"✅  共复制 {total} 张照片")
    return total


def copy_clip_videos():
    """复制 CLIP 目录下的 MP4 + XML"""
    if not CLIP_SOURCE.is_dir():
        print(f"⚠  CLIP 源目录不存在: {CLIP_SOURCE}")
        return 0

    CLIP_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(CLIP_SOURCE.glob("*.MP4")) + sorted(CLIP_SOURCE.glob("*.XML"))
    if not files:
        print("⚠  CLIP 目录中无文件")
        return 0

    for src in files:
        dst = CLIP_DIR / src.name
        shutil.copy2(src, dst)

    mp4_count = len(list(CLIP_SOURCE.glob("*.MP4")))
    xml_count = len(list(CLIP_SOURCE.glob("*.XML")))
    print(f"✅  共复制 {mp4_count} 个 MP4 + {xml_count} 个 XML → CLIP/")
    return len(files)


def copy_dji_videos():
    """复制 DJI 无人机视频到目标根目录"""
    if not DJI_SOURCE.is_dir():
        print(f"⚠  DJI 源目录不存在: {DJI_SOURCE}")
        return 0

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    mp4s = sorted(DJI_SOURCE.glob("*.MP4"))
    if not mp4s:
        print("⚠  DJI 目录中无 MP4")
        return 0

    for src in mp4s:
        dst = TARGET_DIR / src.name
        shutil.copy2(src, dst)

    print(f"✅  共复制 {len(mp4s)} 个 DJI 视频")
    return len(mp4s)


def main():
    print("=" * 50)
    print("  Step 1 — 复制文件到目标目录")
    print(f"  目标: {TARGET_DIR}")
    print("=" * 50)
    print()

    copy_dji_videos()
    print()
    copy_photos()
    print()
    copy_clip_videos()

    print()
    print(f"📁  目标目录结构:")
    print(f"    {TARGET_DIR}/")
    for p in sorted(TARGET_DIR.iterdir()):
        if p.is_dir():
            print(f"    ├── {p.name}/")
            files = list(p.iterdir())[:5]
            for f in files:
                print(f"    │   ├── {f.name}")
            if len(list(p.iterdir())) > 5:
                print(f"    │   └── ... 共 {len(list(p.iterdir()))} 个文件")
        else:
            print(f"    ├── {p.name}")
    print()


if __name__ == "__main__":
    main()