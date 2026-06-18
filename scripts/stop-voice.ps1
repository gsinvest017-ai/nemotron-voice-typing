# 強制停止所有 whisper-writer process（Ctrl+C 收不乾淨、或重複啟動卡住時用）
$killed = @()
Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'whisper-writer' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $killed += $_.ProcessId }
if ($killed) { "已停止 PID: $($killed -join ', ')" } else { "沒有正在跑的 whisper-writer" }
