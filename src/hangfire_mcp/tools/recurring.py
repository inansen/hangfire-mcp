"""Recurring job management tools for Hangfire MCP server."""

import json
from typing import Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from hangfire_mcp.database import HangfireDatabase


def register_recurring_tools(server: Server, get_db: callable) -> None:
    """Register recurring job-related MCP tools."""
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available recurring job tools."""
        return [
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
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle recurring job tool calls."""
        db = get_db()
        
        if name == "list_recurring_jobs":
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
            
            # Get job's configured queue or use provided/default
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
            
            # Verify job exists
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
        
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


def format_recurring_jobs_table(jobs: list[dict]) -> str:
    """Format recurring jobs as a markdown table."""
    lines = ["| Job ID | Cron | Queue | Last Run | Next Run | Status |", "|--------|------|-------|----------|----------|--------|"]
    
    for job in jobs:
        job_id = job.get("JobId", "")
        cron = job.get("Cron", "")
        queue = job.get("Queue", "default")
        last_exec = job.get("LastExecution", "Never")
        next_exec = job.get("NextExecution", "N/A")
        paused = job.get("Paused", "false")
        status = "⏸️ Paused" if paused == "true" else "✅ Active"
        
        lines.append(f"| {job_id} | `{cron}` | {queue} | {last_exec} | {next_exec} | {status} |")
    
    return "\n".join(lines)


def format_recurring_job_details(job: dict) -> str:
    """Format recurring job details as markdown."""
    lines = [f"# Recurring Job: {job.get('JobId')}"]
    
    cron = job.get("Cron", "Not set")
    lines.append(f"**Cron Schedule:** `{cron}`")
    lines.append(f"**Queue:** {job.get('Queue', 'default')}")
    
    paused = job.get("Paused", "false")
    status = "⏸️ Paused" if paused == "true" else "✅ Active"
    lines.append(f"**Status:** {status}")
    
    if last_exec := job.get("LastExecution"):
        lines.append(f"**Last Execution:** {last_exec}")
    
    if next_exec := job.get("NextExecution"):
        lines.append(f"**Next Execution:** {next_exec}")
    
    if last_job_id := job.get("LastJobId"):
        lines.append(f"**Last Job ID:** {last_job_id}")
    
    # Parse job definition
    if job_def := job.get("Job"):
        try:
            data = json.loads(job_def)
            lines.append("\n## Job Definition")
            lines.append(f"**Type:** `{data.get('Type', 'Unknown')}`")
            lines.append(f"**Method:** `{data.get('Method', 'Unknown')}`")
            
            if args := data.get("Arguments"):
                lines.append("\n**Arguments:**")
                lines.append("```json")
                lines.append(json.dumps(args, indent=2) if isinstance(args, (dict, list)) else str(args))
                lines.append("```")
        except json.JSONDecodeError:
            lines.append(f"\n## Job Definition (raw)\n```\n{job_def}\n```")
    
    # Add cron explanation
    lines.append("\n## Cron Schedule Explanation")
    lines.append(explain_cron(cron))
    
    return "\n".join(lines)


def explain_cron(cron: str) -> str:
    """Provide a human-readable explanation of a cron expression."""
    if not cron:
        return "No cron expression"
    
    parts = cron.split()
    if len(parts) < 5:
        return f"Invalid cron expression: `{cron}`"
    
    # Common patterns
    common_patterns = {
        "* * * * *": "Every minute",
        "*/5 * * * *": "Every 5 minutes",
        "*/10 * * * *": "Every 10 minutes",
        "*/15 * * * *": "Every 15 minutes",
        "*/30 * * * *": "Every 30 minutes",
        "0 * * * *": "Every hour",
        "0 */2 * * *": "Every 2 hours",
        "0 */4 * * *": "Every 4 hours",
        "0 */6 * * *": "Every 6 hours",
        "0 */12 * * *": "Every 12 hours",
        "0 0 * * *": "Every day at midnight",
        "0 0 * * 0": "Every Sunday at midnight",
        "0 0 * * 1": "Every Monday at midnight",
        "0 0 1 * *": "First day of every month at midnight",
    }
    
    # Check 5-part vs 6-part cron (with seconds)
    base_cron = " ".join(parts[:5]) if len(parts) >= 5 else cron
    
    if base_cron in common_patterns:
        return common_patterns[base_cron]
    
    return f"Custom schedule: `{cron}`"
