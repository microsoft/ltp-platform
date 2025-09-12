# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to set the prod job privilege for users in the cluster,
# so the user can submit prod jobs. By default,
# the job privilege is set to one month after the current time.

# Usage: python3 setUserProdJob.py

import requests
import json
import time

def put_request(url, payload, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.put(url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        print(response.text)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

def get_request(url, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        print(response.text)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    cluster_url = input("Enter the cluster URL (e.g. example.openpai.org): ")
    if not cluster_url:
        print("Cluster URL cannot be empty.")
        exit(1)
    
    names = input("Enter the user names (comma separated): ").split(",")
    names = [name.strip() for name in names]  # Strip whitespace from each name
    if not names:
        print("User names cannot be empty.")
        exit(1)

    token = input("Enter the bearer token: ")
    print("***********************************")

    for name in names:
        post_url = f"https://{cluster_url}/rest-server/api/v2/users/{name}"
        data = {
            "data": {
            "username": name,
            "extension": {
                "jobPriority": 1,  # Replace with the desired quota value
                "jobExpiration": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime(time.time() + 2592000))  # One month after current time
            }
            },
            "patch": True
        }
        put_request(post_url, data, token)

        print(f"Set job expiration for user {name} to one month from now.")
        print("***********************************")

    print("Job expiration set successfully for all users.")