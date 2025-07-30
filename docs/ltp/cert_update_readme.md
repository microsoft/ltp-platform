# Certification Update Readme

There are two kinds of certificate used in the LTP project:

1. **Certification for the OIDC**: This certificate is used to verify the identity of the Azure OIDC provider. This certificate is required by `rest-server` service to ensure that the users accessing the LTP services are authenticated through Azure Active Directory (AAD) using OpenID Connect (OIDC) protocol. 

2. **Certification for the HTTPS**: This certificate is used to secure the web communication between the LTP services and the clients. It ensures that the data transmitted over the network is encrypted and secure. This certificate is required by the `pylon` service.


## How to set up the certificate

**OIDC Certification**: 


1. Update the OIDC certificate in Azure.

    You can create a new version of this certificate in the Azure KeyVault.

    1. Go to the Azure KeyVault.
    2. Click on the `Certificates` tab.
    3. Click on the `openpai-aad` certificate.
    4. Click on the `New Version` button to create a new version of the certificate.

2. Obtain the OIDC certificate from the Azure.

    * Our OIDC certificate is in a the [Azure KeyVault](https://ms.portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/c8d60900-6fe3-4e3c-a626-63616f03478f/resourceGroups/openpai/providers/Microsoft.KeyVault/vaults/openpai/overview). You can access it by

    
    2.1 Obtain by azure CLI:

    * To download the OIDC certificate, you can use the Azure CLI command:
      ```bash
        az keyvault secret download --subscription c8d60900-6fe3-4e3c-a626-63616f03478f --vault-name openpai --name openpai-aad --encoding base64 --file ltp-oidc-cert.pfx
      ```
    
    * To get the thumbprint of the OIDC certificate, you can use the Azure CLI command:
      ```bash
        az keyvault certificate show --vault-name openpai --name openpai-aad --query "x509ThumbprintHex" -o tsv
      ```
    2.2 Obtain by Azure portal:

    * You can also use the Azure portal to download the OIDC certificate and get the thumbprint. 
      1. Go to the Azure KeyVault.
      2. Click on the `Certificates` tab.
      3. Click on the `openpai-aad` certificate.
      4. Click on the `Download` button to download the certificate in `.pfx` formats.
      5. The thumbprint is displayed in the certificate details.

3.  Convert the `.pfx` file to `.crt` and `pem` format using the following command:
    ```bash
      openssl pkcs12 -in ltp-oidc-cert.pfx -clcerts -nokeys -out ltp-oidc.crt 
      openssl pkcs12 -in ltp-oidc-cert.pfx -nocerts -nodes -out ltp-oidc.pem
    ```
    Press `Enter` when prompted for the password, as the OIDC certificate does not have a password.


4. Set the OIDC certificate by configuring the `services-configuration.yaml` file:

    ```yaml
    authentication:
      OIDC: true
      OIDC-type: AAD
      AAD:
        ......
        certificate:
          thumbprint: <thumbprint>
          keyPath: <Local path to the .pem file>
          certPath: <Local path to the .crt file>
    ```

5. Restart the `rest-server` service to apply the changes. And you should also to restart the alertmanager service to mount the new OIDC certificate for monitoring.

**HTTPS Certification**:

The HTTPS certificate should be renewed for every 3 months.

### Pre-requisites
To set up the HTTPS certificate, you need to have the following:

1. Install certbot https://certbot.eff.org/ on Ubuntu
2. Have a domain name (e.g., `openpai.org`) that you own and can manage DNS records for.

The current domain name used in the LTP project is `openpai.org`. It is registered with GoDaddy, and the DNS records are managed there. To log in to the GoDaddy account, you can find the username and password in the `Secrets` of this [Azure KeyVault](https://ms.portal.azure.com/?feature.msaljs=true#@microsoft.onmicrosoft.com/resource/subscriptions/f27cdf3b-ad0f-4d36-9b19-f4957575966c/resourceGroups/sigma/providers/Microsoft.KeyVault/vaults/ltp-secrets/secrets)

### Steps to renew the HTTPS certificate

1. Run command: 

    ```bash
    sudo certbot certonly -d "*.openpai.org" -a manual --preferred-challenges dns 
    ```

2. Go to https://dcc.godaddy.com/manage/openpai.org/dns, add corresponding TXT record for dns challenge. 
   Go to https://developers.google.com/speed/public-dns/cache and flush corresponding TXT record.

3. Wait for 2 minutes and continue the command in step 2.

4. Get fullchain.pem and privkey.pem from /etc/letsencrypt/live/openpai.org/.

5. Run command:
    ```bash
    sudo openssl pkcs12 -export -out cert.pfx -inkey privkey.pem -in fullchain.pem 
    ```

    to get a cert in pfx format, set password to "core666" when exporting pfx cert. 

6. Remove dns challenge TXT record from https://dcc.godaddy.com/manage/openpai.org/dns. 

7. Set the HTTPS certificate to by configuring `pylon` in the `services-configuration.yaml` file:

    ```yaml
    pylon:
      # Other configurations...
      ssl:
        crt_name: <Name of the .fullchain.pem file>
        crt_path: <Local path to the .fullchain.pem file>
        key_name: <Name of the .privkey.pem file>
        key_path: <Local path to the .privkey.pem file>
    ```

8. Restart the `pylon` service to apply the changes.