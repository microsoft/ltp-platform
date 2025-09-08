# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Execution Engine for Monitor Service

Executes data collection based on specifications.
"""

import time
import logging
import re
from typing import Dict, Any
from datetime import datetime, timezone
from dataclasses import asdict

from models import DataCollectionSpec, CollectionResult
from resolver import NodeJobResolver
from data_sources import (
    PrometheusClient, JobLogsClient, NodeLogsClient, JobMetadataClient, parse_interval
)

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """Executes data collection based on specifications"""
    
    def __init__(self, prometheus_client: PrometheusClient, job_logs_client: JobLogsClient,
                 node_logs_client: NodeLogsClient, job_metadata_client: JobMetadataClient):
        self.prometheus_client = prometheus_client
        self.job_logs_client = job_logs_client
        self.node_logs_client = node_logs_client
        self.job_metadata_client = job_metadata_client
        self.resolver = NodeJobResolver(job_metadata_client)
    
    def execute_collection(self, spec: DataCollectionSpec, window_start: int = None, window_end: int = None) -> CollectionResult:
        """Execute data collection according to specification
        
        Args:
            spec: The data collection specification
            window_start: Optional start timestamp for the collection window (Unix timestamp)
            window_end: Optional end timestamp for the collection window (Unix timestamp)
        """
        start_time = time.time()
        
        result = CollectionResult(
            spec_id=spec.spec_id,
            collection_timestamp=datetime.now(timezone.utc).isoformat(),
            status="success",
            metrics_data={},
            job_logs={},
            node_logs={},
            historical_data={},
            nodes_collected={},
            collection_duration=0.0,
            errors=[]
        )
        
        try:
            # Calculate time window first
            if window_start is not None and window_end is not None:
                # Use provided window times
                start_time_ts = window_start
                end_time_ts = window_end
                logger.info(f"Using provided time window: {start_time_ts} to {end_time_ts} for spec {spec.spec_id}")
            elif window_start is None:
                # Initialize end_time_ts
                if window_end is not None:
                    end_time_ts = window_end
                else:
                    end_time_ts = int(time.time())
                
                time_offset = spec.schedule.get('interval') if spec.schedule and spec.schedule.get('interval') else spec.time_window.get('relative_start') if spec.time_window and spec.time_window.get('relative_start') else '1h'
                if not time_offset:
                    logger.error(f"Spec {spec.spec_id} is missing both schedule interval and time_window.relative_start. Cannot proceed.")
                    raise ValueError("No time window specified")
                start_time_ts = end_time_ts - parse_interval(time_offset)
                logger.info(f"Using calculated time window from schedule: {start_time_ts} to {end_time_ts} for spec {spec.spec_id}")
            else:
                logger.error(f"Spec {spec.spec_id} is missing both window_start and window_end. Cannot proceed.")
                raise ValueError("No time window specified")
            end_time_ts = int(end_time_ts)
            start_time_ts = int(start_time_ts)
            time_offset = f"{int(end_time_ts - start_time_ts)}s"
            
            result.window_start = start_time_ts
            result.window_end = end_time_ts
            result.time_offset = time_offset
            
            # Resolve target nodes and jobs
            target_nodes = {}
            target_jobs = {}
            
            if spec.target_nodes:
                target_nodes = self.resolver.resolve_nodes(spec.target_nodes.get('node_selector', {}), end_time_ts, time_offset)
                result.nodes_collected = target_nodes  # keep as dict
            
            if spec.target_jobs:
                target_jobs = self.resolver.resolve_jobs(spec.target_jobs.get('job_selector', {}), end_time_ts, time_offset)
                
            # Collect metrics
            self._collect_metrics(spec, result, target_nodes, start_time_ts, end_time_ts)
            
            # Collect logs
            self._collect_logs(spec, result, target_nodes, target_jobs, start_time_ts, end_time_ts)
            
            # Collect API data
            self._collect_api_data(spec, result, target_nodes, target_jobs)
            
            if result.errors:
                result.status = "partial" if result.metrics_data or result.job_logs or result.node_logs else "failed"
            
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
            logger.error(f"Execution failed for spec {spec.spec_id}: {e}")
        
        result.collection_duration = round(time.time() - start_time, 2)
        return result
    
    def _collect_metrics(self, spec: DataCollectionSpec, result: CollectionResult, 
                        target_nodes: dict, start_time_ts: int, end_time: int):
        """Collect metrics from Prometheus with node constraints"""
        for req in spec.metrics_requirements:
            try:
                if req.get('source') == 'prometheus':
                    query = req.get('query')
                    if target_nodes and spec.target_nodes.get('node_selector', None) is not None:
                        metric_data = self._collect_metrics_with_adaptive_batching(
                            req, query, target_nodes, start_time_ts, end_time
                        )
                    else:
                        metric_data = self._collect_metrics_simple(
                            req, query, start_time_ts, end_time
                        )
                    # Group metrics by node name
                    if target_nodes:
                        grouped_metrics = self._group_metrics_by_node(metric_data, target_nodes)
                        result.metrics_data[req['name']] = grouped_metrics
                    else:
                        result.metrics_data[req['name']] = metric_data
                else:
                    raise ValueError(f"Invalid metric source: {req.get('source')}")
            except Exception as e:
                error_msg = f"Failed to collect metric {req['name']}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

    def _collect_metrics_with_adaptive_batching(self, req: dict, query: str, target_nodes: dict, 
                                               start_time_ts: int, end_time: int) -> dict:
        """Collect metrics using adaptive batch sizing"""
        initial_batch_size = req.get('node_batch_size', 256)
        min_batch_size = req.get('min_batch_size', 16)
        
        collection_stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'nodes_requested': len(target_nodes),
            'nodes_collected': 0,
            'total_results': 0,
            'adaptive_batching_used': True
        }
        
        all_metric_data = []
        node_names = list(target_nodes.keys())
        remaining_nodes = node_names.copy()
        current_batch_size = initial_batch_size
        
        while remaining_nodes and current_batch_size >= min_batch_size:
            # Execute batch query
            batch_nodes = remaining_nodes[:current_batch_size]
            batch_ips = [target_nodes[node].get('host_ip') or target_nodes[node].get('ip') for node in batch_nodes]
            batch_query = self._build_node_filtered_query(query, batch_ips)
            
            collection_stats['total_queries'] += 1
            logger.info(f"Query {collection_stats['total_queries']}: trying batch size {current_batch_size} with {len(batch_nodes)} nodes")
            
            try:
                batch_data = self.prometheus_client.query_range(
                    query=batch_query,
                    start_time=start_time_ts,
                    end_time=end_time,
                    step=req.get('step', '30s')
                )
                
                if batch_data:
                    all_metric_data.extend(batch_data['result'])
                    collection_stats['successful_queries'] += 1
                    logger.info(f"Query {collection_stats['total_queries']} successful: {len(batch_data['result'])} results")
                    
                    # Remove successful nodes and try to increase batch size
                    remaining_nodes = remaining_nodes[current_batch_size:]

                else:
                    collection_stats['failed_queries'] += 1
                    logger.warning(f"Query {collection_stats['total_queries']} returned no data")
                    current_batch_size = max(current_batch_size // 2, min_batch_size)
                    logger.info(f"Reducing batch size to {current_batch_size}")
                    
            except Exception as e:
                collection_stats['failed_queries'] += 1
                logger.error(f"Query {collection_stats['total_queries']} failed: {e}")
                current_batch_size = max(current_batch_size // 2, min_batch_size)
                logger.info(f"Reducing batch size to {current_batch_size}")
                
                # Skip nodes if we've reached minimum batch size and still failing
                if current_batch_size == min_batch_size:
                    logger.warning(f"Skipping {len(batch_nodes)} nodes after repeated failures")
                    remaining_nodes = remaining_nodes[current_batch_size:]
                    current_batch_size = initial_batch_size
        
        collection_stats['nodes_collected'] = len(node_names) - len(remaining_nodes)
        collection_stats['total_results'] = len(all_metric_data)
        return {
            'results': all_metric_data,
            'stats': collection_stats
        }
    
    def _build_node_filtered_query(self, query: str, batch_ips: list) -> str:
        """Build a Prometheus query with node filters"""
        original_filter_regex = r'\{(.*)\}'
        original_filters = re.findall(original_filter_regex, query)
        
        node_filters = []
        for node_ip in batch_ips:
            node_filters.append(f'{node_ip}:[0-9]*')
        
        node_filter = '|'.join(node_filters)
        node_filter = f'instance=~"{node_filter}"'
        
        if 'instance=~' in query:
            match = re.search(r'instance=~["\']([^"\']*)["\']', query)
            if match:
                query = query.replace(match.group(0), node_filter)
        elif original_filters:
            for original_filter in original_filters:
                new_filter = original_filter+','+node_filter
                query = query.replace(original_filter, new_filter)
        else:
            query = query + '{' + node_filter + '}'
        
        return query
    
    def _collect_metrics_simple(self, req: dict, query: str, start_time_ts: int, end_time: int) -> dict:
        """Collect metrics without node constraints"""
        return self.prometheus_client.query_range(
            query=query,
            start_time=start_time_ts,
            end_time=end_time,
            step=req.get('step', '30s')
        )

    def _group_metrics_by_node(self, metric_data: dict, target_nodes: dict) -> dict:
        """Group metric results by node name"""
        grouped = {}
        
        # Initialize empty lists for all target nodes
        for node_name in target_nodes.keys():
            grouped[node_name] = []
        
        # Get results from metric_data
        results = metric_data.get('results', []) if isinstance(metric_data, dict) else []
        if isinstance(metric_data, dict) and 'data' in metric_data and 'result' in metric_data['data']:
            results = metric_data['data']['result']
        
        # Group results by matching node IP to node name
        for entry in results:
            instance = entry.get('metric', {}).get('instance', '')
            entry_ip = instance.split(':')[0] if ':' in instance else instance
            
            # Find the node name that matches this IP
            matched_node = None
            for node_name, node_meta in target_nodes.items():
                node_ip = node_meta.get('host_ip') or node_meta.get('ip', '')
                if node_ip == entry_ip:
                    matched_node = node_name
                    break
            
            # Add to the appropriate node's results
            if matched_node:
                grouped[matched_node].append(entry)
            else:
                # If no match found, try to match by node name
                node_name = entry.get('node_name', '')
                if node_name:
                    grouped[node_name].append(entry)
        
        # Add collection stats if available
        if isinstance(metric_data, dict) and 'stats' in metric_data:
            grouped['_collection_stats'] = metric_data['stats']
        
        return grouped
    
    def _collect_logs(self, spec: DataCollectionSpec, result: CollectionResult,
                     target_nodes: dict, target_jobs: dict, start_time_ts: int, end_time_ts: int):
        """Collect logs from various sources with appropriate time handling"""
        
        for req in spec.logs_requirements:
            try:
                if req.get('source') == 'job_logs':
                    # Job logs are stream-based and don't support time window filtering
                    # Collect current/recent logs only
                    logger.info(f"Collecting job logs for {req['name']} (no time window filtering - stream-based)")
                    if not target_jobs or len(target_jobs) == 0:
                        time_offset = f"{int(end_time_ts - start_time_ts)}s"
                        target_jobs = self.resolver.resolve_jobs({}, end_time_ts, time_offset)
                    for job_key, job_meta in target_jobs.items():
                        job_name = f'{job_meta.get("username")}~{job_meta.get("name")}'
                        log_contents = self.job_logs_client.get_job_logs(
                            job_name=job_name,
                            job_meta=job_meta,
                            tail=req.get('tail', False)
                        )
                        if log_contents:
                            # Initialize job entry in job_logs if not exists
                            if job_key not in result.job_logs:
                                result.job_logs[job_key] = {}
                            
                            for node_name, content in log_contents.items():
                                log_entries = self.job_logs_client.parse_logs_with_patterns(
                                    log_content=content,
                                    patterns=req.get('patterns', []),
                                    max_entries=req.get('max_entries')
                                )
                                if len(log_entries) > 0:
                                    result.job_logs[job_key][node_name] = log_entries
                            if len(result.job_logs[job_key]) == 0:
                                result.job_logs.pop(job_key)
                                    
                elif req.get('source') == 'node_logs':
                    # Node logs are collected per node and grouped by log requirement name
                    log_name = req['name']
                    
                    # Initialize log entry in node_logs if not exists
                    if log_name not in result.node_logs:
                        result.node_logs[log_name] = {}
                    
                    for node_name, node_meta in target_nodes.items():
                        log_entries = self.node_logs_client.collect_node_logs(
                            node_ip=node_meta.get('host_ip', ''),
                            log_paths=req.get('log_paths', []),
                            patterns=req.get('patterns', []),
                            max_entries=req.get('max_entries'),
                            tail_lines=req.get('tail_lines'),
                            start_time_ts=start_time_ts,
                            end_time_ts=end_time_ts
                        )
                        
                        # Group node logs by node name within the log requirement
                        if node_name not in result.node_logs[log_name]:
                            result.node_logs[log_name][node_name] = []
                        result.node_logs[log_name][node_name].extend([asdict(entry) for entry in log_entries])
                        
                else:
                    raise ValueError(f"Invalid log source: {req.get('source')}")
            except Exception as e:
                error_msg = f"Failed to collect logs {req['name']}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
    
    def _collect_api_data(self, spec: DataCollectionSpec, result: CollectionResult, target_nodes: dict, target_jobs: dict):
        """Collect API data with node and job constraints"""
        for req in spec.api_requirements:
            try:
                if req.get('source') == 'job_metadata':
                    # Filter job metadata by target jobs if specified
                    if target_jobs:
                        result.historical_data[req['name']] = target_jobs
                    else:
                        raise ValueError("No target jobs specified")
                else:
                    raise ValueError(f"Invalid API source: {req.get('source')}")
                    
            except Exception as e:
                error_msg = f"Failed to collect API data {req['name']}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

 