package types

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
)

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type Source struct {
	SourceName string `json:"source_name"`
	Location   string `json:"location,omitempty"`
}

// Request is the struct for request of openai chat. It is used to parse the request body
type Request struct {
	Messages         []Message          `json:"messages"`
	Model            string             `json:"model"`
	Temperature      float64            `json:"temperature,omitempty"`
	Choices          int                `json:"n,omitempty"`
	PresencePenalty  float64            `json:"presence_penalty,omitempty"`
	TopP             float64            `json:"top_p,omitempty"`
	FrequencyPenalty float64            `json:"frequency_penalty,omitempty"`
	Stream           bool               `json:"stream,omitempty"`
	Stop             string             `json:"stop,omitempty"`
	MaxTokens        int                `json:"max_tokens,omitempty"`
	LogitBias        map[string]float64 `json:"logit_bias,omitempty"`
	User             string             `json:"user,omitempty"`

	Source        *Source            `json:"source,omitempty"`
	CategoryInfo  *map[string]string `json:"category_info,omitempty"`
	Label         *[]string          `json:"labels,omitempty"`
	OtherMetadata string             `json:"other_metadata,omitempty"`
}

func (r *Request) Unmarshal(data []byte) error {
	return json.Unmarshal(data, r)
}

// Response is the struct for response of openai chat
type Response struct {
	ID      string `json:"id"`
	Object  string `json:"object"`
	Created int64  `json:"created"`
	Model   string `json:"model"`
	Choices []struct {
		Index        int     `json:"index"`
		FinishReason string  `json:"finish_reason"`
		Message      Message `json:"message"`
	} `json:"choices"`
	Usage struct {
		PromptTokens     int `json:"prompt_tokens"`
		CompletionTokens int `json:"completion_tokens"`
		TotalTokens      int `json:"total_tokens"`
	} `json:"usage"`
}

func (r *Response) Unmarshal(data []byte) error {
	return json.Unmarshal(data, r)
}

// ResponseChunk is the struct for response of openai chat stream
type ResponseChunk struct {
	ID      string `json:"id"`
	Object  string `json:"object"`
	Created int64  `json:"created"`
	Model   string `json:"model"`
	Choices []struct {
		Index        int    `json:"index"`
		FinishReason string `json:"finish_reason"`
		Delta        struct {
			Content string `json:"content"`
		} `json:"delta"`
	} `json:"choices"`
}

func (rc *ResponseChunk) Unmarshal(data []byte) error {
	return json.Unmarshal(data, rc)
}

// TraceMessage is the struct for each message in a trace
type TraceMessage struct {
	Role     string  `json:"from"`
	Content  string  `json:"value"`
	Score    float64 `json:"score"`
	ParentID int     `json:"parent_id"`
	ID       int     `json:"id"`
}

type ModelInfo struct {
	ModelName        string             `json:"model_name"`
	Temperature      float64            `json:"temperature,omitempty"`
	Choices          int                `json:"n,omitempty"`
	PresencePenalty  float64            `json:"presence_penalty,omitempty"`
	TopP             float64            `json:"top_p,omitempty"`
	FrequencyPenalty float64            `json:"frequency_penalty,omitempty"`
	Stream           bool               `json:"stream,omitempty"`
	Stop             string             `json:"stop,omitempty"`
	MaxTokens        int                `json:"max_tokens,omitempty"`
	LogitBias        map[string]float64 `json:"logit_bias,omitempty"`
	User             string             `json:"user,omitempty"`
}

// Trace is the struct for one trace. It is recorded in the json file
type Trace struct {
	ID             string             `json:"id"`
	Source         *Source            `json:"source,omitempty"`
	CategoryInfo   *map[string]string `json:"category_info,omitempty"`
	Other_metadata string             `json:"other_metadata,omitempty"`
	ModelInfo      *ModelInfo         `json:"model_info"`
	Conversations  []*TraceMessage    `json:"conversation"`
}

func (t *Trace) Marshal() ([]byte, error) {
	return json.Marshal(t)
}

// convert a request and reqponse to a trace
func ConvertReqResp2Trace(req *Request, response []string) *Trace {
	conversactions := make([]*TraceMessage, 0, len(req.Messages)+len(response))
	for i, msg := range req.Messages {
		conversactions = append(conversactions, &TraceMessage{
			Role:     msg.Role,
			Content:  msg.Content,
			Score:    -1,
			ParentID: i - 1,
			ID:       i,
		})
	}
	for _, resp := range response {
		conversactions = append(conversactions, &TraceMessage{
			Role:     "assistant",
			Content:  resp,
			Score:    -1,
			ParentID: len(req.Messages) - 1,
			ID:       len(conversactions),
		})
	}

	id, _ := generateID()

	trace := &Trace{
		ID:             id,
		Source:         req.Source,
		CategoryInfo:   req.CategoryInfo,
		Other_metadata: req.OtherMetadata,
		ModelInfo: &ModelInfo{
			ModelName:        req.Model,
			Temperature:      req.Temperature,
			Choices:          req.Choices,
			PresencePenalty:  req.PresencePenalty,
			TopP:             req.TopP,
			FrequencyPenalty: req.FrequencyPenalty,
			Stream:           req.Stream,
			Stop:             req.Stop,
			MaxTokens:        req.MaxTokens,
			LogitBias:        req.LogitBias,
			User:             req.User,
		},
		Conversations: conversactions,
	}

	return trace
}

// generate a 16bytes id
func generateID() (string, error) {
	buf := make([]byte, 16)
	_, err := rand.Read(buf)
	if err != nil {
		return "", err
	}
	res := hex.EncodeToString(buf)
	return res, nil
}
