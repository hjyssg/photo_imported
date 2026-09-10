@echo off
chcp 65001 >nul
title Photo Saver — 一键导入照片视频

cd /d "%~dp0"

echo ========================================
echo   Photo Saver
echo   一键复制^>重命名^>连拍分组
echo ========================================
echo.

echo 请选择操作:
echo [1] 完整流程（逐步确认）
echo [2] 完整流程（自动全部确认）
echo [3] 仅预览（不修改任何文件）
echo [4] 仅复制文件
echo [5] 仅重命名照片+视频
echo [6] 仅连拍分组
echo.

set /p CHOICE="输入数字 (1-6): "

if "%CHOICE%"=="1" python run_all.py
if "%CHOICE%"=="2" python run_all.py --yes
if "%CHOICE%"=="3" python run_all.py --dry
if "%CHOICE%"=="4" python run_all.py --skip-rename --skip-group
if "%CHOICE%"=="5" python run_all.py --skip-copy
if "%CHOICE%"=="6" python run_all.py --skip-copy --skip-rename

if errorlevel 1 (
    echo.
    echo ⚠ 执行出错，按任意键退出...
    pause >nul
) else (
    echo.
    echo ✅ 完成！按任意键退出...
    pause >nul
)