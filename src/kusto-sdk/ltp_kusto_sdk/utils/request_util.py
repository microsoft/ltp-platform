import json
import os
import logging

from joblib import Parallel, delayed
from copy import deepcopy
import requests

logger = logging.getLogger(__name__)


class RequestUtil:

    def __init__(self):
        pass

    @staticmethod
    def put_request(url, payload, token):
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.put(url,
                                    data=json.dumps(payload),
                                    headers=headers)
            response.raise_for_status()  # Raise an error for bad status codes
            print(response.text)
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")

    @staticmethod
    def get_request(url, token):
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(url, headers=headers)
        # response.raise_for_status()  # Raise an error for bad status codes
        return response

    @staticmethod
    def prometheus_query(query, data, retry=3, entrypoint="we"):
        query = f"https://{entrypoint}.openpai.org/prometheus/api/v1/{query}"
        token = os.getenv("PAI_TOKEN")
        while retry > 0:
            response = RequestUtil.get_request(query, token)
            if response and response.ok:
                return json.loads(response.content)["data"]
            logger.error(
                f"Prometheus query failed. Query: {query} Response:{response.content}"
            )
            retry -= 1
        return None
