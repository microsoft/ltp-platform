"""This module contains functions for generating, parsing, and aligning DCW objects."""

from __future__ import annotations

import requests

class RestAPIClient:
    def __init__(self, base_url, headers=None):
        """
        Initialize the REST API client.
        
        :param base_url: Base URL of the REST API server.
        :param headers: Default headers to include in all requests.
        """
        self.base_url = base_url
        self.headers = headers if headers else {}

    def get(self, endpoint, params=None):
        """
        Perform a GET request.
        
        :param endpoint: API endpoint (relative to base_url).
        :param params: Query parameters for the request.
        :return: Response object.
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        return response

    def post(self, endpoint, data=None, json=None):
        """
        Perform a POST request.
        
        :param endpoint: API endpoint (relative to base_url).
        :param data: Form data for the request.
        :param json: JSON data for the request.
        :return: Response object.
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, headers=self.headers, data=data, json=json)
        return response

    def put(self, endpoint, data=None, json=None):
        """
        Perform a PUT request.
        
        :param endpoint: API endpoint (relative to base_url).
        :param data: Form data for the request.
        :param json: JSON data for the request.
        :return: Response object.
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.put(url, headers=self.headers, data=data, json=json)
        return response

    def delete(self, endpoint):
        """
        Perform a DELETE request.
        
        :param endpoint: API endpoint (relative to base_url).
        :return: Response object.
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.delete(url, headers=self.headers)
        return response