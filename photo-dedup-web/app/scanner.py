"""scanner.py — 扫描 + 图片内容指纹 + MD5 字节分组 + 推荐保留。

重复判定分两类：
  A. 图片内容重复（同目录内、像素一致）：懒加载缩略图指纹 (folder, h128) 粗分组
     → (h64, w, h) 精分组，精组 ≥2 即为像素重复候选。
  B. 字节级相同（跨目录 + 视频）：按 size 分桶，同 size ≥2 的桶算 MD5，相同即成组。

单张指纹失败（损坏/非解码）→ 记为不可用、跳过，不影响整体。
"""
import hashlib
import re
from pathlib import Path

from .cache import Cache

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
VIDEO_EXTS = {".mov", ".mp4", ".avi", ".mkv", ".m4v"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}

_DATE_RE = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}")
_TIME_RE = re.compile(r"\d{1,2}:\d{1,2}(?::\d{1,2})?")


class ScanCancelled(Exception):
    """扫描被用户取消。"""


def _is_skipped(name):
    if name in SKIP_NAMES:
        return True
    if name.startswith("._"):
        return True
    return False


# ---------- 推荐保留启发式（对应旧 dup_common.name_score / pick_keep） ----------

def _name_score(name):
    s = 0
    if _DATE_RE.search(name):
        s += 100
    m = _TIME_RE.search(name)
    if m:
        s += 200
        if m.group(0).count(":") >= 2:  # 含秒
            s += 50
    return s


# ---------- 指纹 ----------

def _file_md5(path):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _md5_cached(path, rel, size, cache):
    if cache.has(rel, size, "md5"):
        return cache.get(rel, size, "md5")
    m = _file_md5(path)
    if m is not None:
        cache.set(rel, size, "md5", m)
    return m


def _img_fingerprint(path, rel, size, cache):
    """返回 (data, from_cache)；解码失败返回 (None, False)。"""
    if cache.has(rel, size, "img"):
        return cache.get(rel, size, "img"), True
    try:
        from PIL import Image, ImageFile

        Image.MAX_IMAGE_PIXELS = 10 ** 9
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        with Image.open(str(path)) as img:
            w, h = img.size
            exif_len = 0
            try:
                exif = img.getexif()
                if exif is not None:
                    exif_len = len(exif.tobytes())
            except Exception:
                exif_len = 0
            g = img.convert("L")
            g.thumbnail((128, 128))
            h128 = hashlib.md5(g.tobytes()).hexdigest()
            g.thumbnail((64, 64))
            h64 = hashlib.md5(g.tobytes()).hexdigest()
        data = {"w": w, "h": h, "exif_len": exif_len, "h128": h128, "h64": h64}
        cache.set(rel, size, "img", data)
        return data, False
    except Exception:
        return None, False


# ---------- 枚举与过滤 ----------

def _enumerate(root, progress):
    items = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part == ".photo_dup_removed" for part in p.parts):
            continue
        if _is_skipped(p.name):
            continue
        ext = p.suffix.lower()
        if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
            continue
        rel = p.relative_to(root)
        folder = rel.parent.as_posix() if str(rel.parent) != "." else ""
        kind = "img" if ext in IMAGE_EXTS else "vid"
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        items.append({
            "abs": str(p.resolve()),
            "rel": rel.as_posix(),
            "size": size,
            "exif_len": 0,
            "kind": kind,
            "folder": folder,
        })
        if progress and len(items) % 200 == 0:
            if progress({"phase": "counting", "scanned": len(items), "total": None}):
                raise ScanCancelled()
    if progress:
        progress({"phase": "counting", "scanned": len(items), "total": len(items)})
    return items


# ---------- 分组与汇总 ----------

def _dedupe(root, items, cache, progress):
    images = [it for it in items if it["kind"] == "img"]

    # A. 图片内容重复（同目录像素一致）
    img_groups = []
    coarse = {}
    for i, it in enumerate(images):
        if progress:
            if progress({"phase": "图片指纹", "scanned": i + 1, "total": len(images)}):
                raise ScanCancelled()
        data, _from_cache = _img_fingerprint(root / it["rel"], it["rel"], it["size"], cache)
        if data is None:
            continue
        it.update(data)
        coarse.setdefault((it["folder"], data["h128"]), []).append(it)

    for members in coarse.values():
        fine = {}
        for it in members:
            fine.setdefault((it["h64"], it["w"], it["h"]), []).append(it)
        for group in fine.values():
            if len(group) >= 2:
                img_groups.append(group)

    # 已被像素组消耗的文件不再参与 MD5，保证文件集合互不重叠。
    consumed = set()
    for g in img_groups:
        for it in g:
            consumed.add(it["abs"])

    # B. 字节级相同（跨目录 + 视频）
    buckets = {}
    for it in items:
        if it["abs"] in consumed:
            continue
        buckets.setdefault(it["size"], []).append(it)

    md5_groups = []
    big_buckets = [m for m in buckets.values() if len(m) >= 2]
    for bi, members in enumerate(big_buckets):
        if progress:
            if progress({"phase": "MD5", "scanned": bi + 1, "total": len(big_buckets)}):
                raise ScanCancelled()
        by_md5 = {}
        for it in members:
            m = _md5_cached(root / it["rel"], it["rel"], it["size"], cache)
            if m is None:
                continue
            by_md5.setdefault(m, []).append(it)
        for group in by_md5.values():
            if len(group) >= 2:
                md5_groups.append(group)

    # 汇总
    groups = []
    gid = 1
    for group in img_groups:
        groups.append(_build_group(gid, group, "内容重复(像素一致)"))
        gid += 1
    for group in md5_groups:
        groups.append(_build_group(gid, group, "字节级相同(MD5)"))
        gid += 1

    # 按 folder 升序、组总大小降序排序（仅影响展示顺序）
    groups.sort(key=lambda g: (g["folder"], -g["total_size"]))

    stats = {"groups": 0, "files": 0, "to_move": 0, "freed_bytes": 0}
    for g in groups:
        stats["groups"] += 1
        stats["files"] += len(g["items"])
        stats["to_move"] += len(g["items"]) - 1
        stats["freed_bytes"] += g["total_size"] - g["items"][0]["size"]

    return {"groups": groups, "stats": stats}


def _build_group(gid, members, mode):
    members = sorted(
        members,
        key=lambda it: (_name_score(it["rel"]), it.get("exif_len", 0), it.get("size", 0)),
        reverse=True,
    )
    items = []
    total = 0
    for it in members:
        total += it["size"]
        items.append({
            "abs": it["abs"],
            "rel": it["rel"],
            "size": it["size"],
            "exif_len": it.get("exif_len", 0),
            "kind": it["kind"],
        })
    return {
        "id": gid,
        "mode": mode,
        "folder": members[0]["folder"] if members else "",
        "keep_abs": items[0]["abs"] if items else None,
        "items": items,
        "total_size": total,
    }


# ---------- 对外入口 ----------

def scan(root, progress=None):
    root = Path(root)
    items = _enumerate(root, progress)
    cache = Cache(root / ".dup_cache.json")
    try:
        result = _dedupe(root, items, cache, progress)
    finally:
        cache.save()
    return result