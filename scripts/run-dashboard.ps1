# Run the Hangfire Dashboard
# Reads configuration from .vscode/mcp.json

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$configPath = Join-Path $projectRoot ".vscode/mcp.json"

Write-Host "🔥 Hangfire Dashboard" -ForegroundColor Red
Write-Host ""

# Get connection string from mcp.json
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    
    # Try to get the hangfire-mcp server config
    $serverConfig = $config.servers.'hangfire-mcp'
    
    if ($serverConfig -and $serverConfig.env) {
        $env:HANGFIRE_CONNECTION_STRING = $serverConfig.env.HANGFIRE_CONNECTION_STRING
        Write-Host "✓ Loaded connection string from mcp.json" -ForegroundColor Green
    }
}

if (-not $env:HANGFIRE_CONNECTION_STRING) {
    Write-Host "⚠ HANGFIRE_CONNECTION_STRING not found" -ForegroundColor Yellow
    Write-Host "Set it in .vscode/mcp.json or as an environment variable" -ForegroundColor Yellow
    exit 1
}

# Get parameters
$host = if ($args[0]) { $args[0] } else { "127.0.0.1" }
$port = if ($args[1]) { [int]$args[1] } else { 8080 }

Write-Host ""
Write-Host "Starting dashboard at http://${host}:${port}" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Run dashboard
Set-Location $projectRoot
python -m uvicorn hangfire_mcp.dashboard:app --host $host --port $port
