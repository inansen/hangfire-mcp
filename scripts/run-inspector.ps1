# Read config from .vscode/mcp.json
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$mcpConfigPath = Join-Path $projectDir ".vscode\mcp.json"

if (-not (Test-Path $mcpConfigPath)) {
    Write-Error "mcp.json not found at $mcpConfigPath"
    exit 1
}

$config = Get-Content $mcpConfigPath | ConvertFrom-Json
$serverConfig = $config.servers."hangfire-mcp"

# Set environment variables from mcp.json
$env:DANGEROUSLY_OMIT_AUTH = "true"
foreach ($key in $serverConfig.env.PSObject.Properties.Name) {
    Set-Item -Path "env:$key" -Value $serverConfig.env.$key
}

# Build args from config
$command = $serverConfig.command
$args = $serverConfig.args -replace '\$\{workspaceFolder\}', $projectDir

Write-Host "Starting MCP Inspector..."
Write-Host "Dashboard: http://localhost:6274"
Write-Host "Config: $mcpConfigPath"
Write-Host ""

npx @modelcontextprotocol/inspector $command $args
