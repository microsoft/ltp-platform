import base64
from bs4 import BeautifulSoup
from datetime import timezone, datetime, timedelta
import logging
import markdown
import http
import os
import re
import requests
import tempfile
from urllib.parse import urljoin, urlparse
import urllib3
import uuid


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CLUSTER_QUERY_STRING = "avg(avg_over_time(nvidiasmi_utilization_gpu[7d]))"
JOB_GPU_PERCENT = 'avg by (job_name) (avg_over_time(task_gpu_percent[7d]))'
JOB_GPU_HOURS = 'sum by (job_name) (count_over_time(task_gpu_percent[7d]))'
# user used gpu hours / total gpu hours
USER_QUERY_STRING = \
    "(sum by (username) (sum_over_time(task_gpu_percent[7d]))) / (sum by (username) (count_over_time(task_gpu_percent[7d])*100)) * 100"

QUERY_PREFIX = "/prometheus/api/v1/query"
ALERT_PREFIX = "/alert-manager/api/v2/alerts"
# only the jobs that are running or completed within 7d should be included
# currently, we just set the limit to max
REST_JOB_API_PREFIX = "/rest-server/api/v2/jobs?order=completionTime,DESC"

TOKEN = os.environ.get('PAI_BEARER_TOKEN')
PROMETHEUS_SCRAPE_INTERVAL = int(os.environ.get('PROMETHEUS_SCRAPE_INTERVAL'))

SESSION_ID=""

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


def datetime_to_hours(dt):
    """Converts datetime.timedelta to hours

    Parameters:
    -----------
    dt: datetime.timedelta

    Returns:
    --------
    float
    """
    return dt.days * 24 + dt.seconds / 3600


def check_timestamp_within_7d(timestamp):
    """
    check if a timestamp is within 7 days
    """
    return datetime.fromtimestamp(int(timestamp/1000), timezone.utc) > datetime.now(timezone.utc) - timedelta(days=7)


def get_related_jobs(rest_url):
    """
    Returns all related jobs

    Returns:
    --------
    list
        All the jobs completed within 7 days will be included in the list.
        Jobs completed before 7 days may also be included.
        The list may contain duplicated jobs.
    """
    jobs_related = []

    offset = 0
    limit = 5000
    headers = {'Authorization': f"Bearer {TOKEN}"}
    while True:
        resp = requests.get(rest_url+f"limit={limit}&offset={offset}", headers=headers)
        resp.raise_for_status()
        jobs = resp.json()
        jobs_related += jobs
        # no more jobs or the last job in the list completed before 7 days
        if not jobs or (jobs[-1]["completedTime"] is not None and not check_timestamp_within_7d(jobs[-1]["completedTime"])) :
            break
        offset += limit

    return jobs_related


@enable_request_debug_log
def get_usage_info(job_gpu_percent, job_gpu_hours, user_usage_result, rest_url):
    job_infos = {}
    user_infos = {}
    jobs_related = get_related_jobs(rest_url)

    for v in user_usage_result["data"]["result"]:
        user_infos[v["metric"]["username"]] = {
            "username": v["metric"]["username"],
            "usage": v["value"][1][:6] + "%", "resources_occupied": 0
        }
    for v in job_gpu_percent["data"]["result"]:
        job_name = v["metric"]["job_name"]
        matched_job = list(
            filter(lambda job: f"{job['username']}~{job['name']}" == job_name,
            jobs_related))
        # ingore unfounded jobs
        if not matched_job:
            logging.warning("Job %s not found.", job_name)
            continue
        job_info = matched_job[0]
        # ignore jobs not started
        if not job_info["launchedTime"]:
            logging.warning("job not start, ignore it")
            continue

        job_infos[job_name] = {
            "job_name": job_name,
            "usage": v["value"][1],
            "gpu_number": job_info["totalGpuNumber"]
        }

        # get job duration
        job_infos[job_name]["start_time"] = datetime.fromtimestamp(
            int(job_info["launchedTime"]) / 1000,
            timezone.utc)
        # job has not finished
        if not job_info["completedTime"]:
            job_infos[job_name]["duration"] = datetime.now(timezone.utc) - job_infos[job_name]["start_time"]
        # job has finished
        else:
            job_infos[job_name]["duration"] = datetime.fromtimestamp(
                int(job_info["completedTime"]) / 1000,
                timezone.utc) - job_infos[job_name]["start_time"]
        job_infos[job_name]["status"] = job_info["state"]

        # get matched job gpu hours info
        gpu_hours_info = list(
            filter(lambda job: job["metric"]["job_name"] == job_name,
            job_gpu_hours["data"]["result"]))
        job_infos[job_name]["resources_occupied"] = float(gpu_hours_info[0]["value"][1]) * PROMETHEUS_SCRAPE_INTERVAL / 3600 # GPU * hours

        # gpu hours by user
        username = job_info["username"]
        user_infos[username]["resources_occupied"] += job_infos[job_name]["resources_occupied"]

    # format
    for job_info in job_infos.values():
        job_info["usage"] = job_info["usage"][:6] + "%"
        job_info["gpu_number"] = str(job_info["gpu_number"])
        job_info["duration"] = str(job_info["duration"])
        job_info["start_time"] = job_info["start_time"].strftime("%y-%m-%d %H:%M:%S")
        job_info["resources_occupied"] = f"{job_info['resources_occupied']:.2f}"
    for user_info in user_infos.values():
        user_info["resources_occupied"] = f"{user_info['resources_occupied']:.2f}"

    # sort usage info by resources occupied
    job_usage = sorted(job_infos.values(), key=lambda x: float(x["resources_occupied"]), reverse=True)
    user_usage = sorted(user_infos.values(), key=lambda x: float(x["resources_occupied"]), reverse=True)

    return job_usage[:10], user_usage


@enable_request_debug_log
def collect_metrics_from_prometheus(url):
    query_url = url.rstrip("/") + QUERY_PREFIX
    rest_url = url.rstrip("/") + REST_JOB_API_PREFIX

    # cluster info
    logging.info("Collecting cluster usage info...")
    resp = requests.get(query_url, params={"query": CLUSTER_QUERY_STRING})
    resp.raise_for_status()
    result = resp.json()
    cluster_usage = result["data"]["result"][0]["value"][1][:6] + "%"

    # user info
    logging.info("Collecting user usage info...")
    resp = requests.get(query_url, params={"query": USER_QUERY_STRING})
    resp.raise_for_status()
    user_usage_result = resp.json()

    # job info
    logging.info("Collecting job usage info...")
    # job gpu percent
    resp = requests.get(query_url, params={"query": JOB_GPU_PERCENT})
    resp.raise_for_status()
    job_gpu_percent = resp.json()
    # job gpu hours
    resp = requests.get(query_url, params={"query": JOB_GPU_HOURS})
    resp.raise_for_status()
    job_gpu_hours = resp.json()

    job_usage, user_usage = get_usage_info(job_gpu_percent, job_gpu_hours, user_usage_result, rest_url)

    return cluster_usage, job_usage, user_usage


@enable_request_debug_log
def collect_report_from_lucia(url, token, trace_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "x-lucia-traceId": trace_id,
        "Content-Type": "application/json"
    }
    end_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "async": False,
        "stream": False,
        "data": {
            "client": "openpai-monitor",
            "message": f"Please generate a cluster utilization report for OpenPAI. end_time is {end_time}, time_offset is {os.environ.get('LUCIA_TIME_OFFSET')}"
        }
    }
    resp = requests.post(url, headers=headers, json=payload, verify=False, timeout=1200)
    resp.raise_for_status()
    result = resp.json()
    # parse the message filed part
    # TODO(binyli): Avoid using global variable
    global SESSION_ID
    SESSION_ID = next(iter(result))
    message = result[SESSION_ID]["data"]["messages"][0]["data"]["messages"]["result"]
    return message


def generate_alerts_from_prometheus():
    alerts = []
    trigger_time = str(datetime.now(timezone.utc).date())
    # for cluster
    alert = {
        "labels": {
            "alertname": "usage",
            "report_type": "cluster-usage",
            "severity": "info",
            "cluster_usage": cluster_usage,
            "trigger_time": trigger_time,
            "group_email": os.environ.get("REPORT_GROUP_EMAIL"),
        },
        "annotations": {
            "summary": "The cluster usage has been reported, please check your email-box for details."
        }
    }
    alerts.append(alert)

    # for job
    for job in job_usage:
        alert = {
            "labels": {
                "alertname": "usage",
                "report_type": "cluster-usage",
                "severity": "info",
                "job_name": job["job_name"],
                "resources_occupied": job["resources_occupied"],
                "gpu_number": job["gpu_number"],
                "usage": job["usage"],
                "duration": job["duration"],
                "start_time": job["start_time"],
                "status": job["status"],
                "trigger_time": trigger_time,
            },
            "annotations": {
                "summary": "The cluster usage has been reported, please check your email-box for details."
            }
        }
        alerts.append(alert)

    # for user
    for user in user_usage:
        alert = {
            "labels": {
                "alertname": "usage",
                "report_type": "cluster-usage",
                "severity": "info",
                "username": user["username"],
                "resources_occupied": user["resources_occupied"],
                "usage": user["usage"],
                "trigger_time": trigger_time,
            },
            "annotations": {
                "summary": "The cluster usage has been reported, please check your email-box for details."
            }
        }
        alerts.append(alert)
    return alerts


def download_png_files_from_nginx(url, temp_dir):
    response = requests.get(url, verify=False, timeout=1200)
    if response.status_code == http.HTTPStatus.OK:
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all anchor tags (links)
        anchor_tags = soup.find_all('a')

        # Filter and download PNG files
        for tag in anchor_tags:
            file_link = tag.get('href')
            if file_link and file_link.endswith('.png'):
                # Construct the full URL if the file link is relative
                file_url = urljoin(url, file_link)
                # Extract the image filename
                file_name = os.path.basename(file_url)
                file_path = os.path.join(temp_dir, file_name)

                # Download the image
                try:
                    file_data = requests.get(file_url, verify=False)
                    if file_data.status_code == http.HTTPStatus.OK:
                        with open(file_path, 'wb') as file:
                            file.write(file_data.content)
                        logging.info(f"Downloaded: {file_name} to {file_path}")
                    else:
                        logging.error(f"Failed to download: {file_url} (Status code: {file_data.status_code})")
                except Exception as e:
                    logging.exception(f"Error downloading {file_url}: {e}")
    else:
        logging.error(f"Failed to access {url} (Status code: {response.status_code})")

def convert_markdown_to_html_with_embedded_images(markdown_text, pic_dir):
    # Find all image references in the markdown text
    image_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
    matches = image_pattern.findall(markdown_text)

    # Replace image references with base64-encoded versions
    for alt_text, image_name in matches:
        image_path = os.path.join(pic_dir, image_name)
        try:
            # Read the image file and encode it in base64
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                # Determine the image type (assuming png for simplicity, adjust if needed)
                image_type = image_name.split('.')[-1]
                image_data_uri = f"data:image/{image_type};base64,{encoded_string}"
                # Replace the markdown image with the HTML image tag containing base64
                html_image_tag = f'<img alt="{alt_text}" src="{image_data_uri}" />'
                markdown_text = markdown_text.replace(f'![{alt_text}]({image_name})', html_image_tag)
        except FileNotFoundError:
            logging.exception(f"Image {image_path} not found.")
    return markdown_text

def generate_alerts_from_lucia(message: str, lucia_url: str, trace_id: str):
    alerts = []
    trigger_time = str(datetime.now(timezone.utc).date())
    with tempfile.TemporaryDirectory() as temp_dir:
        parsed_url = urlparse(lucia_url)
        url = f"{parsed_url.scheme}://{parsed_url.netloc}" + f"/system-files/agents/openpai-monitor/report/{trigger_time}/{SESSION_ID}/{trace_id}/"
        download_png_files_from_nginx(url, temp_dir)
        message = convert_markdown_to_html_with_embedded_images(message, temp_dir)
    alert = {
        "labels": {
            "alertname": "cluster-report-lucia",
            "report_type": "cluster-report-lucia",
            "severity": "info",
            "trigger_time": trigger_time,
            "group_email": os.environ.get("REPORT_GROUP_EMAIL"),
        },
        "annotations": {
            "summary": "Cluster utilization report",
            "description": markdown.markdown(message, extensions=['tables']), # convert markdown to html
        }
    }
    alerts.append(alert)
    return alerts


@enable_request_debug_log
def send_alert(pai_url: str, alerts):
    post_url = pai_url.rstrip("/") + ALERT_PREFIX
    logging.info("Sending alerts to alert-manager...")
    resp = requests.post(post_url, json=alerts)
    resp.raise_for_status()
    logging.info("Alerts sent to alert-manager.")


def main():
    REPORT_SOURCE = os.environ.get("REPORT_SOURCE")
    PAI_URI = os.environ.get("PAI_URI")

    if REPORT_SOURCE == "PROMETHEUS":
        logging.info("Collecting metrics from Prometheus...")
        # collect cluster gpu usage information
        cluster_usage, job_usage, user_usage = collect_metrics_from_prometheus(PAI_URI)
        alerts = generate_alerts_from_prometheus(cluster_usage, job_usage, user_usage)

        # send alert to alert manager
    elif REPORT_SOURCE == "LUCIA":
        logging.info("Collecting metrics from Lucia...")
        trace_id = str(uuid.uuid4())
        lucia_url = os.environ.get("LUCIA_URL")
        # collect cluster gpu usage information
        message = collect_report_from_lucia(
            lucia_url,
            os.environ.get("LUCIA_BEARER_TOKEN"),
            trace_id
        )
        alerts = generate_alerts_from_lucia(message, lucia_url, trace_id)
    send_alert(PAI_URI, alerts)

if __name__ == "__main__":
    logging.basicConfig(
        format=
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s",
        level=logging.INFO,
    )
    main()
