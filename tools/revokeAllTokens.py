# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to revoke all tokens in the cluster.
# When the cluster has been updated with configuration such as 
# a user email alias has been moved to another group,
# we need to revoke all tokens to make the change effective
# so the user can login with the new group permission.

# Usage: python3 revokeAllTokens.py

import requests
import sys

def revoke_tokens(bearer_token, url):
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
    print("NOTE: This tool will revoke all tokens in the cluster including the application tokens.")
    print("Removing them may cause service disruptions.")
    print("If you try to remove the user releated tokens, please run `revokeUserTokens.py` instead.")
    print("Please make sure you understand the impact before proceeding.")
    confirm = input("Type 'yes' to proceed: ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        sys.exit(0)

    cluster_url = input("Enter the cluster URL (e.g. example.openpai.org): ")
    if not cluster_url:
        print("Cluster URL cannot be empty.")
        exit(1)
    
    token = input("Enter the bearer token: ")
    print("***********************************")   

    paiurl = f"https://{cluster_url}/rest-server/api/v1/token"

    response = revoke_tokens(token, paiurl)
    if response.status_code == 200:
        print("All tokens have been revoked successfully.")
    else:
        print(f"Failed to revoke tokens. Status code: {response.status_code}, Response: {response.text}")
