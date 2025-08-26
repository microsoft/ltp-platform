mkdir -p ./Traces
nohup ./bin/modelproxy --config ./bin/config.json >> ./Traces/all.log 2>&1 &