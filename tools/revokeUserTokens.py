# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to revoke all tokens in the cluster and restore the application token.
# Usage: python3 revokeUserTokens.py

import sys
import jwt
import base64
import uuid
import requests
from kubernetes import client, config


def revoke_all_tokens_via_api(cluster_name, bearer_token):
    url = f"https://{cluster_name}.ltp.hpc-lucia.com/rest-server/api/v2/token"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        print("✓ All tokens revoked via REST API (cache cleared).")
        return True
    else:
        print(f"✗ Failed to revoke tokens. Status: {response.status_code}, Response: {response.text}")
        return False


def get_application_token(namespace="default", deployment_name="alertmanager", container_name="job-status-change-notification"):
    """
    Retrieve PAI_BEARER_TOKEN from application deployment.

    Args:
        namespace: Kubernetes namespace (default: default)
        deployment_name: Name of the deployment (default: alertmanager)
        container_name: Name of the container (default: job-status-change-notification)

    Returns:
        The token string, or None if not found
    """
    try:
        config.load_kube_config()
        apps_v1 = client.AppsV1Api()

        # Get the deployment
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)

        # Find the container and get the PAI_BEARER_TOKEN env var
        for container in deployment.spec.template.spec.containers:
            if container.name == container_name:
                if container.env:
                    for env_var in container.env:
                        if env_var.name == "PAI_BEARER_TOKEN":
                            if env_var.value:
                                return env_var.value
                            elif env_var.value_from:
                                print(f"PAI_BEARER_TOKEN is from a secret/configmap, not a direct value")
                                return None

        print(f"PAI_BEARER_TOKEN not found in container {container_name}")
        return None

    except Exception as e:
        print(f"Error retrieving token from deployment: {e}")
        return None




def add_token_to_k8s_secret(token_string, namespace="pai-user-token"):
    """
    Add a token to Kubernetes secret.

    Args:
        token_string: The JWT token to add
        namespace: Kubernetes namespace (default: pai-user-token)

    Returns:
        True if successful, False otherwise
    """
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()

        # Decode JWT to get username
        try:
            payload = jwt.decode(token_string, options={"verify_signature": False})
            username = payload.get('username')
            if not username:
                print("Username not found in token")
                return False
        except jwt.DecodeError as e:
            print(f"Failed to decode token: {e}")
            return False

        print(f"Token belongs to user: {username}")

        # Convert username to HEX for secret name
        secret_name = username.encode('utf-8').hex()
        print(f"Secret name (HEX): {secret_name}")

        # Generate UUID for the key
        key = str(uuid.uuid4())
        print(f"Generated UUID key: {key}")

        # Create the secret with the token
        encoded_data = {
            key: base64.b64encode(token_string.encode('utf-8')).decode('utf-8')
        }

        new_secret = client.V1Secret(
            metadata=client.V1ObjectMeta(name=secret_name, namespace=namespace),
            data=encoded_data
        )

        v1.create_namespaced_secret(namespace=namespace, body=new_secret)
        print(f"Created secret '{secret_name}' with token")

        return True

    except Exception as e:
        print(f"Error adding token to K8s secret: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Token Revocation and Restoration Tool")
    print("=" * 70)
    print("\nThis tool will revoke all user tokens via REST API (clearing cache)")
    print("and restore the application token.")
    print("\n⚠️  WARNING: This will cause service disruptions during execution!")
    print("=" * 70)

    cluster_name = input("\nEnter the cluster name: ")
    if not cluster_name:
        print("Cluster name cannot be empty.")
        sys.exit(1)

    admin_token = input("Enter an admin bearer token: ")
    if not admin_token:
        print("Bearer token cannot be empty.")
        sys.exit(1)

    confirm = input("\nType 'yes' to proceed: ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        sys.exit(0)

    # Step 1: Retrieve alert-manager token
    print("\n" + "=" * 70)
    print("Step 1: Retrieving PAI_BEARER_TOKEN from alert-manager")
    print("=" * 70)

    alert_token = get_application_token()

    if not alert_token:
        print("\n✗ Failed to retrieve alert-manager token.")
        print("Do you want to continue without it? (The alert-manager token will NOT be restored)")
        continue_choice = input("Type 'yes' to continue: ")
        if continue_choice.lower() != 'yes':
            print("Operation cancelled.")
            sys.exit(1)
    else:
        print(f"✓ Successfully retrieved alert-manager token")
        print(f"Token (truncated): {alert_token[:20]}...{alert_token[-20:]}")

    # Step 2: Revoke all tokens via REST API (clears cache)
    print("\n" + "=" * 70)
    print("Step 2: Revoking all tokens via REST API")
    print("=" * 70)

    if not revoke_all_tokens_via_api(cluster_name, admin_token):
        sys.exit(1)

    # Step 3: Add alert-manager token back
    if alert_token:
        print("\n" + "=" * 70)
        print("Step 3: Adding alert-manager token back")
        print("=" * 70)

        if add_token_to_k8s_secret(alert_token):
            print("✓ Alert-manager token has been restored successfully.")
        else:
            print("✗ Failed to restore alert-manager token.")
            sys.exit(1)

    print("\n" + "=" * 70)
    print("✓ Operation completed successfully!")
    print("=" * 70)
