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

    cluster_name = input("Enter the cluster name: ")
    if not cluster_name:
        print("Cluster name cannot be empty.")
        exit(1)
    
    token = input("Enter the bearer token: ")
    print("***********************************")   

    paiurl = f"https://{cluster_name}.openpai.org/rest-server/api/v1/token"
    
    response = revoke_tokens(token, paiurl)
    if response.status_code == 200:
        print("All tokens have been revoked successfully.")
    else:
        print(f"Failed to revoke tokens. Status code: {response.status_code}, Response: {response.text}")
