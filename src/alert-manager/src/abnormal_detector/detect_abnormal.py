# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from dataclasses import dataclass
from datetime import timezone, datetime
import logging
import os
import requests
import uuid
import json

ALERT_PREFIX = "/alert-manager/api/v2/alerts"

@dataclass
class AbnormalJob:
    username: str
    job_name: str
    action: int
    reason: str
    notification: str


@dataclass
class QuotaAdjuestInfo:
    username: str
    max_gpus_per_job: int
    expiration_time: str
    reason: str

@dataclass
class DiagnoseInfo:
    abnormal_jobs: list[AbnormalJob]
    quota_adjustments: list[QuotaAdjuestInfo]


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
def get_diagnose_info() -> DiagnoseInfo:
    lucia_url = os.environ.get("LUCIA_URL")
    lucia_token = os.environ.get("LUCIA_BEARER_TOKEN")
    if not lucia_url or not lucia_token:
        raise ValueError("LUCIA_URL and LUCIA_TOKEN environment variables must be set")
    lucia_trace_id = uuid.uuid4()
    trigger_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    time_offset = os.environ.get("LUCIA_DIAGNOSTIC_TIME_OFFSET", "30m")
    headers = {
        "Authorization": f"Bearer {lucia_token}",
        "x-lucia-traceId": str(lucia_trace_id),
        "Content-Type": "application/json",
    }
    body = {
        "async": False,
        "stream": False,
        "data": {
            "client": "openpai-monitor",
            "message": f"I want to detect abnormal behavior of the jobs and users running on Lucia Training platform and take corresponding actions. action is detect-abnormal-behavior, end_time is {trigger_time} and time_offset is {time_offset}"
        }
    }
    resp = requests.post(lucia_url, json=body, headers=headers, verify=False, timeout=1200)
    resp.raise_for_status()
    data = resp.json()
    uuid_key = next(iter(data))
    data = data[uuid_key]["data"]["messages"][0]["data"]["messages"]["result"]
    data = json.loads(data)
    abnormal_jobs = []
    for job in data["abnormal_jobs"]:
        abnormal_jobs.append(AbnormalJob(
            username=job["user"],
            job_name=job["job_name"],
            action=job.get("action", "none"),
            reason=job["reason"],
            notification=job["notification"],
        ))
    quota_adjustments = []
    for quota in data["quota_adjustments"]:
        expiration_time = datetime.strptime(quota["expiration"], '%Y-%m-%d %H:%M:%S')
        expiration_time = expiration_time.replace(tzinfo=timezone.utc)
        expiration_time = expiration_time.isoformat()
        quota_adjustments.append(QuotaAdjuestInfo(
            username=quota["user"],
            max_gpus_per_job=quota["max_gpus_per_job"],
            expiration_time=expiration_time,
            reason=quota["reason"],
        ))
    return DiagnoseInfo(abnormal_jobs=abnormal_jobs, quota_adjustments=quota_adjustments)

@enable_request_debug_log
def send_abnormal_job_alerts(pai_url: str, abnormal_jobs: list[AbnormalJob]):
    trigger_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    post_url = pai_url.rstrip("/") + ALERT_PREFIX
    alerts = []
    for abnormal_job in abnormal_jobs:
        alert = {
            "status": "firing",
            "labels": {
                "alertname": "PAIAbnormalJob",
                "report_type": "abnormal-job",
                "severity": "warn",
                "trigger_time": trigger_time,
                "username": abnormal_job.username,
                "job_name": f"{abnormal_job.username}~{abnormal_job.job_name}",
                "action": abnormal_job.action,
            },
            "annotations": {
                "summary": f"Job {abnormal_job.job_name} is abnormal due to {abnormal_job.reason} Will take action: {abnormal_job.action}",
                "description": f"Job {abnormal_job.job_name} is abnormal due to {abnormal_job.reason}",
                "action": abnormal_job.action,
                "reason": abnormal_job.reason,
                "notification": abnormal_job.notification
            }
        }
        alerts.append(alert)
    if len(alerts) == 0:
        logging.info("No abnormal job detected.")
        return
    logging.info("Sending alerts abnormal_job to alert-manager...")
    resp = requests.post(post_url, json=alerts)
    resp.raise_for_status()
    logging.info("abnormal_job alerts sent to alert-manager.")



@enable_request_debug_log
def send_quota_adjust_alerts(pai_url: str, qutoa_adjuest_infos: list[QuotaAdjuestInfo]):
    trigger_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    post_url = pai_url.rstrip("/") + ALERT_PREFIX
    alerts = []
    for qutoa_adjuest_info in qutoa_adjuest_infos:
        alert = {
            "status": "firing",
            "labels": {
                "alertname": "PAIQuotaAdjust",
                "report_type": "adjust-user-quota",
                "severity": "warn",
                "trigger_time": trigger_time,
                "username": qutoa_adjuest_info.username,
            },
            "annotations": {
                "summary": f"User {qutoa_adjuest_info.username}'s quota will be adjusted",
                "description": f"User {qutoa_adjuest_info.username}'s quota will be adjusted to {qutoa_adjuest_info.max_gpus_per_job} GPUs due to {qutoa_adjuest_info.reason}. The adjustment will expire at {qutoa_adjuest_info.expiration_time}",
                "expiration": qutoa_adjuest_info.expiration_time,
                "reason": qutoa_adjuest_info.reason,
                "max_gpus_per_job": str(qutoa_adjuest_info.max_gpus_per_job),
            }
        }
        alerts.append(alert)
    if len(alerts) == 0:
        logging.info("No quota adjust detected.")
        return
    logging.info("Sending alerts quota_adjust to alert-manager...")
    resp = requests.post(post_url, json=alerts)
    resp.raise_for_status()
    logging.info("quota_adjust alerts sent to alert-manager.")

def main():
    PAI_URI = os.environ.get("PAI_URI")
    if not PAI_URI:
        logging.error("PAI_URI is not set")
        return
    diagnose_info = get_diagnose_info()
    send_quota_adjust_alerts(PAI_URI, diagnose_info.quota_adjustments)
    send_abnormal_job_alerts(PAI_URI, diagnose_info.abnormal_jobs)

if __name__ == "__main__":
    logging.basicConfig(
        format=
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s",
        level=logging.INFO,
    )
    main()

