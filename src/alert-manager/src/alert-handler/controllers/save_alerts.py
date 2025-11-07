import sys
import os
import json
from datetime import datetime

try:
    from ltp_storage.factory import create_alert_client
    from ltp_storage.data_schema.alert_records import AlertRecordData
except ImportError as e:
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)

# Get temp file path from command line argument
if len(sys.argv) < 2:
    print("Error: Temp file path argument is required", file=sys.stderr)
    sys.exit(1)

tmp_file_path = sys.argv[1]

try:
    # Read alerts from temp file
    if not os.path.exists(tmp_file_path):
        print(f"Error: Temp file does not exist: {tmp_file_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(tmp_file_path, 'r', encoding='utf-8') as f:
            alerts_json = f.read()
    except IOError as e:
        print(f"Failed to read temp file {tmp_file_path}: {e}", file=sys.stderr)
        sys.exit(1)
    
    alerts = json.loads(alerts_json)

    client = create_alert_client()
    records = []

    for alert in alerts:
        try:
            ts_str = alert['timestamp'].replace('Z', '+00:00')
            timestamp = datetime.fromisoformat(ts_str)

            record = AlertRecordData(
                timestamp=timestamp,
                alertname=alert['alertname'],
                severity=alert['severity'],
                summary=alert['summary'],
                node_name=alert.get('node_name'),
                labels=alert.get('labels'),
                annotations=alert.get('annotations'),
                endpoint=alert['endpoint']
            )
            records.append(record)
        except Exception as e:
            print(f"Error parsing alert: {e}", file=sys.stderr)

    if records:
        client.insert_alerts_batch(records)
        print(f"Successfully saved {len(records)} alerts to PostgreSQL")
    else:
        print("No valid alerts to save", file=sys.stderr)

except Exception as e:
    print(f"Failed to save alerts to PostgreSQL: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    # Always delete the temp file after processing, even if there was an error
    try:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
    except OSError as e:
        print(f"Warning: Failed to delete temp file {tmp_file_path}: {e}", file=sys.stderr)


