"""
Data Source Integrators for Monitor Service

Based on the real-world implementations from the design doc.
These provide unified interfaces for all data sources.
"""

from copy import deepcopy
import os
import json
import time
from joblib import Parallel, delayed
import pandas as pd
import requests
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class LogEntry:
    message: str
    fields: Dict[str, Any] 

def parse_interval(time_str: str) -> int:
    """Parse time string into seconds
    
    Supports formats:
    - '30s' -> 30 seconds
    - '5m' -> 300 seconds  
    - '2h' -> 7200 seconds
    - '1d' -> 86400 seconds
    - '60' -> 60 seconds (no suffix)
    """
    if time_str.endswith('s'):
        return int(time_str[:-1])
    elif time_str.endswith('m'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('h'):
        return int(time_str[:-1]) * 3600
    elif time_str.endswith('d'):
        return int(time_str[:-1]) * 86400
    else:
        return int(time_str)


class RequestUtil:
    """Utility class for making requests to PAI APIs"""
    
    @staticmethod
    def get_request(url: str, token: str, timeout: int = 120):
        """Make GET request with token authentication"""
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            return response
        except Exception as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
    
    @staticmethod
    def openpai_query(query: str, json_content: bool = True, retry: int = 5):
        """Make requests to OpenPAI REST API"""
        base_url = os.getenv("REST_SERVER_URI", "https://auto-test.openpai.org/rest-server")
        query = query.replace("restserver", "api/v2")
        url = f"{base_url}/{query}"
        if os.getenv("ENVIRONMENT") == "prod" and "log-manager" in query:
            query = query.replace("log-manager", "/")
            url = f"http:{query}"
        
        token = os.getenv("PAI_TOKEN")
        while retry > 0:
            response = None
            try:
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.get(url, headers=headers)
                if response.ok:
                    #logger.info(f"OpenPAI query successful: {url}")
                    return response.json() if json_content else response.text
                logger.error(f"OpenPAI query failed: {response.status_code} {response.text} {url}")
            except Exception as e:
                logger.error(f"OpenPAI request error: {e}")
            retry -= 1
            if 'Too many requests' in response.text:
                time.sleep(12)  # Rate limit handling
        return None

class PrometheusClient:
    """Client for collecting metrics from Prometheus"""
    
    def __init__(self):
        self.base_url = os.getenv("PROMETHEUS_SERVER_URI", "https://auto-test.openpai.org/prometheus")
        self.token = os.getenv("PAI_TOKEN")
    
    def query_range(self, query: str, start_time: int, end_time: int, step: str = "30s", retry: int = 3) -> Optional[Dict]:
        """Query Prometheus for metrics data over time range"""
        offset = f"{int(end_time - start_time)}s"
        query = f"query?query=({query})[{offset}:{step}] @ {end_time}"
        url = f"{self.base_url}/prometheus/api/v1/{query}"
        response = None
        while retry > 0 and not response:
            response = RequestUtil.get_request(url, self.token)
            if response and response.ok:
                return json.loads(response.content)["data"]
            logger.error(
                f"Prometheus query failed. Query: {query} Response:{response.content}"
            )
            retry -= 1
        return None
    
    def query(self, query, data, retry=5):
        """
        Query Prometheus for a single metric value.
        Args:
            query (str): Prometheus query string
            data (Dict): Additional data to include in the query
            retry (int): Number of retries for the query
        Returns:
            Dict: Parsed response data from Prometheus
        """
        query = f"{self.base_url}/prometheus/api/v1/query?query={query}"
        token = os.getenv("PAI_TOKEN")
        while retry > 0:
            response = RequestUtil.get_request(query, token)
            if response and response.ok:
                return json.loads(response.content)["data"]
            logger.error(
                f"Prometheus query failed. Query: {query} Response:{response.content}"
            )
            retry -= 1
            if "Too many requests" in response.text:
                time.sleep(12)
        return None
    
    def get_metric_sampling_interval(self, metric_name):
        """Get the sampling interval for a given metric."""
        attempt = 10
        while True:
            query = f"{metric_name}[10m]"
            output = self.query(query, {})
            if output:
                values = output["result"][0]["values"]
                return int(float(values[1][0]) - float(values[0][0]))
            attempt = attempt * 10
    
    def query_step(
        self, query, data, end_time, time_offset, step="6h"
    ):
        """Query Prometheus with time intervals in parallel.
        Args:
            query (str): Prometheus query string with {time_offset} placeholder
            data (Dict): Additional data to include in the query
            end_time (int): End timestamp in seconds
            time_offset (str): Time offset string (e.g., "1h", "30m")
            step (str): Step size for the time intervals (default: "6h")
        Returns:
            List[Tuple[int, int, List[Dict]]]: List of tuples with start time, end time, and query results
        """
        start_time = end_time - parse_interval(time_offset)
        step_timedelta = parse_interval(step)

        time_intervals = []
        current_time = start_time

        # Prepare time intervals for parallel queries
        while current_time < end_time:
            next_time = min(current_time + step_timedelta, end_time)
            time_intervals.append((int(float(current_time)), int(float(next_time))))
            current_time = next_time

        def query_interval(start, end):
            # Create the query with the specific time range
            time_offset = f"{int((end - start))}s"
            query_with_time = query.replace("{time_offset}", time_offset).replace(
                "{end_time_stamp}", str(int(end))
            )
            result = self.query(
                query_with_time, data
            )
            return (
                start,
                end,
                deepcopy(result["result"]) if result and result["result"] else [],
            )

        # Execute queries in parallel using joblib
        final_value = Parallel(n_jobs=4, backend="threading")(
            delayed(query_interval)(start, end) for start, end in time_intervals
        )

        return final_value


class JobLogsClient:
    """Client for collecting job logs from PAI"""
    
    def __init__(self):
        pass
    
    def get_job_logs(self, job_name: str, job_meta: Dict[str, Any], job_retry_id: int = 0, task_role_name: str = "worker", 
                     index: int = 0, tail: bool = False, retry: int = 3):
        """Get logs for a specific job"""
        try:
            logs = {}
            # Get job metadata to find failed tasks
            if not job_meta:
                query = f"restserver/jobs/{job_name}/attempts/{job_retry_id}/"
                job_data = RequestUtil.openpai_query(query)
            else:
                job_data = job_meta
            
            if not job_data:
                return None
                
            task_roles = job_data.get("taskRoles", {})
            if not task_roles:
                return None
                
            task_role_name = list(task_roles.keys())[0]
            task_statuses = task_roles[task_role_name]["taskStatuses"]
            
            # Find failed or stopped tasks
            failed_tasks = [task for task in task_statuses if task["taskState"] == "FAILED"]
            stopped_tasks = [task for task in task_statuses 
                           if task.get("containerExitSpec", {}).get("type") == "USER_STOP"]
            
            # Download logs for the task
            for node, node_data in job_data.get("nodes", {}).items():
                index = node_data.get("task_role_index")
                log_content = self.download_log(job_name, job_retry_id, task_role_name, index, tail, retry)
                logs[node] = log_content
            
            return logs
            
        except Exception as e:
            logger.error(f"Error getting job logs for {job_name}: {e}")
            return None
    
    def download_log(self, job_name: str, job_retry_id: int, task_role_name: str, 
                      index: int, tail: bool = False, retry: int = 3) -> Optional[str]:
        """Download log content for a specific task"""
        query = f"restserver/jobs/{job_name}/attempts/{job_retry_id}/taskRoles/{task_role_name}/taskIndex/{index}/attempts/0/logs"
        if tail:
            query += "?tail-mode=true"
            
        response = RequestUtil.openpai_query(query, retry=retry)
        if not response or not response.get("locations"):
            return None
            
        # Find stdout logs
        stdout_logs = [res for res in response["locations"] if res["name"] == "all"]
        if not stdout_logs:
            return None
            
        # Get log content
        log_uri = stdout_logs[0]["uri"].lstrip("/")
        log_content = RequestUtil.openpai_query(log_uri, json_content=False, retry=retry)
        
        return log_content
    
    def parse_logs_with_patterns(self, log_content: str, patterns: List[Dict], 
                                max_entries: int = None) -> List[LogEntry]:
        """Parse log content using regex patterns, or return raw lines if no pattern is defined."""
        if not log_content:
            return []
        
        log_entries = []
        lines = log_content.split('\n')
        
        if not patterns:
            # No pattern: return raw lines as log entries
            for line in lines:
                if max_entries and len(log_entries) >= max_entries:
                    break
                line = line.strip()
                if not line:
                    continue
                log_entries.append(LogEntry(
                    message=line,
                    fields={}
                ))
            return log_entries

        # Patterns defined: use regex matching
        for line_num, line in enumerate(lines):
            if max_entries and len(log_entries) >= max_entries:
                break
            line = line.strip()
            if not line:
                continue
            for pattern_info in patterns:
                regex_pattern = pattern_info.get('regex')
                if not regex_pattern:
                    continue
                try:
                    match = re.search(regex_pattern, line)
                    if match:
                        fields = match.groupdict() if hasattr(match, 'groupdict') else {}
                        log_entries.append(LogEntry(
                            message=line,
                            fields=fields
                        ))
                        break  # Only match first pattern per line
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{regex_pattern}': {e}")
                    continue
        return log_entries

class NodeLogsClient:
    """Client for collecting node system logs via log-manager API"""
    
    def __init__(self,):
        self.base_url = os.getenv('REST_SERVER_URI')
        self.session = requests.Session()
        self.token = None
        self.log_manager_port = os.getenv("LOG_MANAGER_PORT", "9103")
    
    def get_token(self, node_ip: str) -> str:
        """Get authentication token for log-manager API on a specific node"""
        payload = {
            "username": "admin",
            "password": "admin",
        }
        url = f"{self.base_url}/log-manager/{node_ip}:{self.log_manager_port}/api/v1/tokens"
        try:
            res = self.session.post(url, json=payload, timeout=30)
            if res.status_code != 200:
                raise Exception(f"Failed to get authentication token: {res.status_code}")
            token_data = res.json()
            if "token" not in token_data:
                raise Exception("Invalid token response format")
            self.token = token_data["token"]
            logger.info(f"Token obtained successfully from {url}")
            return self.token
        except Exception as e:
            logger.error(f"Error getting token from {url}: {e}")
            raise
    
    def collect_node_logs(self, node_ip: str, log_paths: List[str], patterns: List[Dict],
                         max_entries: int = None, tail_lines: int = 1000,
                         start_time_ts: int = None, end_time_ts: int = None) -> List[LogEntry]:
        """Collect logs from a node based on patterns with optional time filtering"""
        if not self.token:
            self.get_token(node_ip)
            
        all_matched_lines = []
        
        # Convert timestamps to string format expected by the API
        start_time_str = None
        end_time_str = None
        
        if start_time_ts:
            start_time_str = datetime.fromtimestamp(start_time_ts).strftime('%Y-%m-%d %H:%M:%S')
        if end_time_ts:
            end_time_str = datetime.fromtimestamp(end_time_ts).strftime('%Y-%m-%d %H:%M:%S')
        
        logger.info(f"Collecting node logs with time window: {start_time_str} to {end_time_str}")
        
  
        try:
            node_results = self._collect_from_node(
                node_ip, log_paths, patterns, max_entries, tail_lines,
                start_time_str, end_time_str
            )
            all_matched_lines.extend(node_results)
            
            if max_entries and len(all_matched_lines) >= max_entries:
                return all_matched_lines[:max_entries]
            
            return all_matched_lines
                
        except Exception as e:
            logger.error(f"Failed to collect from node {node_ip}: {e}")
            return []
    
    def _collect_from_node(self, node_ip: str, log_paths: List[str], patterns: List[Dict],
                          max_entries: int, tail_lines: int,
                          start_time_str: str = None, end_time_str: str = None) -> List[LogEntry]:
        """Collect logs from a single node with optional time filtering"""
        matched_lines = []
        
        for log_path in log_paths:
            if max_entries and len(matched_lines) >= max_entries:
                break
                
            log_filename = log_path.split('/')[-1]
            regex_pattern = None
            if len(patterns) == 1 and patterns[0].get('regex'):
                regex_pattern = patterns[0].get('regex')
            content = self._get_log_content(
                node_ip, log_filename, tail_lines, 
                start_time=start_time_str, end_time=end_time_str,
                regex_pattern=regex_pattern
            )
            try:
                # if there is only one pattern, use the regex pattern to filter the log
                for line_num, line in enumerate(content.split('\n')):
                    if max_entries and len(matched_lines) >= max_entries:
                        break
                    
                    line = line.strip()
                    if not line:
                        continue

                    if not patterns:
                        matched_lines.append(LogEntry(message=line, fields={}))
                        continue

                    for pattern_info in patterns:
                        regex_pattern = pattern_info.get('regex')
                        if not regex_pattern:
                            continue
                        try:
                            match = re.search(regex_pattern, line)
                            if match:
                                fields = match.groupdict()
                                matched_lines.append(LogEntry(
                                    message=line,
                                    fields=fields
                                ))
                                break
                        except re.error as e:
                            logger.warning(f"Invalid regex pattern '{regex_pattern}': {e}")
                            continue
            except Exception as e:
                logger.error(f"Error processing {node_ip}:{log_path}: {e}")
                continue
                
        return matched_lines 
    
    def _get_log_content(self, node_ip: str, log_filename: str, lines: int = 1000, 
                        tail_mode: bool = True, start_time: str = None, end_time: str = None, regex_pattern: str = None) -> str:
        """Get log content from specific node with optional time filtering"""
        # Correct URL: {base_url}/log-manager/{node_ip}:{port}/api/v1/node-logs/{log_filename}
        url = f"{self.base_url}/log-manager/{node_ip}:{self.log_manager_port}/api/v1/node-logs/{log_filename}"
        params = {
            "token": self.token,
            "lines": lines
        }
        if tail_mode:
            params["tail-mode"] = "true"
        if start_time:
            params["start-time"] = start_time
        if end_time:
            params["end_time"] = end_time
        if regex_pattern:
            params["log-regex"] = regex_pattern
        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to get log content from {node_ip}:{log_filename}: {e}")
            raise

class JobMetadataClient:
    """Client for collecting job metadata from PAI"""
    
    def __init__(self):
        pass
    
    def get_job_metadata(self) -> Dict[str, Any]:
        """Get metadata for all jobs (basic job list without attempts)"""
        query = "restserver/jobs?offset=0&limit=49999&withTotalCount=true&order=completionTime"
        job_metadatas = RequestUtil.openpai_query(query)
        
        if not job_metadatas:
            return {}
            
        data = job_metadatas.get("data", [])
        formatted_metadata = {}
        
        for job in data:
            job_key = f'{job["username"]}~{job["name"]}'
            formatted_metadata[job_key] = job
        
        return formatted_metadata
    
    def get_job_attempt_metadata(self, job_key, attempt_id, job_data=None):
        """Get detailed metadata for a specific job attempt/retry"""        
        attempt_metadata = self.fetch_job_attempt_metadata(job_key, attempt_id) 
        if not attempt_metadata:
            return None

        # Create unique key for this attempt
        attempt_key = f"{job_key}~{attempt_id}"
        # Merge basic job data with attempt-specific data
        if not job_data:
            job_data = {}
        attempt_data = job_data.copy()
        attempt_data.update({
            "attemptId": attempt_id,
            'jobPriority': attempt_data.get("jobPriority") if attempt_data.get("jobPriority") else 'default',
            "state": attempt_metadata.get("jobStatus", {}).get("attemptState"),
            "attemptState": attempt_metadata.get("jobStatus", {}).get("attemptState"),
            "createdTime": attempt_metadata.get("jobStatus", {}).get("appCreatedTime"),
            "launchedTime": attempt_metadata.get("jobStatus", {}).get("appLaunchedTime", None),
            "completedTime": attempt_metadata.get("jobStatus", {}).get("appCompletedTime", None),
            "submissionTime": attempt_metadata.get("jobStatus", {}).get("submissionTime"),
            "taskRoles": attempt_metadata.get("taskRoles", {}),
            "job_id": attempt_key,
            "exitSpec": attempt_metadata.get("exitSpec"),
            "nodes": self.get_nodes_in_attempt(attempt_metadata)
        })
        attempt_data.update({
            'submissionDatetime': pd.to_datetime(attempt_data.get("submissionTime"), unit='ms'),
            'launchedDatetime': pd.to_datetime(attempt_data.get("launchedTime"), unit='ms'),
            'completedDatetime': pd.to_datetime(attempt_data.get("completedTime"), unit='ms') if attempt_data.get("completedTime") else None,
            'createdDatetime': pd.to_datetime(attempt_data.get("createdTime"), unit='ms')
                    })
        return attempt_data
    
    def get_job_attempts_metadata(self, start_time: int, end_time: int, job_finish=False) -> Dict[str, Any]:
        """
        Get metadata for all job attempts within the specified time window.
        Each attempt is treated as a separate job for analysis purposes.
        
        Args:
            start_time: Start timestamp in seconds
            end_time: End timestamp in seconds
            
        Returns:
            Dictionary where each key is 'username~jobname~attemptId' and value is attempt metadata
        """
        # First get all jobs
        basic_jobs = self.get_job_metadata()
        all_attempts = {}
        
        for job_key, job_data in basic_jobs.items():
            try:
                # Get all attempts for this job
                attempts = job_data.get("retries", 0)
                
                for attempt_id in range(attempts+1):
                    if (job_data.get("completedTime") or start_time * 1000) < start_time * 1000:
                        # Job completed before the time window
                        continue
                    # Get detailed metadata for this attempt
                    attempt_metadata = self.get_job_attempt_metadata(job_key, attempt_id, job_data)
                    if not attempt_metadata:
                        continue                    # Check if this attempt was active during the time window
                    attempt_start = attempt_metadata.get("createdTime")
                    attempt_end = attempt_metadata.get("completedTime")
                    
                    if attempt_start:
                        attempt_start_sec = attempt_start / 1000
                        attempt_end_sec = attempt_end / 1000 if attempt_end else end_time
                        
                        if job_finish and attempt_end is None:
                            # Skip attempts that are not finished
                            continue
                        
                        # Attempt was active during the time window
                        if (attempt_start_sec < end_time and attempt_end_sec >= start_time):
                            attempt_key = attempt_metadata.get("job_id", f"{job_key}~{attempt_id}")
                            # Store attempt metadata
                            all_attempts[attempt_key] = attempt_metadata
                            
            except Exception as e:
                logger.error(f"Error processing attempts for job {job_key}: {e}")
                continue
        
        return all_attempts
    
    def get_filtered_job_attempts(self, start_time: int, end_time: int, 
                                 filters) -> Dict[str, Any]:
        """
        Get metadata for job attempts within the specified time window with optional filtering.
        Each attempt is treated as a separate job for analysis purposes.
        
        Args:
            start_time: Start timestamp in seconds
            end_time: End timestamp in seconds
            filters: Optional filters to filter by (e.g., {"status": ["FAILED", "SUCCEEDED"]})
                   If None, includes all attempts regardless of state
            
        Returns:
            Dictionary where each key is 'username~jobname~attemptId' and value is attempt metadata
        """
        all_attempts = self.get_job_attempts_metadata(start_time, end_time)
        
        filtered_attempts_keys = []
        for job_name, job_info in all_attempts.items():            
            if filters.get('status'):
                status = filters.get('status')
                if job_info.get('state').lower() in status:
                    filtered_attempts_keys.append(job_name)
            else:
                filtered_attempts_keys.append(job_name)
            if job_name in filtered_attempts_keys:
                if filters.get('job_instance_count_more_than'):
                    if int(job_info.get('totalTaskNumber')) <= int(filters.get('job_instance_count_more_than')):
                        filtered_attempts_keys.remove(job_name)
                if filters.get('runtime_more_than'):
                    filter_runtime = parse_interval(filters.get('runtime_more_than'))
                    job_completed_time = job_info.get('completedTime') if job_info.get('completedTime') is not None else end_time * 1000
                    if (job_completed_time - job_info.get('launchedTime')) / 1000 < filter_runtime:
                        filtered_attempts_keys.remove(job_name)

        filtered_attempts = {key: all_attempts[key] for key in filtered_attempts_keys}
        return filtered_attempts
    
    def get_nodes_in_attempt(self, attempt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get nodes in attempt"""
        nodes = {}
        for task_role_name, task_role_data in attempt_data.get('taskRoles', {}).items():
            for task_status in task_role_data.get('taskStatuses', []):
                node_name = task_status.get('containerNodeName')
                task_state = task_status.get('taskState')
                exit_spec = task_status.get('containerExitSpec', {})
                if node_name:
                    nodes[node_name] = {
                        "task_state": task_state,
                        "exit_spec": exit_spec,
                        "task_role_index": task_role_data.get('taskIndex')
                    }
        return nodes
    
    
    def get_filtered_job_nodes(self, start_time: int, end_time: int, 
                                 filters) -> List[str]:
        """Get nodes in filtered job attempts"""
        filtered_attempts = self.get_filtered_job_attempts(start_time, end_time, filters)
        nodes = []
        for attempt_key, attempt_data in filtered_attempts.items():
            nodes.extend(self.get_nodes_in_attempt(attempt_data).keys())
        return nodes

    
    def fetch_job_attempt_metadata(self, job_name: str, job_retry_id: int = 0) -> Optional[Dict[str, Any]]:
        """Get detailed metadata for a specific job attempt/retry"""
        query = f"restserver/jobs/{job_name}/attempts/{job_retry_id}/"
        attempt_metadata = RequestUtil.openpai_query(query)
        
        if not attempt_metadata:
            return None
            
        return attempt_metadata
    
    def get_job_attempts_list(self, job_name: str) -> List[int]:
        """Get list of all attempt IDs for a job"""
        query = f"restserver/jobs/{job_name}/attempts"
        attempts_data = RequestUtil.openpai_query(query)
        
        if not attempts_data:
            return []
            
        attempts = attempts_data.get("attempts", [])
        return [attempt.get("attemptId", 0) for attempt in attempts if attempt.get("attemptId") is not None]
    
    def get_job_list(self, end_time_stamp: int, time_offset: str, finished: bool = False) -> List[str]:
        """
        Get list of job attempts within time window.
        Each attempt is treated as a separate job for analysis purposes.
        
        Args:
            end_time_stamp: End timestamp in seconds
            time_offset: Time offset string (e.g., "1h", "30m")
            finished: If True, only return completed attempts
            
        Returns:
            List of job attempt keys in format 'username~jobname~attemptId'
        """
        start_time = end_time_stamp - parse_interval(time_offset)
        
        # Get all attempts within the time window
        all_attempts = self.get_job_attempts_metadata(start_time, end_time_stamp)
        
        filtered_attempts = []
        for attempt_key, attempt_data in all_attempts.items():
            attempt_state = attempt_data.get("attemptState")
            completed_time = attempt_data.get("completedTime")
            
            if finished:
                # Only include completed attempts
                if completed_time and attempt_state in ["SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT"]:
                    filtered_attempts.append(attempt_key)
            else:
                # Include all attempts (running, completed, failed, etc.)
                filtered_attempts.append(attempt_key)
        
        return filtered_attempts
    