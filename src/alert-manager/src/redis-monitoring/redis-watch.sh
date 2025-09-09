#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

INTERVAL=5

while true; do
  echo "==== $(date) ===="
  for stream in collection_requests monitor_results detection_events; do
    len=$(redis-cli xlen $stream 2>/dev/null)
    echo "Stream $stream: ${len:-Not created}"
  done
  redis-cli info memory | grep -E 'used_memory_human|evicted_keys|mem_fragmentation_ratio'
  redis-cli info clients | grep -E 'connected_clients|blocked_clients'
  redis-cli info stats | grep instantaneous_ops_per_sec
  sleep $INTERVAL
done