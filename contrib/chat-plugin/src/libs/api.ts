import ky, { Options } from "ky";
import { Job, useChatStore } from "./state";
import { toast } from "sonner";

const API_BASE_URL = window.location.origin;
const TARGET_JOB_TAG = "model-serving";

export const api = {
  post: async (path: string, key: string | null = null, options: Options = {}) => {
    if (key) {
      options.headers = {
        ...options.headers,
        Authorization: `Bearer ${key}`,
      };
    }
    if (!path.startsWith("http")) {
      // If the path is relative, prepend the API base URL
      path = `${API_BASE_URL}/${path}`;
    }
    const response = await ky.post(path, {
      ...options,
      timeout: options.timeout !== undefined ? options.timeout : false, // disables timeout by default
    }).json();
    return response;
  },

  postStream: async (path: string, key: string | null = null, options: Options = {}) => {
    if (key) {
      options.headers = {
        ...options.headers,
        Authorization: `Bearer ${key}`,
      };
    }
    if (!path.startsWith("http")) {
      // If the path is relative, prepend the API base URL
      path = `${API_BASE_URL}/${path}`;
    }
    const response = await ky.post(path, {
      ...options,
      timeout: options.timeout !== undefined ? options.timeout : false, // disables timeout by default
    });
    return response;
  },

  postStream: async (path: string, key: string | null = null, options: Options = {}) => {
    if (key) {
      options.headers = {
        ...options.headers,
        Authorization: `Bearer ${key}`,
      };
    }
    if (!path.startsWith("http")) {
      // If the path is relative, prepend the API base URL
      path = `${API_BASE_URL}/${path}`;
    }
    const response = await ky.post(path, {
      ...options,
      timeout: options.timeout !== undefined ? options.timeout : false, // disables timeout by default
    });
    return response;
  },

  // You can also add other methods like GET, PUT, DELETE, etc.
  get: async (path: string, key: string | null = null, options: Options = {}) => {
    if (key) {
      options.headers = {
        ...options.headers,
        Authorization: `Bearer ${key}`,
      };
    }
    if (!path.startsWith("http")) {
      // If the path is relative, prepend the API base URL
      path = `${API_BASE_URL}/${path}`;
    }
    const response = await ky.get(path, {
      ...options,
      timeout: options.timeout !== undefined ? options.timeout : false, // disables timeout by default
    }).json();
    return response;
  },

};

export async function fetchJobList(): Promise<void> {
  const restServerPath = useChatStore.getState().restServerPath;
  const restServerToken = useChatStore.getState().restServerToken;

  const getJobsUrl = `${restServerPath}/api/v2/jobs?state=RUNNING`;
  try {
    const data: any = await api.get(getJobsUrl, restServerToken);
    const jobs = (data as { debugId: string, name: string, username: string, state: string }[])
      .filter(job => job.name.includes(TARGET_JOB_TAG))
      .map(job => ({
        id: job.debugId,
        name: job.name,
        username: job.username,
        status: job.state,
        ip: "",
        port: 0,
      } as Job));

    const jobsWithDetails = await Promise.all(jobs.map(async job => {
      const jobDetailsUrl = `${restServerPath}/api/v2/jobs/${job.username}~${job.name}`;
      try {
        const jobInfo: any = await api.get(jobDetailsUrl, restServerToken);
        const details = jobInfo as { taskRoles: { [key: string]: { taskStatuses: [{ containerIp: string, containerPorts: { http: string } }] } } };
        if (!details || !details.taskRoles) {
          console.warn(`No task roles found for job ${job.name}`);
          return null;
        }
        const taskStatuses = Object.values(details.taskRoles)[0].taskStatuses;
        if (!taskStatuses) {
          console.warn(`No task statuses found for job ${job.name}`);
          return null;
        }
        job.ip = taskStatuses[0].containerIp;
        job.port = parseInt(taskStatuses[0].containerPorts.http);
        return job;
      } catch (error) {
        console.warn(`Failed to fetch details for job ${job.name}:`, error);
        return null;
      }
    }));

    const filteredJobs = jobsWithDetails.filter((job): job is Job => job !== null);
    useChatStore.getState().setAllJobs(filteredJobs);
    console.log("Fetched job list:", filteredJobs);
  } catch (error) {
    console.error("Failed to fetch job list:", error);
    useChatStore.getState().setAllJobs([]);
  }
}

export async function fetchModelsInCurrentJob(): Promise<string[]> {
  const currentJob = useChatStore.getState().currentJob;
  if (!currentJob) {
    console.warn("No current job selected");
    return [];
  }

  const jobServerPath = useChatStore.getState().jobServerPath;
  const jobServerToken = useChatStore.getState().jobServerToken;

  const modelsUrl = `${jobServerPath}/${currentJob.ip}:${currentJob.port}/v1/models`;
  try {
    const data: any = await api.get(modelsUrl, jobServerToken);
    const models = data as { data: [{ id: string }] };
    if (!models || !models.data) {
      console.warn(`No models found for job ${currentJob.name}`);
      useChatStore.getState().setAllModelsInCurrentJob([]);
      return [];
    }
    const modelList = models.data.map((model: { id: string }) => model.id);
    useChatStore.getState().setAllModelsInCurrentJob(modelList);
    return modelList;
  } catch (error) {
    console.error("Failed to fetch models in current job:", error);
    useChatStore.getState().setAllModelsInCurrentJob([]);
    return [];
  }
}

export async function chatRequest(abortSignal?: AbortSignal) {
  const currentJob = useChatStore.getState().currentJob;
  if (!currentJob) {
    console.warn("No current job selected");
    return;
  }

  const jobServerPath = useChatStore.getState().jobServerPath;
  const jobServerToken = useChatStore.getState().jobServerToken;
  const currentModel = useChatStore.getState().currentModel;
  const chatMsgs = useChatStore.getState().chatMsgs;

  const modelsUrl = `${jobServerPath}/${currentJob.ip}:${currentJob.port}/v1/chat/completions`;
  const data = {
    model: currentModel,
    messages: chatMsgs.filter(
      (msg) => msg.role === "user" || msg.role === "assistant"
    ).map((msg) => ({
      role: msg.role,
      content: msg.message,
    })),
  };
  try {
    const response: any = await api.post(modelsUrl, jobServerToken, {
      json: data,
      signal: abortSignal,
    });
    const respMessages = response.choices.map((choice: any) => choice.message.content);
    if (respMessages.length === 0) {
      console.warn("No response messages received from chat request");
      return;
    }

    // Return the response message to be added by the component
    return {
      role: "assistant",
      message: respMessages[0],
      timestamp: new Date(),
    };
  }
  catch (error: any) {
    if (error.name === 'AbortError') {
      return null;
    }
    toast.error("Failed to send chat request:" + error);
    return null;
  }
}

export async function chatStreamRequest(abortSignal?: AbortSignal) {
  const currentJob = useChatStore.getState().currentJob;
  if (!currentJob) {
    console.warn("No current job selected");
    return;
  }

  const jobServerPath = useChatStore.getState().jobServerPath;
  const jobServerToken = useChatStore.getState().jobServerToken;
  const currentModel = useChatStore.getState().currentModel;
  const chatMsgs = useChatStore.getState().chatMsgs;

  const modelsUrl = `${jobServerPath}/${currentJob.ip}:${currentJob.port}/v1/chat/completions`;
  const data = {
    model: currentModel,
    stream: true,
    messages: chatMsgs.filter(
      (msg) => msg.role === "user" || msg.role === "assistant"
    ).map((msg) => ({
      role: msg.role,
      content: msg.message,
    })),
  };

  let newMsg = {
    role: "assistant" as const,
    message: "",
    timestamp: new Date(),
    reasoning: "",
  };
  // Add a new message to the chat store to show loading state
  useChatStore.getState().addChatMessage(newMsg);

  try {
    const response = await api.postStream(modelsUrl, jobServerToken, {
      json: data,
      signal: abortSignal,
      timeout: false, // Disable timeout for streaming
    });

    // Process the stream response
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const { value, done } = await reader.read();

        if (done) break;

        // Decode the chunk
        buffer += decoder.decode(value, { stream: true });

        // Process complete events from buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (trimmedLine === "") continue;

          // SSE format: "data: {json}"
          if (trimmedLine.startsWith("data: ")) {
            const data = trimmedLine.slice(6);
            // Check for stream termination
            if (data === "[DONE]") {
              console.log("Stream completed");
              break;
            }

            try {
              const parsed = JSON.parse(data);

              // Handle different response formats (e.g., chat completions vs completions)
              const contentDelta = parsed.choices?.[0]?.delta?.content ||
                parsed.choices?.[0]?.text ||
                "";
              const reasonDelta = parsed.choices?.[0]?.delta?.reasoning_content || "";

              if (contentDelta) {
                if (newMsg.message.length === 0) {
                  contentDelta.trim();
                }
                newMsg.message += contentDelta;
              }
              if (reasonDelta) {
                newMsg.reasoning += reasonDelta;
              }
              if (contentDelta || reasonDelta) {
                // Update the last message in the chat store
                useChatStore.getState().updateLastChatMessage(newMsg);
              }
            } catch (e) {
              toast.error("Failed to parse SSE data:" + e + " \nLine:" + data);
              // Continue processing other lines
            }
          } else if (trimmedLine.startsWith("event:")) {
            // Handle named events if the API uses them
            console.log("SSE event:", trimmedLine);
          }
        }
      }
    } catch (error) {
      console.error("Stream reading error:" + error);
      throw error;
    } finally {
      // Ensure reader is released
      reader.releaseLock();
    }

    // Process any remaining data in buffer
    if (buffer.trim()) {
      console.warn("Incomplete data in buffer:", buffer);
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      return null;
    }
    toast.error("Failed to send chat request:" + error);
    return null;
  }
}


// Store the abort controller at module level
export let currentAbortController: AbortController | null = null;

export function createChatAbortController() {
  // Cancel any existing request
  if (currentAbortController) {
    currentAbortController.abort();
  }
  currentAbortController = new AbortController();
  return currentAbortController;
}

export async function stopChatRequest() {
  if (currentAbortController) {
    currentAbortController.abort();
    currentAbortController = null;
    toast.info("Chat request stopped");
  }
}