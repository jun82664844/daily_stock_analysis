$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path ..\..).Path
Push-Location $repoRoot
try {
    python -m unittest tests.test_user_local_connector_v112
    if ($LASTEXITCODE -ne 0) { throw 'Connector tests failed' }
}
finally {
    Pop-Location
}
python -m PyInstaller dsa-local-connector.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
Copy-Item -Force .\dist\DSA-Local-Connector.exe .\dist\DSA-Local-Connector-Windows-x64.exe
if (-not (Test-Path .\dist\DSA-Local-Connector-Windows-x64.exe)) { throw 'Windows connector artifact missing' }
$downloadDir = Join-Path $repoRoot 'static\downloads'
New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
Copy-Item -Force .\dist\DSA-Local-Connector-Windows-x64.exe (Join-Path $downloadDir 'DSA-Local-Connector-Windows-x64.exe')
