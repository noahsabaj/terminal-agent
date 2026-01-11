# Terminal Agent - Windows Installer
# irm https://raw.githubusercontent.com/noahsabaj/terminal-agent/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

# Colors
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-Host ""
Write-Host "  ╭─────╮" -ForegroundColor Cyan
Write-Host "  │ ◠ ◠ │   Terminal Agent Installer" -ForegroundColor Cyan
Write-Host "  │  ▽  │" -ForegroundColor Cyan
Write-Host "  ╰─────╯" -ForegroundColor Cyan
Write-Host ""

# Check for Podman
$podmanPath = Get-Command podman -ErrorAction SilentlyContinue
if (-not $podmanPath) {
    Write-Host "✗ Podman not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Install Podman Desktop from: " -NoNewline
    Write-Host "https://podman-desktop.io/downloads" -ForegroundColor Cyan
    Write-Host "  After installing, restart your terminal and run this script again."
    Write-Host ""
    exit 1
}
Write-Host "✓ Podman found" -ForegroundColor Green

# Check if Podman machine is running
$machineStatus = podman machine inspect 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "! Podman machine not initialized" -ForegroundColor Yellow
    Write-Host "  Initializing podman machine..."
    podman machine init
}

$machineState = podman machine inspect --format "{{.State}}" 2>&1
if ($machineState -ne "running") {
    Write-Host "! Starting podman machine..." -ForegroundColor Yellow
    podman machine start
}
Write-Host "✓ Podman machine running" -ForegroundColor Green

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
if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}
Write-Host "✓ Created directories" -ForegroundColor Green

# Download files from GitHub
$repoUrl = "https://raw.githubusercontent.com/noahsabaj/terminal-agent/main"

Write-Host "↓ Downloading agent.py..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$repoUrl/agent.py" -OutFile "$installDir\agent.py"

Write-Host "↓ Downloading Containerfile..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$repoUrl/Containerfile" -OutFile "$installDir\Containerfile"

Write-Host "↓ Downloading requirements.txt..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$repoUrl/requirements.txt" -OutFile "$installDir\requirements.txt"

Write-Host "✓ Downloaded all files" -ForegroundColor Green

# Create the agent wrapper script (batch file for Windows)
$agentBat = @'
@echo off
setlocal

set IMAGE_NAME=terminal-agent
set AGENT_DIR=%USERPROFILE%\.terminal-agent

:: Check if image exists, build if not
podman image exists %IMAGE_NAME% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Setting up Terminal Agent (first run only^)...
    podman build -t %IMAGE_NAME% -f "%AGENT_DIR%\Containerfile" "%AGENT_DIR%"
    echo.
)

:: Run sandboxed (--network=host allows access to Ollama on host)
:: Mount at same path so container sees real directory name
podman run --rm -it ^
    -v "%CD%:%CD%" ^
    --workdir "%CD%" ^
    --tmpfs /tmp ^
    --security-opt=no-new-privileges ^
    --hostname terminal-agent ^
    --network=host ^
    -e TERM=xterm-256color ^
    %IMAGE_NAME% %*
'@

$agentBat | Out-File -FilePath "$binDir\agent.bat" -Encoding ASCII
Write-Host "✓ Installed agent command" -ForegroundColor Green

# Add to PATH if needed
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    Write-Host "✓ Added to PATH" -ForegroundColor Green
    $env:Path = "$env:Path;$binDir"
} else {
    Write-Host "✓ PATH already configured" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Run " -NoNewline
Write-Host "agent" -ForegroundColor Cyan -NoNewline
Write-Host " to start."
Write-Host ""
Write-Host "Options:"
Write-Host "  agent" -ForegroundColor Cyan -NoNewline
Write-Host "          Start normally"
Write-Host "  agent --yolo" -ForegroundColor Cyan -NoNewline
Write-Host "   Autonomous mode (no prompts)"
Write-Host ""
Write-Host "Note: You may need to restart your terminal for PATH changes to take effect."
Write-Host ""
