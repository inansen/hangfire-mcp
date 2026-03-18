"""Statistics tools for Hangfire MCP server."""

from mcp.server import Server
from mcp.types import Tool, TextContent

from hangfire_mcp.database import HangfireDatabase


def register_stats_tools(server: Server, get_db: callable) -> None:
    """Register statistics-related MCP tools."""
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available statistics tools."""
        return [
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
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle statistics tool calls."""
        db = get_db()
        
        if name == "get_stats":
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


def format_stats(stats: dict) -> str:
    """Format statistics as markdown."""
    lines = ["# Hangfire Statistics", ""]
    
    # Job counts by state
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
    lines = ["# Queues", "", "| Queue | Pending Jobs |", "|-------|--------------|"]
    
    total = 0
    for queue in queues:
        name = queue.get("Queue", "unknown")
        count = queue.get("JobCount", 0)
        total += count
        lines.append(f"| {name} | {count:,} |")
    
    lines.append(f"| **Total** | **{total:,}** |")
    
    return "\n".join(lines)


def format_servers_table(servers: list[dict]) -> str:
    """Format servers as a markdown table."""
    lines = ["# Active Servers", "", "| Server ID | Workers | Queues | Last Heartbeat |", "|-----------|---------|--------|----------------|"]
    
    for server in servers:
        server_id = server.get("Id", "unknown")
        workers = server.get("WorkersCount", "N/A")
        queues = ", ".join(server.get("Queues", [])) if server.get("Queues") else "N/A"
        heartbeat = server.get("LastHeartbeat", "Unknown")
        
        # Truncate server ID if too long
        if len(server_id) > 40:
            server_id = server_id[:37] + "..."
        
        lines.append(f"| {server_id} | {workers} | {queues} | {heartbeat} |")
    
    return "\n".join(lines)
