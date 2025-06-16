import os
from dataclasses import dataclass
import time

from ltp_kusto_sdk.utils.kusto_client import KustoManageClient
from ltp_kusto_sdk.utils.time_util import convert_timestamp


@dataclass
class VMInfo:
    VMSS: str
    Hostname: str
    RoleInstanceName: str
    InstanceId: str
    VMId: str
    SubscriptionId: str
    ResourceGroupName: str
    VMSize: str

    @classmethod
    def from_record(cls, record: dict) -> "VMInfo":
        return cls(VMSS=record.get("VMSS", ""),
                   Hostname=record.get("Hostname", ""),
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

    def query_vm_info_of_hostname_in_kusto(self):
        hostname = self.hostname
        if isinstance(hostname, list):
            hostnames = ', '.join([f"'{h}'" for h in hostname])
            query = f"""
                VMInstances | where Hostname in~ ({hostnames})
                """
            response = self.kusto_client.execute_command(query)
            if len(response) != len(hostname):
                print(f"ERROR: Not all VM info found for hostnames {hostname}")
                return ''
            else:
                return [VMInfo.from_record(record) for record in response]
        elif isinstance(hostname, str):
            query = f"""
            VMInstances | where Hostname == '{hostname}'
            """
            response = self.kusto_client.execute_command(query)
            if len(response) == 0:
                print(f"ERROR: No VM info found for hostname {hostname}")
                return ''
            else:
                return VMInfo.from_record(response[0])

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
            # print(f"INFO: Found nodeId {response[0]['nodeId']} for hostname {hostname} on time {end_time} with offset {time_offset}")
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
                # get the vm_id from the hostname
                vm_info = self.query_vm_info_of_hostname_in_kusto()
                if vm_info is None or vm_info == '':
                    print(f"ERROR: Failed to get VM info for hostname {self.hostname}")
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