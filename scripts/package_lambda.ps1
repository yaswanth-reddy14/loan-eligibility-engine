$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
# Pass build code over stdin through Python; avoid nested PowerShell/sh/python quoting.
& .\.venv\Scripts\python.exe scripts/package_lambda.py
if ($LASTEXITCODE -ne 0) { throw 'Lambda artifact packaging failed' }
