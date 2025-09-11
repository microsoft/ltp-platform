# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to delete a group in the cluster, which also removes the group from all users' group list.
# Usage: python3 deleteGroup.py <group_name>

import requests
import sys

def delete_group(bearer_token, url):
    """
    Sends a DELETE request to the REST server to delete a group.

    :param bearer_token: The Bearer token for authentication
    :param url: The URL of the group to delete
    :return: Response object from the server
    """
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    response = requests.delete(url, headers=headers)
    return response

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deleteGroup.py <group_name>")
        sys.exit(1)

    group_name = sys.argv[1]

    cluster_name = input("Enter the cluster name: ")
    if not cluster_name:
        print("Cluster name cannot be empty.")
        exit(1)
    
    token = input("Enter the bearer token: ")
    print("***********************************")   

    paiurl = f"https://{cluster_name}.openpai.org/rest-server/api/v2/group/"

    url = f"{paiurl}{group_name}"  # Replace with the actual URL
    response = delete_group(token, url)
    if response.status_code == 200:
        print("Group deleted successfully.")
    else:
        print(f"Failed to delete group. Status code: {response.status_code}, Response: {response.text}")
