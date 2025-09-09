# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import timezone, datetime, timedelta
import logging
import os
import requests
import ssl
import socket
from cryptography import x509
from cryptography.hazmat.backends import default_backend

ALERT_PREFIX = "/alert-manager/api/v2/alerts"
ALERT_MANAGER_URL = os.environ.get(
    "ALERT_MANAGER_URL", "http://localhost:9093")
alertResidualDays = int(os.environ.get('ALERT_RESIDUAL_DAYS', 10))


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
def send_alert(cert_info: str, expiry_date: datetime, certExpirationInfo: str):
    trigger_time = str(datetime.now(timezone.utc).date())
    post_url = ALERT_MANAGER_URL.rstrip("/") + ALERT_PREFIX
    alerts = []
    alert = {
        "status": "firing",
        "labels": {
            "alertname": "cert-expiration",
            "severity": "warn",
            "group_email": os.environ.get("ALERT_GROUP_EMAIL"),
            "trigger_time": trigger_time,
        },
        "annotations": {
            "cert": cert_info,
            "expiry_date": str(expiry_date),
            "description": f"{certExpirationInfo}",
            "summary": f"Certificate {cert_info} will expire on {expiry_date}.",
        }
    }
    alerts.append(alert)
    logging.info("Sending alerts to alert-manager...")
    logging.info(post_url)
    logging.info(alerts)
    header = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    resp = requests.post(post_url, json=alerts, headers=header)
    resp.raise_for_status()
    logging.info("Alerts sent to alert-manager.")


def get_certificate_expiry_date(hostname, port=443):
    """Retrieve the SSL certificate expiry date for a given hostname and port."""
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            expiry_date = datetime.strptime(
                cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
            # Ensure expiry_date is timezone-aware
            if expiry_date.tzinfo is None:
                expiry_date = expiry_date.replace(tzinfo=timezone.utc)
            return expiry_date


def check_https_certificate_expiry():
    """Check the expiry date of the SSL certificate for the PAI URI specified in the environment variable PAI_URI."""
    PAI_URI = os.environ.get("PAI_URI")
    domain = PAI_URI.split("://")[1]
    port = 443
    if ":" in domain:
        try:
            # Extract port if specified
            port = int(domain.split(":")[1])
        except ValueError:
            logging.WARN(f"Invalid port in PAI_URI: {domain}")
            return
        domain = domain.split(":")[0]
    expirationTime = get_certificate_expiry_date(domain, port)
    delta = expirationTime - datetime.now(timezone.utc)
    if (delta < timedelta(days=alertResidualDays)):
        send_alert(PAI_URI, expirationTime,
                   f'The certificate for {PAI_URI} will expire on {expirationTime}. '
                   'There are only {delta.days} days, {delta.seconds//3600} hours '
                   'remaining before it expires.')


def check_file_certificate_expiry():
    """Check the expiry date of an SSL certificate from a file specified in the environment variable OIDC_CERT_FILE_PATH."""
    crt_file_path = os.environ.get("OIDC_CERT_FILE_PATH")
    if not crt_file_path:
        logging.warning("OIDC_CERT_FILE_PATH environment variable is not set.")
        return
    if not os.path.exists(crt_file_path):
        logging.error(f"Certificate file does not exist: {crt_file_path}")
        return
    try:
        with open(crt_file_path, "rb") as cert_file:
            cert_data = cert_file.read()
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            expiry_date = cert.not_valid_after_utc

            # Ensure expiry_date is timezone-aware
            if expiry_date.tzinfo is None:
                expiry_date = expiry_date.replace(tzinfo=timezone.utc)

            current_time = datetime.now(timezone.utc)
            delta = expiry_date - current_time

            if delta < timedelta(days=alertResidualDays):

                send_alert("OIDC_CERT_FILE", expiry_date,
                           f'The certificate file: OIDC_CERT_FILE will expire on {expiry_date}. '
                           f'There are only {delta.days} days, {delta.seconds//3600} hours '
                           f'remaining before it expires.')

    except FileNotFoundError:
        logging.error(f"Certificate file not found: {crt_file_path}")
    except Exception as e:
        logging.error(f"Error reading certificate file: {e}")


def main():
    logging.info("Starting certificate expiration checker...")
    check_https_certificate_expiry()
    check_file_certificate_expiry()
    logging.info("Certificate expiration checker completed.")


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s",
        level=logging.INFO,
    )
    main()
