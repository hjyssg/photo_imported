"""mover.py — 按 keep 清单生成移动计划并执行（dry / real），写 .moved.log。

逻辑同旧 apply_move.py：源不存在 → failed；目标已存在 → skip（不覆盖）；
否则 shutil.move（创建目标父目录）并写日志。移动后源目录每组仅剩 keep 一份，
被移文件不进回收站、不删除，仅移动到 `.photo_dup_removed/同名相对路径`。
"""
import shutil
from pathlib import Path


def build_moves(root, groups, keep_abs):
    """由 keep 清单生成待移动项（保留路径对应的同组其余文件）。

    keep_abs: 每组一个保留的绝对路径；没有出现 keep 的组表示「本组跳过」。
    """
    root = Path(root)
    dest_root = root / ".photo_dup_removed"
    keep_set = set(keep_abs)
    moves = []
    for g in groups:
        keeps = [it["abs"] for it in g["items"] if it["abs"] in keep_set]
        if not keeps:
            continue  # 本组跳过 / 未选中保留
        keep = keeps[0]
        for it in g["items"]:
            if it["abs"] == keep:
                continue
            src = Path(it["abs"])
            try:
                rel = src.relative_to(root)
            except ValueError:
                continue
            moves.append({"from": str(src), "to": str(dest_root / rel), "rel": rel.as_posix()})
    return moves


def execute_moves(moves, dry, root):
    """返回 (ok, skip, failed, results)。results 每项含 from/to/reason。

    reason: move(将移动/dry) | moved(已移动) | dest_exist(跳过) | src_missing(failed)。
    """
    root = Path(root)
    dest_root = root / ".photo_dup_removed"
    log_path = dest_root / ".moved.log"
    log_lines = []
    ok = skip = failed = 0
    results = []

    for m in moves:
        src = Path(m["from"])
        dst = Path(m["to"])
        rec = {"from": m["from"], "to": m["to"]}
        if not src.exists():
            failed += 1
            rec["reason"] = "src_missing"
            results.append(rec)
            continue
        if dst.exists():
            skip += 1
            rec["reason"] = "dest_exist"
            results.append(rec)
            continue
        if dry:
            ok += 1
            rec["reason"] = "move"
            results.append(rec)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dst))
        except Exception:
            failed += 1
            rec["reason"] = "move_failed"
            results.append(rec)
            continue
        ok += 1
        rec["reason"] = "moved"
        results.append(rec)
        log_lines.append("{}\t{}".format(m["from"], m["to"]))

    if log_lines:
        try:
            dest_root.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n".join(log_lines) + "\n")
        except Exception:
            pass

    return ok, skip, failed, results