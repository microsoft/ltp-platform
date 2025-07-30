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