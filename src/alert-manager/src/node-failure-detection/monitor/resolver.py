# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Node and Job Resolver for Monitor Service

Resolves target nodes and jobs based on selectors.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from data_sources import JobMetadataClient, PrometheusClient, parse_interval

logger = logging.getLogger(__name__)

class NodeJobResolver:
    """Resolves target nodes and jobs based on selectors"""
    
    def __init__(self, job_metadata_client: JobMetadataClient):
        self.job_metadata_client = job_metadata_client
        
        
    def filter_node_state(self, start_time, end_time, node_state={}) -> bool:
        filter_key = 'node_name!~"aks-.*"'
        if node_state.get('schedulable'):
            filter_key += ',unschedulable="false"'
        if node_state.get('available'):
            filter_key += ',ready="true"'
        if node_state.get('job_status'):
            filter_key += ',virtual_cluster=~".+"'
        
        
        query = (
            'pai_node_count{' + filter_key + '}'
        )
        
        response = PrometheusClient().query_range(query, start_time, end_time)
        records = {}
        if response is None:
            return {}
        for record in response['result']:
            host_ip = record["metric"]["host_ip"]
            node_name = record["metric"]["node_name"]
            unschedulable = record["metric"]["unschedulable"]
            ready = record["metric"]["ready"]
            records[node_name] = {
                "host_ip": host_ip,
                "unschedulable": unschedulable,
                "available": ready
            }
        return records
    
    def resolve_nodes(self, node_selector: Dict[str, Any], end_time_stamp, time_offset) -> dict:
        """Resolve nodes based on selector criteria"""
        start_time_stamp = end_time_stamp - parse_interval(time_offset)
        filtered_nodes = self.filter_node_state(start_time_stamp, end_time_stamp, node_selector)
        if node_selector.get('job'): 
            filtered_job_nodes = self.resolve_jobs(node_selector.get('job'), end_time_stamp, time_offset)
            # join filtered_nodes and filtered_job_nodes
            filtered_nodes = {node: filtered_nodes[node] for node in filtered_nodes if any(node in filtered_job_nodes[job]['nodes'] for job in filtered_job_nodes)}

        return filtered_nodes
    
    def resolve_jobs(self, job_selector: Dict[str, Any], end_time_stamp, time_offset) -> List[str]:
        """Resolve jobs based on selector criteria"""
        try:
            # Get recent job metadata
            job_metadatas = self.job_metadata_client.get_filtered_job_attempts(
                start_time=end_time_stamp - parse_interval(time_offset),
                end_time=end_time_stamp,
                filters=job_selector
            )
            return job_metadatas
            
        except Exception as e:
            logger.error(f"Error resolving jobs: {e}")
           