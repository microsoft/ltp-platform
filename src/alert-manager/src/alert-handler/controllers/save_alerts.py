import sys
import json
from datetime import datetime

try:
    from ltp_storage.factory import create_alert_client
    from ltp_storage.data_schema.alert_records import AlertRecordData
except ImportError as e:
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)

try:
    fd3 = 3
    with open(fd3, 'r', encoding='utf-8', closefd=False) as f:
        alerts_json = f.read()
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


