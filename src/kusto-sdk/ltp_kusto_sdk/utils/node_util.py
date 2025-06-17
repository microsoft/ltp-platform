import os
from dataclasses import dataclass
import time

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient

from ltp_kusto_sdk.utils.kusto_client import KustoManageClient, KustoIngestionClient
from ltp_kusto_sdk.utils.time_util import convert_timestamp
import pandas as pd


@dataclass
class VMInfo:
    VMSS: str
    HostName: str
    RoleInstanceName: str
    InstanceId: str
    VMId: str
    SubscriptionId: str
    ResourceGroupName: str
    VMSize: str

    @classmethod
    def from_record(cls, record: dict) -> "VMInfo":
        return cls(VMSS=record.get("VMSS", ""),
                   HostName=record.get("HostName", ""),
                   RoleInstanceName=record.get("RoleInstanceName", ""),
                   InstanceId=record.get("InstanceId", ""),
                   VMId=record.get("VMId", ""),
                   SubscriptionId=record.get("SubscriptionId", ""),
                   ResourceGroupName=record.get("ResourceGroupName", ""),
                   VMSize=record.get("VMSize", ""))


class Node:

    def __init__(self, hostname):
        self.hostname = hostname
        self.cluster = os.getenv(
            "LTP_KUSTO_CLUSTER_URI",
            "https://ltp-kusto.westus2.kusto.windows.net")
        self.database = os.getenv("LTP_KUSTO_DATABASE_NAME", "Test")
        self.kusto_client = KustoManageClient(self.cluster, self.database)
        self.retry_count = os.getenv("KUSTO_RETRY_COUNT", 3)
        self.retry_delay = os.getenv("KUSTO_RETRY_DELAY", 10)
        self.kusto_table = os.getenv("LTP_KUSTO_VM_INFO_TABLE_NAME", "VMInfo")

    def query_vm_info_of_hostname_in_kusto(self):
        try:
            hostname = self.hostname
            if isinstance(hostname, list):
                hostnames = ', '.join([f"'{h}'" for h in hostname])
                query = f"""
                    {self.kusto_table} | where HostName in~ ({hostnames})
                    """
                response = self.kusto_client.execute_command(query)
                if len(response) != len(hostname):
                    print(f"ERROR: Not all VM info found for HostNames {hostname}")
                    return ''
                else:
                    return [VMInfo.from_record(record) for record in response]
            elif isinstance(hostname, str):
                query = f"""
                {self.kusto_table} | where HostName == '{hostname}'
                """
                response = self.kusto_client.execute_command(query)
                if len(response) == 0:
                    print(f"ERROR: No VM info found for HostName {hostname}")
                    return ''
                else:
                    return VMInfo.from_record(response[0])
        except Exception as e:
            print(f"ERROR: Exception occurred while querying VM info for hostname {self.hostname}: {str(e)}")
            return None

    def get_node_id_by_vm_id(self, subscription_id, vm_id, end_time,
                             time_offset):
        nodeId = {}
        cluster = "https://azcore.centralus.kusto.windows.net"
        database = "AzureCP"
        # format the end_time into 2025-03-27T23:05:00Z
        end_time_dt = convert_timestamp(end_time, format="str")
        # get the nodeId record since end_time offset time_offset
        query = f"""
        MycroftContainerSnapshot 
        | where TIMESTAMP between(datetime({end_time_dt}) - {time_offset} .. datetime({end_time_dt}))
        | where SubscriptionId == "{subscription_id}"
        | where VirtualMachineUniqueId in~ ("{vm_id}")
        | summarize arg_max(TIMESTAMP, *) by NodeId
        | project TIMESTAMP, NodeId, VirtualMachineUniqueId, RoleInstanceName
        | sort by TIMESTAMP asc
        """
        kusto_client = KustoManageClient(cluster, database)
        response = kusto_client.execute_command(query)

        if len(response) == 0:
            print(
                f"ERROR: No nodeId found for vm_id {vm_id} on time {end_time} with offset {time_offset}"
            )
        elif len(response) == 1:
            nodeId[response[0]["NodeId"]] = response[0]["TIMESTAMP"]
        else:

            # Print all nodeIds
            for row in response:
                nodeId[row["NodeId"]] = row["TIMESTAMP"]
        return nodeId

    def get_vm_node_id_by_hostname(self,
                                    current_time_stamp,
                                    time_offset="24h"):
        """
        Get VM node ID by hostname with retry mechanism.
        
        Args:
            current_time_stamp: Current timestamp
            time_offset: Time offset for query (default: "24h")
            
        Returns:
            str: Node ID if found, empty string otherwise
        """
        retry_count = 0
        last_exception = None
        
        while retry_count < self.retry_count:
            try:
                # get the vm_id from the HostName
                vm_info = self.query_vm_info_of_hostname_in_kusto()
                if vm_info is None or vm_info == '':
                    ComputeClient().update_vm_info()
                    vm_info = self.query_vm_info_of_hostname_in_kusto()
                    if vm_info is None or vm_info == '':
                        print(f"ERROR: No VM info found for hostname {self.hostname} after updating VM info.")
                        return ''
                vm_id = vm_info.VMId
                # get the nodeId from the vm_id
                nodeId = self.get_node_id_by_vm_id(
                    subscription_id=vm_info.SubscriptionId,
                    vm_id=vm_id,
                    end_time=current_time_stamp,
                    time_offset=time_offset,
                )  
                # get the last nodeId
                nodeIds = sorted(nodeId.items(), key=lambda x: x[1], reverse=True)
                result = nodeIds[0][0] if len(nodeIds) > 0 else ''

                return result
                
            except Exception as e:
                last_exception = e
                retry_count += 1
                
                if retry_count < self.retry_count:
                    print(f"ERROR: Exception occurred while getting node ID for hostname {self.hostname}: {str(e)}")
                    print(f"Retrying {retry_count + 1}/{self.retry_count} in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"ERROR: Failed to get node ID for hostname {self.hostname} after {self.retry_count} retries. Last exception: {str(e)}")
                    raise last_exception
                
        return ''
    

class ComputeClient:
    def __init__(self):
        self.azure_client_id = os.getenv("AZURE_CLIENT_ID")
        self.ltp_vmss_ids = os.getenv("LTP_VMSS_IDS", None)
        self.kusto_cluster = os.getenv("LTP_KUSTO_CLUSTER_URI", "")
        self.kusto_database = os.getenv("LTP_KUSTO_DATABASE_NAME", "")
        self.kusto_table = os.getenv("LTP_KUSTO_VM_INFO_TABLE_NAME", "VMInfo")

    def initialize_compute_client(self, subscription_id):
        from azure.identity import DefaultAzureCredential
        credential = None
        if os.getenv("ENVIRONMENT", "prod") == "prod":
            credential = DefaultAzureCredential(managed_identity_client_id=self.azure_client_id)
        else:
            credential = DefaultAzureCredential()
        return ComputeManagementClient(credential, subscription_id)
    
    def parse_vmss_id(self, vmss_id):
        parts = vmss_id.strip().split("/")
        try:
            subscription_id = parts[parts.index("subscriptions") + 1]
            resource_group_name = parts[parts.index("resourceGroups") + 1]
            vmss_name = parts[parts.index("virtualMachineScaleSets") + 1]
        except (ValueError, IndexError):
            print(f"Invalid VMSS resource id: {vmss_id}")
            return None, None, None
        return subscription_id, resource_group_name, vmss_name
    
    def get_vm_info_of_vmss(self, vmss_id):
        """Get VM info of a VMSS"""
        subscription_id, resource_group_name, vmss_name = self.parse_vmss_id(vmss_id)
        if not subscription_id or not resource_group_name or not vmss_name:
            print(f"Invalid VMSS resource id: {vmss_id}")
            return []
        
        compute_client = self.initialize_compute_client(subscription_id)
        vm_list = []
        for vm in compute_client.virtual_machine_scale_set_vms.list(
            resource_group_name=resource_group_name,
            virtual_machine_scale_set_name=vmss_name,
            expand="instanceView",
        ):
            hostname = vm.os_profile.computer_name.lower()
            role_instance_name = vm.name 
            vm_id = vm.vm_id
            vm_size = vm.hardware_profile.vm_size    
            
            record = {
                'VMSS': vmss_name,
                'HostName': hostname,
                'RoleInstanceName': role_instance_name,
                'InstanceId': vm.instance_id,
                'VMId': vm_id,
                'SubscriptionId': subscription_id,
                'ResourceGroupName': resource_group_name,
                'VMSize': vm_size,
            }

            vm_list.append(record)
        return vm_list

    def update_vm_info(self) -> None:
        """Ingest VM info into Kusto table""" 
        kusto_client = KustoManageClient(self.kusto_cluster, self.kusto_database)
        ingestion_client = KustoIngestionClient(self.kusto_cluster, self.kusto_database)
        # Check if the table exists, if not create it
        if not kusto_client.table_exists(self.kusto_table):
            print(f"Creating table {self.kusto_table} in Kusto database {self.kusto_database}")
            kusto_client.create_table(self.kusto_table, VMInfo)      
        df = pd.DataFrame(columns=['VMSS', 'HostName', 'RoleInstanceName', 'VMId', 'SubscriptionId', 'ResourceGroupName', 'VMSize', 'InstanceId'])
        # Iterate through each VMSS ID and get VM info
        if not self.ltp_vmss_ids:
            print("No VMSS IDs provided in environment variable LTP_VMSS_IDS.")
            return
        for vmss_id in self.ltp_vmss_ids.split(','):
            vmss_id = vmss_id.strip()
            if not vmss_id:
                continue
            print(f"Processing VMSS: {vmss_id}")
            # Get VM info of the VMSS
            vm_list = self.get_vm_info_of_vmss(vmss_id)
            if not vm_list or len(vm_list) == 0:
                print(f"No VMs found in VMSS: {vmss_id}")
                continue
            df = pd.DataFrame(vm_list)
            subscription_id, resource_group_name, vmss_name = self.parse_vmss_id(vmss_id)
            query = f"{self.kusto_table} | where VMSS == '{vmss_name}' and SubscriptionId == '{subscription_id}'"
            data = kusto_client.execute_command(query)
            existing_df = pd.DataFrame(data)
            remaining_df = pd.DataFrame()
            if len(existing_df) == 0:
                print("No existing VMs found in Kusto.")
                remaining_df = df
            else:
                print("Existing VMs found in Kusto.")
                # Find the remaining VMs that are not in the existing DataFrame
                remaining_df = df[~df['VMId'].isin(existing_df['VMId'])]
            if remaining_df.empty:
                print("No new VMs to ingest in vmss_id: {vmss_id}")
                continue
            print(f"Remaining VMs to ingest in {vmss_id}: {remaining_df['HostName'].to_list()}")
            ingestion_client.ingest_to_kusto(self.kusto_table, remaining_df)
            print(f"Successfully ingested {len(remaining_df)} VMs from VMSS {vmss_name} into Kusto table {self.kusto_table}.")
        