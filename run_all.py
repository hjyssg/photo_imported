#!/usr/bin/env python3
"""
一键运行：复制 → 重命名 → 连拍分组

用法:
  python run_all.py                  # 完整流程（每步询问确认）
  python run_all.py --yes            # 完整流程（全部自动确认）
  python run_all.py --dry            # 预览模式（不修改任何文件）
  python run_all.py --skip-copy      # 跳过复制步骤
  python run_all.py --skip-rename    # 跳过重命名步骤
  python run_all.py --skip-group     # 跳过连拍分组
"""

import sys
import subprocess

SCRIPTS_DIR = Path(__file__).parent

def run_step(script_name: str, label: str, extra_args: list = None) -> int:
    """Run a step script, return its exit code."""
    script = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script)] + (extra_args or [])
    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"⚠  {label} 执行失败（exit code={result.returncode}）")
    return result.returncode


def main():
    args = sys.argv[1:]
    yes_mode = "--yes" in args
    dry_run = "--dry" in args
    skip_copy = "--skip-copy" in args
    skip_rename = "--skip-rename" in args
    skip_group = "--skip-group" in args

    extra = ["--dry"] if dry_run else []
    if yes_mode and not dry_run:
        extra = ["--yes"]  # 传给 group_bursts.py

    print(f"📅  日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"📁  目标: {TARGET_DIR}")
    if dry_run:
        print("🔍  预览模式 — 不会修改任何文件")
    print()

    # Step 1 — 复制
    if not skip_copy:
        rc = run_step("copy_files.py", "Step 1 — 复制文件", extra)
        if rc != 0 and not yes_mode:
            ans = input("\n复制步骤有错误，继续下一步？(Y/n): ")
            if ans and ans.lower() != "y":
                print("已中止。")
                sys.exit(1)
    else:
        print("⏩  跳过复制步骤")

    # Step 2a — 照片重命名
    if not skip_rename:
        run_step("rename_photos.py", "Step 2a — 照片重命名", extra)
    else:
        print("⏩  跳过照片重命名")

    # Step 2b — 视频重命名
    if not skip_rename:
        run_step("rename_videos.py", "Step 2b — CLIP 视频重命名", extra)
    else:
        print("⏩  跳过视频重命名")

    # Step 3 — 连拍分组
    if not skip_group:
        run_step("group_bursts.py", "Step 3 — 连拍照片分组", extra)
    else:
        print("⏩  跳过连拍分组")

    print(f"\n{'='*50}")
    print(f"  🎉  全部完成！")
    print(f"  文件位置: {TARGET_DIR}")
    print(f"  CLIP 视频: {CLIP_DIR}")
    print(f"{'='*50}")


if __name__ == "__main__":
    from pathlib import Path
    from datetime import datetime

    # 临时导入配置
    sys.path.insert(0, str(Path(__file__).parent))
    from config import TARGET_DIR, CLIP_DIR

    main()