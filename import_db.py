#!/usr/bin/env python3
"""
import_db.py — 导入去重库（SQLite）：记录已导入文件的「部分 MD5」。

为什么要部分 MD5：
  相机卡上的原片动辄几十 MB，整文件 MD5 太慢；这里只读文件头尾各 1MB，
  再加上文件大小一起哈希（小文件等价于整文件 MD5），足够稳且很快。

指纹 = md5( 文件大小(8字节小端) + 头部 1MB + 尾部 1MB )

用法（维护用，导入流程会自动调用）：
  python import_db.py --stats                # 查看已登记数量、总大小
  python import_db.py --list --limit 20      # 列出最近导入的记录
  python import_db.py --forget DSC05673.JPG  # 按文件名/指纹删除记录
  python import_db.py --relocate <旧目录> <新目录>   # 批次归档后修正记录里的目标目录
  python import_db.py --path                 # 打印数据库路径
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HEAD_BYTES = 1024 * 1024
TAIL_BYTES = 1024 * 1024

_SCHEMA = """
CREATE TABLE IF NOT EXISTS imported_files (
    partial_md5 TEXT PRIMARY KEY,   -- 部分 MD5 指纹
    size        INTEGER NOT NULL,   -- 文件字节数
    name        TEXT NOT NULL,      -- 导入时的文件名
    src_path    TEXT NOT NULL,      -- 源路径（卡拔掉后仅作参考）
    dst_dir     TEXT NOT NULL,      -- 导入到的目标目录（重命名后仍在同目录，故稳定）
    imported_at TEXT NOT NULL       -- 导入时间 ISO 格式
);
CREATE INDEX IF NOT EXISTS idx_imported_at ON imported_files(imported_at);
CREATE INDEX IF NOT EXISTS idx_name ON imported_files(name);
"""


def partial_md5(path, head: int = HEAD_BYTES, tail: int = TAIL_BYTES) -> str | None:
    """计算部分 MD5；文件不存在/读取失败返回 None。"""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        return None
    h = hashlib.md5()
    h.update(size.to_bytes(8, "little"))
    try:
        with open(p, "rb") as f:
            h.update(f.read(head))
            if size > head + tail:          # 小文件头块已覆盖全文，无需再读尾部
                f.seek(-tail, 2)
                h.update(f.read(tail))
    except OSError:
        return None
    return h.hexdigest()



class ImportDB:
    """已导入文件指纹库。连接惰性建立，可当上下文管理器用。"""

    def __init__(self, path):
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = None

    # ── 连接 ──────────────────────────────────────────────
    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.path))
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                pass
            conn.executescript(_SCHEMA)
            conn.commit()
            self._conn = conn
        return self._conn

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # ── 查询 / 登记 ───────────────────────────────────────
    def find(self, fingerprint: str) -> dict | None:
        """按指纹查记录，未登记返回 None。"""
        row = self.connect().execute(
            "SELECT * FROM imported_files WHERE partial_md5 = ?", (fingerprint,)
        ).fetchone()
        return dict(row) if row else None

    def has(self, fingerprint: str) -> bool:
        return self.find(fingerprint) is not None

    def add(self, fingerprint: str, size: int, name: str, src_path, dst_dir,
            imported_at: str | None = None):
        """登记一条导入记录；指纹已存在则忽略（保留首次导入信息）。"""
        conn = self.connect()
        conn.execute(
            "INSERT OR IGNORE INTO imported_files"
            " (partial_md5, size, name, src_path, dst_dir, imported_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (fingerprint, int(size), str(name), str(src_path), str(dst_dir),
             imported_at or datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()

    # ── 统计 / 维护 ───────────────────────────────────────
    def stats(self) -> dict:
        row = self.connect().execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(size), 0) AS bytes FROM imported_files"
        ).fetchone()
        return {"count": row["n"], "bytes": row["bytes"]}

    def recent(self, limit: int = 20) -> list[dict]:
        rows = self.connect().execute(
            "SELECT * FROM imported_files ORDER BY imported_at DESC, name LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]

    def forget(self, key: str) -> int:
        """按指纹或文件名删除记录，返回删除条数。"""
        conn = self.connect()
        cur = conn.execute(
            "DELETE FROM imported_files WHERE partial_md5 = ? OR name = ?", (key, key)
        )
        conn.commit()
        return cur.rowcount

    def relocate(self, old_dir, new_dir) -> int:
        """批次归档后修正记录：把 dst_dir 位于 old_dir 下的记录改写到 new_dir。

        子目录会被保留（如 old/CLIP → new/CLIP）。返回更新条数。
        """
        old = str(Path(old_dir))
        new = str(Path(new_dir))
        conn = self.connect()
        rows = conn.execute("SELECT partial_md5, dst_dir FROM imported_files").fetchall()
        n = 0
        for r in rows:
            d = r["dst_dir"]
            if d == old or d.startswith(old + "\\") or d.startswith(old + "/"):
                conn.execute(
                    "UPDATE imported_files SET dst_dir = ? WHERE partial_md5 = ?",
                    (new + d[len(old):], r["partial_md5"]),
                )
                n += 1
        conn.commit()
        return n


def fmt_size(n: int) -> str:
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024 or unit == "TB":
            return f"{int(v)} B" if unit == "B" else f"{v:.1f} {unit}"
        v /= 1024
    return f"{n} B"


def main():
    from config import IMPORT_DB_PATH

    args = sys.argv[1:]
    db = ImportDB(IMPORT_DB_PATH)

    if "--path" in args:
        print(IMPORT_DB_PATH)
        return

    if "--stats" in args:
        s = db.stats()
        print(f"📚  导入库: {IMPORT_DB_PATH}")
        print(f"    已登记 {s['count']} 个文件，合计 {fmt_size(s['bytes'])}")
        db.close()
        return

    if "--list" in args:
        limit = 20
        if "--limit" in args:
            i = args.index("--limit")
            if i + 1 < len(args):
                try:
                    limit = int(args[i + 1])
                except ValueError:
                    pass
        rows = db.recent(limit)
        print(f"📚  最近 {len(rows)} 条导入记录:")
        for r in rows:
            print(f"    {r['imported_at']}  {r['name']:<28} {fmt_size(r['size']):>10}"
                  f"  {r['partial_md5'][:12]}…  → {r['dst_dir']}")
        db.close()
        return

    if "--forget" in args:
        i = args.index("--forget")
        keys = [a for a in args[i + 1:] if not a.startswith("--")]
        if not keys:
            print("用法: python import_db.py --forget <文件名|指纹>")
            sys.exit(1)
        for k in keys:
            n = db.forget(k)
            print(f"{'✓' if n else '·'}  {k}: 删除 {n} 条")
        db.close()
        return

    if "--relocate" in args:
        i = args.index("--relocate")
        paths = [a for a in args[i + 1:] if not a.startswith("--")]
        if len(paths) < 2:
            print('用法: python import_db.py --relocate <旧目录> <新目录>')
            sys.exit(1)
        n = db.relocate(paths[0], paths[1])
        print(f"✓  已更新 {n} 条记录: {paths[0]} → {paths[1]}")
        db.close()
        return

    print(__doc__.strip())


if __name__ == "__main__":
    main()
