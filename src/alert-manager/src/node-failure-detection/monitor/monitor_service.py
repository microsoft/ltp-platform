# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Main Monitor Service

The central orchestrator for the Monitor Service that coordinates all components.
"""

import logging
from typing import Dict, Any

from models import DataCollectionSpec, CollectionResult
from validator import SpecificationValidator
from scheduler import PatternScheduler
from executor import ExecutionEngine
from data_sources import (
    PrometheusClient, JobLogsClient, NodeLogsClient, JobMetadataClient
)

logger = logging.getLogger(__name__)

class MonitorService:
    """Main Monitor Service orchestrator"""
    
    def __init__(self, redis_client=None):
        # Initialize data source clients
        self.prometheus_client = PrometheusClient()
        self.job_logs_client = JobLogsClient()
        self.node_logs_client = NodeLogsClient()
        self.job_metadata_client = JobMetadataClient()
        
        # Initialize service components
        self.validator = SpecificationValidator()
        self.executor = ExecutionEngine(
            prometheus_client=self.prometheus_client,
            job_logs_client=self.job_logs_client,
            node_logs_client=self.node_logs_client,
            job_metadata_client=self.job_metadata_client
        )
        self.scheduler = PatternScheduler(execution_engine=self.executor, redis_client=redis_client)
        
        logger.info("Monitor Service initialized")
    
    def process_specification(self, spec_dict: Dict[str, Any]) -> CollectionResult:
        """Main entry point for processing data collection specifications"""
        spec = DataCollectionSpec(spec_dict)
        
        # Validate specification
        validation_result = self.validator.validate(spec)
        if not validation_result['is_valid']:
            logger.error(f"Specification validation failed: {validation_result['errors']}")
            return self._create_error_result(spec, validation_result['errors'])
        
        # Log warnings if any
        if validation_result['warnings']:
            logger.warning(f"Specification warnings: {validation_result['warnings']}")
        
        # Process based on request type
        if spec.request_type == "pattern":
            return self._process_pattern_request(spec)
        elif spec.request_type == "investigation":
            return self._process_investigation_request(spec)
        else:
            error_msg = f"Invalid request type: {spec.request_type}"
            logger.error(error_msg)
            return self._create_error_result(spec, [error_msg])
    
    def _process_pattern_request(self, spec: DataCollectionSpec) -> CollectionResult:
        """Process pattern-based data collection request"""
        # Schedule for continuous monitoring
        if spec.schedule and spec.schedule.get('enabled', False):
            logger.info(f"Scheduling pattern {spec.spec_id} for continuous monitoring")
            self.scheduler.schedule_spec(spec)
        
        # Execute immediate collection
        logger.info(f"Executing immediate collection for pattern {spec.spec_id}")
        result = self.executor.execute_collection(spec)
        # Write immediate collection result to store using scheduler's method
        self.scheduler._write_result_to_store(result, result.window_start, result.window_end, result.time_offset)
        return result
    
    def _process_investigation_request(self, spec: DataCollectionSpec) -> CollectionResult:
        """Process investigation-based data collection request"""
        logger.info(f"Executing investigation collection for {spec.spec_id}")
        result = self.executor.execute_collection(spec)
        self.scheduler._write_result_to_store(result, result.window_start, result.window_end, result.time_offset)
        return result

    def shutdown(self):
        """Shutdown the monitor service"""
        logger.info("Shutting down Monitor Service")
        self.scheduler.stop_all()
        logger.info("Monitor Service shutdown complete") 