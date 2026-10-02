#!/usr/bin/env python3
"""
分析照片焦段和光圈分布，辅助镜头选择决策（24-70mm f/2.8 vs 25-200mm f/2.8-5.6 等）。

递归扫描指定目录下所有 JPG，读取 EXIF 中的焦距、光圈、镜头型号，
输出焦段/光圈分布统计和镜头覆盖分析。

用法:
  python analyze_lens.py                              # 使用 config 默认目录
  python analyze_lens.py --dir E:/_Photo/_摄影会/2026   # 分析某个批次/目录
  python analyze_lens.py --dir .                       # 分析当前目录
  python analyze_lens.py --dir "E:\_Photo\temp"       # Win 路径也支持
"""

import os
import sys
from collections import Counter
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit("✗ 需要 Pillow: pip install Pillow")

try:
    from config import TARGET_DIR
except ImportError:
    TARGET_DIR = None

# ── EXIF 标签 ID（PIL 十进制编号） ────────────────────────
FNUMBER = 33437            # FNumber（光圈值）
FOCAL_LENGTH = 37386       # FocalLength（焦距）
MAKE = 271                 # 相机制造商
MODEL = 272                # 相机型号
LENS_MODEL = 42036         # LensModel（镜头型号）

# ── 焦段区间标签 ──────────────────────────────────────────
FL_BINS = [
    ("≤24mm",     0, 24),
    ("25-35mm",  25, 35),
    ("36-50mm",  36, 50),
    ("51-70mm",  51, 70),
    ("71-100mm", 71, 100),
    ("101-150mm", 101, 150),
    ("151-200mm", 151, 999),
]


def arg_value(args: list[str], name: str) -> str | None:
    """取 `--name value` 形式参数的值，缺值返回 None。"""
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def get_exif_rational(exif, tag_id) -> float | None:
    """读取 EXIF 的 Rational（分子/分母元组）或 int 值。"""
    val = exif.get(tag_id, None)
    if val is None:
        return None
    if isinstance(val, tuple) and len(val) == 2:
        return round(val[0] / val[1], 1) if val[1] != 0 else None
    return round(float(val), 1)


def bar(count: int, total: int, width: int = 25) -> str:
    """按比例生成进度条字符串。"""
    pct = count / total * 100 if total else 0
    filled = max(1, int(pct / 100 * width))
    return "█" * filled + "░" * (width - filled)


def analyze(directory: Path):
    """对目录下所有 JPG 做焦段/光圈分析并打印结果。"""
    jpg_files = []
    for root, _dirs, files in os.walk(directory):
        for f in sorted(files):
            if f.upper().endswith(('.JPG', '.JPEG')):
                jpg_files.append(Path(root) / f)

    if not jpg_files:
        print("⚠  该目录下没有找到 JPG 文件。")
        return

    # ── 扫描 EXIF ─────────────────────────────────────────
    cameras = Counter()
    lenses = Counter()
    focal_lengths: list[float] = []
    apertures: list[float] = []
    no_exif = 0
    errors = 0

    for path in jpg_files:
        try:
            img = Image.open(path)
            exif = img._getexif()
            if exif is None:
                no_exif += 1
                continue

            make = str(exif.get(MAKE, '')).strip()
            model = str(exif.get(MODEL, '')).strip()
            cm = f"{make} {model}".strip()
            if cm and cm != 'None' and cm != ' ':
                cameras[cm] += 1

            lens = str(exif.get(LENS_MODEL, '')).strip()
            if lens and lens != 'None' and lens != ' ':
                lenses[lens] += 1

            fl = get_exif_rational(exif, FOCAL_LENGTH)
            fn = get_exif_rational(exif, FNUMBER)
            if fl is not None:
                focal_lengths.append(fl)
            if fn is not None:
                apertures.append(fn)

        except Exception:
            errors += 1

    total = len(jpg_files)
    n = len(focal_lengths)

    # ── 输出 ───────────────────────────────────────────────
    print(f"{'='*55}")
    print(f"  📊  焦段・光圈分析")
    print(f"{'='*55}")
    print(f"  目录: {directory}")
    print(f"  JPG 总数: {total}")
    print(f"  含 EXIF:  {n}")
    if no_exif:
        print(f"  无 EXIF:  {no_exif}")
    if errors:
        print(f"  读取错误: {errors}")

    # 相机 / 镜头
    if cameras:
        print(f"\n  📷 相机型号（共 {sum(cameras.values())} 张）:")
        for cm, cnt in cameras.most_common():
            print(f"    {cm:40s} {cnt:>4} 张  ({cnt/n*100:.1f}%)")

    if lenses:
        print(f"\n  🔭 镜头:")
        for lens, cnt in lenses.most_common():
            print(f"    {lens:50s} {cnt:>4} 张  ({cnt/n*100:.1f}%)")

    # ── 主力相机单独分析 ────────────────────────────────────
    main_cam = cameras.most_common(1)[0][0] if cameras else None
    main_fl: list[float] = []
    main_ap: list[float] = []

    for path in jpg_files:
        try:
            img = Image.open(path)
            exif = img._getexif()
            if exif is None:
                continue
            cm = f"{str(exif.get(MAKE, '')).strip()} {str(exif.get(MODEL, '')).strip()}".strip()
            if cm != main_cam:
                continue
            fl = get_exif_rational(exif, FOCAL_LENGTH)
            fn = get_exif_rational(exif, FNUMBER)
            if fl is not None:
                main_fl.append(fl)
            if fn is not None:
                main_ap.append(fn)
        except Exception:
            pass

    if not main_fl:
        return

    sn = len(main_fl)
    print(f"\n{'='*55}")
    print(f"  📊  {main_cam}（主力相机，{sn} 张）")
    print(f"{'='*55}")

    # ── 焦段 ───────────────────────────────────────────────
    min_fl_val = min(main_fl)
    max_fl_val = max(main_fl)
    mean_fl = sum(main_fl) / sn

    print(f"\n  📏 焦段（mm）")
    print(f"    范围: {min_fl_val} — {max_fl_val} mm")
    print(f"    平均: {mean_fl:.1f} mm")

    # Top 10
    print(f"\n    最常用焦段（Top 10）:")
    fl_counter = Counter(main_fl)
    for fl, cnt in fl_counter.most_common(10):
        pct = cnt / sn * 100
        print(f"      {fl:>6}mm : {cnt:>4} 张 ({pct:>5.1f}%)  {bar(cnt, sn)}")

    # 区间分布
    print(f"\n    焦段分布:")
    for label, lo, hi in FL_BINS:
        cnt = sum(1 for fl in main_fl if lo <= fl <= hi)
        if cnt:
            print(f"      {label:<12}: {cnt:>4} 张 ({cnt/sn*100:>5.1f}%)  {bar(cnt, sn)}")

    # 镜头覆盖
    in_70 = sum(1 for fl in main_fl if fl <= 70)
    out_70 = sn - in_70
    print(f"\n    镜头覆盖:")
    print(f"      24-70mm 内:    {in_70:>4} 张 ({in_70/sn*100:.1f}%)")
    print(f"      超出 70mm:     {out_70:>4} 张 ({out_70/sn*100:.1f}%)")

    # ── 光圈 ───────────────────────────────────────────────
    if main_ap:
        min_ap_val = min(main_ap)
        max_ap_val = max(main_ap)
        mean_ap = sum(main_ap) / len(main_ap)

        print(f"\n  💡 光圈")
        print(f"    范围: F/{min_ap_val:.1f} — F/{max_ap_val:.1f}")
        print(f"    平均: F/{mean_ap:.1f}")

        print(f"\n    光圈分布:")
        ap_counter = Counter(main_ap)
        for ap in sorted(ap_counter):
            cnt = ap_counter[ap]
            pct = cnt / len(main_ap) * 100
            print(f"      F/{ap:<4} : {cnt:>4} 张 ({pct:>5.1f}%)  {bar(cnt, len(main_ap))}")

        # 光圈段
        f28 = sum(1 for a in main_ap if a <= 2.8)
        f4 = sum(1 for a in main_ap if 2.8 < a <= 4)
        f56 = sum(1 for a in main_ap if 4 < a <= 5.6)
        f8 = sum(1 for a in main_ap if a > 5.6)
        print(f"\n    光圈段:")
        print(f"      ≤F/2.8:       {f28:>4} 张 ({f28/len(main_ap)*100:.1f}%)")
        print(f"      F/2.8–4.0:    {f4:>4} 张 ({f4/len(main_ap)*100:.1f}%)")
        print(f"      F/4.0–5.6:    {f56:>4} 张 ({f56/len(main_ap)*100:.1f}%)")
        print(f"      >F/5.6:       {f8:>4} 张 ({f8/len(main_ap)*100:.1f}%)")

    # ── 镜头建议 ───────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  🎯  镜头建议 — 24-70 f/2.8 vs 25-200 f/2.8-5.6")
    print(f"{'='*55}")
    print(f"    24-70mm 可覆盖:   {in_70/sn*100:.1f}% 的拍摄")
    print(f"    超出 70mm:        {out_70/sn*100:.1f}% 的拍摄")
    if out_70 / sn > 0.2:
        print(f"    ✅ → 建议带 25-200mm（{out_70/sn*100:.0f}% 的照片 >70mm，2470 拍不到）")
    elif in_70 / sn > 0.85:
        print(f"    ✅ → 建议带 24-70mm f/2.8（90%+ 在 70mm 内，大光圈画质更优）")
    else:
        print(f"    → 介于之间，根据你对画质 vs 焦段覆盖的偏好选择")
    print()


def main():
    args = sys.argv[1:]
    override = arg_value(args, "--dir")
    help_flag = "--help" in args or "-h" in args

    if help_flag:
        print(__doc__)
        return

    if override:
        directory = Path(override)
    elif TARGET_DIR is not None:
        directory = TARGET_DIR.parent  # temp 根，适合临检
        print(f"ℹ  未指定 --dir，默认使用 temp 根目录: {directory}")
        print(f"   针对性分析请使用 --dir <目录路径>")
        print()
    else:
        print("用法: python analyze_lens.py --dir <目录路径>")
        print("      python analyze_lens.py --help")
        sys.exit(1)

    if not directory.exists():
        print(f"❌  目录不存在: {directory}")
        sys.exit(1)

    analyze(directory)


if __name__ == "__main__":
    main()