# 数据库结构（imports.db）

整个项目只有**一个数据库、一张表**：`imports.db` 里的 `imported_files`，作用是记住「哪些文件已经导入过」，避免同一份内容被重复复制。

- 位置：脚本所在目录（`config.py` 里的 `IMPORT_DB_PATH`），首次运行时自动创建，不用手工建库。
- 旁边还会有 `imports.db-wal`、`imports.db-shm` 两个文件，属正常现象（SQLite 的 WAL 模式）；要拷贝备份就三个一起拷。
- 子项目 `photo-dedup-web/` 不用数据库（它用 JSON 缓存），与本文件无关。

## 表结构

```sql
CREATE TABLE IF NOT EXISTS imported_files (
    partial_md5 TEXT PRIMARY KEY,   -- 内容指纹，判重就靠它
    size        INTEGER NOT NULL,   -- 文件大小（字节）
    name        TEXT NOT NULL,      -- 导入时的文件名
    src_path    TEXT NOT NULL,      -- 源路径（卡拔掉后仅作参考）
    dst_dir     TEXT NOT NULL,      -- 导入到的目标目录
    imported_at TEXT NOT NULL       -- 导入时间，如 2026-09-24T21:33:22
);
CREATE INDEX IF NOT EXISTS idx_imported_at ON imported_files(imported_at);
CREATE INDEX IF NOT EXISTS idx_name ON imported_files(name);
```

| 字段 | 说明 |
| --- | --- |
| `partial_md5` | 主键。内容指纹（算法见下）。同一内容重复导入**不会**产生第二行。 |
| `size` | 文件字节数。 |
| `name` | 导入时的文件名。Step 2 改名后这里**不会**跟着变。 |
| `src_path` | 源文件路径，只作历史记录，卡拔了就失效。 |
| `dst_dir` | 导入到的**目录**（不是文件路径）。Step 2 只改名不换目录，所以记目录更稳。 |
| `imported_at` | 首次导入时间，本机时间、无时区。 |

索引：`partial_md5` 是主键自带索引（判重查询用）；`idx_imported_at` 用于「最近导入」列表；`idx_name` 用于按文件名删记录。

## 内容指纹怎么算

```
指纹 = md5( 文件大小 + 文件头 1MB + 文件尾 1MB )
```

只读头尾各 1 MB，比算整个文件的 MD5 快得多：文件 ≤ 1 MB 时读到的头块就是全文（等于整文件 MD5）；
1–2 MB 只读头 1 MB；超过 2 MB 才头尾各读 1 MB。
**注意：指纹里不含路径、不含文件名** —— 这是理解判重的关键。

## 判重规则（人话版）

复制每个文件之前，先算它的指纹，然后去库里查：

- **查到** → 这个内容以前导入过 → **直接跳过，不复制**（打印 `⏭ 跳过重复`）。
- **查不到** → 正常复制，复制成功后才把指纹写进库。
- 目标目录里已经有同名同大小的文件 → 也不重复复制（当成上次中断后的续传，只补记指纹）。

所以「判重」判的是**内容**，不是文件名，也不是路径。

## 移动 / 改名 / 删除文件后，还会被判重吗？

因为只看内容，答案基本都是「会」：

| 你做的事 | 还会被判为重复吗 | 为什么 |
| --- | --- | --- |
| 把导入后的文件移动到别的文件夹（归档） | **会** | 内容没变，指纹就一样。同一批照片不会在别处再存一份。 |
| 用 Step 2 把文件重命名 | **会** | 改名不改内容。 |
| 把文件删掉 | **会**（要小心） | 库里不知道文件已经没了，再插同一张卡会**静默跳过**。想重新导入，先 `--forget` 删记录。 |
| 用软件编辑、压缩、转码过文件 | **不会** | 内容变了指纹就变，会当成新文件重新导入。 |
| 换一张卡 / 改了文件名，但内容一样 | **会** | 这正是这个功能想解决的问题。 |

一句话：**只认「这个内容有没有导入过」，不认文件现在在哪、叫什么名字。**

库里的 `dst_dir` 只是「当初导到哪儿去了」的记录。文件归档后它可能指向旧路径，此时会提示「⚠ 但该目标目录已不存在」——**这只是提示，不影响跳过判断**。想让提示恢复准确，用 `--relocate` 修正记录（它只改库里的路径文字，不会真的移动文件）。

## 常用命令

```bash
python import_db.py --stats                     # 有多少条记录、合计多大
python import_db.py --list --limit 20           # 最近 20 条导入记录
python import_db.py --forget DSC05673.JPG       # 删掉某条记录（之后可重新导入）
python import_db.py --relocate <旧目录> <新目录>   # 归档后修正 dst_dir
python copy_files.py --no-db                    # 本次导入完全不去重
python copy_files.py --allow-dup                # 仍登记指纹，但不跳过重复
```
