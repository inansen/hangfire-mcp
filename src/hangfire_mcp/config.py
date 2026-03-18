"""Configuration management for Hangfire MCP server."""

import json
import os
from pathlib import Path
from typing import Optional


def get_config_path() -> Path:
    """Get the user config directory path."""
    if os.name == "nt":
        config_dir = Path(os.environ.get("APPDATA", "~")) / "hangfire-mcp"
    else:
        config_dir = Path.home() / ".config" / "hangfire-mcp"
    return config_dir


def load_user_config() -> dict:
    """Load user configuration from config file."""
    config_path = get_config_path() / "connections.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"workspaces": {}}


def save_user_config(config: dict) -> None:
    """Save user configuration to config file."""
    config_dir = get_config_path()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "connections.json"
    config_path.write_text(json.dumps(config, indent=2))


def find_connection_string_in_appsettings(workspace: str) -> Optional[str]:
    """Search for Hangfire connection string in project config files."""
    patterns = [
        "appsettings.json",
        "appsettings.Development.json",
        "**/appsettings.json",
        "**/appsettings.Development.json",
    ]
    
    connection_keys = [
        "HangfireConnection",
        "Hangfire",
        "DefaultConnection",
    ]
    
    workspace_path = Path(workspace)
    if not workspace_path.exists():
        return None
    
    for pattern in patterns:
        for config_file in workspace_path.glob(pattern):
            try:
                config = json.loads(config_file.read_text())
                conn_strings = config.get("ConnectionStrings", {})
                for key in connection_keys:
                    if conn := conn_strings.get(key):
                        return conn
            except (json.JSONDecodeError, OSError):
                continue
    
    return None


def get_connection_string(
    cli_connection_string: Optional[str] = None,
    workspace: Optional[str] = None,
) -> Optional[str]:
    """
    Get connection string using priority order:
    1. CLI argument
    2. HANGFIRE_CONNECTION_STRING environment variable
    3. Auto-discover from workspace appsettings*.json
    4. User config at ~/.config/hangfire-mcp/connections.json
    """
    # 1. CLI argument
    if cli_connection_string:
        return cli_connection_string
    
    # 2. Environment variable
    if env_conn := os.environ.get("HANGFIRE_CONNECTION_STRING"):
        return env_conn
    
    # 3. Auto-discover from workspace
    if workspace:
        if conn := find_connection_string_in_appsettings(workspace):
            return conn
        
        # 4. User config for this workspace
        config = load_user_config()
        workspaces = config.get("workspaces", {})
        # Normalize path for comparison
        normalized_workspace = str(Path(workspace).resolve())
        for ws_path, conn_string in workspaces.items():
            if str(Path(ws_path).resolve()) == normalized_workspace:
                return conn_string
    
    return None


def set_workspace_connection_string(workspace: str, connection_string: str) -> None:
    """Save connection string for a workspace to user config."""
    config = load_user_config()
    if "workspaces" not in config:
        config["workspaces"] = {}
    
    normalized_workspace = str(Path(workspace).resolve())
    config["workspaces"][normalized_workspace] = connection_string
    save_user_config(config)
