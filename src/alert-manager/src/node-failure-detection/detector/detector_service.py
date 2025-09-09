# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Detector Service - Main orchestrator for node failure detection

Coordinates pattern loading, Redis communication, analysis execution, 
and monitor result listening using focused, single-responsibility components.
"""

import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List

from redis_client import RedisClient
from analysis_executor import AnalysisExecutor
from monitor_listener import MonitorListener
from pattern_registry import pattern_registry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DetectorService:
    """Main detector service that orchestrates all detection functionality"""
    
    def __init__(self, redis_enabled=True, redis_host='localhost', redis_port=6379, redis_db=0):
        self.redis_enabled = redis_enabled
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        
        # Service state
        self.is_running = False
        self.shutdown_event = threading.Event()
        
        # Initialize components
        self.redis_client = None
        self.analysis_executor = AnalysisExecutor()
        self.monitor_listener = None
        
        # Initialize Redis if enabled
        if self.redis_enabled:
            self.redis_client = RedisClient(redis_host, redis_port, redis_db)
            self.monitor_listener = MonitorListener(self.redis_client, self.analysis_executor)
        
        # Load all patterns
        self._load_patterns()
        
        logger.info("Detector Service initialized")
    
    def _load_patterns(self):
        """Load all pattern modules"""
        loaded_patterns = pattern_registry.load_all_patterns()
        logger.info(f"Loaded {len(loaded_patterns)} patterns: {loaded_patterns}")
    
    def trigger_investigation(self, investigation_spec: Dict[str, Any]) -> Optional[str]:
        """
        Trigger an on-demand investigation by sending a collection request to the monitor.
        
        Args:
            investigation_spec: DataCollectionSpec dict for the investigation
            
        Returns:
            request_id if successful, None if failed
        """
        if not self.redis_enabled or not self.redis_client:
            logger.warning("Cannot trigger investigation - Redis not enabled")
            return None
        
        # Ensure this is marked as an investigation
        investigation_spec['request_type'] = 'investigation'
        investigation_spec['priority'] = investigation_spec.get('priority', 'high')
        
        logger.info(f"Triggering investigation: {investigation_spec.get('spec_id', 'unknown')}")
        request_id = self.redis_client.send_collection_request(investigation_spec)
        
        if request_id:
            logger.info(f"Investigation request sent with ID: {request_id}")
        else:
            logger.error("Failed to send investigation request")
        
        return request_id
    
    def wait_for_investigation_result(self, request_id: str, timeout_seconds: int = 120) -> Optional[Dict[str, Any]]:
        """
        Wait for an investigation result and analyze it.
        
        Args:
            request_id: The request ID to wait for
            timeout_seconds: Maximum time to wait for the result
            
        Returns:
            Analysis result if successful, None if failed or timeout
        """
        if not self.redis_enabled or not self.redis_client:
            logger.error("Cannot wait for investigation result - Redis not enabled")
            return None
        
        logger.info(f"Waiting for investigation result: {request_id}")
        
        # Wait for the collection result
        collection_result = self.redis_client.wait_for_collection_result(request_id, timeout_seconds)
        if not collection_result:
            logger.error(f"No collection result received for request {request_id}")
            return None
        
        # Run analysis using the analysis executor
        analysis_result = self.analysis_executor.analyze(collection_result, request_id)
        
        if analysis_result:
            # Publish the detection event using analysis executor
            success = self.analysis_executor.publish_detection_event(analysis_result)
            if success:
                logger.info(f"Investigation analysis completed: {analysis_result.get('status')}")
            else:
                logger.warning("Failed to publish detection event for investigation")
        else:
            logger.error(f"Analysis failed for investigation {request_id}")
        
        return analysis_result
    
    def get_pattern_status(self) -> Dict[str, Any]:
        """Get status of all registered patterns"""
        return pattern_registry.get_status()
    
    def start(self):
        """Start the detector service"""
        if self.is_running:
            logger.warning("Detector Service is already running")
            return
        
        logger.info("Starting Detector Service...")
        self.is_running = True
        
        try:
            # Connect to Redis if enabled
            if self.redis_enabled and self.redis_client:
                if not self.redis_client.connect():
                    logger.error("Failed to connect to Redis")
                    if not self.redis_enabled:
                        logger.info("Continuing in local-only mode")
                    else:
                        logger.error("Cannot start detector service without Redis")
                        return
                
                # Start monitor listener
                if self.monitor_listener:
                    if not self.monitor_listener.start():
                        logger.error("Failed to start monitor listener")
                        return
            
            # Print status
            self._print_startup_status()
            
            # Main service loop
            while not self.shutdown_event.is_set():
                time.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.shutdown()
        except Exception as e:
            logger.error(f"Detector Service error: {e}")
            self.shutdown()
    
    def shutdown(self):
        """Graceful shutdown of the detector service"""
        if not self.is_running:
            return
        
        logger.info("Shutting down Detector Service...") 
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Stop monitor listener
        if self.monitor_listener:
            self.monitor_listener.stop()
        
        # Disconnect from Redis
        if self.redis_client:
            self.redis_client.disconnect()
            
        self.is_running = False
        
        logger.info("Detector Service shutdown complete")
    
    def _print_startup_status(self):
        """Print startup status information"""
        logger.info("Detector Service Configuration:")
        logger.info(f"  Redis Enabled: {self.redis_enabled}")
        if self.redis_enabled:
            logger.info(f"  Redis Host: {self.redis_host}:{self.redis_port}")
            logger.info(f"  Redis DB: {self.redis_db}")
        
        health = self.health_check()
        logger.info(f"Loaded {health['patterns']['total_patterns']} patterns:")
        for pattern in health['patterns']['patterns']:
            schedule_info = pattern['schedule'] if pattern['schedule'] != 'event-driven' else 'on-demand'
            logger.info(f"  - {pattern['pattern_id']} ({schedule_info})")
        
        if self.redis_enabled:
            if self.redis_client and self.redis_client.connected:
                logger.info("Listening for monitor results on Redis stream 'monitor_results'")
            else:
                logger.warning("Redis connection failed - running in local-only mode")
        else:
            logger.info("Running in local-only mode (Redis disabled)")
    
    def health_check(self) -> Dict[str, Any]:
        """Get health status of the detector service"""
        redis_health = None
        if self.redis_client:
            redis_health = self.redis_client.health_check()
        
        monitor_listener_status = None
        if self.monitor_listener:
            monitor_listener_status = self.monitor_listener.get_status()
        
        return {
            "service": "detector",
            "status": "running" if self.is_running else "stopped",
            "redis_enabled": self.redis_enabled,
            "redis": redis_health,
            "monitor_listener": monitor_listener_status,
            "patterns": self.get_pattern_status()
        }

def main():
    """Main execution function"""
    # Get configuration from environment
    redis_enabled = os.getenv('REDIS_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))
    
    # Create and start detector service
    detector = DetectorService(
        redis_enabled=redis_enabled,
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db
    )
    
    # Start the service
    detector.start()

if __name__ == "__main__":
    main() 