# 照片去重 Web 应用

把「选目录 → 检测 → 看结果 → 移动」收敛到一个**单机自托管 Web 界面**里的照片去重工具。
后端 Python(Flask)，前端零构建的原生 HTML/CSS/JS，双击即用。

> 设计文档见 [`plan.md`](./plan.md)。

## 特性

- 打开网页，输入本地文件夹绝对路径，点击「开始检查」。
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

```bash
cd photo-dedup-web
pip install -r requirements.txt
python run.py
```

浏览器自动打开 `http://127.0.0.1:8000`（也可手动手输入）。

## 目录结构

```
photo-dedup-web/
├── plan.md            # 设计文档
├── README.md
├── requirements.txt   # flask、pillow
├── run.py             # 入口：启动 Flask 并打开浏览器
├── app/
│   ├── __init__.py
│   ├── server.py      # Flask 路由 / API
│   ├── scanner.py     # 扫描 + 图片内容指纹 + MD5 分组 + 推荐保留
│   ├── mover.py       # 按 keep 清单移动（dry/real）+ 日志
│   └── cache.py       # 指纹/哈希缓存（json）
├── static/
│   ├── index.html     # 主页面
│   ├── app.js         # 交互逻辑
│   └── style.css
└── run_tests.md       # 手工验收清单
```

## API 一览

| 方法路径 | 说明 |
|---|---|
| `GET /` | 首页 (`static/index.html`) |
| `POST /api/scan/start` | `{root}` → `{task_id}`，后台线程扫描 |
| `GET /api/scan/status?task_id=` | 轮询进度；`done` 时返回 `groups` / `stats` |
| `POST /api/scan/cancel` | 取消当前任务 |
| `GET /api/file?p=<绝对路径>` | 本地文件代理（只允许被扫目录内），预览缩略图/视频 |
| `POST /api/move` | `{root, keep_abs[], dry}` → `{ok, skip, failed, preview, dest}` |

## 安全提示

- 移动是**不可逆**操作（本工具只移动不删除）。始终先看 dry 预览再确认。
- `/api/file` 限制在用户本次输入的目录内，防任意文件读取。
- 仅本机使用，勿暴露到公网。