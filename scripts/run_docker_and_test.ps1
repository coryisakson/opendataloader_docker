Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot\..

docker compose up -d --build

Write-Host "Waiting for API health endpoint..."
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-RestMethod -Method Get -Uri http://localhost:8080/health -TimeoutSec 5
        if ($resp.status -eq 'ok') {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $healthy) {
    throw 'API did not become healthy in time.'
}

python scripts/test_rest_api.py
