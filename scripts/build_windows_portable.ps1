$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot\.."
$venvPath = Join-Path $repoRoot ".venv-build"
$python = "python"

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating build virtual environment..."
    & $python -m venv $venvPath
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"

Write-Host "Installing/Updating build dependencies..."
& $venvPython -m pip install --upgrade pip wheel
& $venvPython -m pip install -e $repoRoot
& $venvPython -m pip install pyinstaller

$distRoot = Join-Path $repoRoot "dist"
if (-not (Test-Path $distRoot)) {
    New-Item -ItemType Directory -Path $distRoot | Out-Null
}

$toolsDir = Join-Path $repoRoot "tools"
if (-not (Test-Path $toolsDir)) {
    Write-Host "tools folder not found. Creating an empty placeholder at $toolsDir"
    New-Item -ItemType Directory -Path $toolsDir | Out-Null
}

Write-Host "Running PyInstaller..."
& "$venvPath\Scripts\pyinstaller.exe" `
    --clean `
    --noconfirm `
    --name "WinDiagUSB" `
    --windowed `
    --add-data "$toolsDir;tools" `
    "$repoRoot\scripts\launch_app.py"

Write-Host ""
Write-Host "Portable bundle created in: $repoRoot\dist"
Write-Host "Distribute the contents of dist\WinDiagUSB or archive it as needed."
