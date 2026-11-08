# 在桌面创建「一键导入照片」快捷方式
#
# 用法（只需运行一次，之后双击桌面图标即可）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\setup_oneclick_shortcut.ps1
#
# 说明：
#   - 快捷方式指向仓库内的 oneclick_import.bat
#   - 重复运行会覆盖旧快捷方式（保持指向当前仓库路径）
#   - 想删除快捷方式，直接删桌面图标即可

$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $repo 'oneclick_import.bat'
if (-not (Test-Path -LiteralPath $target)) {
    throw "找不到启动脚本: $target"
}

$desktop = [Environment]::GetFolderPath('Desktop')
$linkPath = Join-Path $desktop '一键导入照片.lnk'

$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($linkPath)
$link.TargetPath = $target
$link.WorkingDirectory = $repo
$link.IconLocation = "$env:SystemRoot\System32\imageres.dll,-1003"
$link.Description = 'Photo Saver — 复制照片/视频并按拍摄时间重命名'
$link.Save()

Write-Host ''
Write-Host "✅ 已创建桌面快捷方式: $linkPath"
Write-Host "   目标: $target"
Write-Host "   以后双击桌面「一键导入照片」即可完成全部流程（无需选择菜单/确认）。"
Write-Host ''
