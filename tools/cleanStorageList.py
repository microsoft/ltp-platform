import requests

def post_request_with_token(url, token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers)
    return response.json()

def main():
    cluster_name = input("Enter the cluster name: ")
    if not cluster_name:
        print("Cluster name cannot be empty.")
        exit(1)
    
    token = input("Enter the bearer token: ")
    print("***********************************")

    url = f"https://{cluster_name}.openpai.org/rest-server/api/v2/storages/refresh"
    response = post_request_with_token(url, token)
    print(response)

if __name__ == "__main__":
    main()
