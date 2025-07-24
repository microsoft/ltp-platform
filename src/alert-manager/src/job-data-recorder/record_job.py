import json
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from tqdm import tqdm

from data_sources import *
from job_util import retrieve_period_job_metrics
from kusto_util import KustoUtil


def get_job_duration(job):
    """Calculate the job running duration in hours"""
    if not job.get('completedTime', 0):
        # return large number if job is still running
        return float('inf')
    if not job.get('launchedTime', 0):
        return 0
    return (job.get('completedTime', 0) -
            job.get('launchedTime', 0)) / 1000 / 3600


def meets_job_metadata_criteria(job):
    """Check if the job meets the specified criteria"""
    long_running_job = get_job_duration(job) > 0.1  # 10 minutes
    return long_running_job


def collect_eligible_jobs(current_time_stamp, time_offset):
    """Collect jobs that meet the specified criteria from job metadata"""
    start_time = current_time_stamp - parse_interval(time_offset)
    metadata = JobMetadataClient().get_job_attempts_metadata(
        start_time, current_time_stamp, job_finish=True)
    jobs = []
    for job_attempt_name, job_attempt_metadata in metadata.items():
        # check if job meets the criteria
        if meets_job_metadata_criteria(job_attempt_metadata):
            job_copy = job_attempt_metadata.copy()
            job_copy['jobId'] = job_attempt_name
            jobs.append(job_copy)

    return jobs


def collect_finished_job_metrics(job_attempts_metadata,
                                 debug=False):
    """Collect detailed job metrics for the specified jobs including each attempt and save into a CSV file"""

    df = retrieve_period_job_metrics(end_time_stamp=None,
                                     time_offset=None,
                                     job_metadata_list=job_attempts_metadata,
                                     debug=debug)
    # analyze exit reasons for each job
    df = update_failure_reason_category(df, debug)
    return df


def parse_common_errors(log):
    """Parse common error patterns from job logs."""
    if log is None:
        return '', ''
    lines = log.split('\n')
    # Inline expression to find the first line containing the pattern
    find_line = lambda pattern, default=None: next(
        (line for line in lines if pattern in line), default
        if default is not None else pattern) if pattern in log else None

    if 'One or both of the .idx and .bin files cannot be found' in log:
        return 'Data Missing', 'Platform Failure'
    elif 'Dataset corrup' in log:
        return 'Dataset Missing', 'Platform Failure'
    elif error := find_line('Got async event : port error'):
        return 'IB Link Flaping' + error, 'Hardware Failure'
    elif 'GPU Hang' in log:
        return 'GPU Hang', 'Hardware Failure'
    else:
        return '', ''


def analyze_single_job_exit_reason(job_name,
                                   attempt_id,
                                   job_metadata=None,
                                   debug=False):
    """Analyze the exit reason of a single job."""

    print(f"Analyzing exit reason for job: {job_name}, attempt: {attempt_id}")
    if not job_metadata:
        job_metadata = JobMetadataClient().get_job_attempt_metadata(
            job_name, attempt_id)
    if not job_metadata:
        print(f"Could not fetch details for job {job_name}")
        return

    # Extract job details and analyze exit reason
    task_role_name = list(job_metadata["taskRoles"].keys())[0]
    task_statuses = job_metadata["taskRoles"][task_role_name]["taskStatuses"]
    failed_tasks = get_failed_tasks(task_statuses)
    stopped_tasks = get_stopped_tasks(task_statuses)
    completed_time = job_metadata['completedTime']
    launched_time = job_metadata['launchedTime']

    reason, category = '', ''
    node_failure, category = find_node_failure_in_job(
        job_name, attempt_id, completed_time, launched_time, task_role_name,
        failed_tasks, stopped_tasks, task_statuses, debug)
    if node_failure and len(node_failure) > 0:
        reason = node_failure
    else:
        if len(failed_tasks) == 0 and len(stopped_tasks) > 0:
            reason, category = 'User Stop', 'User Stop'
        elif len(failed_tasks) > 0 and all(task['containerExitSpec']['phrase']
                                           == 'PAIRuntimeUnknownFailed'
                                           for task in failed_tasks):
            reason, category = 'User Code Bug', 'Software Failure'
        elif len(failed_tasks) > 0:
            exit_code = [
                task['containerExitSpec']['phrase'] for task in failed_tasks
                if task['containerExitSpec']['phrase'] !=
                'PAIRuntimeUnknownFailed'
            ]
            exit_code = list(set(exit_code))
            reason, category = exit_code[0], 'Software Failure'
        else:
            reason = 'Succeed'
            category = 'Succeed'

    print(f"Job {job_name} exit reason: {reason}")
    return reason, category if category else ''


def find_node_failure_in_job(job_name,
                             attempt_id,
                             completed_time,
                             launched_time,
                             task_role_name,
                             failed_tasks,
                             stopped_tasks,
                             all_tasks,
                             debug=False):
    """Find node failure reasons in all nodes of a job."""
    # Priority-ordered tasks
    ordered_tasks = failed_tasks + stopped_tasks + [
        task for task in all_tasks
        if task not in failed_tasks and task not in stopped_tasks
    ]
    reasons = {}
    categories = set()

    def wrapped_find(task):
        # Ensure result is always a tuple (task, result_value)
        try:
            result = find_node_failure(task, completed_time, launched_time,
                                       job_name, attempt_id, task_role_name)
            print(f"Task {task.get('taskIndex', 'N/A')} result: {result}")
            return (task, result)
        except Exception as e:
            print(
                f"Error in wrapped_find for task {task.get('taskIndex', 'N/A')}: {e}"
            )
            traceback.print_exc()  # Print full traceback for debugging
            return (task, '')  # Return error message as result

    if debug:
        for task in ordered_tasks:
            try:
                task, result = wrapped_find(task)
                node, reason, category = result
                if reason and len(reason) > 0:
                    reasons[node] = reason
                    categories.add(category)
                    break
            except Exception as e:
                print(
                    f"Error in wrapped_find for task {task.get('taskIndex', 'N/A')}: {e}"
                )
    else:
        # Use ThreadPoolExecutor to parallelize the search across tasks
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_task = {
                executor.submit(wrapped_find, task): task
                for task in ordered_tasks
            }
            found_result = None
            try:
                for future in as_completed(future_to_task):
                    task, result = future.result()
                    node, reason, category = result
                    if reason and len(reason) > 0:
                        reasons[node] = reason
                        categories.add(category)
                        if found_result is None:
                            found_result = result
                            # Cancel pending (not started) futures
                            for pending_future in future_to_task:
                                if not pending_future.done():
                                    try:
                                        pending_future.cancel()
                                    except Exception as cancel_error:
                                        pass  # Ignore cancellation errors

            except Exception as e:
                print(f"Exception occurred: {e}")

    return json.dumps(reasons) if len(
        reasons) > 0 else '', categories.pop() if categories else ''


def find_node_failure(task, completedTime, launchedTime, job_name, attempt,
                      task_role_name):
    """Find node failure reason of one node."""
    error_message = ''
    if completedTime is None:
        # use current time if completedTime is not available
        completedTime = pd.Timestamp.now().timestamp() * 1000
    node_name = task.get('containerNodeName', 'unknown')
    if not node_name or node_name == 'unknown':
        print(
            f"Node name not found for job {job_name}, attempt {attempt}, task {task.get('taskIndex', 'N/A')}"
        )
        return '', '', ''

    error_message, category = KustoUtil().find_node_triaged_failure_in_kusto(
        node_name, completedTime, launchedTime)
    if len(error_message) == 0:
        logs = JobLogsClient().download_log(job_name,
                                            attempt,
                                            task_role_name,
                                            task['taskIndex'],
                                            tail=False,
                                            retry=1)
        error, category = parse_common_errors(logs)
        if error and len(error) > 0:
            print(f"Job {job_name} task {task['taskIndex']} error: {error}")
            error_message += error
            category = category if category else ''
    return node_name, error_message, category if category else ''


def get_failed_tasks(task_statuses):
    """
    Get list of failed tasks, prioritizing those that failed due to external pod deletion.
    
    Args:
        task_statuses: List of task status dictionaries
    
    Returns:
        List of failed task dictionaries
    """
    # Get all failed tasks
    failed_tasks = [
        task for task in task_statuses if task["taskState"] == "FAILED"
    ]

    # Check for tasks that failed specifically due to pod deletion
    pod_deleted_tasks = [
        task for task in failed_tasks
        if task['containerExitSpec']['phrase'] == 'PodExternalDeleted'
    ]

    # Prioritize pod deleted tasks if they exist
    if len(pod_deleted_tasks) > 0:
        return pod_deleted_tasks

    return failed_tasks


def get_stopped_tasks(task_statuses):
    """
    Get list of stopped tasks.
    
    Args:
        task_statuses: List of task status dictionaries
    
    Returns:
        List of stopped task dictionaries
    """
    return [task for task in task_statuses if task["taskState"] == "STOPPED"]


def generate_metrics(current_time, time_offset, debug=False):
    """
    Collect job metrics for jobs completed within the specified time window.

    Args:
        current_time (float): Current timestamp.
        time_offset (str): Time window length (e.g. '24h', '3600s').
        debug (bool): If True, enables debug logging.
    Returns:
        pd.DataFrame: DataFrame containing job metrics.
    """
    eligible_jobs = collect_eligible_jobs(current_time, time_offset)
    df = collect_finished_job_metrics(eligible_jobs,
                                      debug=debug)
    if df.empty:
        print("No eligible jobs found in the specified time window.")
        return pd.DataFrame()
    logger.info(f"Collected {len(df)} job metrics in the time window of {time_offset}")
    # Step 1: Add missing fields
    df["jobHash"] = df.get("job_hash", "unknown")  # use "unknown" if missing
    df["retryDetails"] = df.get("retryDetails",
                                "{}")  # dummy empty dict if needed

    # Step 2: Prepare JobFailureSummary
    df_summary = df[[
        "name", "username", "state", "retries", "attemptId", "retryDetails",
        "virtualCluster", "totalGpuNumber", "jobPriority", "duration",
        "total_gpu_hours", "idle_gpu_hours", "effective_gpu_hours",
        "submissionDatetime", "launchedDatetime", "completedDatetime",
        "exitReason", "jobId", "jobHash", "exitCategory",
        "createdDatetime", "idle_gpu_percentage",
        "assigned_gpu_utilization", "effective_gpu_utilization"
    ]]
    
    df_summary = df_summary.rename(
        columns={
            "job_hash": "jobHash",
            "job_id": "jobId",
            "name": "jobName",
            "username": "userName",
            "state": "jobState",
            "retries": "retryCount",
            "totalGpuNumber": "totalGpuCount",
            "duration": "jobDurationHours",
            "total_gpu_hours": "totalGpuHours",
            "idle_gpu_hours": "idleGpuHours",
            "effective_gpu_hours": "effectiveGpuHours",
            "submissionDatetime": "submissionTime",
            'createdDatetime': 'createdDatetime',
            "launchedDatetime": "launchTime",
            "completedDatetime": "completionTime",
            "idle_gpu_percentage": "idleGpuPercentage",
            "assigned_gpu_utilization": "assignedGpuUtilization",
            "effective_gpu_utilization": "effectiveGpuUtilization",
        })
    df_summary["launchTime"] = pd.to_datetime(df_summary["launchTime"],
                                              errors='coerce')
    df_summary["completionTime"] = pd.to_datetime(df_summary["completionTime"],
                                                  errors='coerce')
    df_summary["submissionTime"] = pd.to_datetime(df_summary["submissionTime"],
                                                  errors='coerce')
    df_summary["createdDatetime"] = pd.to_datetime(df_summary["createdDatetime"],
                                                  errors='coerce')
    logger.info(f"Generated {len(df_summary)} job metrics records")

    return df_summary


def generate_job_react_time(df):
    """
    Generate job react time based on the job metrics DataFrame.

    Args:
        df (pd.DataFrame): DataFrame containing job metrics.
    Returns:
        pd.DataFrame: DataFrame with job_hash, reactTime, job_id columns.
    """
    if df.empty:
        return pd.DataFrame()

    # the react time is the time difference between the job exit and next job start for the same job hash
    df['reactTime'] = pd.NA
    df.sort_values(by=['jobHash', 'completionTime'], inplace=True)
    for job_hash, group in df.groupby('jobHash'):
        if len(group) < 2:
            continue
        for i in range(len(group) - 1):
            try:
                current_job = group.iloc[i]
                next_job = group.iloc[i + 1]
                if pd.isna(current_job['completionTime']) or pd.isna(next_job['launchTime']):
                    continue
                if current_job['completionTime'] and next_job['launchTime']:

                    react_time = (pd.to_datetime(next_job['launchTime']) -
                                pd.to_datetime(current_job['completionTime'])
                                ).total_seconds() / 3600  # convert to hours
                    if react_time >= 0:  # only consider positive react times
                        df.loc[current_job.name, 'reactTime'] = react_time
            except Exception as e:
                logger.error(
                    f"Error calculating react time for job {current_job['jobId']}: {e}"
                )
                traceback.print_exc()

    return df[['jobHash', 'reactTime', 'jobId']].reset_index(drop=True)


def update_react_time(unknown_react_records, metrics_df):
    """
    Update missing react time records using new metrics data.

    Args:
        unknown_react_records (pd.DataFrame): Records with missing reactTime.
        metrics_df (pd.DataFrame): Newly generated job metrics.
    Returns:
        pd.DataFrame: Updated records with reactTime filled where possible.
    """
    if unknown_react_records.empty or metrics_df.empty:
        return pd.DataFrame()

    # query the job summary table for the same jobId in react_df from kusto
    # merge the queried metrics_df_old with metrics_df
    metrics_df_old = KustoUtil().query_job_metrics_by_job_id(
        unknown_react_records['jobId'].unique().tolist())
    if metrics_df_old.empty:
        return pd.DataFrame()
    merged_df = pd.concat([metrics_df_old, metrics_df], ignore_index=True)
    merged_df.sort_values(by=['jobId', 'completionTime'], inplace=True)
    merged_df = merged_df.drop_duplicates(subset=['jobId'],
                                          keep='last').reset_index(drop=True)
    new_react_df = generate_job_react_time(merged_df)
    new_react_df = new_react_df[new_react_df['jobId'].isin(
        unknown_react_records['jobId'])].reset_index(drop=True)
    if new_react_df.empty:
        return pd.DataFrame()
    return new_react_df


def update_failure_reason_category(unknown_category_records, debug=False):
    """
    Update missing failure reason category records.

    Args:
        unknown_category_records (pd.DataFrame): Records with unknown category.
    Returns:
        pd.DataFrame: Updated records with category filled where possible.
    """
    unknown_category_records.reset_index(drop=True, inplace=True)
    if 'exitReason' not in unknown_category_records.columns:
        unknown_category_records['exitReason'] = ''
    if 'exitCategory' not in unknown_category_records.columns:
        unknown_category_records['exitCategory'] = ''
    for i in tqdm(range(len(unknown_category_records)), desc="Updating exit reasons"):
        job_row = unknown_category_records.iloc[i]
        job_id = job_row['jobId']
        user, name, attempt_id = job_id.split('~')
        job_name = f'{user}~{name}'
        reason, category = analyze_single_job_exit_reason(
            job_name, attempt_id, job_row.to_dict(), debug)
        unknown_category_records.loc[i, 'exitReason'] = reason
        unknown_category_records.loc[i, 'exitCategory'] = category
    return unknown_category_records


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Job Metrics and Exit Reason Analysis Tool")
    subparsers = parser.add_subparsers(dest="action",
                                       required=True,
                                       help="Action to perform")

    # Subparser for generating metrics and exit reasons for all jobs
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate metrics and exit reasons for all jobs during a period")
    generate_parser.add_argument(
        "--current_time",
        type=str,
        required=False,
        help="Current time in datetime format (e.g., '2023-10-01 12:00:00')")
    generate_parser.add_argument("--time_offset",
                                 type=str,
                                 required=True,
                                 help="Time offset (e.g., '1d')")
    generate_parser.add_argument("--output_file",
                                 type=str,
                                 default="job_metrics.csv",
                                 help="Output file for job metrics")

    # Subparser for analyzing the exit reason of a single job
    analyze_parser = subparsers.add_parser(
        "diagnosis", help="Diagnosis the exit reason of a single job")
    analyze_parser.add_argument(
        "--job_name",
        type=str,
        required=True,
        help="Name of the job to analyze, e.g., 'user~job_name'")
    analyze_parser.add_argument("--attempt_id",
                                type=str,
                                required=True,
                                help="Attempt ID of the job to analyze")

    args = parser.parse_args()

    if args.action == "generate":
        if not args.current_time:
            args.current_time = pd.Timestamp.now().strftime(
                "%Y-%m-%d %H:%M:%S")
        print(
            f"Current time: {args.current_time}, Time offset: {args.time_offset}"
        )
        current_time = pd.to_datetime(args.current_time).timestamp()
        generate_metrics(current_time, args.time_offset)
    elif args.action == "diagnosis":
        analyze_single_job_exit_reason(args.job_name, args.attempt_id)
    else:
        print("Invalid action. Use 'generate' or 'diagnosis'.")


if __name__ == "__main__":
    main()
