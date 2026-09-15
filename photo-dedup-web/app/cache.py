"""cache.py — 指纹 / 哈希缓存（json）。

缓存保存在被扫目录的 `.dup_cache.json`，随目录走。
键用 `rel + '\\x00' + size`（rel 不含 NUL，size 参与键可在文件变化时自动失效）。
只在内容变化（dirty）时写盘，二次扫描命中时避免无谓写盘。
"""
import json
from pathlib import Path

_NUL = "\x00"


class Cache:
    def __init__(self, path):
        self.path = Path(path)
        self._data = {}
        self._dirty = False
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data = loaded
            except Exception:
                self._data = {}

    @staticmethod
    def _key(rel, size):
        return "{}{}{}".format(rel, _NUL, size)

    def has(self, rel, size, kind):
        return self._key(rel, size) in self._data.get(kind, {})

    def get(self, rel, size, kind):
        return self._data.get(kind, {}).get(self._key(rel, size))

    def set(self, rel, size, kind, data):
        self._data.setdefault(kind, {})[self._key(rel, size)] = data
        self._dirty = True

    def save(self):
        if not self._dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
            self._dirty = False
        except Exception:
            # 写缓存失败不影响主流程
            pass