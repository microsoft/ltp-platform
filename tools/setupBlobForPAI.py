import yaml
import subprocess
import requests
import os
import json
import sys


def create_pv_yaml(storage_name, storage_account, resource_group, identity, output_file):
    container_name = storage_name.replace("-", "")
    blob_name = f'blob-{container_name}-{storage_account}'

    pv_template = {
        'apiVersion': 'v1',
        'kind': 'PersistentVolume',
        'metadata': {
            'name': blob_name,
        },
        'spec': {
            'accessModes': ['ReadWriteMany'],
            'capacity': {
                'storage': '1Pi'
            },
            'csi': {
                'driver': 'blob.csi.azure.com',
                'volumeAttributes': {
                    'AzureStorageAuthType': 'MSI',
                    'AzureStorageIdentityClientID': identity,
                    'containerName': storage_name,
                    'protocol': 'fuse',
                    'resourceGroup': resource_group,
                    'storageAccount': storage_account,
                    'allow-non-empty-temp': 'true',
                    'cleanup-on-start': 'true'
                },
                'volumeHandle': blob_name
            },
            'mountOptions': [
                '--allow-other',
                '--attr-timeout=3600',
                '--entry-timeout=3600',
                '--attr-cache-timeout=7200',
                '--block-cache',
                '--block-cache-pool-size=81920',
                '--block-cache-block-size=1',
                f'--block-cache-path=/mnt/blobfusecache-{container_name}-{storage_account}',
                '--block-cache-disk-size=1572864',
                '--block-cache-prefetch=12',
                '--block-cache-prefetch-on-open=false'
            ],
            'persistentVolumeReclaimPolicy': 'Retain',
            'storageClassName': 'azureblob-fuse-premium',
            'volumeMode': 'Filesystem'
        }
    }

    with open(output_file, 'w') as file:
        yaml.dump(pv_template, file)

    return blob_name

def create_pv_out_yaml(storage_name, storage_account, resource_group, identity, output_file):
    container_name = storage_name.replace("-", "")
    blob_name = f'blob-{container_name}-{storage_account}-out'

    pvc_template = {
        'apiVersion': 'v1',
        'kind': 'PersistentVolume',
        'metadata': {
            'name': blob_name,
        },
        'spec': {
            'accessModes': ['ReadWriteMany'],
            'capacity': {
                'storage': '1Pi'
            },
            'csi': {
                'driver': 'blob.csi.azure.com',
                'volumeAttributes': {
                    'AzureStorageAuthType': 'MSI',
                    'AzureStorageIdentityClientID': identity,
                    'containerName': storage_name,
                    'protocol': 'fuse',
                    'resourceGroup': resource_group,
                    'storageAccount': storage_account
                },
                'volumeHandle': blob_name
            },
            'mountOptions': [
                '--allow-other',
                '--attr-timeout=600',
                '--entry-timeout=600',
                '--attr-cache-timeout=600',
                '--file-cache-timeout=3600',
                f'--tmp-path=/mnt/blobfusecache-{container_name}-{storage_account}-out',
                '--cache-size-mb=512000',
                '--lazy-write',
                'cleanup-on-start': 'true'
            ],
            'persistentVolumeReclaimPolicy': 'Retain',
            'storageClassName': 'azureblob-fuse-premium',
            'volumeMode': 'Filesystem'
        }
    }

    with open(output_file, 'w') as file:
        yaml.dump(pvc_template, file)

    return blob_name

def apply_yaml_to_aks(yaml_file):
    try:
        subprocess.run(["kubectl", "apply", "-f", yaml_file], check=True)
        print(f"Successfully applied {yaml_file} to AKS.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply {yaml_file} to AKS: {e}")

def create_pvc_yaml(blob_name, output_file):
    pvc_template = {
        'apiVersion': 'v1',
        'kind': 'PersistentVolumeClaim',
        'metadata': {
            'name': blob_name,
            'namespace': 'default'
        },
        'spec': {
            'accessModes': ['ReadWriteMany'],
            'resources': {
                'requests': {
                    'storage': '1Pi'
                }
            },
            'volumeName': blob_name,
            'storageClassName': 'azureblob-fuse-premium',
            'volumeMode': 'Filesystem'
        }
    }

    with open(output_file, 'w') as file:
        yaml.dump(pvc_template, file)

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

def refresh_group_info(url, token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers)
    return response.json()


if __name__ == "__main__":
    cluster_name = input("Enter the cluster name: ")
    identity = input("Enter the identity GUID: ")
    
    storage_account = input("Enter the storage account name: ")
    storage_name = input("Enter the container name: ")
    resource_group = input("Enter the resource group name: ")
    bearer_token = input("Enter the bearer token: ")
    groupname = input("Enter the group name: ") # split by comma if multiple groups
    groupname = groupname.split(",")
    
    try:
        in_blob_name = create_pv_yaml(storage_name, storage_account, resource_group, identity, "pv_input.yaml")
    except Exception as e:
        print(f"Failed to create input PV YAML: {e}")
        exit(1)

    print(f"Input blob: {in_blob_name} created successfully.")        

    try:
        out_blob_name = create_pv_out_yaml(storage_name, storage_account, resource_group, identity, "pv_output.yaml")
    except Exception as e:
        print(f"Failed to create output PV YAML: {e}")
        exit(1)

    print(f"Output blob: {out_blob_name} created successfully.")

    if os.path.exists("pv_input.yaml"):
        apply_yaml_to_aks("pv_input.yaml")
    else:
        print("pv_input.yaml does not exist. Skipping.")
    
    print(f"Applying PV {in_blob_name} to AKS...")

    if os.path.exists("pv_output.yaml"):
        apply_yaml_to_aks("pv_output.yaml")
    else:
        print("pv_output.yaml does not exist. Skipping.")

    print(f"Applying PV {out_blob_name} to AKS...")

    os.remove("pv_input.yaml")
    os.remove("pv_output.yaml")

    print("PV YAML files removed.")

    try:
        create_pvc_yaml(in_blob_name, "pvc_input.yaml")
    except Exception as e:
        print(f"Failed to create input PVC YAML: {e}")
        exit(1)

    print(f"Input PVC blob: {in_blob_name} created successfully.")

    try:
        create_pvc_yaml(out_blob_name, "pvc_output.yaml")
    except Exception as e:
        print(f"Failed to create output PVC YAML: {e}")
        exit(1)

    print(f"Output PVC blob: {out_blob_name} created successfully.")

    try:
        apply_yaml_to_aks("pvc_input.yaml")
    except Exception as e:
        print(f"Failed to apply pvc_input.yaml to AKS: {e}")
        exit(1)

    print(f"Applying PVC {in_blob_name} to AKS...")

    try:
        apply_yaml_to_aks("pvc_output.yaml")
    except Exception as e:
        print(f"Failed to apply pvc_output.yaml to AKS: {e}")
        exit(1)

    print(f"Applying PVC {out_blob_name} to AKS...")

    os.remove("pvc_input.yaml")
    os.remove("pvc_output.yaml")

    print("PVC YAML files removed.")

    print("Updating group info...")
    items = [in_blob_name, out_blob_name]

    paiurl = f"https://{cluster_name}.openpai.org/rest-server/api/v2/group/"

    for group in groupname:
        url = f"{paiurl}{group}"
        data = get_group_info(url, bearer_token)

        if data:
            if 'storageConfigs' not in data['extension']['acls']:
                data['extension']['acls']['storageConfigs'] = []
            for item in items:
                if item not in data['extension']['acls']['storageConfigs']:
                    data['extension']['acls']['storageConfigs'].append(item)
        else:
            print(f"Failed to get group info for {group}.")
            continue

        newdata = data

        updated_data = update_group_info(paiurl, bearer_token, newdata)
        if updated_data:
            print(f"Group {group} info updated successfully.")
        else:
            print(f"Failed to update group info for {group}.")

    
    url = f"https://{cluster_name}.openpai.org/rest-server/api/v2/storages/refresh"
    response = refresh_group_info(url, bearer_token)

    print(response)
    print("Storage list refreshed.")
    print("Setup completed successfully.")