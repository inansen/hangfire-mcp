"""Simple web dashboard for Hangfire MCP server."""

import html
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from hangfire_mcp.config import get_connection_string
from hangfire_mcp.database import HangfireDatabase

logger = logging.getLogger("hangfire-mcp.dashboard")

app = FastAPI(title="Hangfire MCP Dash")

# Global database instance
_db: Optional[HangfireDatabase] = None


def get_db() -> HangfireDatabase:
    global _db
    if _db is None:
        conn_str = get_connection_string()
        if not conn_str:
            raise HTTPException(500, "Database not configured")
        _db = HangfireDatabase(conn_str)
    return _db


def esc(value) -> str:
    """HTML-escape a value for safe rendering."""
    return html.escape(str(value)) if value is not None else ""


# HTML Template
def render_page(title: str, content: str, active: str = "", auto_refresh: int = 10) -> str:
    refresh_meta = f'<meta http-equiv="refresh" content="{auto_refresh}">' if auto_refresh > 0 else ''
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {refresh_meta}
    <title>{title} - Hangfire MCP Dash</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; }}
        .header {{ background: #16213e; padding: 1rem 2rem; display: flex; align-items: center; gap: 2rem; border-bottom: 1px solid #0f3460; }}
        .header h1 {{ font-size: 1.5rem; color: #e94560; }}
        .nav {{ display: flex; gap: 1rem; }}
        .nav a {{ color: #aaa; text-decoration: none; padding: 0.5rem 1rem; border-radius: 4px; transition: all 0.2s; }}
        .nav a:hover, .nav a.active {{ color: #fff; background: #0f3460; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .stat-card {{ background: #16213e; padding: 1.5rem; border-radius: 8px; text-align: center; border: 1px solid #0f3460; }}
        .stat-card .value {{ font-size: 2.5rem; font-weight: bold; color: #e94560; }}
        .stat-card .label {{ color: #888; margin-top: 0.5rem; }}
        .stat-card.success .value {{ color: #4ade80; }}
        .stat-card.warning .value {{ color: #fbbf24; }}
        .stat-card.danger .value {{ color: #f87171; }}
        .stat-card.info .value {{ color: #60a5fa; }}
        table {{ width: 100%; border-collapse: collapse; background: #16213e; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 1rem; text-align: left; border-bottom: 1px solid #0f3460; }}
        th {{ background: #0f3460; color: #e94560; font-weight: 600; }}
        tr:hover {{ background: #1a1a3e; }}
        .badge {{ padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
        .badge-success {{ background: #065f46; color: #6ee7b7; }}
        .badge-warning {{ background: #78350f; color: #fcd34d; }}
        .badge-danger {{ background: #7f1d1d; color: #fca5a5; }}
        .badge-info {{ background: #1e3a5f; color: #93c5fd; }}
        .badge-default {{ background: #374151; color: #d1d5db; }}
        .btn {{ padding: 0.5rem 1rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.875rem; transition: all 0.2s; text-decoration: none; display: inline-block; }}
        .btn-primary {{ background: #e94560; color: white; }}
        .btn-primary:hover {{ background: #d63d56; }}
        .btn-secondary {{ background: #374151; color: white; }}
        .btn-secondary:hover {{ background: #4b5563; }}
        .btn-danger {{ background: #dc2626; color: white; }}
        .btn-danger:hover {{ background: #b91c1c; }}
        .btn-sm {{ padding: 0.25rem 0.5rem; font-size: 0.75rem; }}
        .actions {{ display: flex; gap: 0.5rem; }}
        .section {{ margin-bottom: 2rem; }}
        .section-title {{ font-size: 1.25rem; margin-bottom: 1rem; color: #e94560; }}
        .empty {{ text-align: center; padding: 3rem; color: #666; }}
        .cron {{ font-family: monospace; background: #0f3460; padding: 0.25rem 0.5rem; border-radius: 4px; }}
        .refresh {{ float: right; }}
        code {{ background: #0f3460; padding: 0.125rem 0.375rem; border-radius: 4px; font-size: 0.875rem; }}
        .filter-bar {{ margin-bottom: 1rem; display: flex; gap: 1rem; align-items: center; }}
        .filter-bar select, .filter-bar input {{ padding: 0.5rem; border-radius: 4px; border: 1px solid #0f3460; background: #16213e; color: #eee; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 Hangfire MCP Dash</h1>
        <nav class="nav">
            <a href="/" class="{'active' if active == 'home' else ''}">Dashboard</a>
            <a href="/jobs" class="{'active' if active == 'jobs' else ''}">Jobs</a>
            <a href="/recurring" class="{'active' if active == 'recurring' else ''}">Recurring</a>
            <a href="/queues" class="{'active' if active == 'queues' else ''}">Queues</a>
            <a href="/servers" class="{'active' if active == 'servers' else ''}">Servers</a>
        </nav>
        <a href="/" class="btn btn-secondary refresh">↻ Refresh</a>
    </div>
    <div class="container">
        {content}
    </div>
</body>
</html>"""


def get_state_badge(state: str) -> str:
    badges = {
        "Succeeded": "success",
        "Failed": "danger",
        "Processing": "warning",
        "Enqueued": "info",
        "Scheduled": "default",
        "Deleted": "default",
    }
    badge_class = badges.get(state, "default")
    return f'<span class="badge badge-{badge_class}">{esc(state)}</span>'


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    db = get_db()
    stats = db.get_stats()
    queues = db.list_queues()
    recent_jobs = db.list_jobs(limit=10)
    
    # Stats cards
    stats_html = f"""
    <div class="stats">
        <div class="stat-card success"><div class="value">{stats.get('succeeded', 0):,}</div><div class="label">Succeeded</div></div>
        <div class="stat-card danger"><div class="value">{stats.get('failed', 0):,}</div><div class="label">Failed</div></div>
        <div class="stat-card warning"><div class="value">{stats.get('processing', 0):,}</div><div class="label">Processing</div></div>
        <div class="stat-card info"><div class="value">{stats.get('enqueued', 0):,}</div><div class="label">Enqueued</div></div>
        <div class="stat-card"><div class="value">{stats.get('scheduled', 0):,}</div><div class="label">Scheduled</div></div>
        <div class="stat-card"><div class="value">{len(queues):,}</div><div class="label">Queues</div></div>
    </div>
    """
    
    # Recent jobs table
    jobs_html = "<div class='section'><h2 class='section-title'>Recent Jobs</h2>"
    if recent_jobs:
        jobs_html += "<table><thead><tr><th>ID</th><th>State</th><th>Type</th><th>Created</th><th>Actions</th></tr></thead><tbody>"
        for job in recent_jobs:
            job_id = job.get("Id", "")
            state = job.get("StateName", "")
            created = str(job.get("CreatedAt", ""))[:19]
            
            # Parse job type
            job_type = "Unknown"
            if inv_data := job.get("InvocationData"):
                try:
                    data = json.loads(inv_data)
                    type_info = data.get("Type") or data.get("t") or ""
                    method = data.get("Method") or data.get("m") or ""
                    if type_info:
                        class_name = type_info.split(",")[0].split(".")[-1]
                        job_type = f"{class_name}.{method}" if method else class_name
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass
            
            actions = f'<a href="/job/{int(job_id)}" class="btn btn-secondary btn-sm">View</a>'
            if state == "Failed":
                actions += f' <form method="post" action="/job/{int(job_id)}/retry" style="display:inline"><button class="btn btn-primary btn-sm">Retry</button></form>'
            
            jobs_html += f"<tr><td>{esc(job_id)}</td><td>{get_state_badge(state)}</td><td><code>{esc(job_type)}</code></td><td>{esc(created)}</td><td class='actions'>{actions}</td></tr>"
        jobs_html += "</tbody></table>"
    else:
        jobs_html += "<div class='empty'>No jobs found</div>"
    jobs_html += "</div>"
    
    return HTMLResponse(render_page("Dashboard", stats_html + jobs_html, "home"))


@app.get("/jobs", response_class=HTMLResponse)
async def jobs_list(state: Optional[str] = None):
    db = get_db()
    jobs = db.list_jobs(state=state, limit=100)
    
    filter_html = f"""
    <div class="filter-bar">
        <select onchange="window.location='?state='+this.value">
            <option value="">All States</option>
            <option value="Enqueued" {'selected' if state == 'Enqueued' else ''}>Enqueued</option>
            <option value="Processing" {'selected' if state == 'Processing' else ''}>Processing</option>
            <option value="Succeeded" {'selected' if state == 'Succeeded' else ''}>Succeeded</option>
            <option value="Failed" {'selected' if state == 'Failed' else ''}>Failed</option>
            <option value="Scheduled" {'selected' if state == 'Scheduled' else ''}>Scheduled</option>
        </select>
    </div>
    """
    
    if jobs:
        content = filter_html + "<table><thead><tr><th>ID</th><th>State</th><th>Type</th><th>Created</th><th>Reason</th><th>Actions</th></tr></thead><tbody>"
        for job in jobs:
            job_id = job.get("Id", "")
            job_state = job.get("StateName", "")
            created = str(job.get("CreatedAt", ""))[:19]
            reason = (job.get("Reason") or "")[:50]
            
            job_type = "Unknown"
            if inv_data := job.get("InvocationData"):
                try:
                    data = json.loads(inv_data)
                    type_info = data.get("Type") or data.get("t") or ""
                    method = data.get("Method") or data.get("m") or ""
                    if type_info:
                        class_name = type_info.split(",")[0].split(".")[-1]
                        job_type = f"{class_name}.{method}" if method else class_name
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass
            
            actions = f'<a href="/job/{int(job_id)}" class="btn btn-secondary btn-sm">View</a>'
            if job_state == "Failed":
                actions += f' <form method="post" action="/job/{int(job_id)}/retry" style="display:inline"><button class="btn btn-primary btn-sm">Retry</button></form>'
            actions += f' <form method="post" action="/job/{int(job_id)}/delete" style="display:inline" onsubmit="return confirm(\'Delete job {int(job_id)}?\')"><button class="btn btn-danger btn-sm">Delete</button></form>'
            
            content += f"<tr><td>{esc(job_id)}</td><td>{get_state_badge(job_state)}</td><td><code>{esc(job_type)}</code></td><td>{esc(created)}</td><td>{esc(reason)}</td><td class='actions'>{actions}</td></tr>"
        content += "</tbody></table>"
    else:
        content = filter_html + "<div class='empty'>No jobs found</div>"
    
    return HTMLResponse(render_page("Jobs", content, "jobs"))


@app.get("/job/{job_id}", response_class=HTMLResponse)
async def job_detail(job_id: int):
    db = get_db()
    job = db.get_job(job_id)
    
    if not job:
        return HTMLResponse(render_page("Job Not Found", "<div class='empty'>Job not found</div>", "jobs"))
    
    state = job.get("StateName", "")
    content = f"""
    <h2 class="section-title">Job #{job_id}</h2>
    <div class="stats" style="margin-bottom: 2rem;">
        <div class="stat-card"><div class="label">State</div><div style="margin-top: 0.5rem">{get_state_badge(state)}</div></div>
        <div class="stat-card"><div class="label">Created</div><div class="value" style="font-size: 1rem">{str(job.get('CreatedAt', ''))[:19]}</div></div>
    </div>
    """
    
    if job.get("Reason"):
        content += f"<p><strong>Reason:</strong> {esc(job.get('Reason'))}</p>"
    
    if inv_data := job.get("InvocationData"):
        content += "<div class='section'><h3 class='section-title'>Invocation</h3><pre style='background:#0f3460;padding:1rem;border-radius:8px;overflow-x:auto'>"
        try:
            data = json.loads(inv_data)
            content += esc(json.dumps(data, indent=2))
        except (json.JSONDecodeError, TypeError):
            content += esc(inv_data)
        content += "</pre></div>"
    
    if args := job.get("Arguments"):
        content += "<div class='section'><h3 class='section-title'>Arguments</h3><pre style='background:#0f3460;padding:1rem;border-radius:8px;overflow-x:auto'>"
        try:
            data = json.loads(args)
            content += esc(json.dumps(data, indent=2))
        except (json.JSONDecodeError, TypeError):
            content += esc(args)
        content += "</pre></div>"
    
    if state_data := job.get("StateData"):
        content += "<div class='section'><h3 class='section-title'>State Data</h3><pre style='background:#0f3460;padding:1rem;border-radius:8px;overflow-x:auto'>"
        try:
            data = json.loads(state_data)
            content += esc(json.dumps(data, indent=2))
        except (json.JSONDecodeError, TypeError):
            content += esc(state_data)
        content += "</pre></div>"
    
    # Actions
    content += "<div class='actions' style='margin-top:2rem'>"
    if state == "Failed":
        content += f'<form method="post" action="/job/{job_id}/retry" style="display:inline"><button class="btn btn-primary">Retry Job</button></form>'
    content += f'<form method="post" action="/job/{job_id}/delete" style="display:inline" onsubmit="return confirm(\'Delete this job?\')"><button class="btn btn-danger">Delete Job</button></form>'
    content += "</div>"
    
    # History
    history = db.get_job_history(job_id)
    if history:
        content += "<div class='section' style='margin-top:2rem'><h3 class='section-title'>History</h3><table><thead><tr><th>State</th><th>Time</th><th>Reason</th></tr></thead><tbody>"
        for h in history:
            content += f"<tr><td>{get_state_badge(h.get('Name', ''))}</td><td>{esc(str(h.get('CreatedAt', ''))[:19])}</td><td>{esc(h.get('Reason') or '')}</td></tr>"
        content += "</tbody></table></div>"
    
    return HTMLResponse(render_page(f"Job #{job_id}", content, "jobs"))


@app.post("/job/{job_id}/retry")
async def retry_job(job_id: int):
    db = get_db()
    db.retry_job(job_id)
    return RedirectResponse(f"/job/{job_id}", status_code=303)


@app.post("/job/{job_id}/delete")
async def delete_job(job_id: int):
    db = get_db()
    db.delete_job(job_id)
    return RedirectResponse("/jobs", status_code=303)


@app.get("/recurring", response_class=HTMLResponse)
async def recurring_list():
    db = get_db()
    jobs = db.list_recurring_jobs()
    
    if jobs:
        content = "<table><thead><tr><th>Job ID</th><th>Cron</th><th>Queue</th><th>Last Run</th><th>Status</th><th>Actions</th></tr></thead><tbody>"
        for job in jobs:
            job_id = job.get("JobId", "")
            cron = job.get("Cron", "")
            queue = job.get("Queue", "default") or "default"
            last_exec = str(job.get("LastExecution") or "Never")[:19]
            paused = job.get("Paused", "false")
            status = "Paused" if paused == "true" else "Active"
            status_badge = "warning" if paused == "true" else "success"
            
            if paused == "true":
                action = f'<form method="post" action="/recurring/{job_id}/resume" style="display:inline"><button class="btn btn-primary btn-sm">Resume</button></form>'
            else:
                action = f'<form method="post" action="/recurring/{job_id}/pause" style="display:inline"><button class="btn btn-secondary btn-sm">Pause</button></form>'
            action += f' <form method="post" action="/recurring/{job_id}/trigger" style="display:inline"><button class="btn btn-primary btn-sm">Trigger Now</button></form>'
            
            content += f"<tr><td><code>{esc(job_id)}</code></td><td><span class='cron'>{esc(cron)}</span></td><td>{esc(queue)}</td><td>{esc(last_exec)}</td><td><span class='badge badge-{status_badge}'>{esc(status)}</span></td><td class='actions'>{action}</td></tr>"
        content += "</tbody></table>"
    else:
        content = "<div class='empty'>No recurring jobs found</div>"
    
    return HTMLResponse(render_page("Recurring Jobs", content, "recurring"))


@app.post("/recurring/{job_id}/trigger")
async def trigger_recurring(job_id: str):
    db = get_db()
    db.trigger_recurring_job(job_id)
    return RedirectResponse("/recurring", status_code=303)


@app.post("/recurring/{job_id}/pause")
async def pause_recurring(job_id: str):
    db = get_db()
    db.pause_recurring_job(job_id)
    return RedirectResponse("/recurring", status_code=303)


@app.post("/recurring/{job_id}/resume")
async def resume_recurring(job_id: str):
    db = get_db()
    db.resume_recurring_job(job_id)
    return RedirectResponse("/recurring", status_code=303)


@app.get("/queues", response_class=HTMLResponse)
async def queues_list():
    db = get_db()
    queues = db.list_queues()
    
    if queues:
        total = sum(q.get("JobCount", 0) for q in queues)
        content = "<table><thead><tr><th>Queue</th><th>Pending Jobs</th></tr></thead><tbody>"
        for q in queues:
            content += f"<tr><td><code>{esc(q.get('Queue', ''))}</code></td><td>{q.get('JobCount', 0):,}</td></tr>"
        content += f"<tr style='font-weight:bold'><td>Total</td><td>{total:,}</td></tr>"
        content += "</tbody></table>"
    else:
        content = "<div class='empty'>No queues with pending jobs</div>"
    
    return HTMLResponse(render_page("Queues", content, "queues"))


@app.get("/servers", response_class=HTMLResponse)
async def servers_list():
    from datetime import datetime, timedelta
    db = get_db()
    servers = db.list_servers()
    
    if servers:
        content = "<table><thead><tr><th>Server ID</th><th>Status</th><th>Workers</th><th>Queues</th><th>Last Heartbeat</th></tr></thead><tbody>"
        for s in servers:
            server_id = s.get("Id", "")
            if len(server_id) > 50:
                server_id = server_id[:47] + "..."
            workers = s.get("WorkersCount", "N/A")
            queues = ", ".join(s.get("Queues", [])) if s.get("Queues") else "N/A"
            heartbeat_raw = s.get("LastHeartbeat")
            heartbeat = str(heartbeat_raw or "")[:19]
            
            # Determine status based on heartbeat
            status = "Unknown"
            status_badge = "default"
            if heartbeat_raw:
                try:
                    if isinstance(heartbeat_raw, datetime):
                        last_hb = heartbeat_raw
                    else:
                        last_hb = datetime.fromisoformat(str(heartbeat_raw)[:19])
                    age = datetime.now() - last_hb
                    if age < timedelta(seconds=30):
                        status = "Online"
                        status_badge = "success"
                    elif age < timedelta(minutes=5):
                        status = "Idle"
                        status_badge = "warning"
                    else:
                        status = "Offline"
                        status_badge = "danger"
                except (ValueError, TypeError, AttributeError):
                    pass
            
            content += f"<tr><td><code>{esc(server_id)}</code></td><td><span class='badge badge-{status_badge}'>{esc(status)}</span></td><td>{esc(workers)}</td><td>{esc(queues)}</td><td>{esc(heartbeat)}</td></tr>"
        content += "</tbody></table>"
    else:
        content = "<div class='empty'>No active servers</div>"
    
    return HTMLResponse(render_page("Servers", content, "servers"))


def run_dashboard(host: str = "127.0.0.1", port: int = 8080):
    """Run the dashboard server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_dashboard()
