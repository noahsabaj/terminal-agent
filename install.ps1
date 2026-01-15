# Terminal Agent - Windows Installer
# irm https://raw.githubusercontent.com/noahsabaj/open-terminal-agent/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  ╭─────╮" -ForegroundColor Cyan
Write-Host "  │ ◠ ◠ │   Terminal Agent Installer" -ForegroundColor Cyan
Write-Host "  │  ▽  │" -ForegroundColor Cyan
Write-Host "  ╰─────╯" -ForegroundColor Cyan
Write-Host ""

# Check for Python
$pythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    $pythonPath = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $pythonPath) {
    Write-Host "✗ Python not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Install Python 3.10+ from: " -NoNewline
    Write-Host "https://python.org/downloads" -ForegroundColor Cyan
    Write-Host "  Make sure to check 'Add Python to PATH' during installation."
    Write-Host ""
    exit 1
}

# Check Python version
$pythonVersion = & $pythonPath.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$versionParts = $pythonVersion -split '\.'
$major = [int]$versionParts[0]
$minor = [int]$versionParts[1]

if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Write-Host "✗ Python 3.10+ is required (found $pythonVersion)" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please upgrade Python to version 3.10 or later."
    exit 1
}

Write-Host "✓ Python $pythonVersion found" -ForegroundColor Green

# Check for Ollama
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "✗ Ollama not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Download Ollama from: " -NoNewline
    Write-Host "https://ollama.com/download" -ForegroundColor Cyan
    Write-Host "  Install it, then run this script again."
    Write-Host ""
    exit 1
}
Write-Host "✓ Ollama found" -ForegroundColor Green

# Prompt for Ollama signin
Write-Host ""
Write-Host "! Terminal Agent uses cloud models (e.g., minimax-m2.1:cloud)" -ForegroundColor Yellow
Write-Host "  If you haven't already, sign in to Ollama:"
Write-Host ""
Write-Host "  ollama signin" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to continue (or Ctrl+C to sign in first)"
Write-Host ""

# Create directories
$installDir = "$env:USERPROFILE\.terminal-agent"
$binDir = "$env:USERPROFILE\.local\bin"

if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}
if (-not (Test-Path "$installDir\src\terminal_agent")) {
    New-Item -ItemType Directory -Path "$installDir\src\terminal_agent" -Force | Out-Null
}
if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

# Download source files from GitHub
$repoUrl = "https://raw.githubusercontent.com/noahsabaj/open-terminal-agent/main"

Write-Host "↓ Downloading source files..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$repoUrl/src/terminal_agent/__init__.py" -OutFile "$installDir\src\terminal_agent\__init__.py"
Invoke-WebRequest -Uri "$repoUrl/src/terminal_agent/agent.py" -OutFile "$installDir\src\terminal_agent\agent.py"
Write-Host "✓ Downloaded source files" -ForegroundColor Green

# Create virtual environment
Write-Host "↓ Creating virtual environment..." -ForegroundColor Yellow
& $pythonPath.Source -m venv "$installDir\venv"
Write-Host "✓ Created virtual environment" -ForegroundColor Green

# Install dependencies
Write-Host "↓ Installing dependencies..." -ForegroundColor Yellow
& "$installDir\venv\Scripts\pip.exe" install --quiet ollama pygments rich
Write-Host "✓ Installed dependencies" -ForegroundColor Green

# Create wrapper batch file
$wrapperContent = @"
@echo off
set PYTHONPATH=$installDir\src;%PYTHONPATH%
"$installDir\venv\Scripts\python.exe" -c "from terminal_agent import run_agent; run_agent()" %*
"@

$wrapperContent | Out-File -FilePath "$binDir\terminal-agent.bat" -Encoding ASCII
Write-Host "✓ Installed terminal-agent command" -ForegroundColor Green

# Add to PATH if needed
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    $env:Path = "$env:Path;$binDir"
    Write-Host "✓ Added to PATH" -ForegroundColor Green
    $needPathUpdate = $true
} else {
    Write-Host "✓ PATH already configured" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Run " -NoNewline
Write-Host "terminal-agent" -ForegroundColor Cyan -NoNewline
Write-Host " to start."
Write-Host ""
Write-Host "Options:"
Write-Host "  terminal-agent" -ForegroundColor Cyan -NoNewline
Write-Host "                Start normally (prompts for permission)"
Write-Host "  terminal-agent --accept-edits" -ForegroundColor Cyan -NoNewline
Write-Host " Auto-approve file edits"
Write-Host "  terminal-agent --yolo" -ForegroundColor Cyan -NoNewline
Write-Host "         Full autonomous mode (no prompts)"
Write-Host ""

if ($needPathUpdate) {
    Write-Host "Note: You may need to restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
    Write-Host ""
}
