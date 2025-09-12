# Copyright (c) Microsoft Corporation
# All rights reserved.


import logging
import os
import requests
from flask import Flask, request, jsonify

CLUSTER_QUERY_STRING = "avg(avg_over_time(nvidiasmi_utilization_gpu[7d]))"
JOB_GPU_PERCENT = 'avg by (job_name) (avg_over_time(task_gpu_percent[7d]))'
JOB_GPU_HOURS = 'sum by (job_name) (count_over_time(task_gpu_percent[7d]))'
# user used gpu hours / total gpu hours
USER_QUERY_STRING = \
    "(sum by (username) (sum_over_time(task_gpu_percent[7d]))) / (sum by (username) (count_over_time(task_gpu_percent[7d])*100)) * 100"

QUERY_PREFIX = "/prometheus/api/v1/query"
# only the jobs that are running or completed within 7d should be included
# currently, we just set the limit to max
REST_JOB_API_PREFIX = "/rest-server/api/v2/jobs?order=completionTime,DESC"

TOKEN = os.environ.get('PAI_BEARER_TOKEN')

app = Flask(__name__)

def enable_request_debug_log(func):
    def wrapper(*args, **kwargs):
        requests_log = logging.getLogger("urllib3")
        level = requests_log.level
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

        try:
            return func(*args, **kwargs)
        finally:
            requests_log.setLevel(level)
            requests_log.propagate = False

    return wrapper


@enable_request_debug_log
def get_failed_job_gpu_mins(failed_jobs: list, start_timestamp: str, end_timestamp: str):
    # get jobs in time range via prometheus api
    query_url = os.environ.get('PAI_URI').rstrip("/") + QUERY_PREFIX
    time_range_in_min = int((int(end_timestamp) - int(start_timestamp)) / 1000 / 60)
    job_regex = "|".join(failed_jobs)
    query_string = f"sum (count_over_time(task_gpu_percent{{job_name=~\"{job_regex}\"}}[{time_range_in_min}m:]))"
    resp = requests.get(query_url, params={"query": query_string, "time": int(end_timestamp) // 1000})
    resp.raise_for_status()
    result = resp.json()
    job_gpu_mins = result["data"]["result"][0]["value"][1]
    logging.debug(f"Failed job gpu mins in time range from {start_timestamp} to {end_timestamp}: {job_gpu_mins}")
    return job_gpu_mins


@enable_request_debug_log
def get_job_list(state: str, start_timestamp: str, end_timestamp: str):
    # get failed jobs in time range via openpai api
    rest_url = os.environ.get('PAI_URI').rstrip("/") + REST_JOB_API_PREFIX + f"?"
    offset = 0
    limit = 1000
    headers = {'Authorization': f"Bearer {TOKEN}"}
    job_list = []
    while True:
        resp = requests.get(rest_url+f"limit={limit}&offset={offset}&state={state}", headers=headers)
        resp.raise_for_status()
        jobs = resp.json()
        # get the job list in time range
        jobs_in_time_range = [job for job in jobs
                              if int(job["completedTime"]) <= int(end_timestamp)
                              and int(job["completedTime"]) >= int(start_timestamp)]
        job_list += [job["username"] + "~" + job["name"] for job in jobs_in_time_range]
        offset += limit
        if int(jobs[-1]["completedTime"]) <= int(start_timestamp):
            break
    logging.debug(f"Failed jobs in time range from {start_timestamp} to {end_timestamp}: {job_list}")
    return job_list


@app.route('/healthz', methods=['GET'])
def healthz():
    return "ok"


@app.route('/metrics', methods=['GET'])
def get_cluster_job_gpu_hours():
    start_timestamp = request.args.get('start_timestamp')
    end_timestamp = request.args.get('end_timestamp')
    failed_jobs = get_job_list("FAILED", start_timestamp, end_timestamp)
    cluster_failed_job_gpu_mins = 0
    if not failed_jobs:
        cluster_failed_job_gpu_mins = 0
    else:
        cluster_failed_job_gpu_mins = get_failed_job_gpu_mins(failed_jobs, start_timestamp, end_timestamp)

    return jsonify(
        {
            "cluster_failed_job_gpu_mins": cluster_failed_job_gpu_mins,
            # "cluster_non_failed_job_gpu_idle_mins": cluster_non_failed_job_gpu_idle_mins,
            # "cluster_non_failed_job_utilized_gpu_mins": cluster_non_failed_job_utilized_gpu_mins,
            # "cluster_non_failed_job_nonutilized_gpu_mins": cluster_non_failed_job_nonutilized_gpu_mins
        }
    )


def main():
    app.run(host='0.0.0.0', port=5000)


if __name__ == "__main__":
    logging.basicConfig(
        format=
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s",
        level=logging.INFO,
    )
    main()
