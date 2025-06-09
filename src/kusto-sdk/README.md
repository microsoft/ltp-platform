# LTP Kusto SDK

## Overview

Python SDK for Kusto DB interaction.

## Features

- **Node Status**: Manage status records, get/update status, validate transitions.
- **Node Actions**: Record node actions, validate, retrieve history.
- **Kusto Integration**: Uses Azure Kusto SDKs.
- **Configuration**: Via environment variables.

## Prerequisites

- Python 3.8+
- Access to Kusto cluster/database
- Kusto client credentials configured

## Installation

From source (in `src/kusto-sdk`):
```bash
pip install .
```


**Dependencies**: `azure-kusto-data`, `azure-kusto-ingest`, `pandas`, `requests`, `python-dateutil`, `joblib`. Installed automatically via pip.

## Configuration (Environment Variables)

- `LTP_KUSTO_CLUSTER_URI`: Kusto cluster URI.
- `LTP_KUSTO_DATABASE_NAME`: Kusto database name.
- `CLUSTER_ID`: Current cluster/endpoint identifier.
- `KUSTO_NODE_STATUS_TABLE_NAME`: (Optional) Node status table (default: `NodeStatusRecord`).
- `KUSTO_NODE_STATUS_ATTRIBUTE_TABLE_NAME`: (Optional) Status attributes table (default: `NodeStatusAttributes`).
- `KUSTO_NODE_ACTION_TABLE_NAME`: (Optional) Node action table (default: `NodeActionRecord`).
- `KUSTO_NODE_ACTION_ATTRIBUTE_TABLE_NAME`: (Optional) Action attributes table (default: `NodeActionAttributes`).
- `ENVIRONMENT=dev/prod`: (Optional) For integration tests.
- `KUSTO_USER_ASSIGNED_CLIENT_ID`: User assigned management identity client id to access kusto clusters.

## Usage Examples

Ensure environment variables are set.

### 1. Initialization & Table Creation

```python
from ltp_kusto_sdk import NodeStatusClient, NodeActionClient
from ltp_kusto_sdk.features.node_status.models import NodeStatus # For status enums
from datetime import datetime, timedelta

status_client = NodeStatusClient()
action_client = NodeActionClient()

try:
    status_client.create_table()
    status_client.create_attribute_table()
    action_client.create_table()
    action_client.create_attribute_table()
except RuntimeError as e:
    print(f"Error initializing tables: {e}")
```

### 2. Using `NodeStatusClient`

```python
hostname = "my-node-01"
current_timestamp = int(datetime.utcnow().timestamp())

try:
    # Get latest status
    node_record = status_client.get_node_status(hostname, current_timestamp)
    print(f"Node {node_record.HostName} status: {node_record.Status} at {node_record.Timestamp}")

    node_record = status_client.get_node_status(hostname)
    print(f"Node {node_record.HostName} status: {node_record.Status} at {node_record.Timestamp}")

    # Update status
    updated_status = status_client.update_node_status(hostname, NodeStatus.CORDONED.value, current_timestamp)
    print(f"Updated status for {hostname} to {updated_status}")

    # Get Action name
    action = status_client.get_transition_action(NodeStatus.AVAILABLE.value, NodeStatus.CORDONED.value)

    # Get status group
    status_group = status_client.get_status_group(NodeStatus.AVAILABLE.value)
    print(f"Group for AVAILABLE: {status_group}")

    # Get all nodes that are currently cordoned
    cordoned_nodes = client.get_nodes_by_status('cordoned')
    print(f"Found {len(cordoned_nodes)} nodes currently cordoned")

    # Get nodes that were available at a specific time
    reference_time = datetime(2024, 1, 1, 12, 0, 0)
    available_nodes = client.get_nodes_by_status('available', as_of_time=reference_time)

    # Each node record contains:
    # - Timestamp: When the status was set
    # - HostName: Name of the node
    # - Status: Current status
    # - NodeId: Unique identifier
    # - Endpoint: Associated endpoint

    # Example: Print all cordoned nodes
    for node in cordoned_nodes:
        print(f"Node {node['HostName']} was cordoned at {node['Timestamp']}")

except (ValueError, RuntimeError) as e:
    print(f"NodeStatusClient Error: {e}")
```

### 3. Using `NodeActionClient`

```python
node_hostname = "my-node-02"
action_ts_str = int(datetime.utcnow().timestamp())
# Check is_valid_action in SDK for format.
action_name = "available-cordoned" # Ensure this action is valid
reason = "Health check failed"
detail = "Ping test unresponsive"
category = "AutomatedAction"

try:
    # Record action (ensure 'action_name' is valid per SDK logic)
    action_client.update_node_action(node_hostname, action_name, action_ts_str, reason, detail, category)
    print(f"Action '{action_name}' recorded for {node_hostname}.")

    # Get latest action
    latest = action_client.get_latest_node_action(node_hostname)
    if latest: print(f"Latest action for {node_hostname}: {latest.Action}")

    # Get action history
    start_time = (datetime.utcnow() - timedelta(days=1)).isoformat()
    end_time = datetime.utcnow().isoformat()
    history = action_client.get_node_actions(node_hostname, start_time, end_time)
    print(f"Found {len(history)} actions for {node_hostname} recently.")

except (ValueError, RuntimeError) as e:
    print(f"NodeActionClient Error: {e}")
# except Exception as e: print(f"Unexpected error: {e}") # For broader catching during debug
```
**Note on `update_node_action`**: The `action` parameter requires specific formatting (e.g., "from_status-to_status") for validation. Refer to `is_valid_action` method in the SDK.

## Running Tests

1.  `cd src/kusto-sdk`
2.  Set Kusto environment variables (see Configuration). Set `ENVIRONMENT=dev` if needed.
3.  Run:
    ```bash
    python -m pytest tests/test_node_status_client.py 
    python -m pytest tests/test_node_status_models.py 
    python -m pytest tests/test_node_action_client.py
    python -m pytest tests/test_node_action_models.py 
    ```

