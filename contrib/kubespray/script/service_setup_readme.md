## 0. Before you begin

You need to create all required resources in your cloud provider.  

0. Prepare a resource group. If there is no, create a resource group in your cloud provider. 
    * For example, in Azure, you can create a resource group by:
    ```bash
    az group create --name <rg_name> --location <location>
    ```
    1. You may need to provide a ssh key in this resource group. You can create one in portal or  {#ssh_key}
    ```bash
    ssh-keygen -t rsa -b 4096 -C "<your_email>" -f ~/.ssh/id_rsa
    az sshkey create --location <location> --resource-group <rg_name> --name <ssh_key_name> --public-key @~/.ssh/id_rsa.pub
    ```
    or Create a new SSH public key resource with auto-generated value.
    ```bash
    az sshkey create --location <location> --resource-group <rg_name> --name <ssh_key_name>  
    ```

    

1. Configure required parameters in `contrib/aks/aks.bicepparam` file, and deploy an aks cluster and related resources by using `contrib/aks/aks.bicep`. 

    ```bash
    az deployment group create --resource-group <rg_name> --template-file contrib/aks/aks.bicep --parameters @contrib/aks/aks.bicepparam
    ```

    * To avoid SFI items, you may need to set a NSG to the storage account. You can do this manually in the portal.

2. Configure required parameters in `contrib/aks/vmss.bicepparam` file, and deploy a vmss and related resources by using `contrib/aks/vmss.bicep`.
    
    ```bash
    az deployment group create --resource-group <rg_name> --template-file contrib/aks/vmss.bicep --parameters @contrib/aks/vmss.bicepparam
    ```

    * This step assumes there is a ssh key in your provided resource group. If you don't have a ssh key, you need to [create one](#ssh_key) in the resource group.
    * If the value of `vmssSku` in `vmss.bicepparam` does not exist in `contrib/aks/provisionscript.bicep`, you need to add it in `contrib/aks/provisionscript.bicep` file.

    * If you already have a vmss created in other way, you need to update it by deploying `contrib/aks/vmss-upgrade.bicep` file.  

    * Even the `System assigned identity` be claimed as `enable`, it might be not enabled in this vmss. You can enable it manually in the portal. 

3. Ensure your account are the "Azure Kubernetes Service RBAC Cluster Admin" of the `aks-openpai` AKS cluster. This role can be added during step 1. 

4. Ensure your account has the owner role of the `luciaopenai` acr which hosts the docker images of pai services. 


## 1. Setup the aks cluster

1. Setup a dev box and login by:
    ```bash
    az login --use-device-code
    az account set --subscription <your-subscription-id>
    az aks get-credentials --resource-group <rg_name> --name aks-openpai --overwrite-existing # --context <your_context_name> # set a context name if you have multiple aks clusters
    kubelogin convert-kubeconfig -l azurecli
    # kubectl config get-contexts # show all contexts
    # kubectl config use-context <your_context_name> # switch context 

    ```
2. Attach the `luciaopenai` acr to the `aks-openpai` cluster by:
    ```bash
    az aks update --name aks-openpai --resource-group <rg_name> --attach-acr  /subscriptions/c8d60900-6fe3-4e3c-a626-63616f03478f/resourceGroups/openpai/providers/Microsoft.ContainerRegistry/registries/luciaopenai
    ```

3. Configure a `contrib/kubespray/aks-pv.yaml` by referencing the `contrib/kubespray/aks-pv.yaml.example` file. These values should be aligned with the values in `contrib/aks/aks.bicepparam` 

4. Run :
    ```bash
    bash contrib/kubespray/script/setup_k8s.sh
    ```

5. Configure three yaml files in <your_config_folder>:
    * config.yaml
    * layout.yaml
    * services-configuration.yaml
    
    These files are used to configure the services in the cluster. You can get them from existing openpai cluster by:
    ```bash
    ./paictl.py config pull -o <config_folder>
    ```
    And then modify them according to your needs.

6. Run the following command to deploy the services:
    ```bash
    bash contrib/kubespray/script/start-service-in-dev-box.all.sh -c <your_config_folder> -n <your_cluster_name>
    ```

7. Setup the a domain name for the aks cluster. 
    7.1 Get the public ip of pylon service by:
    ```bash
    kubectl get svc 
    ```
    7.2 Create a domain name and point it to the public ip of pylon service.
    7.3 Add the new domain name into `openpai-cluster` Application Registration in Azure AD.
        * Make sure you are the owner of the `openpai-cluster` Application Registration.
        * Go to Azure portal -> Microsoft Entra iD -> App registrations -> openpai-cluster -> Authentication -> Add a platform -> Web -> Redirect URIs
