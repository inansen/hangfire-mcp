# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-18

### Added
- MCP server with 15 tools for Hangfire job management
- Job tools: list, view, retry, delete, requeue jobs
- Recurring job tools: list, view, trigger, pause, resume
- Statistics tools: server stats, queue listing, active servers
- Connection string auto-discovery from `appsettings.json`
- FastAPI web dashboard with real-time stats and auto-refresh
- Dashboard: job list with filtering, one-click retry/delete
- Dashboard: recurring jobs with pause/resume/trigger actions
- Dashboard: server status (Online/Idle/Offline) based on heartbeat
- Cross-platform setup script (`setup.py`)
- VS Code MCP integration via `.vscode/mcp.json`
- GitHub Actions CI workflow (Python 3.11/3.12/3.13)
