Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot\..

if (Test-Path ".venv/Scripts/python.exe") {
	./.venv/Scripts/python.exe -m ruff check docker-api scripts
} elseif (Test-Path "../.venv/Scripts/python.exe") {
	../.venv/Scripts/python.exe -m ruff check docker-api scripts
} else {
	python -m ruff check docker-api scripts
}
