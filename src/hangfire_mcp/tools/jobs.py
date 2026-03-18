"""Job management tools for Hangfire MCP server."""

import json
from typing import Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from hangfire_mcp.database import HangfireDatabase
from hangfire_mcp.models import JobState


def register_job_tools(server: Server, get_db: callable) -> None:
    """Register job-related MCP tools."""
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available job tools."""
        return [
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
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle job tool calls."""
        db = get_db()
        
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
        
        elif name == "get_job_history":
            job_id = arguments["job_id"]
            history = db.get_job_history(job_id)
            
            if not history:
                return [TextContent(type="text", text=f"No history found for job {job_id}.")]
            
            result = format_job_history(history)
            return [TextContent(type="text", text=result)]
        
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


def format_jobs_table(jobs: list[dict]) -> str:
    """Format jobs as a markdown table."""
    lines = ["| ID | State | Job Type | Created | Reason |", "|-----|-------|----------|---------|--------|"]
    
    for job in jobs:
        job_id = job.get("Id", "")
        state = job.get("StateName", "")
        created = job.get("CreatedAt", "")
        reason = job.get("Reason", "") or ""
        
        # Parse invocation data to get job type
        job_type = "Unknown"
        if inv_data := job.get("InvocationData"):
            try:
                data = json.loads(inv_data)
                type_info = data.get("Type", "")
                method = data.get("Method", "")
                if type_info:
                    # Extract class name from full type
                    class_name = type_info.split(",")[0].split(".")[-1]
                    job_type = f"{class_name}.{method}" if method else class_name
            except json.JSONDecodeError:
                pass
        
        # Truncate reason if too long
        if len(reason) > 50:
            reason = reason[:47] + "..."
        
        lines.append(f"| {job_id} | {state} | {job_type} | {created} | {reason} |")
    
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
    
    # Parse and format invocation data
    if inv_data := job.get("InvocationData"):
        try:
            data = json.loads(inv_data)
            lines.append("\n## Invocation")
            lines.append(f"**Type:** `{data.get('Type', 'Unknown')}`")
            lines.append(f"**Method:** `{data.get('Method', 'Unknown')}`")
        except json.JSONDecodeError:
            lines.append(f"\n## Invocation Data (raw)\n```\n{inv_data}\n```")
    
    # Parse and format arguments
    if args := job.get("Arguments"):
        try:
            parsed_args = json.loads(args)
            lines.append("\n## Arguments")
            lines.append("```json")
            lines.append(json.dumps(parsed_args, indent=2))
            lines.append("```")
        except json.JSONDecodeError:
            lines.append(f"\n## Arguments (raw)\n```\n{args}\n```")
    
    # Parse and format state data (exception for failed jobs)
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
