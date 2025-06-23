"use client";

import { fetchJobList, fetchModelsInCurrentJob } from "../libs/api";
import { useEffect, useState } from "react";
import { Job, Status, useChatStore } from "../libs/state";
import { RefreshCw } from "lucide-react";


// Status color mapping
const statusColor = {
  online: "bg-green-500",
  offline: "bg-red-500",
  unknown: "bg-gray-500",
  loading: "bg-yellow-500",
};

// Status text mapping
const statusText = {
  online: "Online",
  offline: "Offline",
  unknown: "Unknown",
  loading: "Loading...",
};

export default function JobBar() {
  const [status, setStatus] = useState<Status>("offline");
  const {
    allJobs,
    currentJob,
    setCurrentJob,
    allModelsInCurrentJob,
    currentModel,
    setCurrentModel
  } = useChatStore();

  // Fetch job list on component mount and set up status polling
  // Loading states for better UI feedback
  const [isJobsLoading, setIsJobsLoading] = useState(false);
  const [isModelsLoading, setIsModelsLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  // Fetch job list with loading indicator
  const fetchJobs = async () => {
    setError(null);
    setIsJobsLoading(true);
    setStatus("loading");
    try {
      await fetchJobList();
      setStatus("unknown");
    } catch (err) {
      setError("Failed to fetch jobs. Please try again.");
      console.error(err);
    } finally {
      setIsJobsLoading(false);
    }
  };

  // Fetch models with loading indicator
  const fetchModels = async () => {
    if (!currentJob) return;
    setError(null);
    setIsModelsLoading(true);
    setStatus("loading");
    try {

      await fetchModelsInCurrentJob();
      await new Promise(res => setTimeout(res, 2500));
      // Use the latest models from the store after fetching
      const models = useChatStore.getState().allModelsInCurrentJob;
      if (models.length > 0) {
        setStatus("online");
      } else {
        setStatus("offline");
      }
    } catch (err) {
      setError("Failed to fetch models. Please try again.");
      console.error(err);
    } finally {
      setIsModelsLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs(); // Initial job list fetch

    const interval = setInterval(async () => {
    }, 500);

    return () => clearInterval(interval);
  }, []);

  // Fetch models when current job changes
  useEffect(() => {
    if (currentJob) {
      fetchModels();
    } else {
      // Clear models when no job is selected
      useChatStore.getState().setAllModelsInCurrentJob([]);
      if (currentModel) {
        // Clear current model selection when job changes
        setCurrentModel(null);
      }
      setStatus("unknown");
    }
  }, [currentJob]);

  // Handle job selection change
  const handleJobChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedJobId = e.target.value;
    const job = allJobs.find(job => job.id === selectedJobId) || null;
    setCurrentJob(job);
  };

  // Handle model selection change
  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedModel = e.target.value;
    setCurrentModel(selectedModel);
  };

  // Handle refresh button click
  const handleRefresh = async () => {
    await fetchJobs();
    if (currentJob) {
      await fetchModels();
    }
  };

  return (
    <div className="w-full h-full flex items-center justify-between p-2">
      <div className="flex items-center gap-2 text-gray-500">
        <div className={`w-3 h-3 rounded-full ${statusColor[status]}`} />
        <p>{statusText[status]}</p>
        {error && <p className="ml-4 text-sm text-red-500">{error}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* Job select */}
        <div className="flex items-center gap-2">
          <label htmlFor="job-select" className="block text-sm font-medium text-gray-700 mr-2">Serving Job:</label>
          <select
            id="job-select"
            className="block w-64 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2"
            value={currentJob?.id || ""}
            onChange={handleJobChange}
            disabled={isJobsLoading}
            size={1}
            style={{ minWidth: "16rem", maxWidth: "30rem" }}
          >
            <option value="">Select a job ({allJobs.length})</option>
            {allJobs.map((job) => (
              <option key={job.id} value={job.id} title={`${job.name} (${job.username})`}>{job.name}</option>
            ))}
          </select>
        </div>

        {/* Model select */}
        <div className="flex items-center gap-2">
          <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mr-2">Models:</label>
          <select
            id="model-select"
            className="block w-48 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            value={currentModel || ""}
            onChange={handleModelChange}
            disabled={!currentJob || allModelsInCurrentJob.length === 0 || isModelsLoading}
          >
            <option value="">Select a model ({allModelsInCurrentJob.length})</option>
            {allModelsInCurrentJob.map((model) => (
              <option key={model} value={model} title={model}>{model}</option>
            ))}
          </select>
        </div>

        {/* Refresh button */}
        <button
          onClick={handleRefresh}
          className="inline-flex items-center p-1.5 border border-transparent rounded-full shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          title="Refresh job and model lists"
          disabled={isJobsLoading || isModelsLoading}
        >
          <RefreshCw className={`h-5 w-5 ${(isJobsLoading || isModelsLoading) ? "animate-spin" : ""}`} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
