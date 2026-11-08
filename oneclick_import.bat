@echo off
chcp 65001 >nul
title Photo Saver — 一键导入（自动确认）

cd /d "%~dp0"

rem ── 找 Python：优先 py -3，其次 python ─────────────────────
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>nul && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo.
    echo ❌ 未找到 Python，请先安装 Python 3.10+ 并加入 PATH。
    echo.
    pause
    exit /b 1
)

echo ========================================
echo   Photo Saver — 一键导入
echo   复制 ^> 按时间重命名 ^> 两场拆分检查
echo   （最后可能问一句 y/n：是否拆成两个日期文件夹）
echo ========================================
echo.

rem 额外参数会原样传给 run_all.py，例如 `oneclick_import.bat --dry` 仅预览
%PY_CMD% run_all.py --yes %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo ⚠ 流程结束，但有步骤返回错误（exit code=%RC%），请查看上方日志。
) else (
    echo ✅ 一键导入完成。
)
echo 按任意键关闭窗口...
pause >nul
exit /b %RC%
