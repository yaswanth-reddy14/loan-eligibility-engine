$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.env')) {
    # Windows PowerShell 5.1 compatible random generation.
    function New-CompatibleSecret {
        $buffer = New-Object byte[] 24
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        $rng.GetBytes($buffer)
        $rng.Dispose()
        return ([BitConverter]::ToString($buffer)).Replace('-', '').ToLowerInvariant()
    }
    $dbSecret = New-CompatibleSecret
    $objectSecret = New-CompatibleSecret
    $content = Get-Content -LiteralPath '.env.example' -Raw
    $content = $content.Replace('POSTGRES_PASSWORD=REPLACE_WITH_GENERATED_LOCAL_SECRET', "POSTGRES_PASSWORD=$dbSecret")
    $content = $content.Replace('MINIO_ROOT_PASSWORD=REPLACE_WITH_GENERATED_LOCAL_SECRET', "MINIO_ROOT_PASSWORD=$objectSecret")
    $content = $content.Replace('loan:REPLACE_WITH_GENERATED_LOCAL_SECRET@', "loan:${dbSecret}@")
    $content = $content.Replace('AWS_SECRET_ACCESS_KEY=REPLACE_WITH_GENERATED_LOCAL_SECRET', "AWS_SECRET_ACCESS_KEY=$objectSecret")
    foreach ($secretName in @('N8N_ENCRYPTION_KEY', 'API_TOKEN', 'WORKFLOW_SECRET')) {
        $secretValue = New-CompatibleSecret
        $content = $content.Replace("$secretName=REPLACE_WITH_GENERATED_LOCAL_SECRET", "$secretName=$secretValue")
    }
    [IO.File]::WriteAllText((Join-Path $PWD '.env'), $content)
}
docker compose build
if ($LASTEXITCODE -ne 0) { throw 'Compose build failed' }
docker compose up -d --no-build
if ($LASTEXITCODE -ne 0) { throw 'Compose startup failed' }
Write-Host 'Dashboard: http://localhost:8000; n8n: http://localhost:5678; Mailpit: http://localhost:8025'
Write-Host 'Next: follow n8n/README.md to import and activate workflows.'
