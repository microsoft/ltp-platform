# How to Manage Data and Code

## Use Code

To access user code, first upload the code to a private Git repository, then use the Git token to clone the repository. The token can be defined in the `secret` section in [How to Use Advanced Job Settings](./job-config.md).

## Use Self-Manage Data

### Data from Public Website

To download data from public websites, use the `wget` command within your job configuration.

### Data from Azure Blob Storage

To access data from Azure Blob Storage, you can either:

- Install `blobfuse` to mount the storage.
- Use `azcopy` to copy the data onto the job storage, with the SAS token, which can be defined in the `secret` section in [How to Use Advanced Job Settings](./job-config.md#parameters-and-secrets).

## Platform-Assisted Data Management

### Onboard Private Azure Blob Storage

To onboard your private storage, follow these steps:

- Assign the Storage Blob Data Contributor role to the platform's managed identities in your storage account. Refer to the detailed instructions in [Grant access to the storage account](https://learn.microsoft.com/en-us/entra/identity-platform/multi-service-web-app-access-storage?tabs=azure-portal%2Cprogramming-language-csharp#grant-access-to-the-storage-account). Make sure you assign the proper role to all below listed platform's managed identities:
  - principal ID: `<ph:principal_id_store_0>`
  - principal ID: `<ph:principal_id_store_1>`
  - principal ID: `<ph:principal_id_store_2>`
- Request your UserGroup Admin to contact the Lucia Training Platform Admin to integrate your storage into your UserGroup. 
  - Please use the [Request for Integrating Private Azure Storage Blob](email-templates/email-templates-user.md#request-for-integrating-private-azure-storage-blob) email template. 
  - Please include both contacts in the "To" field: 
    - Lucia Training Platform Admin Group ([<ph:email_addr_alert>](mailto:<ph:email_addr_alert>))
    - Lucia Training Platform Admin ([<ph:email_addr_main>](mailto:<ph:email_addr_main>))

**Note: Private data storage is accessible to all users within the same UserGroup. Other UserGroups will not have access.**

### Use Private Storage in Job

To use private storage in your jobs, specify the storage names in the `storageConfigNames` section of the `extras` part in your job configuration file:

```yaml
extras:
  storageConfigNames:
    - blob-<account-name>-<blobname>
```

The corresponding storage will be automatically mounted to the `/mnt/blob-<account-name>-<blobname>` folder after the job is launched.
