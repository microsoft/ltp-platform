// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

package proxy

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"modelproxy/types"
)

// Required job configuration parameters for inference jobs
var FORCED_PARAMETERS = []string{
	"INTERNAL_SERVER_IP",
	"INTERNAL_SERVER_PORT",
	"API_KEY",
}

var httpClient = &http.Client{Timeout: 120 * time.Second}

func GETRequest(url string, token string) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	token = strings.TrimPrefix(token, "Bearer ")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))

	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to GET jobs from %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("non-2xx response from %s: %d - %s", url, resp.StatusCode, string(body))
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body of %s: %w", url, err)
	}

	return body, nil
}

// ListInferenceJobs returns a list of model serving jobs with the given request
func ListInferenceJobs(restServerUrl string, restServerToken string) ([]string, error) {
	url := fmt.Sprintf("%s/api/v2/jobs?state=RUNNING&jobType=inference", restServerUrl)

	body, err := GETRequest(url, restServerToken)
	if err != nil {
		return nil, fmt.Errorf("failed to GET jobs from %s: %w", url, err)
	}

	// Expected: array of jobs with fields { name, username }
	var jobs []struct {
		Name     string `json:"name"`
		Username string `json:"username"`
	}
	if err := json.Unmarshal(body, &jobs); err != nil {
		// Try to provide a helpful error if the shape is unexpected
		return nil, fmt.Errorf("failed to parse jobs JSON: %w", err)
	}

	result := make([]string, 0, len(jobs))
	for _, j := range jobs {
		jobId := fmt.Sprintf("%s~%s", j.Username, j.Name)
		result = append(result, jobId)
	}

	return result, nil
}

// get the forced parameters of inference job: INTERNAL_SERVER_IP, INTERNAL_SERVER_PORT, API_KEY
func GetJobParameters(url string, restServerToken string) (string, string, string, error) {
	body, err := GETRequest(url, restServerToken)
	if err != nil {
		return "", "", "", fmt.Errorf("failed to GET job config from %s: %w", url, err)
	}

	var jobConfig struct {
		Parameters map[string]string `json:"parameters"`
	}

	if err := json.Unmarshal(body, &jobConfig); err != nil {
		return "", "", "", fmt.Errorf("failed to parse job config JSON: %w", err)
	}

	for _, para := range FORCED_PARAMETERS {
		if _, ok := jobConfig.Parameters[para]; !ok {
			return "", "", "", fmt.Errorf("missing forced parameter %s in job config", para)
		}
	}
	return jobConfig.Parameters["INTERNAL_SERVER_IP"], jobConfig.Parameters["INTERNAL_SERVER_PORT"], jobConfig.Parameters["API_KEY"], nil
}

// return the job server url
func GetJobServerUrl(url string, restServerToken string, jobId string) (string, error) {

	body, err := GETRequest(url, restServerToken)
	if err != nil {
		return "", fmt.Errorf("failed to GET job details from %s: %w", url, err)
	}

	// Parse expected job details:
	// { taskRoles: { roleName: { taskStatuses: [ { containerIp: "...", containerPorts: { "http": "port" } } ] } } }
	var details struct {
		TaskRoles map[string]struct {
			TaskStatuses []struct {
				ContainerIp    string            `json:"containerIp"`
				ContainerPorts map[string]string `json:"containerPorts"`
			} `json:"taskStatuses"`
		} `json:"taskRoles"`
	}
	if err := json.Unmarshal(body, &details); err != nil {
		return "", fmt.Errorf("failed to parse job details JSON: %w", err)
	}

	if len(details.TaskRoles) == 0 {
		return "", fmt.Errorf("no taskRoles found for job %s", jobId)
	}

	// Pick first role, first taskStatus
	for _, role := range details.TaskRoles {
		if len(role.TaskStatuses) == 0 {
			continue
		}
		ts := role.TaskStatuses[0]
		if ts.ContainerIp == "" {
			return "", fmt.Errorf("no containerIp found for job %s", jobId)
		}
		// prefer http port
		port, ok := ts.ContainerPorts["http"]
		if !ok || port == "" {
			return "", fmt.Errorf("no http port found for job %s", jobId)
		}
		// return the internal url
		jobServerUrl := fmt.Sprintf("http://%s:%s", ts.ContainerIp, port)
		return jobServerUrl, nil
	}

	return "", fmt.Errorf("no taskStatuses found for job %s", jobId)
}

// return model names list
func listModels(jobServerUrl string, modelApiKey string) ([]string, error) {
	if jobServerUrl == "" {
		return nil, fmt.Errorf("empty jobServerUrl")
	}
	// ensure no trailing slash
	jobServerUrl = strings.TrimRight(jobServerUrl, "/")
	url := fmt.Sprintf("%s/v1/models", jobServerUrl)

	body, err := GETRequest(url, modelApiKey)
	if err != nil {
		return nil, fmt.Errorf("failed to list models from %s: %w", url, err)
	}

	// Try the expected shape: { data: [{ id: "model1" }, ...] }
	var wrapper struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &wrapper); err == nil && len(wrapper.Data) > 0 {
		result := make([]string, 0, len(wrapper.Data))
		for _, m := range wrapper.Data {
			if m.ID != "" {
				result = append(result, m.ID)
			}
		}
		return result, nil
	}

	// Fallback: maybe the endpoint returns an array of objects or strings
	var arr []map[string]interface{}
	if err := json.Unmarshal(body, &arr); err == nil && len(arr) > 0 {
		result := []string{}
		for _, item := range arr {
			if idv, ok := item["id"].(string); ok && idv != "" {
				result = append(result, idv)
				continue
			}
			if namev, ok := item["name"].(string); ok && namev != "" {
				result = append(result, namev)
				continue
			}
		}
		if len(result) > 0 {
			return result, nil
		}
	}

	// Fallback: maybe it's an array of strings
	var strArr []string
	if err := json.Unmarshal(body, &strArr); err == nil && len(strArr) > 0 {
		return strArr, nil
	}

	// No models found
	return nil, fmt.Errorf("no models found at %s", url)
}

// return JobURL => models
func ListJobModelsMapping(req *http.Request) (map[string][]*types.BaseSpec, error) {
	// modelName to job server url list
	modelJobMapping := make(map[string][]*types.BaseSpec)

	if req == nil || req.Host == "" {
		return modelJobMapping, fmt.Errorf("invalid request or empty host")
	}
	// get rest server base url from the os environment variable
	restServerUrl := os.Getenv("REST_SERVER_URI")
	if restServerUrl == "" {
		return modelJobMapping, fmt.Errorf("REST_SERVER_URI environment variable is not set")
	}
	// Ensure restServerUrl doesn't end with slash
	restServerUrl = strings.TrimRight(restServerUrl, "/")

	restServerToken := req.Header.Get("Authorization")
	jobIDs, err := ListInferenceJobs(restServerUrl, restServerToken)
	if err != nil {
		return modelJobMapping, fmt.Errorf("failed to list model serving jobs: %w", err)
	}

	// Channel to collect results
	type ModelEndpoint struct {
		modelName    string
		jobID        string
		modelService *types.BaseSpec
	}
	concurrency, err := strconv.Atoi(os.Getenv("FETCH_JOB_CONCURRENCY"))
	if err != nil {
		log.Printf("[-] Error: invalid FETCH_JOB_CONCURRENCY value: %s\n", err)
		concurrency = 10 // default value
	}
	allModelEndpoints := make(chan ModelEndpoint, concurrency) // Buffer for potential models

	// Use a wait group to run jobs in parallel
	var wg sync.WaitGroup

	// Limit concurrent goroutines to avoid overwhelming the server
	semaphore := make(chan struct{}, concurrency) // Allow up to `concurrency` concurrent goroutines

	for _, jobId := range jobIDs {
		if jobId == "" {
			continue
		}

		wg.Add(1)
		go func(jobId string) {
			defer wg.Done()

			// Acquire semaphore
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			jobStatusQueryUrl := fmt.Sprintf("%s/api/v2/jobs/%s", restServerUrl, jobId)
			jobServerUrl, err := GetJobServerUrl(jobStatusQueryUrl, restServerToken, jobId)
			if err != nil {
				// skip this job but continue with others
				log.Printf("[-] Error: failed to get job server URL for job %s: %s\n", jobId, err)
				return
			}
			jobConfigQueryUrl := fmt.Sprintf("%s/api/v2/jobs/%s/config", restServerUrl, jobId)
			_, _, apiKey, err := GetJobParameters(jobConfigQueryUrl, restServerToken)
			if err != nil {
				// skip this job but continue with others
				log.Printf("[-] Error: failed to get job parameters for job %s: %s\n", jobId, err)
				return
			}
			// list models from the job server
			models, err := listModels(jobServerUrl, apiKey)
			if err != nil {
				// skip if cannot list models
				log.Printf("[-] Error: failed to list models for job %s: %s\n", jobId, err)
				return
			}

			userName := strings.Split(jobId, "~")[0]
			jobName := strings.Split(jobId, "~")[1]
			// Send results to channel
			for _, model := range models {
				allModelEndpoints <- ModelEndpoint{
					modelName: model,
					modelService: &types.BaseSpec{
						URL:      jobServerUrl,
						Key:      apiKey,
						JobName:  jobName,
						UserName: userName,
					},
				}
			}
		}(jobId)
	}

	// Close the results channel when all goroutines are done
	go func() {
		wg.Wait()
		close(allModelEndpoints)
	}()

	// Collect results from channel
	for result := range allModelEndpoints {
		if _, ok := modelJobMapping[result.modelName]; !ok {
			modelJobMapping[result.modelName] = make([]*types.BaseSpec, 0)
		}
		modelJobMapping[result.modelName] = append(modelJobMapping[result.modelName], result.modelService)
		jobModelName := fmt.Sprintf("%s@%s", result.modelService.JobName, result.modelName)

		// Also map jobName@modelName to the model service which allows users to specify the job name in the model field
		if _, ok := modelJobMapping[jobModelName]; !ok {
			modelJobMapping[jobModelName] = make([]*types.BaseSpec, 0)
		}
		modelJobMapping[jobModelName] = append(modelJobMapping[jobModelName], result.modelService)
	}

	return modelJobMapping, nil
}
