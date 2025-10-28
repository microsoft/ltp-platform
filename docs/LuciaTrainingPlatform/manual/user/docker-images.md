# How to Use Docker Images

## Access to Docker Images

### Public Docker Images

Public images on Docker Hub can be pulled directly after the job is submitted.

**Note:** The Docker Hub registry has rate limitations and may cause compliance issues. We highly recommend pulling images from the Azure Container Registry (ACR). In the future, we may disable pulling images directly from Docker Hub.

### Private Docker Images

To use private Docker images, you need to assign the `acrPull` permission to the platform's managed identities in your Azure Container Registry (ACR). Make sure you assign the proper role to all below listed platform's managed identities:
- principal ID: `b956019c-3be9-47e5-ae4d-18bc2c599a0b`
- principal ID: `0604b3f1-d040-4545-a9e0-2f4b4f8cabd3`
- principal ID: `3b8d9c3b-6820-45a5-a346-94d13210a9ba`

Refer to the detailed instructions in [Grant the identity permissions to access other Azure resources](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-tasks-authentication-managed-identity#3-grant-the-identity-permissions-to-access-other-azure-resources).

Once the permission is granted, the private image from your ACR can be pulled automatically after the job is submitted.

## Set Docker Image in Job Configuration

To use a Docker image in a job, first define the Docker image in the `prerequisites` section of the job configuration file:

```yaml
prerequisites:
  - type: dockerimage
    uri: 'nvcr.io/nvidia/pytorch:24.03-py3' # image URL
    name: docker_image0
```

Then set the `dockerImage` in the `taskRoles` section of the job configuration file:

```yaml
taskRoles:
  taskrole:
    dockerImage: docker_image0
```
