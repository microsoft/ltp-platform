# PostgreSQL SDK Service

A dedicated service for managing PostgreSQL schema initialization, migrations, and health checks for the LTP platform. This service includes a Python SDK for PostgreSQL database operations.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Using the SDK](#using-the-sdk)
- [Schema Management](#schema-management)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## Overview

The PostgreSQL SDK Service provides:

1. **Schema Management**: Automated initialization and migration of database schemas
2. **Health Monitoring**: Periodic health checks of database schema and tables
3. **Python SDK**: Client library for interacting with PostgreSQL from other services
4. **Migration Support**: Version-controlled schema evolution using Alembic

### Key Features

- **Schema Isolation**: Uses dedicated `ltp_sdk` schema (separate from `database-controller`)
- **Self-Managing**: Service is responsible for its own schema and tables
- **Idempotent Operations**: Safe to run multiple times
- **Automatic Sync**: Intelligently initializes or upgrades schema as needed
- **Version Tracking**: All schema changes are tracked with Alembic migrations

---

## Architecture

```
postgresql-sdk/
├── sdk/                          # Python SDK (client library)
│   └── ltp_postgresql_sdk/
│       ├── __init__.py
│       ├── models.py             # SQLAlchemy models (tables)
│       ├── database.py           # Database connection management
│       ├── base.py               # Base client class
│       └── features/             # Feature-specific clients
│           ├── node_action/
│           ├── node_status/
│           ├── job_summary/
│           └── job_react_time/
│
├── src/                          # Schema management service
│   ├── schema_manager.py         # CLI tool for schema operations
│   └── alembic/                  # Migration scripts
│       ├── env.py
│       └── versions/             # Migration files
│
├── config/                       # Service configuration
│   └── postgresql-sdk.yaml       # Schema name config
│
├── deploy/                       # Kubernetes deployment templates
│   ├── postgresql-sdk-service.yaml.template      # Sync job
│   ├── postgresql-sdk-health-check.yaml.template # Health check cronjob
│   ├── start.sh.template         # Start service
│   ├── stop.sh.template          # Stop service
│   └── delete.sh                 # Delete resources
│
└── tests/                        # Unit tests
    ├── test_node_action_client.py
    └── test_node_status_client.py
```

### Database Schema

The service manages the following tables in the `ltp_sdk` schema:

| Table | Description |
|-------|-------------|
| `node_actions` | Records node actions (cordon, drain, etc.) |
| `node_status` | Tracks node status changes |
| `job_summary` | Job execution summary statistics |
| `job_react_time` | Job reaction time metrics |
| `alembic_version` | Migration version tracking |

---

## Quick Start

### 1. Build the Service Image

```bash
cd /workspaces/paitest/ltp-platform
./paictl.py image build -p /path/to/cluster-config.yaml -n postgresql-sdk
```

### 2. Push the Image

```bash
./paictl.py image push -p /path/to/cluster-config.yaml -n postgresql-sdk
```

### 3. Deploy the Service

```bash
./paictl.py service start -p /path/to/cluster-config.yaml -n postgresql-sdk
```

This will:
- Create the `ltp_sdk` schema
- Initialize all tables
- Set up migration tracking
- Start periodic health checks (runs every 6 hours)

### 4. Check Service Status

```bash
# Check if the sync job completed successfully
kubectl get job postgresql-sdk-sync -n default

# Check the logs
kubectl logs job/postgresql-sdk-sync -n default

# Check the health check cronjob
kubectl get cronjob postgresql-sdk-health-check -n default
```

---

## Using the SDK

### Installation in Other Services

Add the SDK to your service's Dockerfile:

```dockerfile
# Copy SDK from postgresql-sdk service
COPY src/postgresql-sdk/sdk /opt/ltp-postgresql-sdk

# Install SDK
RUN pip install -e /opt/ltp-postgresql-sdk
```

### Basic Usage

```python
from ltp_postgresql_sdk import NodeActionClient
from ltp_postgresql_sdk.features.node_action.models import NodeActionRecord
from datetime import datetime
import os

# Initialize client (reads from environment by default)
client = NodeActionClient()

# Or explicitly provide parameters
client = NodeActionClient(
    connection_str="postgresql://user:pass@host:port/db",
    schema="ltp_sdk"
)

# Insert a single record
record = NodeActionRecord(
    timestamp=datetime.utcnow(),
    hostname="worker-01",
    node_id="node-001",
    action="cordon",
    reason="Scheduled maintenance",
    detail="Node will be drained for updates",
    category="maintenance",
    endpoint="http://api.example.com"
)
record_id = client.insert_action(record)

# Query records
results = client.query_actions(hostname="worker-01", limit=10)
for action in results:
    print(f"{action['timestamp']}: {action['action']}")

# Batch insert
records = [NodeActionRecord(...), NodeActionRecord(...)]
record_ids = client.insert_actions_batch(records)

# Count records
count = client.count_actions(category="maintenance")
```

### Available Clients

```python
from ltp_postgresql_sdk import (
    NodeActionClient,      # Node action operations
    NodeStatusClient,      # Node status tracking
    JobSummaryClient,      # Job summary statistics
    JobReactTimeClient,    # Job reaction time metrics
)
```

### Kusto-SDK Interface Compatibility

The PostgreSQL SDK provides **interface compatibility** with the kusto-sdk for seamless migration. All clients support both PostgreSQL-native methods and kusto-sdk compatible methods:

#### NodeActionClient - Compatible Methods

```python
# Kusto-SDK compatible interface
client = NodeActionClient(connection_str=..., schema="ltp_sdk")

# Get node actions (kusto-sdk style)
actions = client.get_node_actions(
    node="worker-01",
    start_time="2024-01-01T00:00:00Z",
    end_time="2024-01-02T00:00:00Z"
)

# Get latest action
latest = client.get_latest_node_action(node="worker-01")

# Update/insert action
client.update_node_action(
    node="worker-01",
    action="cordoned",
    timestamp=datetime.utcnow(),
    reason="Maintenance",
    detail="Scheduled maintenance",
    category="maintenance"
)

# Execute raw SQL query (for advanced use)
results = client.execute_query("SELECT * FROM node_actions LIMIT 10")

# Access table name (for building custom queries)
table = client.table_name  # Returns "node_actions"
```

#### NodeStatusClient - Compatible Methods

```python
# Kusto-SDK compatible interface
client = NodeStatusClient(connection_str=..., schema="ltp_sdk")

# Get node status at specific time
status = client.get_node_status(hostname="worker-01", timestamp=datetime.utcnow())

# Update node status
new_status = client.update_node_status(
    hostname="worker-01",
    to_status="cordoned",
    timestamp=datetime.utcnow()
)

# Get all nodes with specific status
cordoned_nodes = client.get_nodes_by_status(status="cordoned")

# Execute raw SQL query
results = client.execute_query("SELECT * FROM node_statuses LIMIT 10")

# Access table name
table = client.table_name  # Returns "node_statuses"
```

#### Migration from Kusto-SDK

To migrate from kusto-sdk to postgresql-sdk:

1. **Update imports**:
   ```python
   # Before (kusto-sdk)
   from ltp_kusto_sdk import NodeActionClient, NodeStatusClient
   
   # After (postgresql-sdk)
   from ltp_postgresql_sdk import NodeActionClient, NodeStatusClient
   ```

2. **Initialization is now identical!**:
   ```python
   # Both kusto-sdk and postgresql-sdk work the same way
   client = NodeActionClient()  # Reads from environment variables
   
   # Or explicitly provide parameters (both SDKs support this)
   client = NodeActionClient(
       connection_str=os.environ["POSTGRES_CONNECTION_STR"],
       schema=os.environ["POSTGRES_SCHEMA"]
   )
   ```

3. **Method calls remain the same**:
   ```python
   # These work identically in both SDKs
   actions = client.get_node_actions(node="worker-01", start_time=..., end_time=...)
   latest = client.get_latest_node_action(node="worker-01")
   ```

4. **Query syntax differences** (if using `execute_query`):
   - Kusto Query Language (KQL) → PostgreSQL SQL
   - Example: `| where` → `WHERE`, `| project` → `SELECT`

### Environment Variables

```bash
# Connection string (required)
POSTGRES_CONNECTION_STR="postgresql://user:pass@host:port/db"

# Schema name (should match config/postgresql-sdk.yaml)
POSTGRES_SCHEMA="ltp_sdk"
```

---

## Schema Management

The service uses `schema_manager.py` for all schema operations.

### Available Commands

```bash
# Smart sync (auto init or upgrade)
python /app/src/schema_manager.py sync

# Initialize schema (first-time setup)
python /app/src/schema_manager.py init

# Upgrade to latest schema
python /app/src/schema_manager.py upgrade

# Downgrade to specific revision
python /app/src/schema_manager.py downgrade <revision>

# Health check
python /app/src/schema_manager.py check

# View migration history
python /app/src/schema_manager.py history

# Generate new migration (after model changes)
python /app/src/schema_manager.py generate --message "add new field"
```

### Creating Migrations

#### Develop locally
When you modify the models in `sdk/ltp_postgresql_sdk/models.py`:

1. **Generate the migration**:
   ```bash
   # In the test container or locally with the SDK
    kubectl exec -it <postgresql-sdk-sync-pod> -c test -- python /app/src/schema_manager.py generate --message "remove metadata and previous_status from node_status"
   ```

2. **Review the generated file**:
   ```bash
   # Check: src/alembic/versions/<revision>_add_new_column.py
   cat src/alembic/versions/*_add_new_column.py
   ```

3. **Apply the migration**:
   ```bash
   python src/schema_manager.py upgrade
   ```

4. **Test locally**

#### Commit: Add migration file to git

#### Deploy: Rebuild image → sync applies it automatically


### Migration Safety

Alembic migrations are **data-safe** for most operations:

| Operation | Data Impact | Safe? |
|-----------|-------------|-------|
| Add new table | None - new empty table | ✅ Yes |
| Add new column | Sets NULL or default value | ✅ Yes |
| Rename column | Preserves all data | ✅ Yes |
| Add index | Locks table briefly (MVCC) | ✅ Yes |
| Drop column | **Data loss** | ⚠️ Caution |
| Drop table | **Data loss** | ⚠️ Caution |

**Important**: 
- Adding columns/tables never modifies existing data
- PostgreSQL uses MVCC (Multi-Version Concurrency Control) for safe concurrent operations
- Always review auto-generated migrations before applying

---

## Testing

### Running Tests on the test endpoint

 **Run tests**:
   ```bash
   pytest tests/test_node_action_client.py -v
   pytest tests/test_node_status_client.py -v
   ```


---

## Deployment

### Service Lifecycle

| Command | Action | Database Impact |
|---------|--------|-----------------|
| `start` | Deploy sync job + health check CronJob | Creates/updates schema |
| `stop` | Suspend CronJob, delete sync job | **No change** |
| `delete` | Remove all K8s resources | **No change** |

### Start Service

```bash
./paictl.py service start -p cluster-config.yaml -n postgresql-sdk
```

**What happens:**
1. Waits for PostgreSQL to be ready
2. Runs `schema_manager.py sync` (init or upgrade)
3. Runs `schema_manager.py check` (health check)
4. Deploys health check CronJob (runs every 6 hours)

**Output:**
```
Waiting for PostgreSQL...
PostgreSQL is ready!
Running smart sync...
✓ Schema 'ltp_sdk' ensured
✓ Tables created
✓ Stamped database to head revision
✓ Schema initialized successfully
Health Check Results:
  database_connection: PASS
  schema_exists: PASS
  tables_exist: PASS
  migrations_current: PASS
```

### Stop Service

```bash
./paictl.py service stop -p cluster-config.yaml -n postgresql-sdk
```

**What happens:**
1. Suspends the health check CronJob
2. Deletes the sync Job
3. **Database schema and tables remain untouched**

### Delete Service

```bash
./paictl.py service delete -p cluster-config.yaml -n postgresql-sdk
```

**What happens:**
1. Deletes all Kubernetes resources
2. **Database schema and tables remain untouched**

**Note**: To fully remove the database schema:
```sql
-- Manual cleanup (if needed)
DROP SCHEMA ltp_sdk CASCADE;
```

### Configuration

Edit `config/postgresql-sdk.yaml`:

```yaml
service_type: "common"

# Schema name (must match POSTGRES_SCHEMA in SDK clients)
schema-name: "ltp_sdk"
```

The schema name is injected into Kubernetes manifests via:
```yaml
- name: POSTGRES_SCHEMA
  value: "{{ cluster_cfg['postgresql']['schema-name'] }}"
```

### Health Check Schedule

Edit `deploy/postgresql-sdk-health-check.yaml.template`:

```yaml
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
```

Common schedules:
- `"0 */1 * * *"` - Every hour
- `"0 */6 * * *"` - Every 6 hours (default)
- `"0 0 * * *"` - Daily at midnight
- `"*/5 * * * *"` - Every 5 minutes (testing)

---

## Troubleshooting

### Tables Not Created

**Problem**: Health check shows "No tables found"

**Symptoms**:
```
✓ Found 1 tables in schema 'ltp_sdk': alembic_version
```

**Solution**: Models not imported in `schema_manager.py`. Check:

```python
from ltp_postgresql_sdk.models import (
    NodeAction,
    NodeStatus,
    JobSummary,
    JobReactTime,
)
```

### Migration Failed

**Problem**: `upgrade` command fails

**Diagnosis**:
```bash
# Check current revision
python src/schema_manager.py check

# View migration history
python src/schema_manager.py history
```

**Solution**:
```bash
# Rollback to previous revision
python src/schema_manager.py downgrade <previous_revision>

# Or force re-init (WARNING: drops tables)
python src/schema_manager.py init --force
```

### Schema Isolation Issues

**Problem**: Conflicts with `database-controller`

**Verification**:
```sql
-- Check schema separation
\dn  -- List schemas

-- Check search_path
SHOW search_path;

-- Verify tables
\dt public.*       -- database-controller tables
\dt ltp_sdk.*      -- postgresql-sdk tables
```

**Solution**: Ensure all SDK models have:
```python
__table_args__ = {"schema": "ltp_sdk"}
```

### Logs

```bash
# Sync job logs
kubectl logs job/postgresql-sdk-sync -n default

# Health check logs (latest run)
kubectl logs job/$(kubectl get jobs -l app=postgresql-sdk-health-check --sort-by=.metadata.creationTimestamp -o name | tail -1) -n default

# All health check runs
kubectl get jobs -l app=postgresql-sdk-health-check
```

---

## Best Practices

### 1. SDK Usage in Services

✅ **Do**:
```python
# Single client instance per service
client = NodeActionClient(connection_str=..., schema="ltp_sdk")

# Use context manager for sessions
with client.get_session() as session:
    # ... operations
    session.commit()
```

❌ **Don't**:
```python
# Don't enable auto_init in production
client = NodeActionClient(auto_init=True)  # Only for testing!

# Don't hardcode schema names
client = NodeActionClient(schema="wrong_schema")
```

### 2. Migration Workflow

1. **Development**: Make model changes
2. **Generate**: `python src/schema_manager.py generate --message "..."`
3. **Review**: Check the generated migration file
4. **Test**: Apply in test environment
5. **Deploy**: Build new image, restart service

### 3. Monitoring

- Check health check CronJob results regularly
- Monitor sync job completion time
- Track table growth and performance
- Set up alerts for failed health checks

