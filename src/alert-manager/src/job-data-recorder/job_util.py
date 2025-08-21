"""
Job Metrics Utility Functions

This module provides utility functions for collecting, calculating, and processing job metrics in OpenPAI.

Features:
- Query job configuration from OpenPAI REST API
- Calculate total, idle, and effective GPU hours for jobs
- Generate normalized job configuration hash
- Retrieve and process metrics for multiple jobs in parallel

Key Functions:
- get_job_config: Query job config from OpenPAI
- calculate_job_gpu_hours: Calculate total GPU hours
- calculate_job_idle_gpu_hours: Calculate idle GPU hours
- calculate_job_effective_gpu_hours: Calculate effective GPU hours
- get_single_job_metrics: Get all metrics for a single job
- retrieve_period_job_metrics: Batch process metrics for multiple jobs
"""

import hashlib
import json
import os
from threading import Lock
import time
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from tqdm import tqdm
import yaml

from data_sources import RequestUtil, PrometheusClient, parse_interval


def get_job_config(job):
    """
    Query job configuration from OpenPAI REST API.

    Args:
        job (str): Job name or ID.
    Returns:
        dict or None: Job configuration dictionary, or None if not found.
    """
    if not job:
        return None
    query = f"restserver/jobs/{job}/config"
    job_config = RequestUtil.openpai_query(query)
    if not job_config:
        return None
    return job_config


def calculate_job_gpu_hours(job, end_time_stamp, time_offset):
    """
    Calculate total GPU hours for a job.

    Args:
        job (str): Job name or ID.
        end_time_stamp (int): End timestamp for metrics.
        time_offset (str): Time window length (e.g. '24h', '3600s').
    Returns:
        float: Total GPU hours.
    """
    try:
        prometheus = PrometheusClient()
        job_filter = "{" + f'job_name="{job}"' + "}"
        query = f"sum (count_over_time(task_gpu_percent{job_filter} [{time_offset}] @ {end_time_stamp}))"

        # Use simple query with timestamp
        result = prometheus.query(query, {})
        if not result or not result.get("result"):
            return 0

        job_gpu_hours = result["result"][0]["value"][1]
        # Use fixed scrape interval of 30 seconds (standard for PAI)
        scrape_interval = prometheus.get_metric_sampling_interval(
            "task_gpu_percent")
        return float(job_gpu_hours) * scrape_interval / 3600
    except Exception as e:
        print(f"Error calculating GPU hours for {job}: {e}")
        return 0


def calculate_job_idle_gpu_hours(job, end_time_stamp, time_offset):
    """
    Calculate idle GPU hours for a job.

    Args:
        job (str): Job name or ID.
        end_time_stamp (int): End timestamp for metrics.
        time_offset (str): Time window length.
    Returns:
        float: Idle GPU hours.
    """
    try:
        prometheus = PrometheusClient()
        scrape_interval = prometheus.get_metric_sampling_interval(
            "task_gpu_percent")
        job_filter = "{" + f'job_name="{job}"' + "}"

        query = (f"sum (count_over_time((task_gpu_percent{job_filter}==0) " +
                 "[{time_offset}" + f":{scrape_interval}s]" +
                 " @ {end_time_stamp}))")
        result = prometheus.query_step(query, {}, end_time_stamp, time_offset)

        if not result:
            return 0

        total_idle_hours = 0
        for start, end, values in result:
            if values:
                for item in values:
                    total_idle_hours += float(item["value"][1])

        return total_idle_hours * scrape_interval / 3600
    except Exception as e:
        print(f"Error calculating idle GPU hours for {job}: {e}")
        return 0


def calculate_job_effective_gpu_hours(job, end_time_stamp, time_offset):
    """
    Calculate effective GPU hours for a job.

    Args:
        job (str): Job name or ID.
        end_time_stamp (int): End timestamp for metrics.
        time_offset (str): Time window length.
    Returns:
        float: Effective GPU hours.
    """
    try:
        prometheus = PrometheusClient()
        job_filter = "{" + f'job_name="{job}"' + "}"
        query = f"sum (sum_over_time(task_gpu_percent{job_filter} [{time_offset}] @ {end_time_stamp}))"

        result = prometheus.query(query, {})
        if not result or not result.get("result"):
            return 0

        job_effective_gpu_hours = result["result"][0]["value"][1]
        scrape_interval = prometheus.get_metric_sampling_interval(
            "task_gpu_percent")
        return float(job_effective_gpu_hours) * scrape_interval / 100 / 3600
    except Exception as e:
        print(f"Error calculating effective GPU hours for {job}: {e}")
        return 0


def get_monitor_end_time(end_time_stamp, job_metadata):
    """
    Determine the monitoring end time for a job based on metadata.

    Args:
        end_time_stamp (int): End timestamp.
        job_metadata (dict): Job metadata.
    Returns:
        int: Monitoring end time (timestamp).
    """
    job_end_time = None
    if job_metadata["completedTime"] == None or (
            end_time_stamp
            and end_time_stamp < job_metadata["completedTime"] / 1000):
        job_end_time = end_time_stamp
    else:
        job_end_time = int(job_metadata["completedTime"] / 1000)
    return job_end_time


def hash_normalized_config(config, job_name):
    """
    Generate a hash of normalized job configuration for deduplication and tracking.

    Args:
        config (dict or str): Job configuration.
        job_name (str): Job name.
    Returns:
        str: SHA256 hash of normalized config.
    """
    if isinstance(config, str):
        config = json.loads(config)
    elif config is None:
        return "unknown"

    # Create a copy to avoid modifying original
    config = config.copy()

    # Remove variable fields
    config.pop("extras", None)
    config.pop("jobRetryCount", None)

    # Normalize task roles
    for task_role, task_role_config in config.get("taskRoles", {}).items():
        for key in list(task_role_config.keys()):
            if key not in ["instances", "resourcePerInstance", "commands"]:
                task_role_config[key] = None

    # Use username from job name
    user_name = job_name.split('~')[0]
    config['name'] = user_name

    # Normalize the config by removing newlines and sorting keys
    normalized = yaml.dump(config, sort_keys=True)
    normalized = normalized.replace(' ', '').replace('\n', '')

    # Create a hash of the normalized config
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_single_job_metrics(job, job_metadata, end_time_stamp=None, time_offset=None):
    """
    Get comprehensive metrics for a single job, including GPU hours and utilization.

    Args:
        job (str): Job name or ID.
        job_metadata (dict or str): Job metadata.
        end_time_stamp (int, optional): End timestamp.
        time_offset (str, optional): Time window length.
    Returns:
        dict: Updated job metadata with metrics.
    """
    try:
        if isinstance(job_metadata, str):
            job_metadata = json.loads(job_metadata)

        job_start_time = int(job_metadata["launchedTime"] / 1000)

        if not end_time_stamp:
            end_time_stamp = int(time.time())

        if time_offset:
            job_start_time = max(
                int(job_metadata["launchedTime"] / 1000),
                end_time_stamp - parse_interval(time_offset),
            )

        job_end_time = get_monitor_end_time(end_time_stamp, job_metadata)

        job_idle_gpu_hours = 0
        job_total_allocated_gpu_hours = 0
        job_effective_utilized_gpu_hours = 0

        if job_end_time > job_start_time:
            time_offset_str = f"{int(job_end_time - job_start_time)}s"
            job_idle_gpu_hours = calculate_job_idle_gpu_hours(
                job, job_end_time, time_offset_str)
            job_total_allocated_gpu_hours = calculate_job_gpu_hours(
                job, job_end_time, time_offset_str)
            job_effective_utilized_gpu_hours = calculate_job_effective_gpu_hours(
                job, job_end_time, time_offset_str)

        # Get job config for hashing
        job_config = get_job_config(job)
        job_hash = hash_normalized_config(job_config, job)

        job_metadata.update({
            "duration": (job_end_time - job_start_time) / 3600,
            "total_gpu_hours":
            job_total_allocated_gpu_hours,
            "idle_gpu_hours":
            job_idle_gpu_hours,
            "effective_gpu_hours":
            job_effective_utilized_gpu_hours,
            "effective_gpu_utilization":
            (job_effective_utilized_gpu_hours /
             (job_total_allocated_gpu_hours - job_idle_gpu_hours)
             if job_total_allocated_gpu_hours - job_idle_gpu_hours > 0 else 0),
            "assigned_gpu_utilization":
            ((job_total_allocated_gpu_hours - job_idle_gpu_hours) /
             job_total_allocated_gpu_hours
             if job_total_allocated_gpu_hours > 0 else 0),
            "idle_gpu_percentage":
            (job_idle_gpu_hours / job_total_allocated_gpu_hours
             if job_total_allocated_gpu_hours > 0 else 0),
            "job_hash":
            job_hash,
        })
        return job_metadata
    except Exception as e:
        print(f"Error in getting job metrics for {job}: {e}")
        job_metadata.update({
            "duration": (job_end_time - job_start_time) /
            3600 if 'job_end_time' in locals()
            and 'job_start_time' in locals() else pd.NA,
            "total_gpu_hours":
            pd.NA,
            "idle_gpu_hours":
            pd.NA,
            "effective_gpu_hours":
            pd.NA,
            "effective_gpu_utilization":
            pd.NA,
            "assigned_gpu_utilization":
            pd.NA,
            "idle_gpu_percentage":
            pd.NA,
            "job_hash":
            pd.NA,
        })
        return job_metadata


def retrieve_period_job_metrics(end_time_stamp, time_offset, job_metadata_list, debug=False):
    """
    Retrieve metrics for multiple jobs in a time period, with optional parallel processing.

    Args:
        end_time_stamp (int): End timestamp.
        time_offset (str): Time window length.
        job_metadata_list (list): List of job metadata dicts.
        debug (bool): If True, disables parallel processing for easier debugging.
    Returns:
        pd.DataFrame: DataFrame of all job metrics.
    """
    all_df = pd.DataFrame()

    def process_and_save_job(job_metadata):
        job_name = f'{job_metadata["username"]}~{job_metadata["name"]}'
        job_data = get_single_job_metrics(job_name, job_metadata,
                                          end_time_stamp, time_offset)
        return job_data

    # Use parallel processing with tqdm for jobs
    results = []
    if debug:
        for job in job_metadata_list:
            results.append(process_and_save_job(job))
    else:
        with tqdm(total=len(job_metadata_list),
                  desc="Processing Jobs") as pbar:
            results = Parallel(n_jobs=8, backend="threading")(
                delayed(lambda job:
                        (pbar.update(1), process_and_save_job(job)))(job)
                for job in job_metadata_list)
        results = [result[1] for result in results]

    # Combine results into a single DataFrame
    if results:
        new_df = pd.DataFrame(results)
        all_df = pd.concat([all_df, new_df], ignore_index=True)

    if all_df.empty:
        return all_df

    all_df.sort_values(
        by=["submissionTime", "completedTime"],
        inplace=True,
    )

    return all_df

def find_node_next_job_start_time(node_ip, completedTime):
    """Find the next job start time for a node after it has completed a job."""
    if not node_ip or not isinstance(completedTime, (int, float)):
        print(f"Invalid input: node_ip={node_ip}, completedTime={completedTime}")
        return int(completedTime + 60 * 60 * 1000) if completedTime else int(time.time() * 1000)
    
    default_end_time = (completedTime +  60 * 60 * 1000)  # 1 hour after completedTime
    try:
        prometheus_client = PrometheusClient()
        node_filter = f'instance=~"{node_ip}:[0-9]*"'
        query = "task_cpu_percent{" + node_filter + "}>0"
        result = prometheus_client.query_range(
            query,
            start_time=completedTime // 1000 + 1,  # Start just after completedTime
            end_time=default_end_time // 1000)
        if not result or not result.get("result"):
            return default_end_time
        # Find the first timestamp after completedTime
        earliest_timestamp = None
        for item in result["result"]:
            values = item.get("values", [])
            if not values:
                continue    
            for timestamp_str, value in values:
                try:
                    timestamp_ms = int(float(timestamp_str)) * 1000
                    if (earliest_timestamp is None or timestamp_ms < earliest_timestamp) and timestamp_ms > completedTime:
                        earliest_timestamp = timestamp_ms
                        break
                except (ValueError, TypeError) as parse_error:
                    print(f"Error parsing timestamp/value: {parse_error}")
                    break
        return earliest_timestamp if earliest_timestamp is not None else default_end_time
    except Exception as e:
        print(f"Error finding next job start time for node {node_ip}: {e}")
        return default_end_time
        