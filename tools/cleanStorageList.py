# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to refresh the PV/PVC cache in rest-server.
# If we have changed the PV/PVC directly in Kubernetes, we can use this tool to make the change effective in OpenPAI.

# Usage: python3 cleanStorageList.py

import requests

def post_request_with_token(url, token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers)
    return response.json()

def main():
    cluster_url = input("Enter the cluster URL (e.g. example.openpai.org): ")
    if not cluster_url:
        print("Cluster URL cannot be empty.")
        exit(1)
    
    token = input("Enter the bearer token: ")
    print("***********************************")

    url = f"https://{cluster_url}/rest-server/api/v2/storages/refresh"
    response = post_request_with_token(url, token)
    print(response)

if __name__ == "__main__":
    main()
