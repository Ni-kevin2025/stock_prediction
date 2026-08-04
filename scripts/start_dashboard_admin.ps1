param([switch]$Elevated)

if (-not $Elevated) {
    Start-Process -Verb RunAs -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-Elevated'
    )
    exit
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = 'D:\Condaenv\stock-agent-py311\python.exe'
$dashboard = Join-Path $projectRoot 'src\stock_prediction\dashboard.py'
$env:PYTHONPATH = Join-Path $projectRoot 'src'

if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到指定 Conda 环境：$python"
}
if (-not (Test-Path -LiteralPath $dashboard)) {
    throw "未找到仪表盘：$dashboard"
}

$existing = Get-NetTCPConnection -State Listen -LocalPort 8501 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $existing) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -eq 'python') {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
        } catch {
            # A protected parent process may remain after its dashboard child has stopped.
        }
    }
}

Start-Process -FilePath $python -WorkingDirectory $projectRoot -ArgumentList @(
    '-m', 'streamlit', 'run', $dashboard, '--server.port=8501'
)
