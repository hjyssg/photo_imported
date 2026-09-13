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
"""
from pathlib import Path
import shutil
import sys
import time

from config import (
    PHOTO_SOURCE, DJI_SOURCE, CLIP_SOURCE,
    TARGET_DIR, CLIP_DIR, DJI_DIR,
)


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


def copy_photos(dry: bool = False) -> int:
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
    total = 0
    for sub in subdirs:
        jpgs = sorted(sub.glob("DSC*.JPG")) or sorted(sub.glob("DSC*.jpg"))
        if not jpgs:
            continue
        print(f"    📂 处理文件夹: {sub.name}")
        n = len(jpgs)
        t0 = time.time()
        for i, src in enumerate(jpgs, 1):
            dst = TARGET_DIR / src.name
            # 断点续传：同名且大小一致则跳过
            if not dry and dst.exists() and dst.stat().st_size == src.stat().st_size:
                continue
            if copy_one(src, dst, dry):
                total += 1
            if not dry:
                print_progress(i, n, t0)
        print()
    print(f"✅  照片：共复制 {total} 张")
    return total


def copy_dji_videos(dry: bool = False) -> int:
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
    total = 0
    for i, src in enumerate(mp4s, 1):
        dst = DJI_DIR / src.name
        if not dry and dst.exists() and dst.stat().st_size == src.stat().st_size:
            continue
        if copy_one(src, dst, dry):
            total += 1
        if not dry:
            print_progress(i, n, t0)
    print()
    print(f"✅  DJI：共复制 {total}/{n} 个 MP4 → DJI/")
    return total


def copy_clip_videos(dry: bool = False) -> int:
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
    total = 0
    for i, src in enumerate(mp4s, 1):
        dst = CLIP_DIR / src.name
        if not dry and dst.exists() and dst.stat().st_size == src.stat().st_size:
            continue
        if copy_one(src, dst, dry):
            total += 1
        if not dry:
            print_progress(i, n, t0)
    print()
    print(f"✅  CLIP：共复制 {total}/{n} 个 MP4 → CLIP/")
    return total


def main():
    dry_run = "--dry" in sys.argv
    mode = "预览模式（不实际复制）" if dry_run else "复制文件到目标目录"

    print("=" * 56)
    print(f"  Step 1 — {mode}")
    print(f"  目标: {TARGET_DIR}")
    print("=" * 56)
    print()

    copy_dji_videos(dry_run)
    print()
    copy_photos(dry_run)
    print()
    copy_clip_videos(dry_run)
    print()

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