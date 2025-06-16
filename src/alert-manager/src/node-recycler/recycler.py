# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import json
import time
import random
import string
from datetime import datetime

import icm
import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient

from ltp_kusto_sdk import NodeStatusClient, NodeActionClient
from ltp_kusto_sdk.features.node_status.models import NodeStatus


class NodeRecycler:
    _icm_host = os.getenv("ICM_HOST", "prod.microsofticm.com")
    _icm_cert_path = os.getenv("ICM_CERT_PATH", "cert.pem")
    _icm_key_path = os.getenv("ICM_KEY_PATH", "key.pem")
    _icm_connector_id = os.getenv("ICM_CONNECTOR_ID", "85faeeb7-757f-473e-8948-9c39e519bfaf")
    _icm_routing_id = os.getenv("ICM_ROUTING_ID", "hpclucia://AzureHPC/Lucia/TrainingPlatform")
    _icm_created_by = "ltp-admin-alert@microsoft.com"
    _icm_uri_format = "https://portal.microsofticm.com/imp/v5/incidents/details/{}/summary"

    _azure_client_id = os.getenv("AZURE_CLIENT_ID")
    _ltp_rest_server_uri = os.getenv("REST_SERVER_URI")
    _ltp_rest_server_token = os.getenv("REST_SERVER_TOKEN")
    _ltp_validation_image = os.getenv("LTP_VALIDATION_IMAGE")
    _ltp_vmss_ids = os.getenv("LTP_VMSS_IDS", "")

    @classmethod
    def ofr(cls, node_faults=None, status_client=None, action_client=None):
        """Create IcM tickets for AutoOFR for given nodes and faults via configured routing id.

        Args:
            node_faults (List[Tuple[str, str, str]]):
                List of (hostname, node_id, fault_reason) pairs to send to OFR.
                If None and status_client abd action_client is provided,
                defaults to all nodes in the triaged UA state.
            status_client (NodeStatusClient): Node status client in SDK.
            action_client (NodeActionClient): Node action client in SDK.

        Returns:
            List[int]: A list of hostnames of the succeeded OFR nodes.
        """
        from_state, to_state = NodeStatus.TRIAGED_HARDWARE.value, NodeStatus.UA.value

        created = []
        if not node_faults and status_client and action_client:
            query = """
            {table_name}
            | where Action endswith {state}
            | where HostName == '{hostname}' and NodeId == '{node_id}'
            | top 1 by Timestamp desc
            """
            node_faults = []
            for node in status_client.get_nodes_by_status(from_state):
                hostname, node_id = node["HostName"], node["NodeId"]
                result = action_client.execute_query(query.format(
                    table_name=action_client.table_name,
                    hostname=hostname,
                    node_id=node_id,
                ))
                if result and "Action" in result[0] and "Detail" in result[0]:
                    action, detail = result[0]["Action"], result[0]["Detail"]
                    if action.endswith(from_state):
                        try:
                            detail_json = json.loads(detail)
                            detail_node_id = detail_json.get("NodeId")
                            defail_fault_reason = detail_json.get("FaultCode")
                            if not detail_node_id or not defail_fault_reason:
                                raise ValueError("NodeId or FaultCode is empty in Detail field")
                            node_faults.append((hostname, detail_node_id, defail_fault_reason))
                        except Exception as e:
                            print(f"Failed to parse action detail {detail} due to: {e}")
                            continue
                    if action.startwith(from_state) and action.endswith(to_state):
                        created.append({"hostname": hostname, "node_id": node_id, "ticket_id": detail})
                else:
                    print(f"WARNING: Cannot find action record for node {hostname} with node id {node_id}")
        if not node_faults and not created:
            return
        print(f"Found {len(created)} existing IcM OFR tickets")

        icm_api = icm.ICMApi(
            icm_host=cls._icm_host,
            cert=cls._icm_cert_path,
            key=cls._icm_key_path,
            connector_id=cls._icm_connector_id,
        )

        for hostname, node_id, fault_reason in node_faults:
            ofr_str = f"LiveSite-AutoOFR: NodeId:{node_id}, Fault:{fault_reason}, GPU serial:Unknown"

            incident = icm_api.new_incident()
            for k, v in [
                ("Title", ofr_str),
                ("Summary", ofr_str),
                ("Severity", 4),
                ("CustomerName", "LTP"),
                ("CorrelationId", None),
                ("MonitorId", None),
                ("RoutingId", cls._icm_routing_id),
            ]:
                incident[k] = v
            incident["Source"]["Origin"] = "Other"
            incident["Source"]["CreatedBy"] = cls._icm_created_by
            incident["DescriptionEntries"][0]["DescriptionEntry"]["Text"] = "Incident Created by LTP Automation."

            try:
                result = icm_api.create_incident(incident=incident, connector_id=cls._icm_connector_id)
                ticket_id = result[0]
                print(f"Created IcM ticket {cls._icm_uri_format.format(ticket_id)} with id {ticket_id} for node {node_id} ({hostname})")
                created.append({
                    "hostname": hostname,
                    "node_id": node_id,
                    "ticket_id": ticket_id,
                })
                if action_client:
                    action_client.update_node_action(
                        hostname, f"{from_state}-{to_state}",
                        time.time(), ofr_str, ticket_id, "",
                    )
            except Exception as e:
                print(f"Error occured when creating OFR ticket for node {node_id} ({hostname}): {e}")
        print(f"Found/Created {len(created)} IcM OFR tickets, checking OFR results ...")

        def is_ticket_resolved(tid):
            try:
                incident = icm_api.get_incident(incident_id=tid)
                return incident["Status"] == "Resolved"
            except Exception:
                return False

        completed = []
        curr_delay, max_delay = 60, 180
        while created and curr_delay <= max_delay:
            time.sleep(curr_delay)
            for each in created[:]:
                name, tid = each["hostname"], each["ticket_id"]
                if not is_ticket_resolved(tid):
                    continue
                created.remove(each)
                completed.append(name)
                if status_client:
                    status_client.update_node_status(name, to_state, time.time())
            curr_delay += 60
        print(f"AutoOFRed {len(completed)} nodes successfully")

        return completed

    @classmethod
    def is_ofr_active(cls, node_id):
        """Check whether there are active IcM tickets to AutoOFR the given node.

        Args:
            node_id (str): Node id.

        Returns:
            boolean: True if at least one active ticket exists, otherwise False.
        """
        icm_api = icm.ICMApi(
            icm_host=cls._icm_host,
            cert=cls._icm_cert_path,
            key=cls._icm_key_path,
            connector_id=cls._icm_connector_id,
        )
        ofr_prefix = f"LiveSite-AutoOFR: NodeId:{node_id}"
        query = f"$select=Id,Status,Title&$filter=RoutingId eq '{cls._icm_routing_id}' and Status eq 'Active'"

        for each in icm_api.get_incidents(query=query):
            if each["Title"].startswith(ofr_prefix):
                print(f"Found active IcM ticket for node {node_id}: {each}")
                return True
        return False

    @classmethod
    def operate(cls, vmss_id, operation="start", hostnames=None, status_client=None, action_client=None):
        """Start or deallocate given VMs in VMSS and update Kusto accordingly.

        Args:
            vmss_id (str): 
                /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/
                virtualMachineScaleSets/{vmss}
            operation (str): "start" or "deallocate"
            hostnames (List[str]):
                List of hostnames to act on. If None and status_client is provided,
                defaults to all nodes queried in the desired state.
            status_client (NodeStatusClient): Node status client in SDK.
            action_client (NodeActionClient): Node action client in SDK.

        Returns:
            List[dict]: A list of VMs successfully transitioned.
        """
        op = operation.lower()
        if op == "start":
            from_state, to_state = NodeStatus.DEALLOCATED_UA.value, NodeStatus.ALLOCATED_UA.value
        elif op == "deallocate":
            from_state, to_state = NodeStatus.UA.value, NodeStatus.DEALLOCATED_UA.value
        else:
            raise ValueError(f"Unsupported operation: {operation}")

        if not hostnames and status_client:
            hostnames = [n["HostName"] for n in status_client.get_nodes_by_status(from_state)]
        if not hostnames:
            return []

        parts = vmss_id.strip().split("/")
        try:
            sub_id = parts[parts.index("subscriptions") + 1]
            rg_name = parts[parts.index("resourceGroups") + 1]
            vmss_name = parts[parts.index("virtualMachineScaleSets") + 1]
        except (ValueError, IndexError):
            print(f"Invalid VMSS resource id: {vmss_id}")
            return []

        def is_vm_succeed_in_target(vm):
            statuses = vm.instance_view.statuses or []
            states = {"ProvisioningState": None, "PowerState": None}
            for k in states.keys():
                codes = [s.code for s in statuses if s.code.startswith(f"{k}/")]
                states[k] = codes[0].split("/", 1)[1].lower() if codes else "unknown"
            if op == "start":
                return states["ProvisioningState"] == "succeeded" and states["PowerState"] == "running"
            else:
                return states["ProvisioningState"] == "succeeded" and states["PowerState"] in ("deallocated", "stopped")

        credential = DefaultAzureCredential(managed_identity_client_id=cls._azure_client_id)
        vmss_client = ComputeManagementClient(credential, sub_id).virtual_machine_scale_set_vms

        # Attempt to start given hostnames
        pollers, completed = [], []
        try:
            for vm in vmss_client.list(rg_name, vmss_name, expand="instanceView"):
                name = vm.os_profile.computer_name
                if name not in hostnames:
                    continue
                if op == "start" and is_vm_succeed_in_target(vm):
                    print(f"WARNING: {name} is running but still in {from_state} state")
                    completed.append({"instance_id": vm.instance_id, "computer_name": name})
                    if status_client:
                        status_client.update_node_status(name, to_state, time.time())
                    continue
                poller = getattr(vmss_client, f"begin_{op}")(rg_name, vmss_name, vm.instance_id)
                pollers.append({
                    "instance_id": vm.instance_id,
                    "computer_name": name,
                    "poller": poller,
                })
                if action_client:
                    action_client.update_node_action(
                        name, f"{from_state}-{to_state}",
                        time.time(), f"{op.title()}ing VM", "", "",
                    )
        except Exception as e:
            print(f"List instances in VMSS failed due to: {e}")
        finally:
            if op == "start":
                print(f"Found {len(completed)} {to_state} instances to skip {op} in VMSS {vmss_name}")
            print(f"Found {len(pollers)} {from_state} instances to {op} in VMSS {vmss_name}, {op}ing ...")

        # Wait to finish start and check final state
        for each in pollers:
            inst, name = each["instance_id"], each["computer_name"]
            try:
                # Block until the operation completes or raises
                each["poller"].result()

                # Re-fetch the instance to check its power state
                vm_refreshed = vmss_client.get(rg_name, vmss_name, inst, expand="instanceView")
                if is_vm_succeed_in_target(vm_refreshed):
                    completed.append({"instance_id": inst, "computer_name": name})
                    if status_client:
                        status_client.update_node_status(name, to_state, time.time())
                else:
                    print(f"Instance {inst} ({name}) failed to {op}")
            except Exception as e:
                print(f"Instance {inst} ({name}) failed during {op} due to: {e}")
        print(f"{op.title()}ed {len(completed)} instances in VMSS {vmss_name}")

        return completed

    @classmethod
    def validate(cls, hostnames=None, filter_state='', status_client=None, action_client=None):
        """Submit validation job for the given nodes and update Kusto accordingly.

        Args:
            hostnames (List): List of hostnames to validate.
            filter_state (str): State to filter for validation.
            status_client (NodeStatusClient): Node status client in SDK.
            action_client (NodeActionClient): Node action client in SDK.
        """
        if not filter_state:
            filter_state = NodeStatus.ALLOCATED_UA.value
        if not hostnames and status_client:
            hostnames = [n["HostName"] for n in status_client.get_nodes_by_status(filter_state)]
        if not hostnames:
            return

        with open("validation.yaml", "r") as f:
            template = f.read()
        config = template.format(
            uid="".join(random.choices(string.ascii_letters + string.digits, k=8)),
            image=cls._ltp_validation_image,
            instances=len(hostnames),
            hostnames=",".join(hostnames).lower(),
        )

        res = requests.post(
            f"{cls._ltp_rest_server_uri}/api/v2/jobs",
            data=config,
            headers={
                "Content-Type": "text/yaml",
                "Authorization": f"Bearer {cls._ltp_rest_server_token}"
            },
        )
        if action_client:
            for hostname in hostnames:
                action_client.update_node_action(
                    hostname,
                    f"{filter_state}-{NodeStatus.VALIDATING.value}",
                    time.time(), "Submitting validation job for VM", "", "",
                )
        try:
            res.raise_for_status()
            print(f"Submitted validation job with response: {res.json()}")
            if status_client:
                for hostname in hostnames:
                    status_client.update_node_status(
                        hostname,
                        NodeStatus.VALIDATING.value,
                        time.time(),
                    )
        except Exception as e:
            print(f"Failed to submit validation job due to:\n{e}")
            print(f"Raw response: {res.text}")

    @classmethod
    def ua_and_deallocate_pipeline(cls, status_client, action_client):
        """Pipeline to OFR cordoned nodes and deallocate VMs.
        Update Kusto status and action tables accordingly.

        Args:
            status_client (NodeStatusClient): Node status client in SDK.
            action_client (NodeActionClient): Node action client in SDK.
        """
        print("Starting to UA Cordoned Nodes")
        ualist = cls.ofr(
            status_client=status_client,
            action_client=action_client,
        )
        for vmss_id in cls._ltp_vmss_ids.split(","):
            print(f"Starting to Deallocate Nodes in {vmss_id}")
            cls.operate(
                vmss_id,
                operation="deallocate",
                hostnames=ualist,
                status_client=status_client,
                action_client=action_client,
            )

    @classmethod
    def start_and_validate_pipeline(cls, status_client, action_client):
        """Pipeline to start deallocated VMs in UA and validate started VMs.
        Update Kusto status and action tables accordingly.

        Args:
            status_client (NodeStatusClient): Node status client in SDK.
            action_client (NodeActionClient): Node action client in SDK.
        """
        for vmss_id in cls._ltp_vmss_ids.split(","):
            print(f"Starting to Start Nodes in {vmss_id}")
            started_vms = cls.operate(
                vmss_id,
                operation="start",
                status_client=status_client,
                action_client=action_client,
            )
            if len(started_vms) > 0:
                # TODO: check node status in k8s
                time.sleep(300)
                print(f"Starting to Validate Nodes in {vmss_id}")
                cls.validate(
                    hostnames=[vm["computer_name"] for vm in started_vms],
                    status_client=status_client,
                    action_client=action_client,
                )
        # validate previous failed nodes as well
        time.sleep(30)
        print("Starting to Validate Allocated Nodes")
        cls.validate(status_client=status_client, action_client=action_client)

    @classmethod
    def node_recycle_pipeline_loop(cls, interval=1800):
        """Pipeline loop to recycle nodes with hardware failures.
        Update Kusto status and action tables accordingly.

        Args:
            interval (int): Time interval to repeat the pipeline in the loop.
        """
        status_client, action_client = NodeStatusClient(), NodeActionClient()
        print("Created Kusto clients for node status and action tables")
        while True:
            print(f"{datetime.now()} Starting to UA and Deallocate Nodes")
            cls.ua_and_deallocate_pipeline(status_client, action_client)
            print(f"{datetime.now()} Starting to Start and Validate Nodes")
            cls.start_and_validate_pipeline(status_client, action_client)
            time.sleep(interval)


if __name__ == "__main__":
    NodeRecycler.node_recycle_pipeline_loop()
