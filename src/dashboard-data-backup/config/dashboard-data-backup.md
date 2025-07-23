# Dashboard Data Backup Service

The Dashboard Data Backup service is a containerized cron-based backup solution that automatically backs up Kusto query results from PowerBI dashboards to specified Kusto tables.

## Table of Contents

- [Overview](#overview)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Schedule Management](#schedule)
- [Manual Execution](#manual)
- [Troubleshooting](#troubleshooting)

## Overview <a name="overview"></a>

The service runs scheduled backups of PowerBI dashboard data by:
1. Reading configuration from `table_name.json`
2. Extracting Kusto queries from PowerBI files
3. Executing queries and appending results to backup tables
4. Adding timestamp metadata to track backup times

### Architecture
- **Container**: Python 3.12 with cron daemon
- **Schedule**: Runs at 2am, 8am, 2pm, and 8pm UTC daily
- **Authentication**: Azure device login (requires manual authentication for first run)
- **Logging**: All operations logged to `/var/log/backup/backup.log`

## Configuration <a name="configuration"></a>

### Table Configuration File: `src/tables/table_name.json`

This file defines which PowerBI tables to backup and where to store them.

**Structure:**
```json
[
  {
    "name": "A-r0-na.tmdl",
    "src_table": {
      "cluster": "https://azcore.centralus.kusto.windows.net",
      "database": "AzureCP",
      "table": "source_table_name"
    },
    "dst_table": {
      "cluster": "https://azcore.centralus.kusto.windows.net", 
      "database": "destination_database",
      "table": "PBICacheClusterCapacityStatus"
    }
  }
]
```

**Parameters:**
- `name`: PowerBI file name (must exist in `src/tables/` directory)
- `src_table`: Source Kusto cluster/database configuration
- `dst_table`: Destination backup table configuration

### Generated Configuration

After parsing, the service creates backup jobs with:
```yaml
backup-jobs:
  - source: PowerBI query from A-r0-na.tmdl
    destination: PBICacheClusterCapacityStatus table
    schedule: "0 2,8,14,20 * * *"
    timestamp: BackupTimeStamp column added automatically
```

## Deployment <a name="deployment"></a>

### Available Scripts

All scripts are located in the `deploy/` directory:

#### Start Service
```bash
cd deploy/
./start.sh
```
**What it does:**
- Stops any existing container
- Builds fresh Docker image with latest code
- Starts new container with auto-restart policy
- Shows container status and helpful commands

#### Stop Service  
```bash
./stop.sh
```
**What it does:**
- Stops the running container gracefully
- Preserves container for restart
- Provides next steps and commands

#### Refresh Service
```bash
./refresh.sh  
```
**What it does:**
- Stops current service
- Rebuilds image with latest changes
- Starts updated service
- Useful after code or configuration changes

#### Delete Service
```bash
./delete.sh
```
**What it does:**
- Stops the service
- Removes the Docker container completely
- Removes the Docker image to free disk space
- Complete cleanup for fresh deployment

### Deployment Table

<table>
<tr>
    <td>Command</td>
    <td>Purpose</td>
    <td>Container State After</td>
    <td>Use Case</td>
</tr>
<tr>
    <td>./start.sh</td>
    <td>Deploy/Start service</td>
    <td>Running</td>
    <td>First deployment, restart after stop</td>
</tr>
<tr>
    <td>./stop.sh</td>
    <td>Stop service</td>
    <td>Stopped (preserved)</td>
    <td>Temporary shutdown, maintenance</td>
</tr>
<tr>
    <td>./refresh.sh</td>
    <td>Update and restart</td>
    <td>Running (rebuilt)</td>
    <td>After code/config changes</td>
</tr>
<tr>
    <td>./delete.sh</td>
    <td>Complete removal</td>
    <td>Removed</td>
    <td>Cleanup, fresh start, free space</td>
</tr>
</table>

## Schedule Management <a name="schedule"></a>

### Default Schedule

The service runs every 6 hours:
```bash
# Current schedule in src/crontab
0 2,8,14,20 * * * root cd /app/src && python backup_kusto_query_res.py >> /var/log/backup/backup.log 2>&1
```

### Modifying the Schedule

1. **Edit the crontab file:**
   ```bash
   vi src/crontab
   ```

2. **Cron format:** `minute hour day month dayofweek`
   ```bash
   # Examples:
   0 */4 * * *     # Every 4 hours
   0 6,12,18 * * * # At 6am, 12pm, 6pm daily  
   0 2 * * 1       # Every Monday at 2am
   */30 * * * *    # Every 30 minutes
   ```

3. **Apply changes:**
   ```bash
   ./refresh.sh
   ```

### Schedule Examples

<table>
<tr>
    <td>Schedule</td>
    <td>Cron Expression</td>
    <td>Description</td>
</tr>
<tr>
    <td>Every hour</td>
    <td>0 * * * *</td>
    <td>At minute 0 of every hour</td>
</tr>
<tr>
    <td>Every 6 hours</td>
    <td>0 */6 * * *</td>
    <td>At 00:00, 06:00, 12:00, 18:00</td>
</tr>
<tr>
    <td>Daily at 3am</td>
    <td>0 3 * * *</td>
    <td>Once per day at 3:00 AM</td>
</tr>
<tr>
    <td>Weekdays only</td>
    <td>0 8 * * 1-5</td>
    <td>8am Monday through Friday</td>
</tr>
</table>

## Manual Execution <a name="manual"></a>

### Run Backup Manually

To manually trigger a backup without waiting for the scheduled time:

```bash
# Execute backup script inside running container
docker exec -it dashboard-data-backup-container bash -c "cd /app/src && python backup_kusto_query_res.py"
```

### Debug and Inspect

```bash
# Check container status
docker ps --filter "name=dashboard-data-backup-container"

# View live logs
docker logs -f dashboard-data-backup-container

# Access container shell
docker exec -it dashboard-data-backup-container bash

# Check cron status inside container
docker exec -it dashboard-data-backup-container service cron status

# View cron jobs
docker exec -it dashboard-data-backup-container crontab -l

# Check backup logs
docker exec -it dashboard-data-backup-container cat /var/log/backup/backup.log

# List files in container
docker exec -it dashboard-data-backup-container ls -la /app/src/
```

### Manual Commands Inside Container

Once inside the container (`docker exec -it dashboard-data-backup-container bash`):

```bash
# Navigate to application directory
cd /app/src

# Run backup script directly
python backup_kusto_query_res.py

# Check configuration
cat tables/table_name.json

# Check cron schedule
crontab -l

# View recent logs
tail -f /var/log/backup/backup.log

# Test Python imports
python -c "import util; print('Imports successful')"
```

## Troubleshooting <a name="troubleshooting"></a>

### Common Issues

1. **Authentication Required**
   - First run requires device login authentication
   - Follow the URL and code provided in logs

2. **Configuration Errors**
   - Verify `tables/table_name.json` format
   - Check PowerBI file exists in `tables/` directory

3. **Schedule Not Running**
   - Check cron service: `docker exec -it dashboard-data-backup-container service cron status`
   - Verify crontab: `docker exec -it dashboard-data-backup-container crontab -l`

4. **Container Won't Start**
   - Check Docker logs: `docker logs dashboard-data-backup-container`
   - Rebuild service: `./refresh.sh`

### Log Locations

- **Container logs**: `docker logs dashboard-data-backup-container`
- **Backup logs**: `/var/log/backup/backup.log` (inside container)
- **Cron logs**: `/var/log/cron.log` (if enabled)

### Getting Help

```bash
# Check service status
docker ps --filter "name=dashboard-data-backup"

# View configuration  
docker exec -it dashboard-data-backup-container cat /app/src/tables/table_name.json

# Test manual execution
docker exec -it dashboard-data-backup-container bash -c "cd /app/src && python backup_kusto_query_res.py"
```
