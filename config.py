"""
配置文件 — 修改这里的路径即可适配不同批次
"""
from pathlib import Path
from datetime import datetime

# ── 源路径（相机/SD卡） ──────────────────────────────────
# DJI 无人机/运动相机视频（通常自带时间戳文件名）
DJI_SOURCE = Path("H:/DCIM/DJI_001")

# 索尼相机照片文件夹（会扫描此目录下所有子文件夹中的 DSC*.JPG）
PHOTO_SOURCE = Path("G:/DCIM")

# DJI Pocket / Action 的 CLIP 视频
CLIP_SOURCE = Path("G:/PRIVATE/M4ROOT/CLIP")

# ── 目标路径 ──────────────────────────────────────────────
# 照片和 DJI 视频放进 TEMP_ROOT，CLIP 视频放进 TEMP_ROOT/CLIP/
# 子文件夹名自动使用当天日期 mmdd
TEMP_ROOT = Path("E:/_Photo2/temp")

# ── 派生路径（自动计算） ───────────────────────────────────
TODAY_MMDD = datetime.now().strftime("%m%d")
TARGET_DIR = TEMP_ROOT / TODAY_MMDD
CLIP_DIR = TARGET_DIR / "CLIP"