"""
配置文件 — 修改这里的路径即可适配不同批次

源路径改为「按文件夹自动定位」：
  - 只扫描 LOOKUP_DRIVES 中的盘（盘符不固定，改在此处维护）；
  - 按各源的特征目录判断，且只判断第一层，不做深层扫描；
  - 某源在盘里找不到就跳过，不影响其他源。
"""
from pathlib import Path
from datetime import datetime
import re


# ── 源查找配置 ─────────────────────────────────────────────
# 只在这几个盘中按文件夹特征定位（U盘盘符不固定，就靠文件夹找）
LOOKUP_DRIVES = ["G", "H"]

# 各源的特征目录（仅检查第一层，绝不深扫）：
PHOTO_LOOKUP = "DCIM"                           # 照片：DCIM 下第一层子目录含 DSC*.JPG（索尼）
DJI_LOOKUP = "DJI"                              # DJI 无人机：DCIM/DJI_xxxx
CLIP_LOOKUP = ("PRIVATE", "M4ROOT", "CLIP")     # CLIP：PRIVATE/M4ROOT/CLIP

# DJI 无人机目录名，如 DJI_001
_DJI_DIR_RE = re.compile(r"^DJI_\d+$", re.IGNORECASE)


def _drive_root(letter: str) -> Path:
    return Path(f"{letter}:/")


def _is_photo_drive(letter: str) -> bool:
    """该盘 DCIM 的第一层子目录里是否存在 DSC*.JPG（不做深层扫描）"""
    dcim = _drive_root(letter) / "DCIM"
    if not dcim.is_dir():
        return False
    for entry in dcim.iterdir():
        if entry.is_dir():
            if list(entry.glob("DSC*.JPG")) or list(entry.glob("DSC*.jpg")):
                return True
    return False


def _resolve_fixed(letter: str, parts) -> Path | None:
    """从盘根逐级拼出 parts 组成的目录，任一环不存在则返回 None"""
    cur = _drive_root(letter)
    for p in parts:
        cur = cur / p
        if not cur.is_dir():
            return None
    return cur


def find_source(kind: str) -> Path | None:
    """在 LOOKUP_DRIVES 中按特征定位源目录；找不到返回 None。kind: photo|dji|clip"""
    for letter in LOOKUP_DRIVES:
        root = _drive_root(letter)
        if not root.exists():
            continue  # 该盘未插入
        if kind == "photo":
            if _is_photo_drive(letter):
                return root / "DCIM"
        elif kind == "dji":
            dcim = root / "DCIM"
            if dcim.is_dir():
                for entry in dcim.iterdir():
                    if entry.is_dir() and _DJI_DIR_RE.match(entry.name):
                        return entry
        elif kind == "clip":
            p = _resolve_fixed(letter, CLIP_LOOKUP)
            if p is not None:
                return p
    return None


# ── 源路径（自动解析，找不到为 None，调用方会跳过） ───────────
PHOTO_SOURCE = find_source("photo")   # 索尼照片（含 DSC*.JPG 的 DCIM）
DJI_SOURCE = find_source("dji")       # DJI 无人机视频（DCIM/DJI_xxxx）
CLIP_SOURCE = find_source("clip")     # DJI CLIP 视频（PRIVATE/M4ROOT/CLIP）

# ── 目标路径 ──────────────────────────────────────────────
# 照片 → TARGET_DIR；CLIP 视频 → CLIP_DIR；DJI 单独 → DJI_DIR
# 子文件夹名自动使用当天日期 mmdd
TEMP_ROOT = Path("E:/_Photo/temp")

# ── 派生路径（自动计算） ───────────────────────────────────
TODAY_MMDD = datetime.now().strftime("%m%d")
TARGET_DIR = TEMP_ROOT / TODAY_MMDD
CLIP_DIR = TARGET_DIR / "CLIP"
DJI_DIR = TARGET_DIR / "DJI"