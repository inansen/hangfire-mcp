# Hangfire MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/hangfire-mcp)](https://pypi.org/project/hangfire-mcp/)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for managing [Hangfire](https://www.hangfire.io/) background jobs directly from VS Code Copilot and other MCP-compatible clients. Monitor job queues, retry failed jobs, manage recurring tasks, and view real-time statistics — all without leaving your editor.

## Features

- **Job Management**: List, view, retry, delete, and requeue jobs
- **Recurring Jobs**: List, view, trigger, pause, and resume recurring jobs
- **Statistics**: View server stats, queues, and active servers
- **Auto-Discovery**: Automatically finds connection strings from appsettings.json
- **Web Dashboard**: Built-in web UI with real-time stats and job management

## Quick Start (One-Click Setup)

```bash
# Clone the repo
git clone https://github.com/inansen/hangfire-mcp.git
cd hangfire-mcp

# Run cross-platform setup (Windows, macOS, Linux)
python setup.py
```

The setup script will:
1. Create a virtual environment
2. Install all dependencies (including dashboard)
3. Prompt for your SQL Server connection string (or read from `.vscode/mcp.json`)
4. Create VS Code MCP configuration
5. Test the connection
6. Optionally start the dashboard

## Installation

```bash
pip install hangfire-mcp
```

Or with uvx:

```bash
uvx hangfire-mcp
```

## Configuration

### VS Code (Global Settings)

Add to your VS Code settings (`settings.json`):

```json
{
  "mcp": {
    "servers": {
      "hangfire-mcp": {
        "command": "uvx",
        "args": ["hangfire-mcp", "--workspace", "${workspaceFolder}"]
      }
    }
  }
}
```

### VS Code (Per-Project)

Create `.vscode/mcp.json` in your project:

```json
{
  "servers": {
    "hangfire-mcp": {
      "command": "uvx",
      "args": ["hangfire-mcp", "--workspace", "${workspaceFolder}"]
    }
  }
}
```

### With Explicit Connection String

Use ODBC-style connection strings:

```json
{
  "servers": {
    "hangfire-mcp": {
      "command": "python",
      "args": ["-m", "hangfire_mcp", "--workspace", "${workspaceFolder}"],
      "env": {
        "HANGFIRE_CONNECTION_STRING": "Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=Hangfire;UID=sa;PWD=yourpassword;Encrypt=no;"
      }
    }
  }
}
```

> **Note:** This project uses `pyodbc` and requires ODBC-format connection strings, not ADO.NET format.

## Connection String Discovery

The server finds connection strings in this priority order:

1. `--connection-string` CLI argument
2. `HANGFIRE_CONNECTION_STRING` environment variable
3. Auto-discover from `${workspaceFolder}/**/appsettings*.json`
4. User config at `~/.config/hangfire-mcp/connections.json` (Linux/macOS) or `%APPDATA%\hangfire-mcp\connections.json` (Windows)
5. Use the `configure` tool to set it manually

## Available Tools

### Job Tools

| Tool | Description |
|------|-------------|
| `list_jobs` | List jobs by state (Enqueued, Processing, Succeeded, Failed, etc.) |
| `get_job` | Get detailed job info including arguments and exception details |
| `get_job_history` | Get the state history of a job |
| `retry_job` | Retry a failed job |
| `delete_job` | Delete a job |
| `requeue_job` | Move a job back to queue |

### Recurring Job Tools

| Tool | Description |
|------|-------------|
| `list_recurring_jobs` | List all recurring jobs with cron schedules |
| `get_recurring_job` | Get recurring job details |
| `trigger_recurring_job` | Run a recurring job immediately |
| `pause_recurring_job` | Pause scheduled executions |
| `resume_recurring_job` | Resume a paused job |

### Statistics Tools

| Tool | Description |
|------|-------------|
| `get_stats` | Server statistics (succeeded, failed, processing counts) |
| `list_queues` | List queues with pending job counts |
| `list_servers` | List active Hangfire servers |

### Configuration Tool

| Tool | Description |
|------|-------------|
| `configure` | Set connection string for current workspace |

## Usage Examples

In VS Code Copilot Chat:

```
User: Show me failed jobs
Agent: [calls list_jobs(state="Failed")]
      Found 3 failed jobs:
      | ID | State | Job Type | Created | Reason |
      |----|-------|----------|---------|--------|
      | 123 | Failed | OrderSyncJob.Execute | 2026-03-17 10:30 | Connection timeout |
      | 124 | Failed | EmailJob.Send | 2026-03-17 10:45 | SMTP error |

User: Retry job 123
Agent: [calls retry_job(job_id=123)]
      Job 123 has been requeued to 'default' queue.

User: When did CacheRefreshJob last run?
Agent: [calls get_recurring_job(job_id="CacheRefreshJob")]
      Recurring Job: CacheRefreshJob
      - Cron: 0 */5 * * * (every 5 minutes)
      - Last Run: 2026-03-17 12:55:00
      - Queue: default

User: Trigger CacheRefreshJob now
Agent: [calls trigger_recurring_job(job_id="CacheRefreshJob")]
      CacheRefreshJob has been triggered. New job ID: 456
```

## Web Dashboard

The package includes a built-in web dashboard for visual job management.

### Installation

```bash
pip install hangfire-mcp[dashboard]
```

### Running the Dashboard

```bash
# Windows
.\scripts\run-dashboard.ps1

# macOS / Linux
chmod +x scripts/run-dashboard.sh
./scripts/run-dashboard.sh

# Or manually (any platform)
export HANGFIRE_CONNECTION_STRING="Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=Hangfire;..."
python -m uvicorn hangfire_mcp.dashboard:app --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080 in your browser.

### Dashboard Features

- **Real-time Stats**: Succeeded, Failed, Processing, Enqueued, Scheduled counts
- **Job List**: View all jobs with filtering by state
- **Job Actions**: Retry, Delete, View details with one click
- **Recurring Jobs**: Pause, Resume, Trigger recurring jobs
- **Server Status**: Online/Idle/Offline status based on heartbeat
- **Auto-refresh**: Updates every 10 seconds

## Requirements

- Python 3.11+
- SQL Server with Hangfire database
- ODBC Driver 17 for SQL Server (or compatible)

## Development

```bash
# Clone the repository
git clone https://github.com/inansen/hangfire-mcp.git
cd hangfire-mcp

# Install all dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -am 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

MIT
