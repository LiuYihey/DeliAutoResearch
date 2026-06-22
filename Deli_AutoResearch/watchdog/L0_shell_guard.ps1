# L0 Resident Shell Guard (Windows)
# Run in a separate PowerShell window:  .\Deli_AutoResearch\watchdog\L0_shell_guard.ps1
param(
    [string]$RepoRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [int]$MaxStaleHours = 2,
    [int]$PollSeconds = 300
)

$heartbeat = Join-Path $RepoRoot ".heartbeat"
Write-Host "L0 guard watching $heartbeat (max stale ${MaxStaleHours}h)"

while ($true) {
    if (-not (Test-Path $heartbeat)) {
        Set-Content -Path $heartbeat -Value (Get-Date -Format o)
        Write-Host "Created heartbeat file"
    }
    $last = Get-Item $heartbeat
    $ageHours = ((Get-Date) - $last.LastWriteTime).TotalHours
    if ($ageHours -gt $MaxStaleHours) {
        Write-Host "ALERT: heartbeat stale ${ageHours}h — start L1 patrol (Deli_AutoResearch/watchdog/L1_cron_prompt.md)"
        Set-Content -Path $heartbeat -Value (Get-Date -Format o)
    }
    Start-Sleep -Seconds $PollSeconds
}
