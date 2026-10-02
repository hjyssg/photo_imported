# Photo Saver 🏞️

一键导入相机照片和视频：复制 → 按拍摄时间重命名。

## 目录结构

```
photo_saver/
├── config.py           ← 改这里！配置源路径/目标路径
├── copy_files.py       Step 1: 从 SD 卡复制文件到 temp 目录
├── import_db.py        导入去重库（部分 MD5 + SQLite），copy_files 自动调用
├── rename_photos.py    Step 2a: 按 EXIF 时间重命名照片
├── rename_videos.py    Step 2b: 按 creation_time 重命名 CLIP 视频
├── analyze_lens.py     焦段 / 光圈分布分析 → 镜头选择建议（24-70 vs 25-200）
├── run_all.py          一键执行全部流程
├── run_all.bat         双击运行（选择菜单）
├── compress-dji-videos.sh  独立的 DJI 视频批量压缩脚本（1080p / H.265）
├── photo-dedup-web/    独立的「照片去重」Web 应用（Flask + React，见其 README）
├── imports.db          自动生成：已导入文件指纹库（已 gitignore）
├── docs/
│   └── database.md     数据库结构说明（imports.db 表结构/索引/维护）
├── LICENSE             MIT
└── README.md
```

## 前置条件

- **Python 3.10+**（代码用到 `X | None` 类型语法；开发环境为 3.14）
- **FFmpeg**（读取视频元数据 / 压缩视频），需保证 `ffprobe`、`ffmpeg` 在 PATH 中

```bash
# Python 包（照片 EXIF 读取）
pip install Pillow

# FFmpeg（视频元数据读取） — https://ffmpeg.org/download.html
# 安装后确保 ffprobe 在 PATH 中可用
ffprobe -version   # 验证安装
```

## 使用前 — 修改 config.py

源路径不再写死盘符，改为「按文件夹自动定位」。打开 `config.py` 按需调整：

```python
LOOKUP_DRIVES = ["G", "H"]          # 只在这几个盘中查找（盘符不固定时改这里）

# 各源的特征目录（仅检查第一层，不深扫）
PHOTO_LOOKUP = "DCIM"                           # 照片：DCIM 下第一层子目录含 DSC*.JPG
DJI_LOOKUP   = "DJI"                            # DJI 无人机：DCIM/DJI_xxxx
CLIP_LOOKUP  = ("PRIVATE", "M4ROOT", "CLIP")    # CLIP：PRIVATE/M4ROOT/CLIP

TEMP_ROOT    = Path("E:/_Photo/temp")           # 目标根目录
```

> 工具会自动在 `LOOKUP_DRIVES` 的盘里按特征文件夹定位三个源；
> 某盘未插入、或找不到对应文件夹，就自动跳过该源，不影响其他源。

## 使用方法

### 双击 run_all.bat（推荐）

```
[1] 完整流程（每步确认）
[2] 完整流程（自动全部确认）
[3] 仅预览（不修改任何文件）
[4] 仅复制文件
[5] 仅重命名照片+视频
[6] 查看导入去重库
```

### 命令行

```bash
# 完整流程
python run_all.py
python run_all.py --yes     # 自动确认

# 预览模式（只看不改）
python run_all.py --dry

# 跳过某些步骤
python run_all.py --skip-copy
python run_all.py --skip-rename
```

### 单独执行各步骤

```bash
python copy_files.py                        # 复制
python copy_files.py --no-db                # 复制，但关闭去重库
python copy_files.py --allow-dup            # 复制，重复文件只登记不跳过
python copy_files.py --db-stats             # 只看去重库状态，不复制
python rename_photos.py --dry              # 照片重命名预览
python rename_photos.py --go               # 照片重命名执行
python rename_videos.py --dry              # 视频重命名预览
python rename_videos.py --go               # 视频重命名执行

# 对任意目录操作（如批次已从 temp 归档到别处）
python rename_photos.py --dir "E:/_Photo/_摄影会/2026/0924 某活动" --dry
python rename_photos.py --dir "E:/_Photo/_摄影会/2026/0924 某活动" --go
python rename_videos.py --dir "E:/_Photo/_摄影会/2026/0924 某活动" --go   # 自动下钻到其 CLIP/

# 焦段/光圈分析（新）
python analyze_lens.py --dir "E:/_Photo/_摄影会/2026/1002 Redland"   # 分析一批照片
python analyze_lens.py --dir .                                         # 分析当前目录
```

### 导入去重库维护

```bash
python import_db.py --path                  # 打印数据库路径（imports.db）
python import_db.py --stats                 # 已登记文件数 / 总大小
python import_db.py --list --limit 20       # 最近 20 条导入记录
python import_db.py --forget DSC05673.JPG   # 删除某文件记录（之后可重新导入）
python import_db.py --relocate "E:/_Photo/temp/0924" "E:/_Photo/_摄影会/2026/0924 某活动"
                                            # 批次归档后修正记录里的目标目录
```

### 焦段 / 光圈分析（analyze_lens.py）

对一批已归档的照片做焦段和光圈统计，帮你决定下次带哪个镜头。

```bash
# 分析任意已归档的批次
python analyze_lens.py --dir "E:/_Photo/_摄影会/2026/1002 Redland"
python analyze_lens.py --dir "E:/_Photo/_年份/2026/0710 BW2026"

# 不指定目录则使用 config.TARGET_DIR 的上一级（temp 根）
python analyze_lens.py
```

输出内容：
- 相机型号、镜头型号
- 主力相机焦段分布（区间 + 最常用焦段 Top 10）
- **24-70mm 覆盖比例** vs **超出 70mm 比例**
- 光圈分布（光圈段、各光圈值的使用频率）
- 镜头选择建议（根据焦段覆盖比例自动推荐 24-70 或 25-200）

典型场景：一场拍摄结束后，用 `analyze_lens.py` 分析焦段使用情况，据此决定下次类似场合带哪个镜头。

该脚本只读不写，可放心使用。

## 流程说明

### Step 1 — 复制文件

从 SD 卡复制到 `E:\_Photo\temp\<mmdd>\`：
- `DCIM\` 下第一层子目录的 `DSC*.JPG`（照片）
- `PRIVATE\M4ROOT\CLIP\` 的 MP4（CLIP，XML 不复制）
- `DCIM\DJI_xxxx\` 的 MP4（DJI 无人机，若有）

目标结构：
```
E:\_Photo\temp\<mmdd>\
├── <照片 DSC*.JPG>
├── CLIP\        ← CLIP 视频
└── DJI\         ← DJI 无人机视频（独立文件夹）
```

#### 导入去重（部分 MD5）

复制前先算源文件的**部分 MD5**，和 `imports.db` 里的记录比对，命中就跳过不复制：

```
指纹 = md5( 文件大小 + 文件头 1MB + 文件尾 1MB )
```

- 只读头尾各 1MB，比整文件 MD5 快得多；小文件等价于整文件 MD5。
- 首次导入成功后登记指纹（文件名、源路径、目标目录、导入时间）。
- 换卡 / 文件被改名后再次插入，只要内容相同就会提示 `⏭ 跳过重复 xxx`，不重复占用空间。
- 同一次导入里出现两份完全相同的文件，第二份也会被跳过。
- 记录里存的是「目标目录」而非文件名，Step 2 重命名后仍然有效。
- 不想要这个行为：`config.py` 里 `SKIP_DUPLICATE_IMPORT = False`（只登记不跳过），
  或命令行 `--allow-dup`；完全关闭用 `--no-db`。

### Step 2 — 按时间重命名

所有文件按拍摄时间统一命名，按时间轴自然排序：

```
DSC05673.JPG  →  2026-09-10_18-58-48.jpg
C1572.MP4     →  2026-09-09_09-53-43.mp4  （配套 XML 同步改名）
```

同秒拍摄自动追加 `_01`、`_02`… 后缀，不另建子文件夹。

## 注意事项

- **先 `--dry` 预览再 `--go` 执行** — 永远不要跳过预览
- 脚本幂等 — 已正确命名的文件自动跳过，可重复运行
- 导入去重库 `imports.db` 与目标目录无关，跨日期/跨批次生效；误判可用 `python import_db.py --forget <文件名>` 删除记录后重跑
- 批次从 `temp/<mmdd>` 归档到别处后，建议执行一次 `import_db.py --relocate <旧目录> <新目录>`，
  让记录里的目标目录保持准确（否则下次导入会提示"⚠ 但该目标目录已不存在"）
- 源按文件夹自动定位，只在 `LOOKUP_DRIVES` 盘中查找；盘未插入/找不到文件夹就跳过
- 照片依赖 EXIF 数据，不含 EXIF 的图片/截图不支持
- 本工具只**复制**和**重命名**，从不删除文件

## 文档

- [`docs/database.md`](docs/database.md) — **数据库结构**：`imports.db` 的表结构与字段含义、内容指纹算法，
  以及「移动 / 改名 / 删除文件后还会不会被判重」的人话说明和常用命令。

## 相关子项目

- **`photo-dedup-web/`** — 独立的「照片去重」Web 应用（Flask + React + Vite）。
  输入一个文件夹路径，服务端按像素指纹 / MD5 找出重复文件，网页上勾选保留哪一份，
  其余移动到 `.photo_dup_removed/`（不删除）。详见 [`photo-dedup-web/README.md`](photo-dedup-web/README.md)。
- **`compress-dji-videos.sh`** — DJI 视频批量压缩为 1080p30 / H.265 ~6Mbps / AAC 128k。

## 许可证

[MIT](LICENSE)
