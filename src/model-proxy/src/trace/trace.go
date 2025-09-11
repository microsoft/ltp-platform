// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

package trace

import (
	"bytes"
	"log"
	"os"
	"path"
	"strings"
	"sync"
	"time"

	"modelproxy/types"
)

const maxNumChoice = 10 // Reasonable upper limit for number of choices per request. Adjust as needed.

// TraceLogger is the interface for trace logger
type TraceLogger interface {
	// Record the trace
	Record(req string, resp []string)
}

// JsonFileLogger is a logger that log the trace into json files, it implements TraceLogger interface
// The log file is named by date, and the log file will be uploaded to Azure Blob Storage everyday
type JsonFileLogger struct {
	localFolderPath string
	currentDay      string
	lock            sync.Mutex
}

// NewJsonFileLogger create a new JsonFileLogger
func NewJsonFileLogger(folderPath string) *JsonFileLogger {
	if _, err := os.Stat(folderPath); os.IsNotExist(err) {
		if err := os.Mkdir(folderPath, os.ModePerm); err != nil {
			log.Printf("Failed to create directory %s: %v", folderPath, err)
		}
	}
	date := time.Now().Format("2006-01-02")
	return &JsonFileLogger{localFolderPath: folderPath, currentDay: date}
}

func (j *JsonFileLogger) Record(req string, resp []string) {
	go j.record(req, resp)
}

// record the trace
func (j *JsonFileLogger) record(req string, resp []string) {
	if req == "" || len(resp) == 0 {
		return
	}

	reqStruct := &types.Request{}
	if err := reqStruct.Unmarshal([]byte(req)); err != nil {
		log.Printf("[-] Error: %s\nrequest: %s\nresponse: %s\n", err, req, resp)
		return
	}

	numChoice := reqStruct.Choices
	if numChoice <= 0 {
		numChoice = 1
	}
	if numChoice > maxNumChoice {
		numChoice = maxNumChoice
	}

	respStr := make([]string, numChoice)
	modelName := ""
	if len(resp) > 1 {
		// If len(resp) > 1, the resp is a 'stream'
		respConcat := make([]bytes.Buffer, numChoice)
		for _, r := range resp {
			lines := strings.Split(r, "\n")
			for _, line := range lines {
				if strings.ReplaceAll(line, " ", "") == "" {
					continue
				}
				line = strings.TrimPrefix(line, "data: ")

				if line == "[DONE]" {
					continue
				}
				responseChunk := types.ResponseChunk{}
				if err := responseChunk.Unmarshal([]byte(line)); err != nil {
					log.Printf("[-] Error: %s\nrequest: %s\nresponse: %s\n", err, req, resp)
					return
				}
				if modelName == "" {
					modelName = responseChunk.Model
				}
				for choice := range responseChunk.Choices {
					respConcat[choice].WriteString(responseChunk.Choices[choice].Delta.Content)
				}
			}
		}
		for i := range respConcat {
			respStr[i] = respConcat[i].String()
		}
	} else {
		// If len(resp) == 1, the resp is not a 'stream'
		response := types.Response{}
		if err := response.Unmarshal([]byte(resp[0])); err != nil {
			log.Printf("[-] Error: %s\nrequest: %s\nresponse: %s\n", err, req, resp)
			return
		}
		modelName = response.Model
		for choice := range response.Choices {
			respStr[choice] = response.Choices[choice].Message.Content
		}
	}
	if modelName != "" {
		reqStruct.Model = modelName
	}
	trace := types.ConvertReqResp2Trace(reqStruct, respStr)
	traceStr, err := trace.Marshal()
	if err != nil {
		log.Printf("[-] Error: %s\nrequest: %s\nresponse: %s\n", err, req, resp)
		return
	}

	j.lock.Lock()
	defer j.lock.Unlock()

	date := time.Now().Format("2006-01-02")
	j.currentDay = date

	filePath := path.Join(j.localFolderPath, date+".jsonl")
	f, err := os.OpenFile(filePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0664)
	if err != nil {
		panic(err)
	}
	defer f.Close()
	// append the trace to the file
	f.WriteString(string(traceStr) + "\n")
}
