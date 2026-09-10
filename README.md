# Photo Saver 🏞️

一键导入相机照片和视频：复制 → 按拍摄时间重命名。

## 目录结构

```
photo_saver/
├── config.py           ← 改这里！配置源路径/目标路径
├── copy_files.py       Step 1: 从 SD 卡复制文件到 temp 目录
├── rename_photos.py    Step 2a: 按 EXIF 时间重命名照片
├── rename_videos.py    Step 2b: 按 creation_time 重命名 CLIP 视频
├── run_all.py          一键执行全部流程
├── run_all.bat         双击运行（选择菜单）
└── README.md
```

## 前置条件

```bash
# Python 包（照片 EXIF 读取）
pip install Pillow

# FFmpeg（视频元数据读取） — https://ffmpeg.org/download.html
# 安装后确保 ffprobe 在 PATH 中可用
ffprobe -version   # 验证安装
```

## 使用前 — 修改 config.py

打开 `config.py`，根据实际情况修改路径：

```python
PHOTO_SOURCE = Path("G:/DCIM")              # 索尼照片目录（会扫描所有子目录）
CLIP_SOURCE  = Path("G:/PRIVATE/M4ROOT/CLIP")  # DJI CLIP 视频
DJI_SOURCE   = Path("H:/DCIM/DJI_001")      # DJI 无人机视频（可选）
TEMP_ROOT    = Path("E:/_Photo2/temp")      # 目标根目录
```

> 如果某个源不存在（如 H 盘没插），脚本会自动跳过，不会报错。

## 使用方法

### 双击 run_all.bat（推荐）

```
[1] 完整流程（每步确认）
[2] 完整流程（自动全部确认）
[3] 仅预览（不修改任何文件）
[4] 仅复制文件
[5] 仅重命名照片+视频
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
python rename_photos.py --dry              # 照片重命名预览
python rename_photos.py --go               # 照片重命名执行
python rename_videos.py --dry              # 视频重命名预览
python rename_videos.py --go               # 视频重命名执行
```

## 流程说明

### Step 1 — 复制文件

从 SD 卡复制到 `E:\_Photo2\temp\<mmdd>\`：
- `G:\DCIM\` 下所有子目录的 `DSC*.JPG`
- `G:\PRIVATE\M4ROOT\CLIP\` 的 MP4+XML
- `H:\DCIM\DJI_001\` 的 MP4（如果有）

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
- 如果 SD 卡盘符变了，改 `config.py` 中的源路径即可
- 照片依赖 EXIF 数据，不含 EXIF 的图片/截图不支持