# 照片去重 Web 项目 · 设计文档（plan.md）

> 目标：把原 `d:\Git\photo_saver` 那套"脚本 + 静态 HTML"去重流程，重做成一个**完整自包含的 Web 应用**：
> 用户打开网页 → 输入文件夹路径 → 点「开始检查」→ 服务端做内容级重复检测 → 结果**逐行**显示，可勾选每份的去留 → 一键把多余份移动到一个 temp 目录（不删除任何文件）。
>
> 本文件是设计稿 / 实现规格。请在新环境里**从零实现本文件描述的项目**，不要依赖 `d:\Git\photo_saver` 里的旧脚本。

---

## 1. 背景与目标

### 1.1 要解决的问题
旧方案是命令行脚本链：`find_dups.py` 扫描 → `make_site.py` 生成静态 HTML → 人工在浏览器审核 → 复制清单 → `apply_move.py` 移动。流程能跑，但对普通用户不友好：**不是"打开即用"，要手敲一堆 --args、要跨 HTML/文本/命令行折腾清单**。

### 1.2 本项目的形态
一个**单机自托管的 Web 应用**（后端 Python，前端浏览器），把"选目录 → 检测 → 看结果 → 移动"全部收敛到一个 UI 里。

### 1.3 核心验收标准（做到才算完成）
1. `pip install -r requirements.txt && python run.py` 后，浏览器打开 `http://127.0.0.1:8000` 出现一个带输入框的页面。
2. 输入任意本地目录路径，点「开始检查」，页面能扫出该目录下的**内容重复**文件，并逐组、逐行列出。
3. 每组可勾选保留哪一份（默认自动推荐 1 份），其余为"待移动"。
4. 点「移动到 temp」，多余份被移到 `被扫目录/.photo_dup_removed/`（保留子目录结构），**源目录每组保留 1 份，不删除任何文件**；有移动记录可还原。
5. 对大目录（上万文件）能缓存哈希、二次扫描秒级完成。

---

## 2. 技术选型

| 层面 | 选型 | 理由 |
|---|---|---|
| 运行时 | **Python 3.8+** | 与原项目一致；指纹检测有现成库 |
| Web 框架 | **Flask**（轻量，内置 dev server） | 自包含、无需额外前端框架 |
| 图片指纹 | **Pillow**（PIL） | `Image.convert('L').thumbnail((128,128))` 做内容指纹 |
| 前端 | **React + Vite**（构建产物进 `static/`） | 组件化、状态机清晰，避免原生 JS 的“作用域被吞”类 bug；`npm run build` 后可继续 `python run.py` 单文件服务 |
| 数据格式 | JSON | 前后端沟通简单 |
| 并发 | 单进程，扫描用线程执行上报进度 | 避免阻塞请求、UI 能刷进度 |

> 决策说明：
> - 前端采用 React+Vite，用 `useScan` Hook 做 800ms 轮询状态机（idle/submitting/running/done/error/cancelled/offline），逐阶段显示进度百分比、计数与耗时。
> - 构建产物输出到 `static/`（`emptyOutDir`），因此 `python run.py` 的服务方式不变；开发时 `npm run dev`（Vite:5173）把 `/api` 代理到 Flask:8000。
> - 不用 SQLite，重复分组只存在于一次扫描的内存结果里；缓存只存"文件路径 → 内容指纹"以便加速。
> - 移动用 `shutil.move`，与旧 `apply_move.py` 相同策略（目标存在则跳过，源不存在则报错）。

---

## 3. 目录结构（新项目布局）

```
photo-dedup-web/
├── plan.md                # 本设计文档
├── README.md              # 安装/运行说明
├── requirements.txt       # flask、pillow
├── run.py                 # 入口：启动 Flask 并打开浏览器
├── package.json           # 前端依赖 / scripts（dev / build）
├── vite.config.js         # Vite：build→static/，dev 代理 /api→Flask:8000
├── index.html             # Vite 入口
├── src/                   # React 前端源码
│   ├── main.jsx / App.jsx / app.css
│   ├── api.js             # 后端接口封装
│   ├── useScan.js         # 扫描轮询 Hook（状态机 + 进度 + 计时）
│   └── components/        # ScanBar / StatusBar / ProgressPanel / Results / GroupCard / Toast
├── app/
│   ├── __init__.py
│   ├── server.py          # Flask 路由 / API（含静态文件代理）
│   ├── scanner.py         # 扫描 + 图片内容指纹 + 分组返回重复列表
│   ├── mover.py           # 按 move 清单做 dry/move，记录日志
│   └── cache.py           # 哈希/指纹缓存读写（json）
└── static/                # 前端构建产物（Flask 服务；由 npm run build 生成，勿手改）
```

> 约定：本项目**自包含**，不复用 `d:\Git\photo_saver` 顶层任何 `.py`。若需参考算法，可对照阅读旧 `dup_common.py / find_dups.py`，但代码全部重写为新结构。

---

## 4. 数据与算法设计

### 4.1 文件枚举与过滤
- 递归扫描 `root.rglob('*')`，仅处理**图片/视频**扩展名：
  - 图片：`.jpg .jpeg .png .gif .bmp .webp`
  - 视频：`.mov .mp4 .avi .mkv .m4v`
- 跳过：`._*`（AppleDouble）、`.DS_Store`、`Thumbs.db`。
- 所有文件记录：`abs / rel / size / kind(img|vid) / folder`。
  - `folder`：`rel` 去掉最后一个文件名后的目录部分；**根目录文件 folder = ''**（`''` 是同组分组键，不是文件夹名，勿当路径拼接）。

### 4.2 重复判定（内容级，分两类）
**A. 图片内容重复（同目录内，像素一致）**
1. 对每张图片算内容指纹：`Image.open` → `convert('L')` → `thumbnail((128,128))` → `md5(pixels)` 得 `h128`；再 `thumbnail((64,64))` → `md5` 得 `h64`；同时取 `(w, h, exif_len)`。
2. 以 `(folder, h128)` 粗分组，组内再按 `(h64, w, h)` 精分组；精组 ≥2 即为"内容重复"候选。
3. 这个指纹能抓到"同像素但 EXIF/格式/文件名不同"的重复。

**B. 字节级相同（跨目录 + 视频）**
1. 先按 `size` 分桶，仅对同 size ≥2 的桶算 MD5（`hashlib.md5` 分块 1MB 读），MD5 相同即重复。
2. 既捕获跨目录的图片备份，也捕获视频（视频不做像素指纹，太慢）。

> 性能点：
> - 图片求指纹必须**懒加载缩略图**并用缓存，否则上万张会卡死。
> - `Image.MAX_IMAGE_PIXELS=1e9`，`ImageFile.LOAD_TRUNCATED_IMAGES=True` 以容忍损坏文件。
> - 单张指纹失败（损坏/非解码）→ 记为 `hash=None`，跳过，不崩溃。

### 4.3 推荐保留规则（默认选中）
组内用启发式挑一份推荐：
1. **文件名信息量**：含日期 `YYYY-MM-DD`(100分)，含 `时间 HH:MM[:SS]`(200分，含秒再+50) → 分最高的优先。
2. 其次 **EXIF 更多**（`exif_len` 大者）。
3. 再其次 **文件更大**（`size` 大者）。
（对应旧 `dup_common.py` 的 `name_score / pick_keep`，此处重写并入 `scanner.py`。）

---
## 5. 后端 API 设计（Flask）

> 所有接口返回 JSON；`扫描` 为长耗时，用"提交任务 + 轮询进度"模式，避免请求超时。

### 5.0 全局约定
- 根路径 `GET /` → 返回 `static/index.html`。
- 静态资源 `GET /static/<path>` → Flask 自带 static 目录。
- 提供一个**本地文件代理**端点（关键！）：
  - `GET /api/file?p=<绝对路径>` → 用 `send_file` 返回该本地图片/视频。
  - **原因**：在 `http://127.0.0.1` 页面里直接 `<img src="file:///E:/...">` 会被浏览器跨源拦截，必须走后端代理。
  - 安全性：仅允许 `p` 为"用户本次输入目录"或其子目录内的文件（后端记录允许根），防任意文件读取。

### 5.1 提交扫描任务
```
POST /api/scan/start
body: { "root": "E:/_Photo/_年份/2017" }
resp: { "task_id": "abc123" }
```
- 校验 `root` 存在且是目录；`root` 存入内存中的任务表（单机只保留最近 1 个任务）。
- 新建后台线程执行扫描（见 §5.3 扫描流程），任务表记录 `state: running|done|error` 与进度计数。

### 5.2 查询进度 / 取结果
```
GET /api/scan/status?task_id=abc123
resp: { "state":"done", "scanned":5928, "phase":"图片指纹|MD5|完成",
        "groups": [ { "id":1, "mode":"内容重复(像素一致)", "folder":"",
                      "keep_abs":"E:/.../keep.jpg",
                      "items":[ {"abs":"E:/.../a.jpg","rel":"a.jpg","size":123456,"exif_len":5120,"kind":"img"},
                                {"abs":"E:/.../b.jpg","rel":"b.jpg","size":123000,"exif_len":2048,"kind":"img"} ] } ],
        "stats":{ "groups":484, "files":968, "to_move":484, "freed_bytes":1234567890 } }
```
- `groups` 仅在 `state==done` 时返回；`stats` 由服务端按"每组保留 1 份"预算。
- `id` 为组内稳定编号；`keep_abs` 为推荐保留；前端用它做默认勾选。

### 5.3 扫描流程（scanner.py）
```
scan(root):
   1. items = 枚举过滤后的文件列表(记 size/rel/folder)
   2. 图片指纹：逐张算 (w,h,exif_len,h128,h64)，写缓存；按 (folder,h128)->精(h64,w,h) 分组，≥2 成组
   3. MD5：按 size 分桶，≥2 的桶读 MD5，相同成组（跨目录/视频）
   4. 汇总去重(按文件集合)、排序、对每组算 keep_abs(推荐保留)
   5. 返回 {groups, stats}
进度阶段：counting -> img_fingerprint(每500更新) -> md5 -> done
```

### 5.4 移动多余份
```
POST /api/move
body: { "root":"...", "keep_abs":["E:/.../keep.jpg", ...],   # 每组保留的绝对路径(每个组且仅给1个)
        "dry": true|false }
resp: { "ok":N, "skip":M, "failed":0, "dest":".../.photo_dup_removed",
        "preview":[ {"from":"...","to":"...","reason":"dest_exist|moved"|...} ] }
```
- `dest` 固定为 `root/.photo_dup_removed/`（保留被扫目录内的相对子目录结构）。
- 待移动 = 该组全部文件 − 该组 keep 的那份。
- 逻辑同旧 `apply_move.py`：源不存在→计 `failed`；目标已存在→跳过计 `skip`；否则 `shutil.move` 并写日志。
- 前端先 `dry:true` 出预览确认，再 `dry:false` 正式移动。

### 5.5 移动记录（可还原）
每次移动写一行 `源\t目标` 到 `root/.photo_dup_removed/.moved.log`。
可选扩展：`POST /api/rollback` 按日志把文件移回源（默认不做，但记录保留，方便手工还原）。

---

## 6. 前端交互设计（static/）

> 重点：**逐行显示重复项**。不做卡片缩略图大图墙，改为紧凑的行式列表；行内左侧预览缩略图(小)、中间文件名+完整路径、右侧大小/类型，最右单选"保留 / 移动"。

### 6.1 页面布局（index.html）
```
┌────────────────────────────────────────────┐
│  照片去重工具                              │
│  [输入文件夹路径＿＿＿＿＿＿] [开始检查]    │
│  ──────────────────────────────────────── │
│  进度区(state / 已扫描 N 文件 / 当前阶段)   │
│  ──────────────────────────────────────── │
│  统计条：重复组 G · 文件 F · 待移动 M · 可释放 X │
│  ──────────────────────────────────────── │
│  [移动到 temp(释出清单)]                    │
│  ──────────────────────────────────────── │
│  组 #12  ▸ 内容重复(像素一致) · 3 份 · 1.2MB │
│   ├─ [缩略] keep.jpg          E:\...  (1.0MB)  (保留⊙)  (移动○)
│   ├─ [缩略] keep_1.jpg        E:\...  (1.0MB)  (保留○)  (移动⊙)
│   └─ [缩略] IMG_0001.JPG      E:\...  (1.1MB)  (保留○)  (移动⊙)
│  组 #13  ▸ 字节级相同(MD5) · 2 份 · ...        '本组跳过' 按钮
│   ├─ ...
└────────────────────────────────────────────┘
```

### 6.2 交互流程（app.js）
1. **输入+开始**：填路径 → `POST /api/scan/start` → 拿到 `task_id` → 每 800ms 轮询 `/api/scan/status`，刷进度。
2. **渲染结果**：`state==done` 后，按 `groups` 渲染：
   - 每个 `<section class="group">` 一个重复组，逐行渲染 `items`。
   - 每行用单选 `保留`（默认按 `keep_abs` 勾选），其余默认 `移动`。
   - 组头提供「本组跳过」（该组不参与移动）。
   - **默认移动项打红/灰标签**；保留项打绿标签，一眼可辨。
   - 行内缩略图 `<img src="/api/file?p=...">` 或 `<video>`（加载小图/元数据，懒加载）。
3. **移动(两阶段)**：
   - 点「移动到 temp」→ 收集每组的保留路径（没跳过且只给第 1 个保留项）→ `POST /api/move {dry:true}` → **列表展示预览**（这 N 个将移动，target 存在则标黄）。
   - 预览区放「确认移动」→ 真正执行 `{dry:false}` → 刷新：移到 temp 的行从源列表移除（或整体标记"已移动"）。

### 6.3 边界与健壮性
- 路径输入：支持中文/空格/反斜杠；`root` 不存在→前端 toast 报错。
- 扫描中禁止重复提交同 root；可「取消」任务（置取消标志，线程到检查点退出）。
- 大数据渲染：上万行用**分批渲染**（虚拟列表：只渲染视口内 group/row）或分页，避免 DOM 卡死。
- 图片解码失败行显示"无法预览"灰块，但行仍参与选中/移动。

---
## 7. 依赖与运行

### 7.1 requirements.txt
```
flask>=3.0
pillow>=10.0
```

### 7.2 运行
```bash
cd photo-dedup-web
pip install -r requirements.txt
python run.py            # 打印 http://127.0.0.1:8000 并自动用浏览器打开
```
- `run.py`：创建 Flask app（`app/server.py` 的 `create_app()`），`app.run(host="127.0.0.1", port=8000, threaded=True)`；可选 `webbrowser.open`。
- 仅绑定 `127.0.0.1`（单机工具，不暴露公网）。

### 7.3 缓存
- 指纹缓存存到 `root/.dup_cache.json`（紧邻被扫目录，随目录走）或 `项目/data/cache_<roothash>.json`。
- 缓存键 `(rel,size)` → 指纹；二次扫描命中免重算，秒级返回。

---

## 8. 实现顺序（里程碑，建议按此提交）

| # | 内容 | 退出标准 |
|---|---|---|
| M1 | 项目骨架 + Flask 起服务 + 静态首页骨架 | `python run.py` 能开盒页面 |
| M2 | `scanner.py` 核心算法（枚举/图片指纹/MD5/分组/推荐保留）+ 用人工构造的重复目录验证 | 对重复目录输出正确 groups |
| M3 | `/api/scan/start` 后台线程 + `/status` 轮询进度 | 大目录能刷进度，`done` 返回 groups |
| M4 | `/api/file` 本地代理预览 | 前端能显示缩略图/视频 |
| M5 | 前端渲染逐行列表 + 保留/移动勾选 + 本组跳过 | 页面逐行显示，勾选生效 |
| M6 | `/api/move`(dry+real) + 前端两阶段确认 | dry 预览 → 确认 → 文件真实移走，log 写入 |
| M7 | 健壮性收尾（虚拟列表、错误 toast、路径校验、缓存加速、README） | 通过下方验收清单 |

---

## 9. 手工验收清单（建议用真实副本小目录测试）
1. 一个目录放 3 份像素相同但文件名/EXIF 不同的 jpg（一份因改过 EXIF 而大小不同），扫描应**只成 1 组、显示 3 行**，默认推荐保留文件名信息量最高的一份。
2. 一个视频在两个不同子目录各一份 → 组为「字节级相同(MD5)」，默认保留 1。
3. 选中保留某行后，其余行标"移动"；点「移动到 temp」先是 dry 预览，再确认后文件真的移到 `.photo_dup_removed/同名相对路径`，源目录每组只剩 1 份。
4. 目标已存在时跳过并提示（不覆盖）。
5. 重复点「开始检查」第二次：命中缓存，秒级返回。
6. 输入不存在路径时，页面报错不崩。

---

## 10. 风险与说明
- **性能**：上万文件首次扫描仍要几分钟（图片解码耗 CPU）；缓存 + 进度显示让体验可接受；极端可加多线程指纹（本期不加，保持简单正确）。
- **权限/安全**：仅本机、仅读用户输入的目录；`/api/file` 限制在用户目录内，防越权。
- **移动是不可逆操作**：移动而非删除；始终 dry 预览 + 日志，误操作可依 `.moved.log` 手工还原。
- **跨平台**：Path 用 `pathlib`，Windows 反斜杠/中文没问题；`send_file` 用内联预览处理非 UTF-8 文件名。