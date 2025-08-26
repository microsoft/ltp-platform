package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"strings"

	"AIMiciusModelProxy/proxy"
	"AIMiciusModelProxy/trace"
	"AIMiciusModelProxy/types"
)

var (
	configFilePath string
	host           string
	port           int
	maxRetries     int = 5 // default value
	logFileDir     string
	accessKeys     string
	modelUrls      string
	modelKeys      string
	modelNames     string
	modelVersion   string = "2025-04-01-preview"
)

func init() {
	flag.StringVar(&configFilePath, "config", "", "path to the config file. If this is set, other flags will be ignored")

	flag.StringVar(&host, "host", "localhost", "host for the proxy server")
	flag.IntVar(&port, "port", 30000, "port for the proxy server")
	flag.IntVar(&maxRetries, "retry", 5, "max retries for the request to the model server")
	flag.StringVar(&logFileDir, "logdir", "./logs", "path to the log file directory")
	flag.StringVar(&accessKeys, "lb-keys", "", "comma-separated access keys for the load balance server")
	flag.StringVar(&modelUrls, "model-urls", "", "comma-separated model urls for the proxy server")
	flag.StringVar(&modelKeys, "model-keys", "", "comma-separated model keys for the proxy server")
	flag.StringVar(&modelNames, "model-names", "", "comma-separated model names for the proxy server")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage of AIMiciusModelProxy:\n")
		fmt.Fprintf(os.Stderr, "\nOptions:\n")
		flag.PrintDefaults()
		fmt.Fprintf(os.Stderr, "\nExample:\n")
		fmt.Fprintf(os.Stderr, "  Using config file:\n")
		fmt.Fprintf(os.Stderr, "    ./AIMiciusModelProxy --config=./config.json\n\n")
		fmt.Fprintf(os.Stderr, "  Using command line arguments:\n")
		fmt.Fprintf(os.Stderr, "    ./AIMiciusModelProxy --host=0.0.0.0 --port=8080 --lb-keys=key1,key2 \\\n")
		fmt.Fprintf(os.Stderr, "      --model-urls=https://api.openai.com,https://azure.openai.com \\\n")
		fmt.Fprintf(os.Stderr, "      --model-keys=sk-xxx,azure-key \\\n")
		fmt.Fprintf(os.Stderr, "      --model-names=gpt-4,gpt-35-turbo\n")
	}
}

func parseArgs() (*types.Config, error) {
	// Parse the command line arguments
	flag.Parse()
	if configFilePath != "" {
		config, err := types.ParseConfig(configFilePath)
		return config, err
	}
	// If config file is not provided, use the command line arguments to create the config
	config := &types.Config{}

	// Parse the server configuration
	var accessKeysList []string
	if accessKeys != "" {
		accessKeysList = strings.Split(accessKeys, ",")
	} else {
		accessKeysList = nil
	}
	config.Server = &types.Server{
		Host:       host,
		Port:       port,
		MaxRetries: maxRetries,
		AccessKeys: accessKeysList,
	}
	// Parse the log configuration
	config.Log = &types.Log{
		LogStorage: &types.LogStorage{
			LocalFolder: logFileDir,
		},
		TraceRelatedKeys: []string{"source", "category_info", "other_metadata"},
	}
	// Parse the endpoints configuration

	azureSpecs := []*types.EndpointsSpec{}
	openAISpecs := []*types.EndpointsSpec{}
	modelUrlList := strings.Split(modelUrls, ",")
	modelKeyList := strings.Split(modelKeys, ",")
	modelNameList := strings.Split(modelNames, ",")
	if len(modelUrlList) != len(modelKeyList) || len(modelUrlList) != len(modelNameList) {
		return nil, errors.New("[-] Error: the length of model urls, keys and names must be the same")
	}
	for i, url := range modelUrlList {
		if url == "" {
			continue
		}
		if strings.Contains(url, "azure") {
			// If the url is an Azure endpoint
			azureSpecs = append(azureSpecs, &types.EndpointsSpec{
				BaseSpec: &types.BaseSpec{
					URL:     url,
					Key:     modelKeyList[i],
					Version: modelVersion,
				},
				ChatModels:      []string{modelNameList[i]},
				EmbeddingModels: []string{},
			})
		} else {
			// If the url is an OpenAI endpoint
			openAISpecs = append(openAISpecs, &types.EndpointsSpec{
				BaseSpec: &types.BaseSpec{
					URL: url,
					Key: modelKeyList[i],
				},
				ChatModels:      []string{modelNameList[i]},
				EmbeddingModels: []string{},
			})
		}
	}

	config.Endpoints = &types.Endpoints{
		AzureSpec:  azureSpecs,
		OpenAISpec: openAISpecs,
	}
	return config, nil
}

func main() {
	config, err := parseArgs()
	if err != nil {
		log.Fatal("[-] Error in converting config to JSON:" + err.Error())
	}

	configJSON, _ := json.MarshalIndent(config, "", "  ")
	fmt.Printf("[*] Using config: %s\n", string(configJSON))
	if err != nil {
		log.Fatal("[-] Error in parsing config:" + err.Error())
	}

	var uploader *trace.BlobUploader
	if config.Log.LogStorage.AzureStorage != nil {
		// If azure storage is configured, use the AzureBlobUploader
		uploader = trace.NewBlobUploader(config.Log.LogStorage.AzureStorage)
	}
	traceLogger := trace.NewJsonFileLogger(config.Log.LogStorage.LocalFolder, uploader)

	ph := proxy.NewProxyHandler(config)
	ph.StartProxy(traceLogger)

}
