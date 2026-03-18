"""Pydantic models for Hangfire MCP server."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobState(str, Enum):
    """Hangfire job states."""
    ENQUEUED = "Enqueued"
    PROCESSING = "Processing"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    DELETED = "Deleted"
    SCHEDULED = "Scheduled"
    AWAITING = "Awaiting"


class Job(BaseModel):
    """Hangfire job model."""
    id: int = Field(alias="Id")
    state_name: Optional[str] = Field(default=None, alias="StateName")
    invocation_data: Optional[str] = Field(default=None, alias="InvocationData")
    arguments: Optional[str] = Field(default=None, alias="Arguments")
    created_at: Optional[datetime] = Field(default=None, alias="CreatedAt")
    expire_at: Optional[datetime] = Field(default=None, alias="ExpireAt")
    reason: Optional[str] = Field(default=None, alias="Reason")
    state_data: Optional[str] = Field(default=None, alias="StateData")
    state_created_at: Optional[datetime] = Field(default=None, alias="StateCreatedAt")
    
    class Config:
        populate_by_name = True


class JobHistory(BaseModel):
    """Job state history entry."""
    id: int = Field(alias="Id")
    name: str = Field(alias="Name")
    reason: Optional[str] = Field(default=None, alias="Reason")
    created_at: datetime = Field(alias="CreatedAt")
    data: Optional[str] = Field(default=None, alias="Data")
    
    class Config:
        populate_by_name = True


class RecurringJob(BaseModel):
    """Recurring job model."""
    job_id: str = Field(alias="JobId")
    cron: Optional[str] = Field(default=None, alias="Cron")
    queue: Optional[str] = Field(default=None, alias="Queue")
    job: Optional[str] = Field(default=None, alias="Job")
    last_execution: Optional[str] = Field(default=None, alias="LastExecution")
    next_execution: Optional[str] = Field(default=None, alias="NextExecution")
    last_job_id: Optional[str] = Field(default=None, alias="LastJobId")
    paused: bool = Field(default=False, alias="Paused")
    
    class Config:
        populate_by_name = True


class QueueStats(BaseModel):
    """Queue statistics."""
    queue: str = Field(alias="Queue")
    job_count: int = Field(alias="JobCount")
    
    class Config:
        populate_by_name = True


class ServerInfo(BaseModel):
    """Hangfire server information."""
    id: str = Field(alias="Id")
    last_heartbeat: Optional[datetime] = Field(default=None, alias="LastHeartbeat")
    workers_count: Optional[int] = Field(default=None, alias="WorkersCount")
    queues: Optional[list[str]] = Field(default=None, alias="Queues")
    started_at: Optional[datetime] = Field(default=None, alias="StartedAt")
    
    class Config:
        populate_by_name = True


class Stats(BaseModel):
    """Server statistics."""
    succeeded: int = 0
    failed: int = 0
    deleted: int = 0
    enqueued: int = 0
    processing: int = 0
    scheduled: int = 0
