# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to display all users in the cluster and their details.
# Usage: python3 displayUser.py

import requests
import json


def get_user_info(url, token):
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
    cluster_url = input("Enter the cluster URL (e.g. example.openpai.org): ")
    if not cluster_url:
        print("Cluster URL cannot be empty.")
        exit(1)
    
    token = input("Enter the bearer token: ")
    print("***********************************")

    paiurl = f"https://{cluster_url}/rest-server/api/v2/user/"

    user_data = get_user_info(paiurl, token)
    if user_data:
        for user in user_data:
            user_name = user['username']
            user_url = f"{paiurl}{user_name}"
            detailed_info = get_user_info(user_url, token)
            if detailed_info:
                if 'extension' in detailed_info and 'jobSSH' in detailed_info['extension']:
                    del detailed_info['extension']['jobSSH']
                print(f"Details for user \"{user_name}\":")
                print(json.dumps(detailed_info, indent=4))
            else:
                print(f"Failed to retrieve details for user \"{user_name}\".")
            print("***********************************")
    else:
        print("Failed to retrieve user data.")