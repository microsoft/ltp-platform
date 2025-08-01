"""
Monitor Listener - Handles consuming monitor results and triggering analysis

Listens for monitor results from Redis Streams and coordinates with 
AnalysisExecutor to run pattern analysis and publish detection events.
"""

import threading
import logging
from typing import Dict, Any, Optional, Callable

from redis_client import RedisClient
from analysis_executor import AnalysisExecutor

logger = logging.getLogger(__name__)

class MonitorListener:
    """Handles consuming monitor results and triggering analysis"""
    
    def __init__(self, redis_client: RedisClient, analysis_executor: AnalysisExecutor):
        self.redis_client = redis_client
        self.analysis_executor = analysis_executor
        self.is_running = False
        self.listener_thread = None
        self.shutdown_event = threading.Event()
        
    def start(self, consumer_name: str = 'detector1') -> bool:
        """
        Start listening for monitor results in a background thread.
        
        Args:
            consumer_name: Name of this consumer instance
            
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("Monitor listener is already running")
            return False
        
        if not self.redis_client.connected:
            logger.error("Cannot start monitor listener - Redis not connected")
            return False
        
        self.is_running = True
        self.shutdown_event.clear()
        
        # Start listener thread
        self.listener_thread = threading.Thread(
            target=self._listen_loop,
            args=(consumer_name,),
            name=f"MonitorListener-{consumer_name}",
            daemon=True
        )
        self.listener_thread.start()
        
        logger.info(f"Monitor listener started with consumer name: {consumer_name}")
        return True
    
    def stop(self, timeout_seconds: int = 10) -> bool:
        """
        Stop the monitor listener.
        
        Args:
            timeout_seconds: Maximum time to wait for graceful shutdown
            
        Returns:
            True if stopped gracefully, False if forced
        """
        if not self.is_running:
            return True
        
        logger.info("Stopping monitor listener...")
        self.shutdown_event.set()
        
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=timeout_seconds)
            if self.listener_thread.is_alive():
                logger.warning("Monitor listener did not stop gracefully")
                return False
            
        self.is_running = False
        logger.info("Monitor listener stopped")
        return True
    
    def _listen_loop(self, consumer_name: str):
        """Main listening loop that runs in the background thread"""
        logger.info("Monitor listener loop started")
        
        try:
            # Create message handler
            def handle_message(msg_id: str, fields: Dict[str, Any]):
                if self.shutdown_event.is_set():
                    return
                
                self._process_monitor_result(msg_id, fields)
            
            # Start consuming (this blocks until exception or shutdown)
            self.redis_client.consume_monitor_results(handle_message, consumer_name)
            
        except Exception as e:
            if not self.shutdown_event.is_set():
                logger.error(f"Monitor listener error: {e}")
            else:
                logger.debug("Monitor listener stopped due to shutdown signal")
        finally:
            self.is_running = False
            logger.info("Monitor listener loop ended")
    
    def _process_monitor_result(self, msg_id: str, fields: Dict[str, Any]):
        """Process a single monitor result message"""
        try:
            # Extract pattern_id
            pattern_id = fields.get('pattern_id')
            if not pattern_id:
                logger.warning(f"No pattern_id in monitor result {msg_id}")
                return
            
            # Parse result data
            result_data = fields
            if 'result' in fields:
                try:
                    import json
                    result_data = json.loads(fields['result'])
                except Exception as e:
                    logger.error(f"Failed to parse result JSON for {pattern_id}: {e}")
                    return
            
            logger.debug(f"Processing monitor result for pattern {pattern_id}")
            
            # Run analysis
            analysis_result = self.analysis_executor.analyze(result_data, msg_id)
            
            if analysis_result:
                # Publish detection event using analysis executor
                self.analysis_executor.publish_detection_event(analysis_result)
            else:
                logger.warning(f"Analysis failed for pattern {pattern_id}")
                
        except Exception as e:
            logger.error(f"Error processing monitor result {msg_id}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the monitor listener"""
        return {
            "is_running": self.is_running,
            "thread_alive": self.listener_thread.is_alive() if self.listener_thread else False,
            "redis_connected": self.redis_client.connected,
            "shutdown_requested": self.shutdown_event.is_set()
        } 