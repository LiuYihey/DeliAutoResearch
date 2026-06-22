#!/usr/bin/env pwsh
# One-command bootstrap for new machines
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
Write-Host "Deli AutoResearch bootstrap at $Root"
if (Get-Command python -ErrorAction SilentlyContinue) {
    python -m pip install -r requirements.txt -q 2>$null
}
if (-not (Test-Path "$Root\tasks\_example")) {
    python tools/init_task.py _example --topic "Example autonomous research survey"
}
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Read AGENTS.md"
Write-Host "  2. python tools/init_task.py <your-slug> --topic `"Your topic`""
Write-Host "  3. Paste Deli_AutoResearch/orchestrator/loop_prompt.md into Cursor /loop 2h"
Write-Host "Done."
