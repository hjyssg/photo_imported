# 照片去重 Web 应用

把「选目录 → 检测 → 看结果 → 移动」收敛到一个**单机自托管 Web 界面**里的照片去重工具。
后端 Python(Flask)，前端 **React + Vite**（构建产物打进 `static/`，仍是双击 `python run.py` 即可用）。

> 设计文档见 [`plan.md`](./plan.md)。

## 特性

- 打开网页，输入本地文件夹绝对路径，点击「开始检查」。扫描进度（阶段/百分比/计数/计时）实时显示。
- 服务端做**内容级**重复检测：
  - 图片：`(folder, h128)→(h64, w, h)` 像素指纹，可抓“同像素但 EXIF/格式/文件名不同”的重复。
  - 视频 / 跨目录备份：按 `size` 分桶 + MD5 字节比对。
- 结果逐组、逐行列出，行内小缩略图预览；每组单选「保留」（默认自动推荐 1 份），其余「待移动」。
- 提供「本组跳过」与文件名过滤、分组分页。
- **两阶段移动**：先 dry 预览，确认后才真正 `shutil.move` 到 `被扫目录/.photo_dup_removed/同名相对路径`（保留子目录结构），**不删除任何文件**；移动记录写在 `.photo_dup_removed/.moved.log`，可手工还原。
- 目标已存在即跳过（不覆盖）；源缺失记失败。
- 指纹/哈希缓存在 `被扫目录/.dup_cache.json`，二次扫描命中缓存，秒级返回。
- 仅绑定 `127.0.0.1`，不暴露公网。

## 安装与运行

### 1. 前端依赖（首次或依赖变更时）
```bash
cd photo-dedup-web
npm install
npm run build        # 构建 React 产物到 static/（Flask 直接服务）
```

### 2. 启动
```bash
cd photo-dedup-web
pip install -r requirements.txt
python run.py        # 构建好 static/ 后，浏览器自动打开 http://127.0.0.1:8000
```

### 3. 前端开发（热更新）
```bash
cd photo-dedup-web
npm run dev          # Vite: http://127.0.0.1:5173 ，已把 /api 代理到 Flask 8000
```
开发时需保持后端 `python run.py`（或 `python -c "from app.server import create_app; create_app().run(port=8000)"`）在运行。
改动 `src/` 后，记得 `npm run build` 再让用户用 `python run.py` 访问。

## 目录结构

```
photo-dedup-web/
├── plan.md            # 设计文档
├── README.md
├── requirements.txt   # flask、pillow
├── run.py             # 入口：启动 Flask 并打开浏览器
├── package.json       # 前端依赖 / 脚本
├── vite.config.js     # Vite 配置（build → static/，dev 代理 /api）
├── index.html         # Vite 入口（构建后输出到 static/index.html）
├── src/               # React 前端源码
│   ├── main.jsx / App.jsx / app.css
│   ├── api.js
│   ├── useScan.js     # 扫描轮询 Hook（状态机 + 进度）
│   └── components/    # ScanBar / StatusBar / ProgressPanel / Results / GroupCard / Toast
├── app/
│   ├── __init__.py
│   ├── server.py      # Flask 路由 / API
│   ├── scanner.py     # 扫描 + 图片内容指纹 + MD5 分组 + 推荐保留
│   ├── mover.py       # 按 keep 清单移动（dry/real）+ 日志
│   └── cache.py       # 指纹/哈希缓存（json）
└── static/            # 前端构建产物（Flask 服务的静态目录；不要再手工改，由 npm run build 生成）
```

## API 一览

| 方法路径 | 说明 |
|---|---|
| `GET /` | 首页（构建后 `static/index.html`） |
| `POST /api/scan/start` | `{root}` → `{task_id}`，后台线程扫描 |
| `GET /api/scan/status?task_id=` | 轮询进度；按 `task_id` 匹配，未命中返回 `idle`；`done` 时返回 `groups` / `stats` / `elapsed` |
| `POST /api/scan/cancel` | 取消当前任务 |
| `GET /api/file?p=<绝对路径>` | 本地文件代理（只允许被扫目录内），预览缩略图/视频 |
| `POST /api/move` | `{root, keep_abs[], dry}` → `{ok, skip, failed, preview, dest}` |

## 安全提示

- 移动是**不可逆**操作（本工具只移动不删除）。始终先看 dry 预览再确认。
- `/api/file` 限制在用户本次输入的目录内，防任意文件读取。
- 仅本机使用，勿暴露到公网。