"""
Pattern Scheduler for Monitor Service

Manages scheduling of pattern-based data collection.
"""

import os
import json
import threading
import time
import logging
from typing import List, Dict, Optional
from dataclasses import asdict

from models import DataCollectionSpec, CollectionResult
from executor import ExecutionEngine
from data_sources import parse_interval

logger = logging.getLogger(__name__)

class PatternScheduler:
    """Manages scheduling of pattern-based data collection with strict timing intervals"""
    
    def __init__(self, execution_engine: ExecutionEngine, redis_client=None):
        self.execution_engine = execution_engine
        self.scheduled_threads: Dict[str, threading.Thread] = {}
        self.active_specs = {}
        self.stop_events: Dict[str, threading.Event] = {}
        
        # Redis client (passed from service_runner)
        self.redis = redis_client
        self.redis_enabled = redis_client is not None
        
        self.output_dir = os.getenv('OUTPUT_DIR', None)
        if self.output_dir and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        if self.redis_enabled:
            logger.info("Scheduler using shared Redis client")
        else:
            logger.info("Scheduler running in local-only mode (no Redis client provided)")
    
    def schedule_spec(self, spec: DataCollectionSpec):
        """Schedule a pattern-based spec for periodic execution"""
        if not spec.schedule or not spec.schedule.get('enabled', False):
            logger.warning(f"Spec {spec.spec_id} has no enabled schedule")
            return
        
        interval = parse_interval(spec.schedule.get('interval', '60s'))
        logger.info(f"Scheduling spec {spec.spec_id} every {interval} seconds")
        
        # Stop existing thread if any
        if spec.spec_id in self.scheduled_threads:
            self._stop_spec_thread(spec.spec_id)
        
        self.active_specs[spec.spec_id] = spec
        self._schedule_periodic(spec, interval)
    
    def _schedule_periodic(self, spec: DataCollectionSpec, interval: int):
        """Schedule periodic execution with strict timing intervals"""
        stop_event = threading.Event()
        self.stop_events[spec.spec_id] = stop_event
        
        def periodic_runner():
            """Runner that maintains strict timing intervals"""
            # Calculate the next execution time based on current time
            # This ensures we start at the next interval boundary
            current_time = time.time()
            next_execution = current_time + interval
            window_start = int(next_execution) - interval
            
            while not stop_event.is_set():
                try:
                    # Wait until the next scheduled execution time
                    wait_time = next_execution - time.time()
                    if wait_time > 0:
                        # Use event.wait() so we can be interrupted for stopping
                        if stop_event.wait(wait_time):
                            break  # Stop event was set
                    
                    # Check if we should still be running
                    if spec.spec_id not in self.active_specs:
                        break
                    
                    # Execute the collection
                    execution_start = time.time()
                    logger.info(f"Executing scheduled spec: {spec.spec_id} at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(execution_start))}")
                    
                    # Calculate the time window for this execution
                    # The window should cover the previous interval period
                    window_end = int(next_execution)  # Current execution time
                    # window_start = window_end - interval  # Start of the interval period
                    
                    logger.info(f"Collection window for {spec.spec_id}: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(window_start))} to {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(window_end))}")
                    
                    try:
                        result = self.execution_engine.execute_collection(spec, window_start, window_end)
                        self._write_result_to_store(result, window_start, window_end, interval)
                    except Exception as e:
                        logger.error(f"Scheduled execution failed for {spec.spec_id}: {e}")
                    
                    execution_duration = time.time() - execution_start
                    logger.debug(f"Execution of {spec.spec_id} took {execution_duration:.2f}s")
                    
                    # Calculate next execution time based on the original interval
                    # This prevents drift by always scheduling relative to the original start time
                    # next_execution += interval
                    
                    # If we're behind schedule, log a warning but continue
                    window_start = window_end 
                    if time.time() > window_end + interval:
                        logger.warning(f"Spec {spec.spec_id} is behind schedule. Execution took {execution_duration:.2f}s, interval is {interval}s")
                        # Reset to current time + interval to catch up
                        next_execution = time.time() + interval
                    else:
                        next_execution += interval
                except Exception as e:
                    logger.error(f"Unexpected error in periodic runner for {spec.spec_id}: {e}")
                    # Wait a bit before retrying to avoid tight loops
                    time.sleep(1)
                    next_execution = time.time() + interval
        
        # Start the periodic runner thread
        thread = threading.Thread(
            target=periodic_runner,
            name=f"PatternScheduler-{spec.spec_id}",
            daemon=True
        )
        thread.start()
        self.scheduled_threads[spec.spec_id] = thread
    
    def _stop_spec_thread(self, spec_id: str):
        """Stop a specific spec's thread"""
        if spec_id in self.stop_events:
            self.stop_events[spec_id].set()
        
        if spec_id in self.scheduled_threads:
            thread = self.scheduled_threads[spec_id]
            if thread.is_alive():
                thread.join(timeout=5)  # Wait up to 5 seconds for graceful shutdown
                if thread.is_alive():
                    logger.warning(f"Thread for spec {spec_id} did not stop gracefully")
        
        # Clean up
        self.scheduled_threads.pop(spec_id, None)
        self.active_specs.pop(spec_id, None)
        self.stop_events.pop(spec_id, None)
    
    def _write_result_to_store(self, result: CollectionResult, window_start: int = None, window_end: int = None, interval: int = None):
        """Write result to storage (Redis Streams if enabled, always write to local file)"""
        # Prepare result data with collection window info if available
        result_data = asdict(result)
        if window_start and window_end and interval:
            result_data['collection_window'] = {
                'start_time': window_start,
                'end_time': window_end,
                'interval_seconds': interval,
                'start_time_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(window_start)),
                'end_time_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(window_end))
            }

        if self.output_dir:
            try:
                redis_key_timestamp = result.collection_timestamp if hasattr(result, 'collection_timestamp') else time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime())
                stream_result = {
                    'pattern_id': result.spec_id,
                    'timestamp': redis_key_timestamp,
                    'result': json.dumps(result_data),
                    'source': 'scheduled_pattern'  # Distinguish from on-demand requests
                }
                output_file = os.path.join(self.output_dir, f'result_{result.spec_id}_{redis_key_timestamp}.json')
                with open(output_file, 'w') as f:
                    json.dump(stream_result, f)
                logger.debug(f"Wrote backup file for {result.spec_id}")
            except Exception as e:
                logger.error(f"Failed to write backup file: {e}")
        
        # Write to Redis Streams only if Redis client is available
        if self.redis_enabled and self.redis:
            try:
                self.redis.xadd('monitor_results', stream_result)
                # Optionally publish notification
                self.redis.publish('monitor_results', f"pattern:{result.spec_id}:{redis_key_timestamp}")
                logger.info(f"[Redis] Wrote scheduled result to monitor_results stream for {result.spec_id}")
            except Exception as e:
                logger.error(f"[Redis] Failed to write result to stream: {e}")
        else:
            logger.info(f"[Local] Result saved to local file for {result.spec_id} (Redis disabled)")
        
        # Log result summary
        logger.info(f"Collection result for {result.spec_id}:")
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Duration: {result.collection_duration}s")
        logger.info(f"  Nodes: {result.nodes_collected}")
        logger.info(f"  Metrics collected: {list(result.metrics_data.keys())}")
        logger.info(f"  Job logs: {len(result.job_logs)} jobs")
        logger.info(f"  Node logs: {len(result.node_logs)} log types")
        logger.info(f"  Errors: {result.errors}")
        
        if window_start and window_end and interval:
            logger.info(f"  Collection window: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(window_start))} to {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(window_end))} (interval: {interval}s)")
        


    
    def stop_all(self):
        """Stop all scheduled tasks"""
        # Set stop events for all threads
        for stop_event in self.stop_events.values():
            stop_event.set()
        
        # Wait for all threads to finish
        for spec_id, thread in self.scheduled_threads.items():
            if thread.is_alive():
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(f"Thread for spec {spec_id} did not stop gracefully")
        
        # Clean up
        self.scheduled_threads.clear()
        self.active_specs.clear()
        self.stop_events.clear()
        logger.info("All scheduled tasks stopped")
    
    def get_schedule_status(self) -> Dict[str, dict]:
        """Get status of all scheduled specs"""
        status = {}
        for spec_id, spec in self.active_specs.items():
            thread = self.scheduled_threads.get(spec_id)
            interval = parse_interval(spec.schedule.get('interval', '60s'))
            current_time = time.time()
            
            # Calculate next expected execution time
            # This is a rough estimate based on the last execution
            next_execution_estimate = current_time + interval
            
            status[spec_id] = {
                'spec_id': spec_id,
                'interval': spec.schedule.get('interval', '60s'),
                'interval_seconds': interval,
                'thread_alive': thread.is_alive() if thread else False,
                'active': spec_id in self.active_specs,
                'next_execution_estimate': next_execution_estimate,
                'next_execution_estimate_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(next_execution_estimate))
            }
        return status 