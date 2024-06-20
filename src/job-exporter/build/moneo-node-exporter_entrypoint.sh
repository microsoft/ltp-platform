#!/bin/bash
# Starts Node Exporter
python3 /Moneo/src/worker/exporters/node_exporter.py &
echo "Node Exporter Started!"

# Waits for any process to exit and returns the exit status
wait -n
exit $?
