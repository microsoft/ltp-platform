# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Job react time client for PostgreSQL operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_, func
from ...base import PostgreSQLBaseClient
from ...models import JobReactTime as JobReactTimeModel
from ltp_storage.data_schema.job_records import JobReactTimeRecord
from ltp_storage.utils.time_util import parse_duration


class JobReactTimeClient(PostgreSQLBaseClient):
    """Client for managing job react time records in PostgreSQL."""

    def _insert_record(self, record: JobReactTimeRecord) -> int:
        """
        Insert a job react time record.

        Args:
            record: JobReactTimeRecord to insert

        Returns:
            int: The ID of the inserted record

        Raises:
            RuntimeError: If insertion fails
        """
        try:
            session = self.get_session()
            try:
                job_react_time = JobReactTimeModel(
                    job_id=record.job_id,
                    react_time=record.react_time,
                    job_hash=record.job_hash,
                    time_generated=record.time_generated or datetime.utcnow(),
                    endpoint=record.endpoint,
                )
                session.add(job_react_time)
                session.commit()
                session.refresh(job_react_time)
                return job_react_time.id
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert job react time record: {str(e)}")

    def insert_job_react_times_batch(self, records: List[Dict[str, Any]]) -> None:
        """
        Insert multiple job react time records in a batch.

        Args:
            records: List of job react time records as dictionaries

        Raises:
            RuntimeError: If insertion fails
        """
        if not records:
            return
        
        try:
            # Convert dicts to JobReactTimeRecord objects
            react_records = [JobReactTimeRecord.from_record(r) for r in records]
            
            session = self.get_session()
            try:
                job_react_times = [
                    JobReactTimeModel(
                        job_id=record.job_id,
                        react_time=record.react_time,
                        job_hash=record.job_hash,
                        time_generated=record.time_generated or datetime.utcnow(),
                        endpoint=record.endpoint,
                    )
                    for record in react_records
                ]
                session.add_all(job_react_times)
                session.commit()
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert job react time records: {str(e)}")

    def _query_records(
        self,
        job_id: Optional[str] = None,
        job_hash: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query job react time records with filters.

        Args:
            job_id: Filter by job ID
            job_hash: Filter by job hash
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of records to return

        Returns:
            List of job react time records as dictionaries
        """
        session = self.get_session()
        try:
            query = select(JobReactTimeModel)

            filters = []
            if job_id:
                filters.append(JobReactTimeModel.job_id == job_id)
            if job_hash:
                filters.append(JobReactTimeModel.job_hash == job_hash)
            if start_time:
                filters.append(JobReactTimeModel.time_generated >= start_time)
            if end_time:
                filters.append(JobReactTimeModel.time_generated <= end_time)

            if filters:
                query = query.where(and_(*filters))

            query = query.order_by(JobReactTimeModel.time_generated.desc()).limit(limit)

            results = session.execute(query).scalars().all()
            return [result.to_dict() for result in results]
        finally:
            session.close()

    def _get_record(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest react time for a specific job ID.

        Args:
            job_id: Job identifier

        Returns:
            Job react time record as dictionary, or None if not found
        """
        session = self.get_session()
        try:
            query = select(JobReactTimeModel).where(
                JobReactTimeModel.job_id == job_id
            ).order_by(JobReactTimeModel.time_generated.desc()).limit(1)

            result = session.execute(query).scalar_one_or_none()
            return result.to_dict() if result else None
        finally:
            session.close()

    def get_average_react_time(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Get average react time for jobs within a time range.

        Args:
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            Average react time in seconds, or None if no records found
        """
        session = self.get_session()
        try:
            query = select(func.avg(JobReactTimeModel.react_time))

            filters = []
            if start_time:
                filters.append(JobReactTimeModel.time_generated >= start_time)
            if end_time:
                filters.append(JobReactTimeModel.time_generated <= end_time)

            if filters:
                query = query.where(and_(*filters))

            result = session.execute(query).scalar()
            return float(result) if result else None
        finally:
            session.close()

    
    def query_unknown_react_records(self, retain_time: str = "30d", endpoint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query records with missing reactTime within the retention window.
        
        Args:
            retain_time: Retention window (e.g. '30d')
            endpoint: Filter by endpoint (cluster ID)
            
        Returns:
            List of react time records with missing react_time
        """
        session = self.get_session()
        try:
            cutoff_time = datetime.utcnow() - parse_duration(retain_time)
            
            query = select(JobReactTimeModel).where(
                and_(
                    JobReactTimeModel.time_generated >= cutoff_time,
                    JobReactTimeModel.react_time.is_(None),
                    JobReactTimeModel.job_hash != "unknown"
                )
            )
            
            if endpoint:
                query = query.where(JobReactTimeModel.endpoint == endpoint)
            
            results = session.execute(query).scalars().all()
            return [result.to_dict() for result in results]
        finally:
            session.close()
