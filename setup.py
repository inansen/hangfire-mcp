#!/usr/bin/env python3
"""Hangfire MCP - Cross-platform setup script."""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def print_colored(text, color="white"):
    colors = {"red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m", "cyan": "\033[96m", "gray": "\033[90m", "white": "\033[0m"}
    print(f"{colors.get(color, '')}{text}\033[0m")


def run(cmd, **kwargs):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)


def main():
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)
    is_windows = platform.system() == "Windows"

    print()
    print_colored("🔥 Hangfire MCP Setup", "red")
    print_colored("=" * 30, "red")
    print()

    # Step 1: Check Python
    print_colored("Step 1: Checking Python...", "cyan")
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info < (3, 11):
        print_colored(f"  ✗ Python {py_version} found, but 3.11+ is required", "red")
        sys.exit(1)
    print_colored(f"  ✓ Python {py_version}", "green")

    # Step 2: Create virtual environment
    venv_path = project_root / ".venv"
    print()
    print_colored("Step 2: Setting up virtual environment...", "cyan")
    if not venv_path.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        print_colored("  ✓ Created .venv", "green")
    else:
        print_colored("  ✓ Using existing .venv", "green")

    # Determine venv python path
    if is_windows:
        venv_python = str(venv_path / "Scripts" / "python.exe")
    else:
        venv_python = str(venv_path / "bin" / "python")

    # Step 3: Install dependencies
    print()
    print_colored("Step 3: Installing dependencies...", "cyan")
    result = subprocess.run([venv_python, "-m", "pip", "install", "-q", "-e", ".[dashboard]"], capture_output=True, text=True)
    if result.returncode != 0:
        print_colored(f"  ✗ Install failed: {result.stderr}", "red")
        sys.exit(1)
    print_colored("  ✓ Installed hangfire-mcp with dashboard", "green")

    # Step 4: Configure connection string
    print()
    print_colored("Step 4: Configuring connection...", "cyan")

    mcp_config_dir = project_root / ".vscode"
    mcp_config_path = mcp_config_dir / "mcp.json"
    connection_string = None

    # Try to get from mcp.json
    if mcp_config_path.exists():
        try:
            config = json.loads(mcp_config_path.read_text())
            connection_string = config.get("servers", {}).get("hangfire-mcp", {}).get("env", {}).get("HANGFIRE_CONNECTION_STRING")
            if connection_string and "YOUR_" not in connection_string:
                print_colored("  ✓ Found connection string in mcp.json", "green")
        except (json.JSONDecodeError, KeyError):
            pass

    # Try env var
    if not connection_string:
        connection_string = os.environ.get("HANGFIRE_CONNECTION_STRING")
        if connection_string:
            print_colored("  ✓ Found HANGFIRE_CONNECTION_STRING env var", "green")

    # Prompt user
    if not connection_string:
        print()
        print_colored("  Enter your SQL Server connection string (ODBC format):", "yellow")
        print_colored("  Example: Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=Hangfire;UID=sa;PWD=pass;", "gray")
        connection_string = input("  Connection String: ").strip()

    if not connection_string:
        print_colored("  ✗ No connection string provided", "red")
        sys.exit(1)

    # Create .vscode/mcp.json
    mcp_config_dir.mkdir(exist_ok=True)
    mcp_config = {
        "servers": {
            "hangfire-mcp": {
                "command": "python",
                "args": ["-m", "hangfire_mcp", "--workspace", "${workspaceFolder}", "--verbose"],
                "env": {
                    "HANGFIRE_CONNECTION_STRING": connection_string
                }
            }
        }
    }
    mcp_config_path.write_text(json.dumps(mcp_config, indent=2))
    print_colored("  ✓ Created .vscode/mcp.json", "green")

    # Step 5: Test connection
    print()
    print_colored("Step 5: Testing connection...", "cyan")
    test_code = f"""
import sys, os
sys.path.insert(0, 'src')
os.environ['HANGFIRE_CONNECTION_STRING'] = '''{connection_string}'''
from hangfire_mcp.database import HangfireDatabase
try:
    db = HangfireDatabase(os.environ['HANGFIRE_CONNECTION_STRING'])
    stats = db.get_stats()
    print(f"  ✓ Connected! Found {{stats.get('succeeded', 0)}} succeeded jobs")
except Exception as e:
    print(f"  ✗ Connection failed: {{e}}")
    sys.exit(1)
"""
    result = subprocess.run([venv_python, "-c", test_code], capture_output=True, text=True)
    if result.returncode != 0:
        print_colored(result.stdout.strip() or result.stderr.strip(), "red")
        print_colored("  Check your connection string and try again.", "yellow")
        sys.exit(1)
    print_colored(result.stdout.strip(), "green")

    # Done
    print()
    print_colored("=" * 40, "green")
    print_colored("  Setup Complete!", "green")
    print_colored("=" * 40, "green")
    print()
    print_colored("Next steps:", "cyan")
    print()
    print_colored("  1. MCP Server (for VS Code Copilot):", "white")
    print_colored("     Reload VS Code window - the server auto-starts", "gray")
    print()
    print_colored("  2. Web Dashboard:", "white")
    if is_windows:
        print_colored("     .\\scripts\\run-dashboard.ps1", "yellow")
    else:
        print_colored("     ./scripts/run-dashboard.sh", "yellow")
    print_colored("     Then open http://127.0.0.1:8080", "gray")
    print()

    # Offer to start dashboard
    try:
        answer = input("Start the dashboard now? (Y/n): ").strip().lower()
        if answer not in ("n", "no"):
            print()
            print_colored("Starting dashboard at http://127.0.0.1:8080 ...", "cyan")
            print_colored("Press Ctrl+C to stop", "gray")
            print()
            env = os.environ.copy()
            env["HANGFIRE_CONNECTION_STRING"] = connection_string
            subprocess.run([venv_python, "-m", "uvicorn", "hangfire_mcp.dashboard:app", "--host", "127.0.0.1", "--port", "8080"], env=env)
    except KeyboardInterrupt:
        print()
        print_colored("Dashboard stopped.", "gray")


if __name__ == "__main__":
    main()
