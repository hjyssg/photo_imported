#!/usr/bin/env python3
"""
视频压缩启动器 — 供 VS Code launch.json 调用

用法:
    python compress_launcher.py -dir "E:/_Photo/2026/0830/舞台"
    python compress_launcher.py                        # 会提示输入路径
    python compress_launcher.py --dry                  # 预览 + 提示输入
"""
import subprocess
import sys
import os
import shutil


def find_bash():
    """在 Windows 上查找 Git Bash 的位置"""
    # 1) 先从 PATH 找
    bash = shutil.which("bash")
    if bash:
        return bash
    # 2) 常见 Git Bash 安装位置
    common_paths = [
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files (x86)\Git\usr\bin\bash.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Git\usr\bin\bash.exe"),
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p
    # 3) 用 where 命令查
    try:
        r = subprocess.run(["where", "bash"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
            if lines and os.path.isfile(lines[0]):
                return lines[0]
    except Exception:
        pass
    return None


def main():
    args = list(sys.argv[1:])
    dir_path = None
    dry_run = False

    i = 0
    while i < len(args):
        if args[i] in ("-dir", "--dir", "-d", "--directory"):
            if i + 1 < len(args):
                dir_path = args[i + 1]
                i += 2
            else:
                print("  ❌ -dir 后面缺少路径")
                sys.exit(1)
        elif args[i] in ("--dry", "--preview", "-n"):
            dry_run = True
            i += 1
        elif args[i] in ("-h", "--help"):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            bash = find_bash()
            if bash:
                subprocess.run([bash, os.path.join(script_dir, "compress-dji-videos.sh"), "--help"])
            else:
                print("  ❌ 未找到 bash (Git Bash)，请在终端直接运行:")
                print(f"     bash \"{os.path.join(script_dir, 'compress-dji-videos.sh')}\" --help")
            return
        else:
            i += 1

    # 提示输入路径
    if not dir_path:
        print("")
        print("╔══════════════════════════════════════════════════╗")
        print("║   视频压缩 — 请输入文件夹路径                     ║")
        print("╚══════════════════════════════════════════════════╝")
        print("")
        dir_path = input("  路径 > ").strip().strip('"').strip("'")
        if not dir_path:
            print("  ❌ 未输入路径")
            sys.exit(1)
        print("")

    # 确定脚本路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "compress-dji-videos.sh")
    if not os.path.exists(script_path):
        print(f"  ❌ 找不到脚本: {script_path}")
        sys.exit(1)

    # 查找 bash 并执行
    bash = find_bash()
    if not bash:
        print("  ❌ 未找到 Git Bash。请安装 Git for Windows 或直接在终端运行:")
        print(f"     bash \"{script_path}\" -dir \"{dir_path}\"")
        sys.exit(1)

    cmd = [bash, script_path, "-dir", dir_path]
    if dry_run:
        cmd.append("--dry")

    print(f"  🚀 运行: bash compress-dji-videos.sh -dir \"{dir_path}\"")
    print("")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()