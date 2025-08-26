package proxy

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"sort"
	"strconv"
	"strings"
	"time"

	"modelproxy/trace"
	"modelproxy/types"
)

// hookWriter is a wrapper of http.ResponseWriter, which can get the response body and status code, and does not dis
type hookWriter struct {
	http.ResponseWriter
	status int
	body   []string
}

// Implement the Write method of http.ResponseWriter. It can record the response body
func (w *hookWriter) Write(data []byte) (int, error) {
	w.body = append(w.body, string(data))
	// Disable nginx buffering (do this before first write)
	if len(w.body) == 1 { // First write
		w.Header().Set("X-Accel-Buffering", "no")
	}

	n, err := w.ResponseWriter.Write(data)
	// Flush the response writer immediately if it implements http.Flusher
	if flusher, ok := w.ResponseWriter.(http.Flusher); ok {
		flusher.Flush()
	}
	return n, err
}

// Implement the WriteHeader method of http.ResponseWriter. It can record the status code
func (w *hookWriter) WriteHeader(statusCode int) {
	w.status = statusCode
	w.ResponseWriter.WriteHeader(statusCode)
}

// ProxyHandler is the key struct for proxy server
type ProxyHandler struct {
	authenticator *RestServerAuthenticator
	port          int
	maxRetries    int
	// traceRelatedKeys is the keys that will be logged in trace, but will be filtered in the api request
	traceRelatedKeys map[string]struct{}
}

// NewProxyHandler create a new ProxyHandler according to the config
func NewProxyHandler(config *types.Config) *ProxyHandler {
	traceRelatedKeys := make(map[string]struct{})
	for _, key := range config.Log.TraceRelatedKeys {
		traceRelatedKeys[key] = struct{}{}
	}

	return &ProxyHandler{
		authenticator:    NewRestServerAuthenticator(nil, config.Server.ModelKey),
		port:             config.Server.Port,
		maxRetries:       config.Server.MaxRetries,
		traceRelatedKeys: traceRelatedKeys,
	}
}

// ReverseProxyHandler act as a reverse proxy, it will redirect the request to the destination website and return the response
func (ph *ProxyHandler) ReverseProxyHandler(w http.ResponseWriter, r *http.Request) (string, []string, bool) {
	// handle /v1/models
	if r.URL.Path == "/v1/models" {
		model2Url, err := GetJobModelsMapping(r, ph.authenticator.modelKey)
		if err != nil {
			log.Printf("[-] Error: failed to get models mapping: %v\n", err)
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return "", nil, false
		}
		// Update the ph.authenticator
		token := r.Header.Get("Authorization")
		token = strings.Replace(token, "Bearer ", "", 1)
		ph.authenticator.UpdateTokenModels(token, model2Url)

		// convert models list to OpenAI style list and write it to w
		ids := make([]string, 0, len(model2Url))
		for id := range model2Url {
			ids = append(ids, id)
		}
		sort.Strings(ids)

		list := map[string]interface{}{
			"object": "list",
			"data":   make([]map[string]interface{}, 0, len(ids)),
		}
		for _, id := range ids {
			item := map[string]interface{}{
				"id":     id,
				"object": "model",
				// intentionally not including created or owned_by
			}
			list["data"] = append(list["data"].([]map[string]interface{}), item)
		}

		out, err := json.Marshal(list)
		if err != nil {
			log.Printf("[-] Error: failed to marshal models list: %v\n", err)
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return "", nil, false
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if _, err := w.Write(out); err != nil {
			log.Printf("[-] Error: failed to write response: %v\n", err)
		}
		// We've handled the response, do not continue proxying this request
		return "", nil, false
	}
	log.Printf("[*] receive a request from %s\n", r.RemoteAddr)

	// filter the request body and check whether the request should be traced
	rawReqBody, newReqBody, data, shouldTraced := ph.requestBodyFilter(r)

	// check the key of the request
	ok, modelUrls := ph.authenticator.AuthenticateReq(r, data)

	if !ok {
		log.Printf("[-] Error: unauthorized request from %s\n", r.RemoteAddr)
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return "", nil, false
	}

	// get the url poller to generate and poll the destination url
	urlPoller := NewUrlPollerWithKey(r.URL.String(), modelUrls, ph.authenticator.modelKey)
	if urlPoller == nil {
		log.Printf("[-] Error: cannot get the url poller: \n\trawReqBody: %s\n\tURL: %s\n", rawReqBody, r.URL.String())
		proxy := &httputil.ReverseProxy{Director: func(req *http.Request) {}}
		proxy.ServeHTTP(w, r)
		return rawReqBody, nil, false
	}

	responseWriter := &hookWriter{ResponseWriter: w, body: make([]string, 0, 1)}
	director := func(req *http.Request) {
		// get the new destination url and the related key
		newUrl, curkey := urlPoller.GetUrlAndKey()
		log.Printf("[*] redirect to %s\n", newUrl.String())

		if newUrl == nil {
			log.Println("[-] Error: cannot get the destinaton url")
			return
		}
		req.Header.Set("Content-Length", strconv.Itoa(len(newReqBody)))
		// ket setting for openai spec endpoints
		req.Header.Set("Authorization", "Bearer "+curkey)
		// ket setting for azure spec endpoints
		req.Header.Set("Api-key", curkey)

		req.Host = newUrl.Host
		req.URL = newUrl

		// the request body has been read out, so we need to reset the request body
		req.Body = io.NopCloser(bytes.NewBufferString(newReqBody))
		req.ContentLength = int64(len(newReqBody))
	}

	// create the reverse proxy
	proxy := &httputil.ReverseProxy{Director: director}
	retries := 0
	modifyResponse := func(resp *http.Response) error {
		// Handle error response here
		// If the response is an error response, we will retry the request to another destination url
		if resp.StatusCode >= 400 && retries < ph.maxRetries {
			log.Printf("[-] receive error response %s\n", resp.Status)
			retries++
			time.Sleep(100 * time.Millisecond)
			// clear the response body and status code in the responseWriter
			responseWriter.body = make([]string, 0, 1)
			proxy.ServeHTTP(responseWriter, r)
			return errors.New("retry")
		} else {
			return nil
		}

	}
	proxy.ModifyResponse = modifyResponse
	proxy.ErrorHandler = func(http.ResponseWriter, *http.Request, error) {}
	proxy.ServeHTTP(responseWriter, r)

	log.Printf("[*] receive the destination website response\n")

	return rawReqBody, responseWriter.body, shouldTraced
}

// requestBodyFilter filter the request body, return the original request body, the filtered request body and whether the request should be traced (only trace chat request)
func (ph *ProxyHandler) requestBodyFilter(r *http.Request) (string, string, map[string]interface{}, bool) {
	reqBody, _ := io.ReadAll(r.Body)
	// check whether the request is a completion request
	if !strings.Contains(r.URL.Path, "completions") {
		log.Printf("[-] Request from %s is not a completion request\n", r.URL.Path)
		return string(reqBody), string(reqBody), nil, false
	}

	var data map[string]interface{}

	// parse request body
	if err := json.Unmarshal(reqBody, &data); err != nil {
		log.Printf("[-] Filter Error: %s\n", err)
		return string(reqBody), string(reqBody), nil, false
	}
	for k := range data {
		if _, ok := ph.traceRelatedKeys[k]; ok {
			delete(data, k)
		}
	}
	filtedBody, _ := json.Marshal(data)

	// check whether the request is a chat request
	_, ok := data["messages"]
	return string(reqBody), string(filtedBody), data, ok
}

// ProxyHandlerWithLogger return a http.HandlerFunc, which can be used to start the proxy server and call the logger.Record method
func (ph *ProxyHandler) ProxyHandlerWithLogger(logger trace.TraceLogger) http.HandlerFunc {
	res := func(w http.ResponseWriter, r *http.Request) {
		log.Println("-----------------------------------------------")
		req, resp, shouldTraced := ph.ReverseProxyHandler(w, r)
		if shouldTraced {
			log.Printf("[*] Debug: response: %s\n", resp)
			logger.Record(req, resp)
		}
	}
	return res
}

// StartProxy start the proxy server
func (ph *ProxyHandler) StartProxy(logger trace.TraceLogger) {
	log.Printf("[*] Start proxy at port \n")
	handler := ph.ProxyHandlerWithLogger(logger)
	if err := http.ListenAndServe(":"+strconv.Itoa(ph.port), handler); err != nil {
		log.Fatal("[*] Server error: " + err.Error())
	}
}
