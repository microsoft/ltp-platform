# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to update group info in the cluster, such as adding/removing virtual clusters or blob storage configs.
# Usage: python3 updateGroupInfo.py <group_name> <command_type> <item1,item2,...>
# command_type: addvc, removevc, addblob, removeblob

import requests
import sys

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

def update_group_info(url, token, data):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'patch': True,
        'data': data
    }
    try:
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()  # Assuming the response is in JSON format
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python updateGroupInfo.py <group_name> <command_type> <item1,item2,...>")
        sys.exit(1)

    command_type = sys.argv[2]
    items = sys.argv[3].split(',')
    if command_type not in ["addvc", "removevc", "addblob", "removeblob"]:
        print("Invalid command type. Must be one of: addvc, removevc, addblob, removeblob")
        sys.exit(1)

    cluster_name = input("Enter the cluster name: ")
    if not cluster_name:
        print("Cluster name cannot be empty.")
        exit(1)
    
    token = input("Enter the bearer token: ")
    print("***********************************")    

    group_name = sys.argv[1]
    paiurl = f"https://{cluster_name}.openpai.org/rest-server/api/v2/group/"
    url = f"{paiurl}{group_name}"  # Replace with the actual URL
    data = get_group_info(url, token)

    if data:
        if command_type == "addvc":
            for item in items:
                if item not in data['extension']['acls']['virtualClusters']:
                    data['extension']['acls']['virtualClusters'].append(item)
        elif command_type == "removevc":
            for item in items:
                if item in data['extension']['acls']['virtualClusters']:
                    data['extension']['acls']['virtualClusters'].remove(item)
        elif command_type == "addblob":
            if 'storageConfigs' not in data['extension']['acls']:
                data['extension']['acls']['storageConfigs'] = []
            for item in items:
                if item not in data['extension']['acls']['storageConfigs']:
                    data['extension']['acls']['storageConfigs'].append(item)
        elif command_type == "removeblob":
            if 'storageConfigs' not in data['extension']['acls']:
                    print("No storageConfigs found to remove.")
                    sys.exit(0)
            for item in items:
                if item in data['extension']['acls']['storageConfigs']:
                    data['extension']['acls']['storageConfigs'].remove(item)

        newdata = data
        print("Received data:", newdata)
        print("-------------------------")

        updated_data = update_group_info(paiurl, token, newdata)
        if updated_data:
            print("Group info updated successfully.")
        else:
            print("Failed to update group info.")
    else:
        print("Failed to retrieve data.")