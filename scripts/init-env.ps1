$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (Test-Path '.env') { throw '.env existe déjà — aucun fichier modifié.' }
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3 est requis pour générer les secrets.' }
Copy-Item '.env.example' '.env'
$secret = (& python -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
if ($LASTEXITCODE -ne 0 -or -not $secret) {
    Remove-Item '.env' -ErrorAction SilentlyContinue
    throw 'Impossible de générer SECRET_KEY avec Python.'
}
$fernet = (& python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())").Trim()
if ($LASTEXITCODE -ne 0 -or -not $fernet) {
    Remove-Item '.env' -ErrorAction SilentlyContinue
    throw 'Impossible de générer ENCRYPTION_KEY avec Python.'
}
$adminPassword = (& python -c "import secrets; print(secrets.token_urlsafe(18))").Trim()
if ($LASTEXITCODE -ne 0 -or -not $adminPassword) {
    Remove-Item '.env' -ErrorAction SilentlyContinue
    throw 'Impossible de générer le mot de passe administrateur avec Python.'
}
$content = Get-Content '.env' -Raw
$content = $content.Replace('REPLACE_WITH_RANDOM_SECRET_AT_LEAST_32_CHARS', $secret)
$content = $content.Replace('REPLACE_WITH_GENERATED_FERNET_KEY', $fernet)
$content = $content.Replace('ChangeThis-Immediately-123!', $adminPassword)
[System.IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $content, [System.Text.Encoding]::ASCII)
Write-Host 'Fichier .env créé.'
Write-Host 'Identifiant initial : admin'
Write-Host "Mot de passe initial : $adminPassword" -ForegroundColor Yellow
Write-Host 'Conservez ce mot de passe et les clés du fichier .env dans un coffre sécurisé.'
