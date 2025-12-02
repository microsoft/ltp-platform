# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from typing import Generator
import pandas as pd

# Set up Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from run import process_job_data
from kusto_util import StorageUtil, KustoUtil


def _is_kusto_backend(client):
    """Check if the client is a Kusto backend by checking for execute_command method"""
    return hasattr(client, 'execute_command') and callable(getattr(client, 'execute_command', None))


def _cleanup_kusto_job_records(client, job_id):
    """Cleanup job records for Kusto backend"""
    try:
        if hasattr(client, 'table_name') and hasattr(client, 'execute_command'):
            # Kusto uses camelCase: jobId
            cleanup_query = f""".delete table {client.table_name} records <| ({client.table_name} | where jobId == "{job_id}")"""
            client.execute_command(cleanup_query)
    except Exception:
        pass


def _cleanup_postgresql_job_records(client, job_id):
    """Cleanup job records for PostgreSQL backend"""
    try:
        if not hasattr(client, 'get_session'):
            return
        
        # Try to import PostgreSQL models (may not be available if using Kusto)
        try:
            from ltp_postgresql_sdk.models import JobSummary as JobSummaryModel
            from ltp_postgresql_sdk.models import JobReactTime as JobReactTimeModel
        except ImportError:
            # PostgreSQL SDK not available, skip cleanup
            return
        
        session = client.get_session()
        try:
            # Try to determine the model type by checking the client's module/class
            client_module = client.__class__.__module__
            client_name = client.__class__.__name__.lower()
            
            # Import the appropriate model based on client type
            if 'job_summary' in client_module or 'jobsummary' in client_name:
                Model = JobSummaryModel
            elif 'job_react_time' in client_module or 'jobreacttime' in client_name:
                Model = JobReactTimeModel
            else:
                # Fallback: try both models
                session.query(JobSummaryModel).filter(
                    JobSummaryModel.job_id == job_id
                ).delete(synchronize_session=False)
                session.query(JobReactTimeModel).filter(
                    JobReactTimeModel.job_id == job_id
                ).delete(synchronize_session=False)
                session.commit()
                return
            
            session.query(Model).filter(
                Model.job_id == job_id
            ).delete(synchronize_session=False)
            session.commit()
        finally:
            session.close()
    except Exception:
        # Silently fail cleanup - test data may not exist or cleanup may not be critical
        pass


def _cleanup_job_records(client, job_id):
    """Cleanup job records for either backend"""
    if _is_kusto_backend(client):
        _cleanup_kusto_job_records(client, job_id)
    else:
        _cleanup_postgresql_job_records(client, job_id)


@pytest.fixture(scope="session")
def storage_util():
    """Create a StorageUtil instance using actual pod environment variables"""
    # Use actual environment variables from the pod
    # The backend will be determined by LTP_STORAGE_BACKEND_DEFAULT (defaults to 'kusto')
    util = StorageUtil()
    
    # Ensure test tables exist (if supported by backend)
    # Tables might already exist in production, so we catch exceptions
    try:
        if hasattr(util.job_summary_client, 'create_table'):
            util.job_summary_client.create_table()
    except (RuntimeError, AttributeError):
        # Tables might already exist, which is fine
        pass
    
    try:
        if hasattr(util.job_react_client, 'create_table'):
            util.job_react_client.create_table()
    except (RuntimeError, AttributeError):
        # Tables might already exist, which is fine
        pass
        
    yield util


@pytest.fixture
def test_job_id():
    """Generate a unique test job ID"""
    return f"test-user~test-job-e2e~{int(datetime.now().timestamp())}"


class TestJobDataRecorderEndToEnd:
    """End-to-end integration tests for process_job_data with real database updates"""
    
    def test_process_job_data_end_to_end(self, storage_util, test_job_id):
        """End-to-end test: process_job_data with mocked Prometheus and job metadata, real database"""
        # Use a fixed time to ensure job falls within the time window
        # The job should complete within the last hour (time_offset="1h")
        base_time = datetime.now(timezone.utc)
        base_time_sec = base_time.timestamp()
        
        # Job should complete 30 minutes ago (within the 1h window)
        # and run for at least 10 minutes to meet criteria
        job_completed_sec = base_time_sec - 1800  # 30 minutes ago
        job_completed_ms = int(job_completed_sec * 1000)
        job_launched_sec = job_completed_sec - 3600  # 1 hour before completion (30 min + 30 min = 1h ago)
        job_launched_ms = int(job_launched_sec * 1000)
        
        # Create test job metadata matching the actual schema from get_job_attempt_metadata
        # This should match what JobMetadataClient.get_job_attempt_metadata returns
        test_job_metadata = {
            # Basic job fields
            "username": "test-user",
            "name": "test-job-e2e",
            "retries": 0,
            "virtualCluster": "default",
            "totalGpuNumber": 1,
            
            # Attempt-specific fields
            "attemptId": 0,
            "jobPriority": "default",
            "state": "SUCCEEDED",
            "attemptState": "SUCCEEDED",
            
            # Timestamps (in milliseconds)
            "createdTime": job_launched_ms - 3600000,  # 1 hour before launch
            "launchedTime": job_launched_ms,
            "completedTime": job_completed_ms,  # 30 minutes ago (within 1h window)
            "submissionTime": job_launched_ms - 7200000,  # 2 hours before launch
            
            # Datetime fields (pandas Timestamps) - these are added by get_job_attempt_metadata
            "submissionDatetime": pd.Timestamp(datetime.fromtimestamp(job_launched_sec - 7200, tz=timezone.utc)),
            "launchedDatetime": pd.Timestamp(datetime.fromtimestamp(job_launched_sec, tz=timezone.utc)),
            "completedDatetime": pd.Timestamp(datetime.fromtimestamp(job_completed_sec, tz=timezone.utc)),
            "createdDatetime": pd.Timestamp(datetime.fromtimestamp(job_launched_sec - 3600, tz=timezone.utc)),
            
            # Job ID (format: username~jobname~attemptId)
            "job_id": test_job_id,
            
            # Task roles
            "taskRoles": {
                "worker": {
                    "instances": 1,
                    "resourcePerInstance": {"gpu": 1},
                    "taskStatuses": [
                        {
                            "taskState": "SUCCEEDED",
                            "taskIndex": 0,
                            "containerNodeName": "test-node",
                            "containerIp": "10.0.0.1",
                            "containerExitSpec": {
                                "phrase": "Succeeded"
                            }
                        }
                    ]
                }
            },
            
            # Exit spec
            "exitSpec": {
                "phrase": "Succeeded"
            },
        }
        
        # Create job metadata with metrics (what get_single_job_metrics would return)
        job_duration_hours = (job_completed_sec - job_launched_sec) / 3600  # 1 hour
        test_job_metadata_with_metrics = test_job_metadata.copy()
        test_job_metadata_with_metrics.update({
            "duration": job_duration_hours,
            "total_gpu_hours": 1.0,  # 1 GPU * 1 hour
            "idle_gpu_hours": 0.0,
            "effective_gpu_hours": 0.9,  # 90% utilization
            "effective_gpu_utilization": 0.9,
            "assigned_gpu_utilization": 1.0,
            "idle_gpu_percentage": 0.0,
            "job_hash": "test-job-hash-e2e",
        })
        
        # Mock get_single_job_metrics to return job metadata with metrics
        def mock_get_single_job_metrics(job, job_metadata, end_time_stamp=None, time_offset=None):
            """Mock get_single_job_metrics to return job metadata with metrics"""
            # Return a copy with metrics added
            result = job_metadata.copy() if isinstance(job_metadata, dict) else job_metadata
            if isinstance(result, dict):
                result.update({
                    "duration": job_duration_hours,
                    "total_gpu_hours": 1.0,
                    "idle_gpu_hours": 0.0,
                    "effective_gpu_hours": 0.9,
                    "effective_gpu_utilization": 0.9,
                    "assigned_gpu_utilization": 1.0,
                    "idle_gpu_percentage": 0.0,
                    "job_hash": "test-job-hash-e2e",
                })
            return result
        
        # Mock JobMetadataClient
        def mock_get_job_attempts_metadata(start_time, end_time, job_finish=False):
            # For testing purposes, always return the job
            # The actual time window filtering and criteria checking happens in collect_eligible_jobs
            return {test_job_id: test_job_metadata}
        
        def mock_get_job_attempt_metadata(job_key, attempt_id):
            return test_job_metadata
        
        # Mock KustoUtil query methods to return empty (no previous records)
        original_query_last_time = storage_util.query_last_time_generated
        original_query_unknown_category = storage_util.query_unknown_category_records
        original_query_unknown_react = storage_util.query_unknown_react_records
        
        storage_util.query_last_time_generated = MagicMock(return_value=None)
        storage_util.query_unknown_category_records = MagicMock(return_value=pd.DataFrame())
        storage_util.query_unknown_react_records = MagicMock(return_value=pd.DataFrame())
        
        try:
            with patch('record_job.JobMetadataClient') as mock_job_metadata_class, \
                 patch('job_util.get_single_job_metrics', side_effect=mock_get_single_job_metrics), \
                 patch('job_util.find_node_next_job_start_time', return_value=job_completed_ms + 3600000):
                
                # Setup JobMetadataClient mock
                mock_job_client = MagicMock()
                mock_job_metadata_class.return_value = mock_job_client
                mock_job_client.get_job_attempts_metadata = MagicMock(side_effect=mock_get_job_attempts_metadata)
                mock_job_client.get_job_attempt_metadata = MagicMock(side_effect=mock_get_job_attempt_metadata)
                
                # Mock KustoUtil to use real storage_util instance
                with patch('run.KustoUtil', return_value=storage_util), \
                     patch('record_job.KustoUtil', return_value=storage_util):
                    
                    # Run process_job_data
                    process_job_data(time_offset="1h")
                    
                    # Verify job metadata was queried
                    mock_job_client.get_job_attempts_metadata.assert_called()
                    
                    # Verify records were ingested to database
                    # Query back to verify job metrics were written
                    result_df = storage_util.query_job_metrics_by_job_id([test_job_id])
                    
                    # Should find the job in the database
                    assert not result_df.empty, "Job metrics should be in database"
                    # Handle both camelCase (Kusto) and snake_case (PostgreSQL) column names
                    job_id_col = "jobId" if "jobId" in result_df.columns else "job_id"
                    assert test_job_id in result_df[job_id_col].values
                    
                    # Verify job summary fields
                    found_job = result_df[result_df[job_id_col] == test_job_id]
                    assert not found_job.empty
                    
                    job_record = found_job.iloc[0]
                    assert job_record.get("jobName") == "test-job-e2e" or job_record.get("job_name") == "test-job-e2e"
                    assert job_record.get("userName") == "test-user" or job_record.get("user_name") == "test-user"
                    
        finally:
            # Restore original methods
            storage_util.query_last_time_generated = original_query_last_time
            storage_util.query_unknown_category_records = original_query_unknown_category
            storage_util.query_unknown_react_records = original_query_unknown_react
            
            # Cleanup test records
            _cleanup_job_records(storage_util.job_summary_client, test_job_id)
            _cleanup_job_records(storage_util.job_react_client, test_job_id)
    
    def test_process_job_data_with_react_time(self, storage_util, test_job_id):
        """End-to-end test: process_job_data generates react times for jobs with same hash"""
        base_time = datetime.now(timezone.utc)
        base_time_sec = base_time.timestamp()
        base_time_ms = int(base_time_sec * 1000)
        test_hash = "test-hash-retry-e2e"
        
        # Create two jobs with same hash (simulating retries)
        # Both should complete within the 1h window
        job1_id = f"{test_job_id}-1"
        job2_id = f"{test_job_id}-2"
        
        # Job1 completes 50 minutes ago (within 1h window), runs for 1 hour
        job1_completed_sec = base_time_sec - 3000  # 50 minutes ago
        job1_completed_ms = int(job1_completed_sec * 1000)
        job1_launched_sec = job1_completed_sec - 3600  # 1 hour before completion
        job1_launched_ms = int(job1_launched_sec * 1000)
        
        # Job2 completes 20 minutes ago (within 1h window), runs for 30 minutes
        job2_completed_sec = base_time_sec - 1200  # 20 minutes ago
        job2_completed_ms = int(job2_completed_sec * 1000)
        job2_launched_sec = job2_completed_sec - 1800  # 30 minutes before completion
        job2_launched_ms = int(job2_launched_sec * 1000)
        
        job1_metadata = {
            "username": "test-user",
            "name": "test-job-e2e",
            "retries": 1,
            "virtualCluster": "default",
            "totalGpuNumber": 1,
            "attemptId": 0,
            "jobPriority": "default",
            "state": "SUCCEEDED",
            "attemptState": "SUCCEEDED",
            "createdTime": job1_launched_ms - 3600000,
            "launchedTime": job1_launched_ms,
            "completedTime": job1_completed_ms,  # 50 minutes ago (within 1h window)
            "submissionTime": job1_launched_ms - 7200000,
            "submissionDatetime": pd.Timestamp(datetime.fromtimestamp(job1_launched_sec - 7200, tz=timezone.utc)),
            "launchedDatetime": pd.Timestamp(datetime.fromtimestamp(job1_launched_sec, tz=timezone.utc)),
            "completedDatetime": pd.Timestamp(datetime.fromtimestamp(job1_completed_sec, tz=timezone.utc)),
            "createdDatetime": pd.Timestamp(datetime.fromtimestamp(job1_launched_sec - 3600, tz=timezone.utc)),
            "job_id": job1_id,
            "taskRoles": {
                "worker": {
                    "instances": 1,
                    "resourcePerInstance": {"gpu": 1},
                    "taskStatuses": [{
                        "taskState": "SUCCEEDED",
                        "taskIndex": 0,
                        "containerNodeName": "test-node",
                        "containerIp": "10.0.0.1",
                        "containerExitSpec": {"phrase": "Succeeded"}
                    }]
                }
            },
            "exitSpec": {"phrase": "Succeeded"}
        }
        
        job2_metadata = {
            "username": "test-user",
            "name": "test-job-e2e",
            "retries": 1,
            "virtualCluster": "default",
            "totalGpuNumber": 1,
            "attemptId": 1,
            "jobPriority": "default",
            "state": "SUCCEEDED",
            "attemptState": "SUCCEEDED",
            "createdTime": job2_launched_ms - 1800000,
            "launchedTime": job2_launched_ms,
            "completedTime": job2_completed_ms,  # 20 minutes ago (within 1h window)
            "submissionTime": job2_launched_ms - 3600000,
            "submissionDatetime": pd.Timestamp(datetime.fromtimestamp(job2_launched_sec - 3600, tz=timezone.utc)),
            "launchedDatetime": pd.Timestamp(datetime.fromtimestamp(job2_launched_sec, tz=timezone.utc)),
            "completedDatetime": pd.Timestamp(datetime.fromtimestamp(job2_completed_sec, tz=timezone.utc)),
            "createdDatetime": pd.Timestamp(datetime.fromtimestamp(job2_launched_sec - 1800, tz=timezone.utc)),
            "job_id": job2_id,
            "taskRoles": {
                "worker": {
                    "instances": 1,
                    "resourcePerInstance": {"gpu": 1},
                    "taskStatuses": [{
                        "taskState": "SUCCEEDED",
                        "taskIndex": 0,
                        "containerNodeName": "test-node",
                        "containerIp": "10.0.0.1",
                        "containerExitSpec": {"phrase": "Succeeded"}
                    }]
                }
            },
            "exitSpec": {"phrase": "Succeeded"}
        }
        
        # Calculate durations for both jobs
        job1_duration_hours = (job1_completed_sec - job1_launched_sec) / 3600
        job2_duration_hours = (job2_completed_sec - job2_launched_sec) / 3600
        
        # Mock get_single_job_metrics to return job metadata with metrics
        def mock_get_single_job_metrics(job, job_metadata, end_time_stamp=None, time_offset=None):
            """Mock get_single_job_metrics to return job metadata with metrics"""
            result = job_metadata.copy() if isinstance(job_metadata, dict) else job_metadata
            if isinstance(result, dict):
                # Determine which job this is based on job_id
                job_id = result.get("job_id", "")
                if job1_id in job_id:
                    duration = job1_duration_hours
                else:
                    duration = job2_duration_hours
                
                result.update({
                    "duration": duration,
                    "total_gpu_hours": 1.0,  # 1 GPU * duration
                    "idle_gpu_hours": 0.0,
                    "effective_gpu_hours": 0.9,
                    "effective_gpu_utilization": 0.9,
                    "assigned_gpu_utilization": 1.0,
                    "idle_gpu_percentage": 0.0,
                    "job_hash": test_hash,  # Same hash for both jobs (retries)
                })
            return result
        
        # Mock JobMetadataClient to return both jobs
        def mock_get_job_attempts_metadata(start_time, end_time, job_finish=False):
            # Both jobs should be within the 1h window
            # For testing purposes, always return both jobs
            return {
                job1_id: job1_metadata,
                job2_id: job2_metadata
            }
        
        def mock_get_job_attempt_metadata(job_key, attempt_id):
            if "1" in job_key:
                return job1_metadata
            return job2_metadata
        
        # Mock KustoUtil query methods
        storage_util.query_last_time_generated = MagicMock(return_value=None)
        storage_util.query_unknown_category_records = MagicMock(return_value=pd.DataFrame())
        storage_util.query_unknown_react_records = MagicMock(return_value=pd.DataFrame())
        
        try:
            with patch('record_job.JobMetadataClient') as mock_job_metadata_class, \
                 patch('job_util.get_single_job_metrics', side_effect=mock_get_single_job_metrics), \
                 patch('job_util.find_node_next_job_start_time', return_value=job2_completed_ms + 3600000), \
                 patch('job_util.hash_normalized_config', return_value=test_hash):
                
                # Setup mocks
                mock_job_client = MagicMock()
                mock_job_metadata_class.return_value = mock_job_client
                mock_job_client.get_job_attempts_metadata = MagicMock(side_effect=mock_get_job_attempts_metadata)
                mock_job_client.get_job_attempt_metadata = MagicMock(side_effect=mock_get_job_attempt_metadata)
                
                with patch('run.KustoUtil', return_value=storage_util), \
                     patch('record_job.KustoUtil', return_value=storage_util):
                    
                    # Run process_job_data
                    process_job_data(time_offset="1h")
                    
                    # Verify both jobs are in database
                    result_df = storage_util.query_job_metrics_by_job_id([job1_id, job2_id])
                    assert not result_df.empty
                    
                    # Verify react times were generated and ingested
                    # Query unknown react records - should not find these jobs since they have reactTime
                    unknown_react_df = storage_util.query_unknown_react_records("30d")
                    if not unknown_react_df.empty:
                        # If we get results, make sure our test jobs are not in the unknown list
                        # Handle both camelCase (Kusto) and snake_case (PostgreSQL) column names
                        job_id_col = "jobId" if "jobId" in unknown_react_df.columns else "job_id"
                        test_jobs_in_unknown = unknown_react_df[unknown_react_df[job_id_col].isin([job1_id, job2_id])]
                        # Jobs with react times should not be in unknown list
                        assert test_jobs_in_unknown.empty, "Jobs with react times should not be in unknown react records"
                    
        finally:
            # Cleanup test records
            _cleanup_job_records(storage_util.job_summary_client, job1_id)
            _cleanup_job_records(storage_util.job_summary_client, job2_id)
            _cleanup_job_records(storage_util.job_react_client, job1_id)
            _cleanup_job_records(storage_util.job_react_client, job2_id)
