# ULTRON Startup Script (PowerShell)
# Run from the project root: .\start_ultron.ps1

param(
    [switch]$Text,       # Text-only mode
    [switch]$Check,      # System check only
    [switch]$Debug,      # Enable debug logging
    [switch]$Install,    # Install dependencies only
    [switch]$NoVoice     # Disable voice
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host "   ULTRON - Local AI Assistant" -ForegroundColor Cyan
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host ""

# Change to project root
Set-Location $PSScriptRoot

# Check Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "  Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found." -ForegroundColor Red
    Write-Host "  Install from: https://python.org" -ForegroundColor Yellow
    exit 1
}

# Install dependencies
function Install-Dependencies {
    Write-Host "  Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to install dependencies." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Dependencies installed." -ForegroundColor Green
}

if ($Install) {
    Install-Dependencies
    exit 0
}

# Check if PyQt6 is installed
$pyqtCheck = python -c "import PyQt6" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Dependencies not installed. Installing..." -ForegroundColor Yellow
    Install-Dependencies
}

# Check Ollama
Write-Host "  Checking Ollama..." -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method GET -TimeoutSec 3
    $models = $response.models.name -join ", "
    Write-Host "  Ollama: ONLINE (models: $models)" -ForegroundColor Green
} catch {
    Write-Host "  Ollama: OFFLINE (will start in limited mode)" -ForegroundColor Yellow
}

# Build argument list
$args_list = @()
if ($Text) { $args_list += "--text" }
if ($Check) { $args_list += "--check" }
if ($Debug) { $args_list += "--debug" }
if ($NoVoice) { $args_list += "--no-voice" }

Write-Host "  Starting ULTRON..." -ForegroundColor Cyan
Write-Host ""

python main.py @args_list

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ULTRON exited with error code $LASTEXITCODE" -ForegroundColor Red
    Write-Host "  Check logs\ultron.log for details." -ForegroundColor Yellow
    Read-Host "  Press Enter to close"
}
