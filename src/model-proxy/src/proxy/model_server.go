// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

package proxy

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"
)

// target job tag to identify model serving jobs
const TARGET_JOB_TAG = "model-serving"

// REST server and Job server path segments in the URL
const REST_SERVER_PATH = "rest-server"
const JOB_SERVER_PATH = "job-server"

var httpClient = &http.Client{Timeout: 120 * time.Second}

// ListModelServingJobs returns a list of model serving jobs with the given request
func ListModelServingJobs(restServerUrl string, restServerToken string) ([]string, error) {
	url := fmt.Sprintf("%s/api/v2/jobs?state=RUNNING", restServerUrl)

	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	restServerToken = strings.TrimPrefix(restServerToken, "Bearer ")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", restServerToken))

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
		return nil, fmt.Errorf("failed to read jobs response: %w", err)
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
		if j.Name == "" {
			continue
		}
		if strings.Contains(j.Name, TARGET_JOB_TAG) {
			// Use the same identifier as TS: username~name
			jobId := fmt.Sprintf("%s~%s", j.Username, j.Name)
			result = append(result, jobId)
		}
	}

	return result, nil
}

// return the job server url
func GetJobServerUrl(restServerUrl string, restServerToken string, jobId string) (string, error) {
	if restServerUrl == "" {
		return "", fmt.Errorf("empty restServerUrl")
	}
	if jobId == "" {
		return "", fmt.Errorf("empty jobId")
	}

	// Ensure restServerUrl doesn't end with slash
	restServerUrl = strings.TrimRight(restServerUrl, "/")
	url := fmt.Sprintf("%s/api/v2/jobs/%s", restServerUrl, jobId)

	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}
	restServerToken = strings.TrimPrefix(restServerToken, "Bearer ")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", restServerToken))

	resp, err := httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to GET job details from %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("non-2xx response from %s: %d - %s", url, resp.StatusCode, string(body))
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read job details response: %w", err)
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

	jobServerPath := strings.Replace(restServerUrl, REST_SERVER_PATH, JOB_SERVER_PATH, 1)
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
		jobServerUrl := fmt.Sprintf("%s/%s:%s", jobServerPath, ts.ContainerIp, port)
		return jobServerUrl, nil
	}

	return "", fmt.Errorf("no taskStatuses found for job %s", jobId)
}

// return model names list
func listModels(jobServerUrl string, token string) ([]string, error) {
	if jobServerUrl == "" {
		return nil, fmt.Errorf("empty jobServerUrl")
	}
	// ensure no trailing slash
	jobServerUrl = strings.TrimRight(jobServerUrl, "/")
	url := fmt.Sprintf("%s/v1/models", jobServerUrl)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request for %s: %w", url, err)
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))

	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to GET models from %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("non-2xx response from %s: %d - %s", url, resp.StatusCode, string(body))
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read models response: %w", err)
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
func GetJobModelsMapping(req *http.Request, modelToken string) (map[string][]string, error) {
	mapping := make(map[string][]string)

	if req == nil || req.Host == "" {
		return mapping, fmt.Errorf("invalid request or empty host")
	}
	restBase := fmt.Sprintf("https://%s/rest-server", req.Host)

	restServerToken := req.Header.Get("Authorization")
	jobIDs, err := ListModelServingJobs(restBase, restServerToken)
	if err != nil {
		return mapping, fmt.Errorf("failed to list model serving jobs: %w", err)
	}

	for _, jobId := range jobIDs {
		jobServerUrl, err := GetJobServerUrl(restBase, restServerToken, jobId)
		if err != nil {
			// skip this job but continue with others
			log.Printf("[-] Error: failed to get job server URL for job %s: %s\n", jobId, err)
			continue
		}
		//
		models, err := listModels(jobServerUrl, modelToken)
		if err != nil {
			// skip if cannot list models
			log.Printf("[-] Error: failed to list models for job %s: %s\n", jobId, err)
			continue
		}
		for _, model := range models {
			// map model name -> [jobServerUrl]
			if _, ok := mapping[model]; !ok {
				mapping[model] = []string{}
			}
			mapping[model] = append(mapping[model], jobServerUrl)
		}
	}

	return mapping, nil
}
