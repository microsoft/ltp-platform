# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Service Runner for Monitor Service

Handles service initialization, configuration loading, and running.
"""

import os
import yaml
import time
import logging
import threading
import redis
import json
from typing import Dict
from dataclasses import asdict

from monitor_service import MonitorService
from models import DataCollectionSpec
from scheduler import PatternScheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ServiceRunner:
    """Handles service initialization and running"""
    
    def __init__(self, specs_dir: str, redis_enabled=True, redis_host='localhost', redis_port=6379, redis_db=0):
        self.specs_dir = specs_dir
        self.specs: Dict[str, DataCollectionSpec] = {}
        self.monitor_service = None
        
        # Redis configuration
        self.redis_enabled = redis_enabled
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_client = None
        
        # Threading control
        self.shutdown_event = threading.Event()
        self.request_listener_thread = None
        
        # Initialize Redis only if enabled
        if self.redis_enabled:
            self._init_redis()
        else:
            logger.info("Redis disabled - running in local-only mode")
        
        # Initialize monitor service with Redis client
        self.monitor_service = MonitorService(redis_client=self.redis_client)
        
        # Load specifications
        self.load_specs()
    
    def _init_redis(self):
        """Initialize Redis connection and streams"""
        try:
            self.redis_client = redis.StrictRedis(
                host=self.redis_host, 
                port=self.redis_port, 
                db=self.redis_db, 
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis connection established: {self.redis_host}:{self.redis_port}")
            
            # Create consumer group for collection requests
            try:
                self.redis_client.xgroup_create('collection_requests', 'monitor_group', id='0', mkstream=True)
                logger.info("Created Redis consumer group for collection_requests")
            except redis.ResponseError as e:
                if 'BUSYGROUP' not in str(e):
                    raise
                logger.info("Redis consumer group already exists")
                
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            logger.warning("Continuing in local-only mode")
            self.redis_enabled = False
            self.redis_client = None
    
    def _collection_request_listener(self):
        """Background thread to listen for collection requests from Redis Stream"""
        if not self.redis_enabled or not self.redis_client:
            logger.warning("Redis not enabled - request listener will not start")
            return
            
        STREAM_KEY = 'collection_requests'
        GROUP = 'monitor_group'
        CONSUMER = 'monitor1'
        RESULT_STREAM = 'monitor_results'
        
        logger.info("Starting collection request listener...")
        
        while not self.shutdown_event.is_set():
            try:
                # Read new requests from the stream
                events = self.redis_client.xreadgroup(
                    GROUP, CONSUMER, {STREAM_KEY: '>'}, 
                    count=1, block=5000  # 5 second timeout
                )
                
                for stream, messages in events:
                    for msg_id, fields in messages:
                        if self.shutdown_event.is_set():
                            break
                            
                        try:
                            # Parse the request
                            spec_json = fields['spec']
                            request_id = fields['request_id']
                            requested_by = fields.get('requested_by', 'unknown')
                            
                            logger.info(f"Processing collection request {request_id} from {requested_by}")
                            
                            # Parse and validate the spec
                            spec_dict = json.loads(spec_json)
                            
                            # Process using the main monitor service
                            result_obj = self.monitor_service.process_specification(spec_dict)
                            
                            # Write result to Redis stream
                            result = {
                                'pattern_id': result_obj.spec_id,
                                'timestamp': result_obj.collection_timestamp,
                                'result': json.dumps(asdict(result_obj)),
                                'request_id': request_id,
                                'status': result_obj.status
                            }
                            
                            self.redis_client.xadd(RESULT_STREAM, result)
                            logger.info(f"Completed collection request {request_id}, status: {result_obj.status}")
                            
                            # Acknowledge the message
                            self.redis_client.xack(STREAM_KEY, GROUP, msg_id)
                            
                            # Delete the processed message from the stream
                            self.redis_client.xdel(STREAM_KEY, msg_id)
                            logger.debug(f"Deleted processed request {msg_id} from {STREAM_KEY}")
                            
                        except Exception as e:
                            logger.error(f"Error processing collection request {msg_id}: {e}")
                            # Still acknowledge to avoid reprocessing
                            self.redis_client.xack(STREAM_KEY, GROUP, msg_id)
                            # Delete the problematic message from the stream
                            self.redis_client.xdel(STREAM_KEY, msg_id)
                            logger.debug(f"Deleted problematic request {msg_id} from {STREAM_KEY}")
                            
            except redis.ConnectionError as e:
                if not self.shutdown_event.is_set():
                    logger.error(f"Redis connection error in request listener: {e}")
                    time.sleep(5)  # Wait before retry
            except Exception as e:
                if not self.shutdown_event.is_set():
                    logger.error(f"Unexpected error in request listener: {e}")
                    time.sleep(1)
        
        logger.info("Collection request listener stopped")
    
    def load_specs(self):
        """Load all YAML specs from the specs directory"""
        if not os.path.exists(self.specs_dir):
            logger.error(f"Specs directory not found: {self.specs_dir}")
            return
        
        for fname in os.listdir(self.specs_dir):
            if fname.endswith('.yaml') or fname.endswith('.yml'):
                path = os.path.join(self.specs_dir, fname)
                try:
                    with open(path, 'r') as f:
                        spec_dict = yaml.safe_load(f)
                        spec = DataCollectionSpec(spec_dict)
                        
                        # Validate spec
                        validation_result = self.monitor_service.validator.validate(spec)
                        if validation_result['is_valid']:
                            self.specs[spec.spec_id] = spec
                            logger.info(f"Loaded valid spec: {spec.spec_id}")
                        else:
                            logger.error(f"Invalid spec {fname}: {validation_result['errors']}")
                            
                except Exception as e:
                    logger.error(f"Error loading spec {fname}: {e}")
        
        logger.info(f"Successfully loaded {len(self.specs)} valid specs: {list(self.specs.keys())}")
    
    def start_monitoring(self):
        """Start the monitoring service - schedule all pattern-based specs"""
        logger.info("Starting Monitor Service...")
        
        pattern_specs = [spec for spec in self.specs.values() 
                        if spec.request_type == "pattern"]
        # sort the pattern specs by priority from high to low and schedule interval from small to large
        priority_order = {'high': 1, 'medium': 2, 'low': 3}
        pattern_specs.sort(key=lambda x: (priority_order[x.priority], x.schedule.get('interval', 0)))
        
        for spec in pattern_specs:
            try:
                result = self.monitor_service.process_specification(spec.raw)
                logger.info(f"Processed pattern spec {spec.spec_id}: {result.status}")
            except Exception as e:
                logger.error(f"Failed to process spec {spec.spec_id}: {e}")
        
        logger.info(f"Processed {len(pattern_specs)} pattern-based specs")
    
    def start_request_listener(self):
        """Start the Redis request listener in a background thread"""
        if not self.redis_enabled:
            logger.info("Redis disabled - skipping request listener")
            return
            
        if self.request_listener_thread is not None:
            logger.warning("Request listener already started")
            return
            
        self.request_listener_thread = threading.Thread(
            target=self._collection_request_listener,
            name="CollectionRequestListener",
            daemon=True
        )
        self.request_listener_thread.start()
        logger.info("Collection request listener started")
    
    def run(self):
        """Run the service"""
        try:
            # Start monitoring
            self.start_monitoring()
            
            # Start Redis request listener (only if Redis is enabled)
            self.start_request_listener()
            
            logger.info("Monitor Service is running. Press Ctrl+C to exit.")
            logger.info("Available specs:")
            for spec_id, spec in self.specs.items():
                logger.info(f"  - {spec_id} ({spec.request_type})")
            
            if self.redis_enabled:
                logger.info("Listening for collection requests on Redis stream 'collection_requests'")
            else:
                logger.info("Running in local-only mode (Redis disabled)")
            
            # Keep running
            while not self.shutdown_event.is_set():
                time.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("Shutting down Monitor Service...")
            self.shutdown()
        except Exception as e:
            logger.error(f"Service error: {e}")
            self.shutdown()
    
    def shutdown(self):
        """Graceful shutdown of the service"""
        logger.info("Initiating graceful shutdown...")
        
        # Signal shutdown to all threads
        self.shutdown_event.set()
        
        # Wait for request listener thread to finish
        if self.request_listener_thread and self.request_listener_thread.is_alive():
            logger.info("Waiting for request listener to stop...")
            self.request_listener_thread.join(timeout=10)
            if self.request_listener_thread.is_alive():
                logger.warning("Request listener did not stop gracefully")
        
        # Shutdown monitor service
        if hasattr(self.monitor_service, 'shutdown'):
            self.monitor_service.shutdown()
        
        # Close Redis connection
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
        
        logger.info("Shutdown complete")

def main():
    """Main execution function"""
    # Get configuration from environment or use defaults
    redis_enabled = os.getenv('REDIS_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))
    
    specs_dir = os.path.join(os.path.dirname(__file__), '../config_specs/')
    
    runner = ServiceRunner(
        specs_dir=specs_dir,
        redis_enabled=redis_enabled,
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db
    )
    runner.run()

if __name__ == "__main__":
    main() 