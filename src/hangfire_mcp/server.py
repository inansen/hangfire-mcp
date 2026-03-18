"""MCP server for Hangfire job management."""

import argparse
import asyncio
import json
import logging
import sys
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging to stderr (stdout is used for MCP protocol)
logger = logging.getLogger("hangfire-mcp")

from hangfire_mcp.config import (
    get_connection_string,
    set_workspace_connection_string,
)
from hangfire_mcp.database import HangfireDatabase
from hangfire_mcp.models import JobState


# Global state
_db: Optional[HangfireDatabase] = None
_workspace: Optional[str] = None


def get_db() -> HangfireDatabase:
    """Get the database instance."""
    if _db is None:
        raise RuntimeError("Database not configured. Use the 'configure' tool to set a connection string.")
    return _db


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("hangfire-mcp")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available tools."""
        tools = [
            # Configuration
            Tool(
                name="configure",
                description="Configure the Hangfire database connection string for the current workspace",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "connection_string": {
                            "type": "string",
                            "description": "SQL Server connection string for the Hangfire database",
                        },
                    },
                    "required": ["connection_string"],
                },
            ),
            # Job tools
            Tool(
                name="list_jobs",
                description="List Hangfire jobs filtered by state and/or queue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "Filter by job state",
                            "enum": [s.value for s in JobState],
                        },
                        "queue": {
                            "type": "string",
                            "description": "Filter by queue name",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of jobs to return (default: 50)",
                            "default": 50,
                        },
                    },
                },
            ),
            Tool(
                name="get_job",
                description="Get detailed information about a specific Hangfire job including arguments and exception details",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "integer",
                            "description": "The job ID",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="get_job_history",
                description="Get the state history of a Hangfire job",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "integer",
                            "description": "The job ID",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="retry_job",
                description="Retry a failed Hangfire job by re-enqueueing it",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "integer",
                            "description": "The job ID to retry",
                        },
                        "queue": {
                            "type": "string",
                            "description": "Queue to enqueue the job to (default: 'default')",
                            "default": "default",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="delete_job",
                description="Delete a Hangfire job and its associated data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "integer",
                            "description": "The job ID to delete",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="requeue_job",
                description="Move a Hangfire job back to the queue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "integer",
                            "description": "The job ID to requeue",
                        },
                        "queue": {
                            "type": "string",
                            "description": "Queue to enqueue the job to (default: 'default')",
                            "default": "default",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            # Recurring job tools
            Tool(
                name="list_recurring_jobs",
                description="List all recurring Hangfire jobs with their cron schedules",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_recurring_job",
                description="Get detailed information about a specific recurring Hangfire job",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "The recurring job ID/name",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="trigger_recurring_job",
                description="Trigger a recurring Hangfire job to run immediately",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "The recurring job ID/name to trigger",
                        },
                        "queue": {
                            "type": "string",
                            "description": "Queue to enqueue the job to (default: uses job's configured queue or 'default')",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="pause_recurring_job",
                description="Pause a recurring Hangfire job to prevent scheduled executions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "The recurring job ID/name to pause",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="resume_recurring_job",
                description="Resume a paused recurring Hangfire job",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "The recurring job ID/name to resume",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            # Statistics tools
            Tool(
                name="get_stats",
                description="Get Hangfire server statistics including job counts by state",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="list_queues",
                description="List all Hangfire queues with their pending job counts",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="list_servers",
                description="List active Hangfire servers",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]
        return tools
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls."""
        global _db
        
        logger.info(f"Tool called: {name}")
        logger.debug(f"Arguments: {arguments}")
        
        try:
            result = await _handle_tool_call(name, arguments)
            logger.debug(f"Tool {name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {e}")]
    
    async def _handle_tool_call(name: str, arguments: dict) -> list[TextContent]:
        """Internal handler for tool calls."""
        global _db
        
        # Configuration tool
        if name == "configure":
            connection_string = arguments["connection_string"]
            _db = HangfireDatabase(connection_string)
            logger.info("Database connection configured")
            
            # Save to user config if workspace is set
            if _workspace:
                set_workspace_connection_string(_workspace, connection_string)
                logger.debug(f"Saved connection string for workspace: {_workspace}")
            
            return [TextContent(type="text", text="Connection string configured successfully.")]
        
        # All other tools require database connection
        try:
            db = get_db()
        except RuntimeError as e:
            return [TextContent(type="text", text=str(e))]
        
        # Job tools
        if name == "list_jobs":
            state = arguments.get("state")
            queue = arguments.get("queue")
            limit = arguments.get("limit", 50)
            
            jobs = db.list_jobs(state=state, queue=queue, limit=limit)
            
            if not jobs:
                return [TextContent(type="text", text="No jobs found matching the criteria.")]
            
            result = format_jobs_table(jobs)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_job":
            job_id = arguments["job_id"]
            job = db.get_job(job_id)
            
            if not job:
                return [TextContent(type="text", text=f"Job {job_id} not found.")]
            
            result = format_job_details(job)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_job_history":
            job_id = arguments["job_id"]
            history = db.get_job_history(job_id)
            
            if not history:
                return [TextContent(type="text", text=f"No history found for job {job_id}.")]
            
            result = format_job_history(history)
            return [TextContent(type="text", text=result)]
        
        elif name == "retry_job":
            job_id = arguments["job_id"]
            queue = arguments.get("queue", "default")
            
            success = db.retry_job(job_id, queue)
            
            if success:
                return [TextContent(type="text", text=f"Job {job_id} has been requeued to '{queue}' queue.")]
            else:
                return [TextContent(type="text", text=f"Failed to retry job {job_id}.")]
        
        elif name == "delete_job":
            job_id = arguments["job_id"]
            
            success = db.delete_job(job_id)
            
            if success:
                return [TextContent(type="text", text=f"Job {job_id} has been deleted.")]
            else:
                return [TextContent(type="text", text=f"Failed to delete job {job_id}. Job may not exist.")]
        
        elif name == "requeue_job":
            job_id = arguments["job_id"]
            queue = arguments.get("queue", "default")
            
            success = db.requeue_job(job_id, queue)
            
            if success:
                return [TextContent(type="text", text=f"Job {job_id} has been moved to '{queue}' queue.")]
            else:
                return [TextContent(type="text", text=f"Failed to requeue job {job_id}.")]
        
        # Recurring job tools
        elif name == "list_recurring_jobs":
            jobs = db.list_recurring_jobs()
            
            if not jobs:
                return [TextContent(type="text", text="No recurring jobs found.")]
            
            result = format_recurring_jobs_table(jobs)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_recurring_job":
            job_id = arguments["job_id"]
            job = db.get_recurring_job(job_id)
            
            if not job:
                return [TextContent(type="text", text=f"Recurring job '{job_id}' not found.")]
            
            result = format_recurring_job_details(job)
            return [TextContent(type="text", text=result)]
        
        elif name == "trigger_recurring_job":
            job_id = arguments["job_id"]
            
            job = db.get_recurring_job(job_id)
            if not job:
                return [TextContent(type="text", text=f"Recurring job '{job_id}' not found.")]
            
            queue = arguments.get("queue") or job.get("Queue") or "default"
            
            new_job_id = db.trigger_recurring_job(job_id, queue)
            
            if new_job_id:
                return [TextContent(type="text", text=f"Recurring job '{job_id}' has been triggered. New job ID: {new_job_id}")]
            else:
                return [TextContent(type="text", text=f"Failed to trigger recurring job '{job_id}'.")]
        
        elif name == "pause_recurring_job":
            job_id = arguments["job_id"]
            
            job = db.get_recurring_job(job_id)
            if not job:
                return [TextContent(type="text", text=f"Recurring job '{job_id}' not found.")]
            
            success = db.pause_recurring_job(job_id)
            
            if success:
                return [TextContent(type="text", text=f"Recurring job '{job_id}' has been paused.")]
            else:
                return [TextContent(type="text", text=f"Failed to pause recurring job '{job_id}'.")]
        
        elif name == "resume_recurring_job":
            job_id = arguments["job_id"]
            
            success = db.resume_recurring_job(job_id)
            
            if success:
                return [TextContent(type="text", text=f"Recurring job '{job_id}' has been resumed.")]
            else:
                return [TextContent(type="text", text=f"Failed to resume recurring job '{job_id}'. Job may not exist.")]
        
        # Statistics tools
        elif name == "get_stats":
            stats = db.get_stats()
            result = format_stats(stats)
            return [TextContent(type="text", text=result)]
        
        elif name == "list_queues":
            queues = db.list_queues()
            
            if not queues:
                return [TextContent(type="text", text="No queues with pending jobs found.")]
            
            result = format_queues_table(queues)
            return [TextContent(type="text", text=result)]
        
        elif name == "list_servers":
            servers = db.list_servers()
            
            if not servers:
                return [TextContent(type="text", text="No active Hangfire servers found.")]
            
            result = format_servers_table(servers)
            return [TextContent(type="text", text=result)]
        
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    return server


# Formatting functions
def format_jobs_table(jobs: list[dict]) -> str:
    """Format jobs as a markdown table."""
    # Prepare data first to calculate column widths
    rows = []
    for job in jobs:
        job_id = str(job.get("Id", ""))
        state = job.get("StateName", "") or ""
        created = str(job.get("CreatedAt", ""))[:19]  # Trim to datetime without microseconds
        reason = (job.get("Reason", "") or "")[:40]
        
        job_type = "Unknown"
        if inv_data := job.get("InvocationData"):
            try:
                data = json.loads(inv_data)
                type_info = data.get("Type") or data.get("t") or data.get("TypeName") or ""
                method = data.get("Method") or data.get("m") or data.get("MethodName") or ""
                if type_info:
                    class_name = type_info.split(",")[0].split(".")[-1]
                    job_type = f"{class_name}.{method}" if method else class_name
                elif method:
                    job_type = method
            except json.JSONDecodeError:
                pass
        
        rows.append((job_id, state, job_type[:30], created, reason))
    
    # Calculate column widths
    headers = ("ID", "State", "Job Type", "Created", "Reason")
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))
    
    # Build table
    def format_row(values):
        return "| " + " | ".join(v.ljust(widths[i]) for i, v in enumerate(values)) + " |"
    
    lines = [
        format_row(headers),
        "|" + "|".join("-" * (w + 2) for w in widths) + "|",
    ]
    lines.extend(format_row(row) for row in rows)
    
    return "\n".join(lines)


def format_job_details(job: dict) -> str:
    """Format job details as markdown."""
    lines = [f"# Job {job.get('Id')}"]
    lines.append(f"**State:** {job.get('StateName', 'Unknown')}")
    lines.append(f"**Created:** {job.get('CreatedAt', 'Unknown')}")
    
    if expire := job.get("ExpireAt"):
        lines.append(f"**Expires:** {expire}")
    
    if reason := job.get("Reason"):
        lines.append(f"**Reason:** {reason}")
    
    inv_data = job.get("InvocationData")
    lines.append("\n## Invocation")
    if inv_data:
        lines.append(f"**Raw InvocationData:** `{inv_data[:500] if len(str(inv_data)) > 500 else inv_data}`")
        try:
            data = json.loads(inv_data)
            # Hangfire can store type info in different keys
            type_info = data.get("Type") or data.get("t") or data.get("TypeName") or ""
            method = data.get("Method") or data.get("m") or data.get("MethodName") or ""
            
            if type_info:
                lines.append(f"**Type:** `{type_info}`")
            if method:
                lines.append(f"**Method:** `{method}`")
            
            if not type_info and not method:
                # Show all keys if we can't find expected ones
                lines.append(f"**Keys found:** {list(data.keys())}")
        except json.JSONDecodeError as e:
            lines.append(f"**Parse error:** {e}")
    else:
        lines.append("**Note:** InvocationData is empty or null")
    
    if args := job.get("Arguments"):
        try:
            parsed_args = json.loads(args)
            lines.append("\n## Arguments")
            lines.append("```json")
            lines.append(json.dumps(parsed_args, indent=2))
            lines.append("```")
        except json.JSONDecodeError:
            lines.append(f"\n## Arguments (raw)\n```\n{args}\n```")
    
    if state_data := job.get("StateData"):
        try:
            data = json.loads(state_data)
            if "ExceptionType" in data or "ExceptionMessage" in data:
                lines.append("\n## Exception")
                lines.append(f"**Type:** `{data.get('ExceptionType', 'Unknown')}`")
                lines.append(f"**Message:** {data.get('ExceptionMessage', 'No message')}")
                if details := data.get("ExceptionDetails"):
                    lines.append(f"\n**Stack Trace:**\n```\n{details}\n```")
            else:
                lines.append("\n## State Data")
                lines.append("```json")
                lines.append(json.dumps(data, indent=2))
                lines.append("```")
        except json.JSONDecodeError:
            pass
    
    return "\n".join(lines)


def format_job_history(history: list[dict]) -> str:
    """Format job history as markdown."""
    lines = ["# Job History", ""]
    
    for entry in history:
        state = entry.get("Name", "Unknown")
        created = entry.get("CreatedAt", "Unknown")
        reason = entry.get("Reason", "")
        
        lines.append(f"### {state}")
        lines.append(f"**Time:** {created}")
        if reason:
            lines.append(f"**Reason:** {reason}")
        
        if data := entry.get("Data"):
            try:
                parsed = json.loads(data)
                lines.append("```json")
                lines.append(json.dumps(parsed, indent=2))
                lines.append("```")
            except json.JSONDecodeError:
                pass
        
        lines.append("")
    
    return "\n".join(lines)


def format_recurring_jobs_table(jobs: list[dict]) -> str:
    """Format recurring jobs as a markdown table."""
    rows = []
    for job in jobs:
        job_id = job.get("JobId", "")
        cron = job.get("Cron", "")
        queue = job.get("Queue", "default") or "default"
        last_exec = str(job.get("LastExecution", "Never") or "Never")[:19]
        next_exec = str(job.get("NextExecution", "N/A") or "N/A")[:19]
        paused = job.get("Paused", "false")
        status = "Paused" if paused == "true" else "Active"
        rows.append((job_id, cron, queue, last_exec, next_exec, status))
    
    headers = ("Job ID", "Cron", "Queue", "Last Run", "Next Run", "Status")
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    
    def format_row(values):
        return "| " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(values)) + " |"
    
    lines = [
        format_row(headers),
        "|" + "|".join("-" * (w + 2) for w in widths) + "|",
    ]
    lines.extend(format_row(row) for row in rows)
    
    return "\n".join(lines)


def format_recurring_job_details(job: dict) -> str:
    """Format recurring job details as markdown."""
    lines = [f"# Recurring Job: {job.get('JobId')}"]
    
    cron = job.get("Cron", "Not set")
    lines.append(f"**Cron Schedule:** `{cron}`")
    lines.append(f"**Queue:** {job.get('Queue', 'default')}")
    
    paused = job.get("Paused", "false")
    status = "Paused" if paused == "true" else "Active"
    lines.append(f"**Status:** {status}")
    
    if last_exec := job.get("LastExecution"):
        lines.append(f"**Last Execution:** {last_exec}")
    
    if next_exec := job.get("NextExecution"):
        lines.append(f"**Next Execution:** {next_exec}")
    
    if last_job_id := job.get("LastJobId"):
        lines.append(f"**Last Job ID:** {last_job_id}")
    
    if job_def := job.get("Job"):
        try:
            data = json.loads(job_def)
            lines.append("\n## Job Definition")
            lines.append(f"**Type:** `{data.get('Type', 'Unknown')}`")
            lines.append(f"**Method:** `{data.get('Method', 'Unknown')}`")
        except json.JSONDecodeError:
            pass
    
    return "\n".join(lines)


def format_stats(stats: dict) -> str:
    """Format statistics as markdown."""
    lines = ["# Hangfire Statistics", ""]
    lines.append("## Job Counts")
    lines.append(f"- **Succeeded:** {stats.get('succeeded', 0):,}")
    lines.append(f"- **Failed:** {stats.get('failed', 0):,}")
    lines.append(f"- **Processing:** {stats.get('processing', 0):,}")
    lines.append(f"- **Scheduled:** {stats.get('scheduled', 0):,}")
    lines.append(f"- **Enqueued:** {stats.get('enqueued', 0):,}")
    lines.append(f"- **Deleted:** {stats.get('deleted', 0):,}")
    
    return "\n".join(lines)


def format_queues_table(queues: list[dict]) -> str:
    """Format queues as a markdown table."""
    rows = []
    total = 0
    for queue in queues:
        name = queue.get("Queue", "unknown")
        count = queue.get("JobCount", 0)
        total += count
        rows.append((name, f"{count:,}"))
    rows.append(("**Total**", f"**{total:,}**"))
    
    headers = ("Queue", "Pending Jobs")
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    
    def format_row(values):
        return "| " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(values)) + " |"
    
    lines = [
        "# Queues",
        "",
        format_row(headers),
        "|" + "|".join("-" * (w + 2) for w in widths) + "|",
    ]
    lines.extend(format_row(row) for row in rows)
    
    return "\n".join(lines)


def format_servers_table(servers: list[dict]) -> str:
    """Format servers as a markdown table."""
    rows = []
    for server in servers:
        server_id = server.get("Id", "unknown")
        if len(server_id) > 40:
            server_id = server_id[:37] + "..."
        workers = str(server.get("WorkersCount", "N/A"))
        queues = ", ".join(server.get("Queues", [])) if server.get("Queues") else "N/A"
        heartbeat = str(server.get("LastHeartbeat", "Unknown"))[:19]
        rows.append((server_id, workers, queues, heartbeat))
    
    headers = ("Server ID", "Workers", "Queues", "Last Heartbeat")
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    
    def format_row(values):
        return "| " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(values)) + " |"
    
    lines = [
        "# Active Servers",
        "",
        format_row(headers),
        "|" + "|".join("-" * (w + 2) for w in widths) + "|",
    ]
    lines.extend(format_row(row) for row in rows)
    
    return "\n".join(lines)


async def run_server(workspace: Optional[str] = None, connection_string: Optional[str] = None):
    """Run the MCP server."""
    global _db, _workspace
    
    _workspace = workspace
    logger.info(f"Starting Hangfire MCP server")
    if workspace:
        logger.info(f"Workspace: {workspace}")
    
    # Try to get connection string
    conn_str = get_connection_string(connection_string, workspace)
    if conn_str:
        _db = HangfireDatabase(conn_str)
        logger.info("Database connection established from config")
    else:
        logger.warning("No connection string found - use 'configure' tool to set one")
    
    server = create_server()
    logger.info("MCP server ready")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Log to stderr since stdout is used for MCP protocol
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    ))
    
    logger.setLevel(level)
    logger.addHandler(handler)
    
    # Also configure database logger
    db_logger = logging.getLogger("hangfire-mcp.database")
    db_logger.setLevel(level)
    db_logger.addHandler(handler)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Hangfire MCP Server")
    parser.add_argument(
        "--workspace",
        type=str,
        help="Workspace folder path for auto-discovering connection string",
    )
    parser.add_argument(
        "--connection-string",
        type=str,
        help="SQL Server connection string for Hangfire database",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    
    asyncio.run(run_server(workspace=args.workspace, connection_string=args.connection_string))


if __name__ == "__main__":
    main()
