package types

import (
	"encoding/json"
	"os"
)

// Config is the struct for config.json
type Config struct {
	Server    *Server    `json:"server"`
	Log       *Log       `json:"log"`
	Endpoints *Endpoints `json:"endpoints"`
}

// Server is the struct for proxy server config
type Server struct {
	// Host is the host of the server
	Host string `json:"host"`
	// Port is the port of the server
	Port int `json:"port"`
	// MaxRetries is the max retries for the request
	MaxRetries int `json:"retry"`
	// Access keys  for the server, it can be empty, a list (["key1", "key2"]), or a map with the key and the deadline (like {"key1": "2023-08-01"}, the time shoud be in this format: "2006-01-02")
	AccessKeys interface{} `json:"access_keys,omitempty"`
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

type Endpoints struct {
	AzureSpec  []*EndpointsSpec `json:"azure_spec,omitempty"`
	OpenAISpec []*EndpointsSpec `json:"openai_spec,omitempty"`
}

// BaseSpec is the base spec for azure and openai
type BaseSpec struct {
	URL     string `json:"url"`
	Key     string `json:"key"`
	Version string `json:"version,omitempty"`
}

type EndpointsSpec struct {
	*BaseSpec
	ChatModels      []string `json:"chat,omitempty"`
	EmbeddingModels []string `json:"embeddings,omitempty"`
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
	SuceessRate       float64
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

// According to the struct Endpoints, convert it into the two ReverseMap from deploy_name to to BaseSpec for AzureSpec and OpenAISpec
func (e *Endpoints) ToReverseMap() *AllReverseMap {
	azureChat := make(ModelToBase)
	azureEmbedding := make(ModelToBase)
	openAIChat := make(ModelToBase)
	openAIEmbedding := make(ModelToBase)

	for _, spec := range e.AzureSpec {
		for _, model := range spec.ChatModels {
			if _, ok := azureChat[model]; !ok {
				azureChat[model] = make(BaseSpecList, 0, 1)
			}
			azureChat[model] = append(azureChat[model],
				&BaseSpecStatistic{BaseSpec: spec.BaseSpec})
		}
		for _, model := range spec.EmbeddingModels {
			if _, ok := azureEmbedding[model]; !ok {
				azureEmbedding[model] = make(BaseSpecList, 0, 1)
			}
			azureEmbedding[model] = append(azureEmbedding[model],
				&BaseSpecStatistic{BaseSpec: spec.BaseSpec})
		}
	}

	for _, spec := range e.OpenAISpec {
		for _, model := range spec.ChatModels {
			if _, ok := openAIChat[model]; !ok {
				openAIChat[model] = make(BaseSpecList, 0, 1)
			}
			openAIChat[model] = append(openAIChat[model],
				&BaseSpecStatistic{BaseSpec: spec.BaseSpec})
		}
		for _, model := range spec.EmbeddingModels {
			if _, ok := openAIEmbedding[model]; !ok {
				openAIEmbedding[model] = make(BaseSpecList, 0, 1)
			}
			openAIEmbedding[model] = append(openAIEmbedding[model],
				&BaseSpecStatistic{BaseSpec: spec.BaseSpec})
		}
	}

	return &AllReverseMap{
		Azure: &ReverseMap{
			Chat:      azureChat,
			Embedding: azureEmbedding,
		},
		OpenAI: &ReverseMap{
			Chat:      openAIChat,
			Embedding: openAIEmbedding,
		},
	}
}
