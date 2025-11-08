# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Job summary client for PostgreSQL operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_, func
from ...base import PostgreSQLBaseClient
from ...models import JobSummary as JobSummaryModel
from ltp_storage.data_schema.job_records import JobSummaryRecord
from ltp_storage.utils.time_util import parse_duration


class JobSummaryClient(PostgreSQLBaseClient):
    """Client for managing job summary records in PostgreSQL."""

    def _insert_record(self, record: JobSummaryRecord) -> int:
        """
        Insert a job summary record.

        Args:
            record: JobSummaryRecord to insert

        Returns:
            int: The ID of the inserted record

        Raises:
            RuntimeError: If insertion fails
        """
        try:
            session = self.get_session()
            try:
                job_summary = JobSummaryModel(
                    job_id=record.job_id,
                    job_hash=record.job_hash,
                    job_name=record.job_name,
                    user_name=record.user_name,
                    job_state=record.job_state,
                    retry_count=record.retry_count,
                    attempt_id=record.attempt_id,
                    retry_details=record.retry_details,
                    virtual_cluster=record.virtual_cluster,
                    total_gpu_count=record.total_gpu_count,
                    job_priority=record.job_priority,
                    job_duration_hours=record.job_duration_hours,
                    total_gpu_hours=record.total_gpu_hours,
                    idle_gpu_hours=record.idle_gpu_hours,
                    effective_gpu_hours=record.effective_gpu_hours,
                    submission_time=record.submission_time,
                    launch_time=record.launch_time,
                    completion_time=record.completion_time,
                    created_datetime=record.created_datetime or datetime.utcnow(),
                    idle_gpu_percentage=record.idle_gpu_percentage,
                    assigned_gpu_utilization=record.assigned_gpu_utilization,
                    effective_gpu_utilization=record.effective_gpu_utilization,
                    exit_reason=record.exit_reason,
                    exit_category=record.exit_category,
                    time_generated=record.time_generated,
                    endpoint=record.endpoint,
                )
                session.add(job_summary)
                session.commit()
                session.refresh(job_summary)
                return job_summary.id
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert job summary record: {str(e)}")

    def insert_job_summaries_batch(self, records: List[Dict[str, Any]]) -> None:
        """
        Insert multiple job summary records in a batch.

        Args:
            records: List of job summary records as dictionaries

        Raises:
            RuntimeError: If insertion fails
        """
        if not records:
            return
        
        try:
            # Convert dicts to JobSummaryRecord objects
            job_records = [JobSummaryRecord.from_record(r) for r in records]
            
            session = self.get_session()
            try:
                job_summaries = [
                    JobSummaryModel(
                        job_id=record.job_id,
                        job_hash=record.job_hash,
                        job_name=record.job_name,
                        user_name=record.user_name,
                        job_state=record.job_state,
                        retry_count=record.retry_count,
                        attempt_id=record.attempt_id,
                        retry_details=record.retry_details,
                        virtual_cluster=record.virtual_cluster,
                        total_gpu_count=record.total_gpu_count,
                        job_priority=record.job_priority,
                        job_duration_hours=record.job_duration_hours,
                        total_gpu_hours=record.total_gpu_hours,
                        idle_gpu_hours=record.idle_gpu_hours,
                        effective_gpu_hours=record.effective_gpu_hours,
                        submission_time=record.submission_time,
                        launch_time=record.launch_time,
                        completion_time=record.completion_time,
                        created_datetime=record.created_datetime or datetime.utcnow(),
                        idle_gpu_percentage=record.idle_gpu_percentage,
                        assigned_gpu_utilization=record.assigned_gpu_utilization,
                        effective_gpu_utilization=record.effective_gpu_utilization,
                        exit_reason=record.exit_reason,
                        exit_category=record.exit_category,
                        time_generated=record.time_generated,
                        endpoint=record.endpoint,
                    )
                    for record in job_records
                ]
                session.add_all(job_summaries)
                session.commit()
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert job summary records: {str(e)}")

    def _query_records(
        self,
        job_id: Optional[str] = None,
        user_name: Optional[str] = None,
        job_state: Optional[str] = None,
        virtual_cluster: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query job summary records with filters.

        Args:
            job_id: Filter by job ID
            user_name: Filter by user name
            job_state: Filter by job state
            virtual_cluster: Filter by virtual cluster
            start_time: Filter by start submission time
            end_time: Filter by end submission time
            limit: Maximum number of records to return

        Returns:
            List of job summary records as dictionaries
        """
        session = self.get_session()
        try:
            query = select(JobSummaryModel)

            filters = []
            if job_id:
                filters.append(JobSummaryModel.job_id == job_id)
            if user_name:
                filters.append(JobSummaryModel.user_name == user_name)
            if job_state:
                filters.append(JobSummaryModel.job_state == job_state)
            if virtual_cluster:
                filters.append(JobSummaryModel.virtual_cluster == virtual_cluster)
            if start_time:
                filters.append(JobSummaryModel.submission_time >= start_time)
            if end_time:
                filters.append(JobSummaryModel.submission_time <= end_time)

            if filters:
                query = query.where(and_(*filters))

            query = query.order_by(JobSummaryModel.submission_time.desc()).limit(limit)

            results = session.execute(query).scalars().all()
            return [result.to_dict() for result in results]
        finally:
            session.close()

    def _get_record(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest job summary for a specific job ID.

        Args:
            job_id: Job identifier

        Returns:
            Job summary record as dictionary, or None if not found
        """
        session = self.get_session()
        try:
            query = select(JobSummaryModel).where(
                JobSummaryModel.job_id == job_id
            ).order_by(JobSummaryModel.created_datetime.desc()).limit(1)

            result = session.execute(query).scalar_one_or_none()
            return result.to_dict() if result else None
        finally:
            session.close()

    
    def query_last_completion_time(self, endpoint: Optional[str] = None) -> Optional[datetime]:
        """
        Query the last completion time from job summary table.
        
        Args:
            endpoint: Filter by endpoint (cluster ID)
            
        Returns:
            datetime: Last completion time, or None if not found
        """
        session = self.get_session()
        try:
            query = select(func.max(JobSummaryModel.completion_time))
            
            if endpoint:
                query = query.where(JobSummaryModel.endpoint == endpoint)
            
            result = session.execute(query).scalar()
            return result
        finally:
            session.close()
    
    def query_unknown_category_records(self, retain_time: str = "30d", endpoint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query records with unknown exit category within the retention window.
        
        Args:
            retain_time_hours: Retention window in hours (default 30 days = 720 hours)
            endpoint: Filter by endpoint (cluster ID)
            
        Returns:
            List of job summary records with unknown category
        """
        session = self.get_session()
        try:
            cutoff_time = datetime.utcnow() - parse_duration(retain_time)
            
            query = select(JobSummaryModel).where(
                and_(
                    JobSummaryModel.time_generated >= cutoff_time,
                    JobSummaryModel.exit_category == 'Unknown'
                )
            )
            
            if endpoint:
                query = query.where(JobSummaryModel.endpoint == endpoint)
            
            results = session.execute(query).scalars().all()
            return [result.to_dict() for result in results]
        finally:
            session.close()
    
    def query_job_summaries_by_job_ids(self, job_ids: List[str], endpoint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query job summaries for a list of job IDs (latest record for each job).
        
        Args:
            job_ids: List of job IDs to query
            endpoint: Filter by endpoint (cluster ID)
            
        Returns:
            List of job summary records (latest for each job ID)
        """
        if not job_ids:
            return []
        
        session = self.get_session()
        try:
            # Subquery to get max time_generated for each job_id
            subquery = (
                select(
                    JobSummaryModel.job_id,
                    func.max(JobSummaryModel.time_generated).label('max_time')
                )
                .where(JobSummaryModel.job_id.in_(job_ids))
            )
            
            if endpoint:
                subquery = subquery.where(JobSummaryModel.endpoint == endpoint)
            
            subquery = subquery.group_by(JobSummaryModel.job_id).subquery()
            
            # Join with main table to get full records
            query = select(JobSummaryModel).join(
                subquery,
                and_(
                    JobSummaryModel.job_id == subquery.c.job_id,
                    JobSummaryModel.time_generated == subquery.c.max_time
                )
            )
            
            results = session.execute(query).scalars().all()
            return [result.to_dict() for result in results]
        finally:
            session.close()
