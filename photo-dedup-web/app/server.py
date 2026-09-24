"""server.py — Flask 路由 / API（含静态文件与本地文件代理）。

扫描为长耗时，采用「提交任务 + 后台线程 + 轮询进度」模式。单机只保留最近 1 个任务。
"""
import os
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file

from .mover import build_moves, execute_moves
from .scanner import ScanCancelled, scan as run_scan

BASE_DIR = Path(__file__).resolve().parent.parent

_lock = threading.Lock()
_TASK = None          # 最近一个任务
_allowed_root = None  # /api/file 允许访问的根


class Task:
    def __init__(self, task_id, root):
        self.task_id = task_id
        self.root = str(root)
        self.started_at = time.time()
        self.state = "running"  # running|cancelling|cancelled|done|error
        self.phase = "counting"
        self.scanned = 0
        self.total = 0
        self.groups = None
        self.stats = None
        self.error = None
        self.cancel = False


def _scan_thread(task):
    def progress(pr):
        task.phase = pr.get("phase", task.phase)
        task.scanned = pr.get("scanned", task.scanned)
        task.total = pr.get("total", task.total)
        return task.cancel

    print("[扫描] 开始  root=%s" % task.root, flush=True)
    cur_phase = [""]
    try:
        def progress_printed(pr):
            phase = pr.get("phase", "")
            if phase != cur_phase[0]:
                cur_phase[0] = phase
                print("[扫描] 阶段=%s  %d/%s" % (
                    phase, pr.get("scanned", 0), pr.get("total", "?")) if phase != "counting" else
                    "[扫描] 阶段=%s  %d 文件" % (phase, pr.get("scanned", 0)), flush=True)
            return task.cancel

        result = run_scan(Path(task.root), progress_printed)
        with _lock:
            if task.cancel:
                task.state = "cancelled"
            else:
                task.state = "done"
                task.phase = "完成"
                task.groups = result["groups"]
                task.stats = result["stats"]
        print("[扫描] 完成  %d 组 / %d 文件 / 待移动 %d" % (
            result["stats"]["groups"], result["stats"]["files"],
            result["stats"]["to_move"]), flush=True)
    except ScanCancelled:
        with _lock:
            task.state = "cancelled"
        print("[扫描] 已取消", flush=True)
    except Exception as e:  # noqa: BLE001
        with _lock:
            task.state = "error"
            task.error = str(e)
        print("[扫描] 出错: %s" % e, flush=True)


def create_app():
    app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/static")

    @app.after_request
    def _no_cache(resp):
        # 开发自托管工具：静态资源与本地文件代理不缓存，避免浏览器拿到旧版 app.js
        if request.path.startswith(("/static/", "/api/", "/")):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/")
    def index():
        return send_file(str(BASE_DIR / "static" / "index.html"))

    @app.get("/api/ping")
    def ping():
        return jsonify(ok=True, pid=os.getpid(), version=3)

    @app.post("/api/backend/restart")
    def backend_restart():
        # 交给 run.py 的监督进程接管：以退出码 23 触发自动重启
        threading.Timer(0.05, lambda: os._exit(23)).start()
        return jsonify(ok=True)

    # ---------- 提交扫描任务 ----------
    @app.post("/api/scan/start")
    def scan_start():
        global _TASK, _allowed_root
        data = request.get_json(silent=True) or {}
        root = (data.get("root") or "").strip()
        if not root:
            return jsonify(error="请输入文件夹路径"), 400
        p = Path(root)
        if not p.exists() or not p.is_dir():
            return jsonify(error="路径不存在或不是文件夹"), 400
        with _lock:
            if _TASK is not None and _TASK.state in ("running", "cancelling"):
                return jsonify(error="已有任务正在进行，请等待完成或取消"), 409
            task = Task(uuid.uuid4().hex[:8], p)
            _TASK = task
            _allowed_root = str(p.resolve())
            threading.Thread(target=_scan_thread, args=(task,), daemon=True).start()
        return jsonify(task_id=task.task_id, root=str(p.resolve()))

    # ---------- 查询进度 / 取结果 ----------
    @app.get("/api/scan/status")
    def scan_status():
        task_id = (request.args.get("task_id") or "").strip()
        with _lock:
            task = _TASK
        # 无任务，或请求了具体 task_id 但对不上（后端可能已重启）→ 明确返回 idle
        if task is None or (task_id and task.task_id != task_id):
            return jsonify(state="idle", scanned=0, phase="", elapsed=0)
        resp = {
            "task_id": task.task_id,
            "root": task.root,
            "state": task.state,
            "phase": task.phase,
            "scanned": task.scanned,
            "total": task.total,
            "elapsed": time.time() - task.started_at,
        }
        if task.state == "done":
            resp["groups"] = task.groups or []
            resp["stats"] = task.stats or {}
        if task.state == "error":
            resp["error"] = task.error
        return jsonify(resp)

    # ---------- 取消扫描 ----------
    @app.post("/api/scan/cancel")
    def scan_cancel():
        with _lock:
            if _TASK is not None and _TASK.state == "running":
                _TASK.cancel = True
                _TASK.state = "cancelling"
                return jsonify(ok=True)
        return jsonify(error="没有正在运行的任务"), 404

    # ---------- 本地文件代理（预览缩略图 / 视频） ----------
    @app.get("/api/file")
    def proxy_file():
        p = request.args.get("p", "")
        if not p:
            abort(400)
        with _lock:
            root = _allowed_root
        if not root:
            abort(403)
        path = Path(p)
        try:
            path.resolve().relative_to(Path(root).resolve())
        except Exception:
            abort(403)
        if not path.is_file():
            abort(404)
        return send_file(str(path), conditional=True)

    # ---------- 移动多余份（dry / real） ----------
    @app.post("/api/move")
    def move():
        data = request.get_json(silent=True) or {}
        root = (data.get("root") or "").strip()
        keep_abs = data.get("keep_abs") or []
        dry = bool(data.get("dry", True))
        if not root:
            return jsonify(error="缺少 root"), 400
        with _lock:
            task = _TASK
        groups = []
        if task is not None:
            try:
                same_root = Path(task.root).resolve() == Path(root).resolve()
            except Exception:
                same_root = False
            if same_root:
                groups = task.groups or []
        if not groups:
            return jsonify(error="未找到该目录的扫描结果，请先执行扫描"), 400

        root_p = Path(root)
        moves = build_moves(root_p, groups, keep_abs)
        ok, skip, failed, preview = execute_moves(moves, dry, root_p)
        return jsonify(
            ok=ok,
            skip=skip,
            failed=failed,
            dest=str(root_p / ".photo_dup_removed"),
            preview=preview,
        )

    return app