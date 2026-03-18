# Hangfire MCP - One-Click Setup
# Run this script to set up everything

param(
    [string]$ConnectionString,
    [switch]$SkipDashboard
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "🔥 Hangfire MCP Setup" -ForegroundColor Red
Write-Host "=====================" -ForegroundColor Red
Write-Host ""

# Step 1: Check Python
Write-Host "Step 1: Checking Python..." -ForegroundColor Cyan
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python not found. Please install Python 3.11+"
    exit 1
}
Write-Host "  ✓ $pythonVersion" -ForegroundColor Green

# Step 2: Create virtual environment if needed
$venvPath = Join-Path $projectRoot ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host ""
    Write-Host "Step 2: Creating virtual environment..." -ForegroundColor Cyan
    python -m venv $venvPath
    Write-Host "  ✓ Created .venv" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Step 2: Virtual environment exists" -ForegroundColor Cyan
    Write-Host "  ✓ Using existing .venv" -ForegroundColor Green
}

# Activate venv
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
. $activateScript

# Step 3: Install package with dashboard
Write-Host ""
Write-Host "Step 3: Installing dependencies..." -ForegroundColor Cyan
pip install -q -e ".[dashboard]"
Write-Host "  ✓ Installed hangfire-mcp with dashboard" -ForegroundColor Green

# Step 4: Configure connection string
Write-Host ""
Write-Host "Step 4: Configuring connection..." -ForegroundColor Cyan

$mcpConfigDir = Join-Path $projectRoot ".vscode"
$mcpConfigPath = Join-Path $mcpConfigDir "mcp.json"

# Try to get connection string from mcp.json first
if (-not $ConnectionString -and (Test-Path $mcpConfigPath)) {
    try {
        $existingConfig = Get-Content $mcpConfigPath -Raw | ConvertFrom-Json
        $existingConnStr = $existingConfig.servers.'hangfire-mcp'.env.HANGFIRE_CONNECTION_STRING
        if ($existingConnStr) {
            Write-Host "  ✓ Found connection string in mcp.json" -ForegroundColor Green
            $ConnectionString = $existingConnStr
        }
    } catch {
        # Ignore parse errors
    }
}

if (-not $ConnectionString) {
    Write-Host ""
    Write-Host "  Enter your SQL Server connection string (ODBC format):" -ForegroundColor Yellow
    Write-Host "  Example: Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=Hangfire;UID=sa;PWD=pass;" -ForegroundColor Gray
    $ConnectionString = Read-Host "  Connection String"
}

# Create .vscode directory if needed
if (-not (Test-Path $mcpConfigDir)) {
    New-Item -ItemType Directory -Path $mcpConfigDir | Out-Null
}

# Create/update mcp.json
$mcpConfig = @{
    servers = @{
        "hangfire-mcp" = @{
            command = "python"
            args = @("-m", "hangfire_mcp", "--workspace", "`${workspaceFolder}")
            env = @{
                HANGFIRE_CONNECTION_STRING = $ConnectionString
            }
        }
    }
} | ConvertTo-Json -Depth 10

Set-Content -Path $mcpConfigPath -Value $mcpConfig
Write-Host "  ✓ Created .vscode/mcp.json" -ForegroundColor Green

# Step 5: Test connection
Write-Host ""
Write-Host "Step 5: Testing connection..." -ForegroundColor Cyan
$env:HANGFIRE_CONNECTION_STRING = $ConnectionString

$testScript = @"
import sys
sys.path.insert(0, 'src')
from hangfire_mcp.database import HangfireDatabase
import os
try:
    db = HangfireDatabase(os.environ['HANGFIRE_CONNECTION_STRING'])
    stats = db.get_stats()
    print(f"  ✓ Connected! Found {stats.get('succeeded', 0)} succeeded jobs")
except Exception as e:
    print(f"  ✗ Connection failed: {e}")
    sys.exit(1)
"@

$result = python -c $testScript
if ($LASTEXITCODE -ne 0) {
    Write-Host $result -ForegroundColor Red
    Write-Host ""
    Write-Host "  Check your connection string and try again." -ForegroundColor Yellow
    exit 1
}
Write-Host $result -ForegroundColor Green

# Done!
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. MCP Server (for VS Code Copilot):" -ForegroundColor White
Write-Host "     - Reload VS Code window" -ForegroundColor Gray
Write-Host "     - The hangfire-mcp server will auto-start" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Web Dashboard:" -ForegroundColor White
Write-Host "     .\scripts\run-dashboard.ps1" -ForegroundColor Yellow
Write-Host "     Then open http://127.0.0.1:8080" -ForegroundColor Gray
Write-Host ""

if (-not $SkipDashboard) {
    Write-Host ""
    $startDash = Read-Host "Start the dashboard now? (Y/n)"
    if ($startDash -ne "n" -and $startDash -ne "N") {
        Write-Host ""
        Write-Host "Starting dashboard at http://127.0.0.1:8080 ..." -ForegroundColor Cyan
        Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
        Write-Host ""
        python -m uvicorn hangfire_mcp.dashboard:app --host 127.0.0.1 --port 8080
    }
}
