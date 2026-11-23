$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "== A股趋势工作台 打包 =="
& "$Root\.venv-market\Scripts\python.exe" -m PyInstaller --clean --noconfirm "$Root\market_app.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }

$Exe = Join-Path $Root "dist\AStockWorkbench\AStockWorkbench.exe"
if (-not (Test-Path $Exe)) { throw "未生成 $Exe" }
Write-Host "OK: $Exe"
