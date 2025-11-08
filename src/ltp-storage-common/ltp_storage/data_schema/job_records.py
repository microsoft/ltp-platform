# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Job-related record dataclasses."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class JobSummaryRecord:
    """Job summary record with metrics."""
    
    job_id: str
    time_generated: datetime
    endpoint: str
    job_hash: Optional[str] = None
    job_name: Optional[str] = None
    user_name: Optional[str] = None
    job_state: Optional[str] = None
    retry_count: Optional[int] = None
    attempt_id: Optional[int] = None
    retry_details: Optional[Dict[str, Any]] = None
    virtual_cluster: Optional[str] = None
    total_gpu_count: Optional[int] = None
    job_priority: Optional[str] = None
    job_duration_hours: Optional[float] = None
    total_gpu_hours: Optional[float] = None
    idle_gpu_hours: Optional[float] = None
    effective_gpu_hours: Optional[float] = None
    submission_time: Optional[datetime] = None
    launch_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    created_datetime: Optional[datetime] = None
    idle_gpu_percentage: Optional[float] = None
    assigned_gpu_utilization: Optional[float] = None
    effective_gpu_utilization: Optional[float] = None
    exit_reason: Optional[str] = None
    exit_category: Optional[str] = None

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "JobSummaryRecord":
        from ..utils.time_util import convert_timestamp
        
        def parse_time(value):
            if value is None:
                return None
            if isinstance(value, str):
                return convert_timestamp(value, "datetime")
            return value
        
        return cls(
            job_id=record.get("job_id") or record.get("jobId", ""),
            time_generated=parse_time(record.get("time_generated") or record.get("timeGenerated")),
            endpoint=record.get("endpoint") or record.get("Endpoint", ""),
            job_hash=record.get("job_hash") or record.get("jobHash"),
            job_name=record.get("job_name") or record.get("jobName"),
            user_name=record.get("user_name") or record.get("userName"),
            job_state=record.get("job_state") or record.get("jobState"),
            retry_count=record.get("retry_count") or record.get("retryCount"),
            attempt_id=record.get("attempt_id") or record.get("attemptId"),
            retry_details=record.get("retry_details") or record.get("retryDetails"),
            virtual_cluster=record.get("virtual_cluster") or record.get("virtualCluster"),
            total_gpu_count=record.get("total_gpu_count") or record.get("totalGpuCount"),
            job_priority=record.get("job_priority") or record.get("jobPriority"),
            job_duration_hours=record.get("job_duration_hours") or record.get("jobDurationHours"),
            total_gpu_hours=record.get("total_gpu_hours") or record.get("totalGpuHours"),
            idle_gpu_hours=record.get("idle_gpu_hours") or record.get("idleGpuHours"),
            effective_gpu_hours=record.get("effective_gpu_hours") or record.get("effectiveGpuHours"),
            submission_time=parse_time(record.get("submission_time") or record.get("submissionTime")),
            launch_time=parse_time(record.get("launch_time") or record.get("launchTime")),
            completion_time=parse_time(record.get("completion_time") or record.get("completionTime")),
            created_datetime=parse_time(record.get("created_datetime") or record.get("createdDatetime")),
            idle_gpu_percentage=record.get("idle_gpu_percentage") or record.get("idleGpuPercentage"),
            assigned_gpu_utilization=record.get("assigned_gpu_utilization") or record.get("assignedGpuUtilization"),
            effective_gpu_utilization=record.get("effective_gpu_utilization") or record.get("effectiveGpuUtilization"),
            exit_reason=record.get("exit_reason") or record.get("exitReason"),
            exit_category=record.get("exit_category") or record.get("exitCategory"),
        )

    def to_dict(self) -> Dict[str, Any]:
        def format_time(value):
            if value is None:
                return None
            return value.isoformat() if isinstance(value, datetime) else value
        
        return {
            "job_id": self.job_id,
            "job_hash": self.job_hash,
            "job_name": self.job_name,
            "user_name": self.user_name,
            "job_state": self.job_state,
            "retry_count": self.retry_count,
            "attempt_id": self.attempt_id,
            "retry_details": self.retry_details,
            "virtual_cluster": self.virtual_cluster,
            "total_gpu_count": self.total_gpu_count,
            "job_priority": self.job_priority,
            "job_duration_hours": self.job_duration_hours,
            "total_gpu_hours": self.total_gpu_hours,
            "idle_gpu_hours": self.idle_gpu_hours,
            "effective_gpu_hours": self.effective_gpu_hours,
            "submission_time": format_time(self.submission_time),
            "launch_time": format_time(self.launch_time),
            "completion_time": format_time(self.completion_time),
            "created_datetime": format_time(self.created_datetime),
            "idle_gpu_percentage": self.idle_gpu_percentage,
            "assigned_gpu_utilization": self.assigned_gpu_utilization,
            "effective_gpu_utilization": self.effective_gpu_utilization,
            "exit_reason": self.exit_reason,
            "exit_category": self.exit_category,
            "time_generated": format_time(self.time_generated),
            "endpoint": self.endpoint,
        }


@dataclass
class JobReactTimeRecord:
    """Job reaction time record."""
    
    job_id: str
    endpoint: str
    react_time: Optional[float] = None
    job_hash: Optional[str] = None
    time_generated: Optional[datetime] = None

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "JobReactTimeRecord":
        from ..utils.time_util import convert_timestamp
        
        time_generated = record.get("time_generated") or record.get("timeGenerated")
        if time_generated and isinstance(time_generated, str):
            time_generated = convert_timestamp(time_generated, "datetime")
        
        return cls(
            job_id=record.get("job_id") or record.get("jobId", ""),
            endpoint=record.get("endpoint") or record.get("Endpoint", ""),
            react_time=record.get("react_time") or record.get("reactTime"),
            job_hash=record.get("job_hash") or record.get("jobHash"),
            time_generated=time_generated,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "react_time": self.react_time,
            "job_hash": self.job_hash,
            "time_generated": self.time_generated.isoformat() if isinstance(self.time_generated, datetime) else self.time_generated,
            "endpoint": self.endpoint,
        }

