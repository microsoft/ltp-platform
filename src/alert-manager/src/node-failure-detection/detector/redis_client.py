"""
Redis Client for Detector Service

Handles all Redis Stream operations for the detector:
- Sending collection requests to monitor
- Consuming monitor results
"""

import redis
import json
import uuid
import time
import os
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

class RedisClient:
    """Handles Redis Stream operations for the detector service"""
    
    def __init__(self, host='localhost', port=6379, db=0):
        self.host = host
        self.port = port
        self.db = db
        self.redis = None
        self.connected = False
        self.consume_batch_size = os.getenv('CONSUME_BATCH_SIZE', 1)
        self.consume_timeout = os.getenv('CONSUME_TIMEOUT', 5000)
        
        
    def connect(self) -> bool:
        """Connect to Redis and create necessary consumer groups"""
        try:
            self.redis = redis.StrictRedis(
                host=self.host, 
                port=self.port, 
                db=self.db, 
                decode_responses=True
            )
            # Test connection
            self.redis.ping()
            self.connected = True
            logger.info(f"Redis connection established: {self.host}:{self.port}")
            
            # Create consumer group for monitor results
            try:
                self.redis.xgroup_create('monitor_results', 'detector_group', id='0', mkstream=True)
                logger.info("Created Redis consumer group for monitor_results")
            except redis.ResponseError as e:
                if 'BUSYGROUP' not in str(e):
                    raise
                logger.debug("Redis consumer group already exists")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Close Redis connection"""
        if self.redis:
            try:
                self.redis.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
        self.connected = False
    
    def send_collection_request(self, spec_dict: Dict[str, Any]) -> Optional[str]:
        """Send a collection request to the monitor via Redis Stream"""
        if not self.connected or not self.redis:
            logger.error("Cannot send collection request - Redis not connected")
            return None
            
        request_id = str(uuid.uuid4())
        request = {
            'request_id': request_id,
            'spec': json.dumps(spec_dict),
            'requested_by': 'detector_service',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        try:
            self.redis.xadd('collection_requests', request)
            logger.info(f"Sent collection request with request_id: {request_id}")
            return request_id
        except Exception as e:
            logger.error(f"Failed to send collection request: {e}")
            return None
    
    def wait_for_collection_result(self, request_id: str, timeout_seconds: int = 60) -> Optional[Dict[str, Any]]:
        """Wait for a specific collection result by request_id"""
        if not self.connected or not self.redis:
            return None
            
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                # Read from monitor_results stream looking for our request_id
                events = self.redis.xread({'monitor_results': '0'}, block=self.consume_timeout, count=self.consume_batch_size)
                for stream, messages in events:
                    for msg_id, fields in messages:
                        if fields.get('request_id') == request_id:
                            logger.info(f"Received result for request_id {request_id}")
                            try:
                                json.loads(fields.get('result', '{}'))
                                # Delete the message after successful consumption
                                self.redis.xdel('monitor_results', msg_id)
                                return fields
                            except Exception as e:
                                logger.error(f"Failed to parse result JSON: {e}")
                                logger.info(f"Error result: {fields}")
                                # Still delete the problematic message
                                try:
                                    self.redis.xdel('monitor_results', msg_id)
                                except Exception as e:
                                    logger.error(f"Failed to delete problematic message {msg_id}: {e}")
                                return None
            except Exception as e:
                logger.error(f"Error waiting for result: {e}")
                break
            time.sleep(1)
        
        logger.warning(f"Timeout waiting for result {request_id}")
        return None
    
    def consume_monitor_results(self, message_handler: Callable[[str, Dict[str, Any]], None], 
                              consumer_name: str = 'detector1') -> None:
        """
        Consume monitor results and call handler for each message.
        This is a blocking call that runs until an exception occurs.
        
        Args:
            message_handler: Function to call with (message_id, fields) for each message
            consumer_name: Name of this consumer instance
        """
        if not self.connected or not self.redis:
            logger.error("Cannot consume monitor results - Redis not connected")
            return
            
        GROUP = 'detector_group'
        logger.info(f"Starting monitor results consumer: {consumer_name}")
        

        while True:
            # Read new results from the stream
            try:
                events = self.redis.xreadgroup(
                    GROUP, consumer_name, {'monitor_results': '>'}, 
                    count=1, block=5000  # 5 second timeout
                )
            except redis.ConnectionError as e:
                logger.error(f"Redis connection error in consumer: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in consumer: {e}")
                raise
            for stream, messages in events:
                for msg_id, fields in messages:
                    try:
                        # Skip if this is a response to our own investigation request
                        if fields.get('request_id'):
                            # xack the message to remove it from the group
                            self.redis.xack('monitor_results', GROUP, msg_id)
                            # Delete the message from the stream
                            self.redis.xdel('monitor_results', msg_id)
                            continue
                        
                        # Call the message handler
                        message_handler(msg_id, fields)
                        
                        # Acknowledge the message
                        self.redis.xack('monitor_results', GROUP, msg_id)
                        
                        # Delete the processed message from the stream
                        self.redis.xdel('monitor_results', msg_id)
                        logger.debug(f"Deleted processed message {msg_id} from monitor_results")
                        
                    except Exception as e:
                        logger.error(f"Error processing monitor result {msg_id}: {e}")
                        logger.info(f"Error result: {fields}")
                        try:
                            # Still acknowledge to avoid reprocessing
                            self.redis.xack('monitor_results', GROUP, msg_id)
                            # Delete the problematic message from the stream
                            self.redis.xdel('monitor_results', msg_id)
                        except Exception as e:
                            logger.error(f"Failed to delete problematic message {msg_id}: {e}")
                            

    
    def health_check(self) -> Dict[str, Any]:
        """Check Redis connection health"""
        if not self.connected or not self.redis:
            return {
                "connected": False,
                "host": self.host,
                "port": self.port,
                "error": "Not connected"
            }
        
        try:
            # Test with a simple ping
            self.redis.ping()
            return {
                "connected": True,
                "host": self.host,
                "port": self.port,
                "db": self.db
            }
        except Exception as e:
            return {
                "connected": False,
                "host": self.host,
                "port": self.port,
                "error": str(e)
            }
