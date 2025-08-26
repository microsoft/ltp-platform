mkdir -p ./Traces
nohup ./bin/AIMiciusModelProxy --config ./bin/config.json >> ./Traces/all.log 2>&1 &