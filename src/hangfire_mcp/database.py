"""Database connection and query utilities for Hangfire."""

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

import pyodbc

logger = logging.getLogger("hangfire-mcp.database")


class HangfireDatabase:
    """Database connection manager for Hangfire SQL Server database."""
    
    def __init__(self, connection_string: str, schema: str = "Hangfire"):
        self.connection_string = connection_string
        self.schema = schema
    
    @contextmanager
    def connection(self) -> Generator[pyodbc.Connection, None, None]:
        """Context manager for database connections."""
        conn = pyodbc.connect(self.connection_string)
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def cursor(self) -> Generator[pyodbc.Cursor, None, None]:
        """Context manager for database cursors."""
        with self.connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
    
    def _table(self, name: str) -> str:
        """Get fully qualified table name."""
        return f"[{self.schema}].[{name}]"
    
    # Job queries
    def list_jobs(
        self,
        state: Optional[str] = None,
        queue: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List jobs with optional filtering by state and queue."""
        logger.debug(f"list_jobs(state={state}, queue={queue}, limit={limit})")
        query = f"""
            SELECT TOP (?)
                j.Id,
                j.StateName,
                j.InvocationData,
                j.Arguments,
                j.CreatedAt,
                j.ExpireAt,
                s.Reason,
                s.Data AS StateData,
                s.CreatedAt AS StateCreatedAt
            FROM {self._table('Job')} j
            LEFT JOIN {self._table('State')} s ON j.StateId = s.Id
        """
        
        conditions = []
        params = [limit]
        
        if state:
            conditions.append("j.StateName = ?")
            params.append(state)
        
        if queue:
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM {self._table('JobQueue')} jq 
                    WHERE jq.JobId = j.Id AND jq.Queue = ?
                )
            """)
            params.append(queue)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY j.CreatedAt DESC"
        
        with self.cursor() as cursor:
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    
    def get_job(self, job_id: int) -> Optional[dict[str, Any]]:
        """Get detailed job information."""
        logger.debug(f"get_job(job_id={job_id})")
        query = f"""
            SELECT
                j.Id,
                j.StateName,
                j.InvocationData,
                j.Arguments,
                j.CreatedAt,
                j.ExpireAt,
                s.Reason,
                s.Data AS StateData,
                s.CreatedAt AS StateCreatedAt
            FROM {self._table('Job')} j
            LEFT JOIN {self._table('State')} s ON j.StateId = s.Id
            WHERE j.Id = ?
        """
        
        with self.cursor() as cursor:
            cursor.execute(query, [job_id])
            row = cursor.fetchone()
            if not row:
                return None
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
    
    def get_job_history(self, job_id: int) -> list[dict[str, Any]]:
        """Get state history for a job."""
        query = f"""
            SELECT
                Id,
                Name,
                Reason,
                CreatedAt,
                Data
            FROM {self._table('State')}
            WHERE JobId = ?
            ORDER BY CreatedAt DESC
        """
        
        with self.cursor() as cursor:
            cursor.execute(query, [job_id])
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    
    def retry_job(self, job_id: int, queue: str = "default") -> bool:
        """Retry a failed job by changing its state to Enqueued."""
        logger.info(f"Retrying job {job_id} to queue '{queue}'")
        now = datetime.utcnow().isoformat()
        state_data = json.dumps({"EnqueuedAt": now, "Queue": queue})
        
        with self.cursor() as cursor:
            # Insert new state
            cursor.execute(f"""
                INSERT INTO {self._table('State')} (JobId, Name, Reason, CreatedAt, Data)
                VALUES (?, 'Enqueued', 'Retried via MCP', GETUTCDATE(), ?)
            """, [job_id, state_data])
            
            # Get the new state ID
            cursor.execute("SELECT SCOPE_IDENTITY()")
            state_id = cursor.fetchone()[0]
            
            # Update job
            cursor.execute(f"""
                UPDATE {self._table('Job')}
                SET StateId = ?, StateName = 'Enqueued'
                WHERE Id = ?
            """, [state_id, job_id])
            
            # Add to job queue
            cursor.execute(f"""
                INSERT INTO {self._table('JobQueue')} (JobId, Queue)
                VALUES (?, ?)
            """, [job_id, queue])
            
            return cursor.rowcount > 0
    
    def delete_job(self, job_id: int) -> bool:
        """Delete a job and its associated data."""
        logger.info(f"Deleting job {job_id}")
        with self.cursor() as cursor:
            # Delete from JobQueue
            cursor.execute(f"""
                DELETE FROM {self._table('JobQueue')} WHERE JobId = ?
            """, [job_id])
            
            # Delete states
            cursor.execute(f"""
                DELETE FROM {self._table('State')} WHERE JobId = ?
            """, [job_id])
            
            # Delete job parameters
            cursor.execute(f"""
                DELETE FROM {self._table('JobParameter')} WHERE JobId = ?
            """, [job_id])
            
            # Delete job
            cursor.execute(f"""
                DELETE FROM {self._table('Job')} WHERE Id = ?
            """, [job_id])
            
            return cursor.rowcount > 0
    
    def requeue_job(self, job_id: int, queue: str = "default") -> bool:
        """Move a job back to the queue."""
        return self.retry_job(job_id, queue)
    
    # Recurring job queries
    def list_recurring_jobs(self) -> list[dict[str, Any]]:
        """List all recurring jobs with their configurations."""
        query = f"""
            SELECT 
                s.Value AS JobId,
                s.Score
            FROM {self._table('Set')} s
            WHERE s.[Key] = 'recurring-jobs'
            ORDER BY s.Value
        """
        
        with self.cursor() as cursor:
            cursor.execute(query)
            job_ids = [row[0] for row in cursor.fetchall()]
        
        jobs = []
        for job_id in job_ids:
            job_data = self.get_recurring_job(job_id)
            if job_data:
                jobs.append(job_data)
        
        return jobs
    
    def get_recurring_job(self, job_id: str) -> Optional[dict[str, Any]]:
        """Get recurring job details."""
        query = f"""
            SELECT Field, Value
            FROM {self._table('Hash')}
            WHERE [Key] = ?
        """
        
        with self.cursor() as cursor:
            cursor.execute(query, [f"recurring-job:{job_id}"])
            rows = cursor.fetchall()
            
            if not rows:
                return None
            
            job_data = {"JobId": job_id}
            for field, value in rows:
                job_data[field] = value
            
            return job_data
    
    def trigger_recurring_job(self, job_id: str, queue: str = "default") -> Optional[int]:
        """Trigger a recurring job to run immediately."""
        logger.info(f"Triggering recurring job '{job_id}' to queue '{queue}'")
        job_data = self.get_recurring_job(job_id)
        if not job_data or "Job" not in job_data:
            return None
        
        job_info = json.loads(job_data["Job"])
        invocation_data = json.dumps({
            "Type": job_info.get("Type", ""),
            "Method": job_info.get("Method", ""),
            "ParameterTypes": job_info.get("ParameterTypes", ""),
        })
        arguments = job_info.get("Arguments", "[]")
        
        now = datetime.utcnow().isoformat()
        state_data = json.dumps({"EnqueuedAt": now, "Queue": queue})
        
        with self.cursor() as cursor:
            # Create job
            cursor.execute(f"""
                INSERT INTO {self._table('Job')} (InvocationData, Arguments, CreatedAt, StateName)
                OUTPUT INSERTED.Id
                VALUES (?, ?, GETUTCDATE(), 'Enqueued')
            """, [invocation_data, arguments])
            
            new_job_id = cursor.fetchone()[0]
            
            # Create state
            cursor.execute(f"""
                INSERT INTO {self._table('State')} (JobId, Name, Reason, CreatedAt, Data)
                VALUES (?, 'Enqueued', 'Triggered via MCP', GETUTCDATE(), ?)
            """, [new_job_id, state_data])
            
            cursor.execute("SELECT SCOPE_IDENTITY()")
            state_id = cursor.fetchone()[0]
            
            # Update job with state ID
            cursor.execute(f"""
                UPDATE {self._table('Job')}
                SET StateId = ?
                WHERE Id = ?
            """, [state_id, new_job_id])
            
            # Add to queue
            cursor.execute(f"""
                INSERT INTO {self._table('JobQueue')} (JobId, Queue)
                VALUES (?, ?)
            """, [new_job_id, queue])
            
            return new_job_id
    
    def pause_recurring_job(self, job_id: str) -> bool:
        """Pause a recurring job by removing it from the set."""
        logger.info(f"Pausing recurring job '{job_id}'")
        with self.cursor() as cursor:
            cursor.execute(f"""
                DELETE FROM {self._table('Set')}
                WHERE [Key] = 'recurring-jobs' AND Value = ?
            """, [job_id])
            
            # Mark as paused in hash
            cursor.execute(f"""
                IF EXISTS (SELECT 1 FROM {self._table('Hash')} WHERE [Key] = ? AND Field = 'Paused')
                    UPDATE {self._table('Hash')} SET Value = 'true' WHERE [Key] = ? AND Field = 'Paused'
                ELSE
                    INSERT INTO {self._table('Hash')} ([Key], Field, Value) VALUES (?, 'Paused', 'true')
            """, [f"recurring-job:{job_id}", f"recurring-job:{job_id}", f"recurring-job:{job_id}"])
            
            return True
    
    def resume_recurring_job(self, job_id: str) -> bool:
        """Resume a paused recurring job."""
        logger.info(f"Resuming recurring job '{job_id}'")
        with self.cursor() as cursor:
            # Check if job exists
            cursor.execute(f"""
                SELECT 1 FROM {self._table('Hash')}
                WHERE [Key] = ? AND Field = 'Cron'
            """, [f"recurring-job:{job_id}"])
            
            if not cursor.fetchone():
                return False
            
            # Remove paused flag
            cursor.execute(f"""
                DELETE FROM {self._table('Hash')}
                WHERE [Key] = ? AND Field = 'Paused'
            """, [f"recurring-job:{job_id}"])
            
            # Add back to recurring jobs set
            cursor.execute(f"""
                IF NOT EXISTS (SELECT 1 FROM {self._table('Set')} WHERE [Key] = 'recurring-jobs' AND Value = ?)
                    INSERT INTO {self._table('Set')} ([Key], Value, Score) VALUES ('recurring-jobs', ?, 0)
            """, [job_id, job_id])
            
            return True
    
    # Statistics queries
    def get_stats(self) -> dict[str, int]:
        """Get server statistics."""
        query = f"""
            SELECT [Key], SUM(CAST([Value] AS bigint)) AS Total
            FROM {self._table('Counter')}
            WHERE [Key] IN ('stats:succeeded', 'stats:failed', 'stats:deleted', 'stats:enqueued')
            GROUP BY [Key]
        """
        
        # Also get aggregated stats
        agg_query = f"""
            SELECT [Key], CAST([Value] AS bigint) AS Total
            FROM {self._table('AggregatedCounter')}
            WHERE [Key] IN ('stats:succeeded', 'stats:failed', 'stats:deleted', 'stats:enqueued')
        """
        
        stats = {
            "succeeded": 0,
            "failed": 0,
            "deleted": 0,
            "enqueued": 0,
            "processing": 0,
            "scheduled": 0,
        }
        
        with self.cursor() as cursor:
            # Counter table
            try:
                cursor.execute(query)
                for key, total in cursor.fetchall():
                    stat_name = key.replace("stats:", "")
                    if stat_name in stats:
                        stats[stat_name] += total or 0
            except pyodbc.Error:
                pass
            
            # Aggregated counter table
            try:
                cursor.execute(agg_query)
                for key, total in cursor.fetchall():
                    stat_name = key.replace("stats:", "")
                    if stat_name in stats:
                        stats[stat_name] += total or 0
            except pyodbc.Error:
                pass
            
            # Count current processing jobs
            cursor.execute(f"""
                SELECT COUNT(*) FROM {self._table('Job')}
                WHERE StateName = 'Processing'
            """)
            stats["processing"] = cursor.fetchone()[0]
            
            # Count scheduled jobs
            cursor.execute(f"""
                SELECT COUNT(*) FROM {self._table('Job')}
                WHERE StateName = 'Scheduled'
            """)
            stats["scheduled"] = cursor.fetchone()[0]
        
        return stats
    
    def list_queues(self) -> list[dict[str, Any]]:
        """List queues with job counts."""
        query = f"""
            SELECT Queue, COUNT(*) AS JobCount
            FROM {self._table('JobQueue')}
            WHERE FetchedAt IS NULL
            GROUP BY Queue
            ORDER BY Queue
        """
        
        with self.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    
    def list_servers(self) -> list[dict[str, Any]]:
        """List active Hangfire servers."""
        query = f"""
            SELECT Id, Data, LastHeartbeat
            FROM {self._table('Server')}
            ORDER BY LastHeartbeat DESC
        """
        
        with self.cursor() as cursor:
            cursor.execute(query)
            servers = []
            for row in cursor.fetchall():
                server_data = {"Id": row[0], "LastHeartbeat": row[2]}
                try:
                    data = json.loads(row[1]) if row[1] else {}
                    server_data.update(data)
                except json.JSONDecodeError:
                    pass
                servers.append(server_data)
            return servers
