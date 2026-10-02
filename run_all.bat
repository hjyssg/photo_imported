@echo off
chcp 65001 >nul
title Photo Saver — 一键导入照片视频

cd /d "%~dp0"

echo ========================================
echo   Photo Saver
echo   复制 ^> 按时间重命名 ^> 焦段分析
echo ========================================
echo.
echo 请选择操作:
echo [1] 完整流程（每步确认）
echo [2] 完整流程（自动全部确认）
echo [3] 仅预览（不修改任何文件）
echo [4] 仅复制文件
echo [5] 仅重命名照片+视频
echo [6] 查看导入去重库
echo [7] 焦段分析 — 分析一批照片的焦段/光圈
echo.
echo [8] 综合焦段分析 — 对比 BW2026 + Redland
echo.

set /p CHOICE="输入数字 (1-8): "

if "%CHOICE%"=="1" python run_all.py
if "%CHOICE%"=="2" python run_all.py --yes
if "%CHOICE%"=="3" python run_all.py --dry
if "%CHOICE%"=="4" python run_all.py --skip-rename
if "%CHOICE%"=="5" python run_all.py --skip-copy
if "%CHOICE%"=="6" python import_db.py --stats
if "%CHOICE%"=="7" goto ANALYZE
if "%CHOICE%"=="8" goto COMPARE

goto END

:ANALYZE
echo.
echo ⚠ 输入要分析的目录路径（留空则分析 temp 最新批次）：
echo    例: E:\_Photo\_摄影会\2026\0924 某活动
echo    例: E:\_Photo\_年份\2026\0710 BW2026
echo.
set /p DIR_PATH="目录路径: "
if "%DIR_PATH%"=="" (
    python analyze_lens.py
) else (
    python analyze_lens.py --dir "%DIR_PATH%"
)
pause >nul
exit /b

:COMPARE
echo.
echo ⚡ 对比两个目录的焦段分布...
python analyze_lens.py --dir "E:\_Photo\_摄影会\2026\1002 Redland"
echo.
echo ========================================
echo  对比完毕，按任意键分析另一个目录...
echo ========================================
pause >nul
python analyze_lens.py
pause >nul
exit /b

:END
if errorlevel 1 (
    echo.
    echo ⚠ 执行出错，按任意键退出...
    pause >nul
) else (
    echo.
    echo ✅ 完成！按任意键退出...
    pause >nul
)