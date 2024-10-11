#!/bin/bash

# Copyright (c) Microsoft Corporation
# All rights reserved.

set -o errexit
set -o pipefail

log_exist_time=30 # 30 day
if [ -n "${LOG_EXIST_TIME}" ]; then
  log_exist_time=${LOG_EXIST_TIME}
fi

archive_base_dir="$ARCHIVE_LOG_DIR"

cat > /etc/periodic/daily/move_logs << EOF
#!/bin/bash
archive_base_dir="\$ARCHIVE_LOG_DIR"
/usr/bin/pgrep -f ^find 2>&1 > /dev/null || {
  find /usr/local/pai/logs/* -mtime +${log_exist_time} -type f | while read -r log_file; do
    # Extract the path component of the log file
    relative_path="\${log_file#/usr/local/pai/logs/}"

    # Remove the last section (file name) from the relative path
    target_dir="\${archive_base_dir}/\${relative_path%/*}"

    # Check if log_file is named 'lock' or 'state'
    if [[ "\$log_file" =~ /(lock|state)$ ]]; then
      echo "Ignoring file: \$log_file"
      rm -fv "\$log_file"
      continue
    fi

    if [[ -n "\${archive_base_dir}" ]]; then
      mkdir -p "\$target_dir"
      echo "move file: \$log_file to \$target_dir"
      mv -v "\$log_file" "\$target_dir/"
    else
      echo "remove file: \$log_file"
      rm -fv "\$log_file"
    fi
  done
}
EOF

cat > /etc/periodic/daily/remove_log_dir << EOF
#!/bin/bash
/usr/bin/pgrep -f ^find 2>&1 > /dev/null || find /usr/local/pai/logs/* -mtime +${log_exist_time} -type d -empty -exec rmdir -v {} \;
EOF

chmod a+x /etc/periodic/daily/move_logs /etc/periodic/daily/remove_log_dir

echo "cron job added"

crond -f -l 0

