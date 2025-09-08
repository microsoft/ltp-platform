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
    cluster_name = input("Enter the cluster name: ")
    if not cluster_name:
        print("Cluster name cannot be empty.")
        exit(1)
    
    names = input("Enter the user names (comma separated): ").split(",")
    names = [name.strip() for name in names]  # Strip whitespace from each name
    if not names:
        print("User names cannot be empty.")
        exit(1)

    vc_names = input("Enter the VC names (comma separated), empty means removing all existing admins for the users: ").split(",")
    if vc_names == [''] or not vc_names:
        vc_names = []
    else:
        vc_names = [vc.strip() for vc in vc_names if vc.strip()]

    token = input("Enter the bearer token: ")
    print("***********************************")        

    for name in names:
        post_url = f"https://{cluster_name}.openpai.org/rest-server/api/v2/users/{name}"
        data = {
            "data": {
            "username": name,
            "extension": {
                "vcadmins": vc_names
            }
            },
            "patch": True
        }
        put_request(post_url, data, token)

        print(f"Set user {name} as the admin of the clusters {vc_names}.")
        print("***********************************")

    print("Successfully setting VC admins for all users.")