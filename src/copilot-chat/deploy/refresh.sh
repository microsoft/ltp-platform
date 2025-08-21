#!/bin/bash

# Stop the running copilot-chat container
bash "$(dirname "$0")/stop.sh"

# Start the copilot-chat container
bash "$(dirname "$0")/start.sh"