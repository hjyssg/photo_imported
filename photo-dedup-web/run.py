"""入口：以监督进程启动 Flask，并在收到退出码 23 时自动重启（配合前端「重启后端」按钮）。

用法：
    cd photo-dedup-web
    python run.py
"""
import subprocess
import sys
import threading
import webbrowser

URL = "http://127.0.0.1:8000"

# 后端子进程实际执行的代码：创建 Flask app 并启动。
# 独立 -c 进程便于监督进程 watch 它的退出码。
_RUNNER = (
    "from app.server import create_app; "
    "app = create_app(); "
    "app.run(host=\"127.0.0.1\", port=8000, threaded=True, debug=False)"
)

_RESTART_CODE = 23  # 由 /api/backend/restart 通过 os._exit(23) 触发重启


def _serve_once():
    print(" * 照片去重 Web 应用: " + URL, flush=True)
    print(" * Ctrl+C 停止服务。", flush=True)
    proc = subprocess.run([sys.executable, "-c", _RUNNER])
    return proc.returncode


def main():
    threading.Timer(1.0, lambda: webbrowser.open(URL)).start()
    while True:
        code = _serve_once()
        if code != _RESTART_CODE:
            print(" * 后端已退出 (code=%s)" % code, flush=True)
            break
        print(" * 检测到重启请求，正在重启后端…", flush=True)


if __name__ == "__main__":
    main()