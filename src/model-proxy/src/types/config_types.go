package types

import (
	"encoding/json"
	"os"
)

// Config is the struct for config.json
type Config struct {
	Server *Server `json:"server"`
	Log    *Log    `json:"log"`
}

// Server is the struct for proxy server config
type Server struct {
	// Host is the host of the server
	Host string `json:"host"`
	// Port is the port of the server
	Port int `json:"port"`
	// MaxRetries is the max retries for the request
	MaxRetries int `json:"retry"`
	// ModelKey is the model key for the proxy server to access the model server
	ModelKey string `json:"model_key"`
}

// Log is the config for log
type Log struct {
	// LogStorage is the log storage config
	LogStorage *LogStorage `json:"storage"`
	// TraceRelatedKeys is the keys that will be logged in trace,
	// which will be used to identify the trace and filtered in the api request
	TraceRelatedKeys []string `json:"trace_related_keys"`
}

// LogStorage is the config for log storage
type LogStorage struct {
	LocalFolder  string        `json:"local_folder,omitempty"`
	AzureStorage *AzureStorage `json:"azure_storage,omitempty"`
}

type AzureStorage struct {
	// URL is the url of the azure blob storage, including the sas token
	URL       string `json:"url"`
	Container string `json:"container"`
	Path      string `json:"path"`
}

// BaseSpec is the base spec for azure and openai
type BaseSpec struct {
	URL     string `json:"url"`
	Key     string `json:"key"`
	Version string `json:"version,omitempty"`
}

// ParseConfig parse the config file into Config struct
func ParseConfig(path string) (*Config, error) {
	file, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var config Config
	err = json.Unmarshal(file, &config)
	if err != nil {
		return nil, err
	}

	return &config, nil
}

// BaseSpecStatistic is the struct for statistic
type BaseSpecStatistic struct {
	*BaseSpec
	ValidRequestCount int
	SuccessCount      int
	SuccessRate       float64
}

type BaseSpecList []*BaseSpecStatistic

// deploy_name -> BaseSpecList
type ModelToBase map[string]BaseSpecList

// Two reverse maps for chat and embedding
type ReverseMap struct {
	Chat      ModelToBase
	Embedding ModelToBase
}

// two ReverseMap for Azure and OpenAI
type AllReverseMap struct {
	Azure  *ReverseMap
	OpenAI *ReverseMap
}
