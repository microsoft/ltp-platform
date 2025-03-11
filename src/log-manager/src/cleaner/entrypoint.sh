#!/bin/bash

# Copyright (c) Microsoft Corporation
# All rights reserved.

set -o errexit
set -o pipefail

log_exist_time=30 # 30 days
if [ -n "${LOG_EXIST_TIME}" ]; then
  log_exist_time=${LOG_EXIST_TIME}
fi

archive_base_dir="$ARCHIVE_LOG_DIR"

# Create rsync_logs script
cat > /etc/periodic/daily/rsync_logs << EOF
#!/bin/bash
archive_base_dir="\$ARCHIVE_LOG_DIR"

# Ensure ARCHIVE_LOG_DIR is set
if [[ -z "\${archive_base_dir}" ]]; then
  echo "Error: ARCHIVE_LOG_DIR is not set. Logs will not be archived." | tee /dev/stdout
  exit 1
fi

# Ensure archive directory exists
mkdir -p "\$archive_base_dir"

echo "Starting log sync..." | tee /dev/stdout
/usr/bin/pgrep -f ^find 2>&1 > /dev/null || {
  rsync -av --ignore-existing --exclude='*/lock' --exclude='*/state' /usr/local/pai/logs/ "\$archive_base_dir/" | tee /dev/stdout
  echo "Log sync completed." | tee /dev/stdout
}
EOF

# Create remove_log_dir script
cat > /etc/periodic/daily/remove_log_dir << EOF
#!/bin/bash
archive_base_dir="\$ARCHIVE_LOG_DIR"

echo "Checking logs for deletion..." | tee /dev/stdout

# Check if ARCHIVE_LOG_DIR is not empty
if [[ -n "\$archive_base_dir" ]]; then
  find /usr/local/pai/logs/ -mtime +${log_exist_time} -type f | while read -r log_file; do
    relative_path="\${log_file#/usr/local/pai/logs/}"
    archived_file="\${archive_base_dir}/\${relative_path}"
    # Only delete if the file exists in the archive and is older than log_exist_time
    rsync --remove-source-files -av "\$log_file" "\$archived_file" | tee /dev/stdout   # This removes the file from source after sync
  done
else
  echo "Error: ARCHIVE_LOG_DIR is not set. Logs will be deleted without being archived." | tee /dev/stdout
  find /usr/local/pai/logs/ -mtime +${log_exist_time} -type f -exec rm -v {} \;
fi

# Remove empty directories
find /usr/local/pai/logs/ -mtime +${log_exist_time} -depth -type d -empty -exec rmdir {} \; 2>/dev/null
EOF

# Set execution permissions
chmod a+x /etc/periodic/daily/rsync_logs /etc/periodic/daily/remove_log_dir

echo "Cron job added."

# Run cron daemon in foreground with logs
crond -f -l 0

