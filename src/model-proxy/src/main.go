package main

import (
	"flag"

	"modelproxy/proxy"
	"modelproxy/trace"
	"modelproxy/types"
)

var (
	port       int
	maxRetries int = 5 // default value
	logFileDir string
	modelKey   string
)

func init() {
	flag.IntVar(&port, "port", 9999, "port for the proxy server")
	flag.IntVar(&maxRetries, "retry", 5, "max retries for the request to the model server")
	flag.StringVar(&logFileDir, "logdir", "./logs", "path to the log file directory")
	flag.StringVar(&modelKey, "modelkey", "", "comma-separated model keys for the proxy server")
}

func main() {
	flag.Parse()

	config := types.Config{
		Server: &types.Server{
			Host:       "0.0.0.0",
			Port:       port,
			MaxRetries: maxRetries,
			ModelKey:   modelKey,
		},
		Log: &types.Log{
			LogStorage: &types.LogStorage{
				LocalFolder:  logFileDir,
				AzureStorage: nil,
			},
			TraceRelatedKeys: []string{},
		},
	}
	ph := proxy.NewProxyHandler(&config)
	traceLogger := trace.NewJsonFileLogger(logFileDir)

	ph.StartProxy(traceLogger)

}
