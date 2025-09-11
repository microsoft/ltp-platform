# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to display all groups in the cluster and their details.
# Usage: python3 displayGroup.py

import requests
import json


def get_group_info(url, token):
    headers = {
        'Authorization': f'Bearer {token}'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()  # Assuming the response is in JSON format
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == "__main__":
    cluster_name = input("Enter the cluster name: ")
    if not cluster_name:
        print("Cluster name cannot be empty.")
        exit(1)
    
    token = input("Enter the bearer token: ")
    print("***********************************")

    paiurl = f"https://{cluster_name}.openpai.org/rest-server/api/v2/group/"

    group_data = get_group_info(paiurl, token)
    if group_data:
        for group in group_data:
            group_name = group['groupname']
            group_url = f"{paiurl}{group_name}"
            detailed_info = get_group_info(group_url, token)
            if detailed_info:
                print(f"Details for group \"{group_name}\":")
                print(json.dumps(detailed_info, indent=4))
            else:
                print(f"Failed to retrieve details for group \"{group_name}\".")
            print("***********************************")
    else:
        print("Failed to retrieve group data.")