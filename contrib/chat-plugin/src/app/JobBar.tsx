// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

"use client";

import { fetchAllModels } from "../libs/api";
import { useEffect, useState } from "react";
import { Status, useChatStore } from "../libs/state";
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
    allModels,
    currentModel,
    setCurrentModel
  } = useChatStore();

  // Fetch job list on component mount and set up status polling
  // Loading states for better UI feedback
  const [isModelsLoading, setIsModelsLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  // Fetch models with loading indicator
  const fetchModels = async () => {
    setError(null);
    setIsModelsLoading(true);
    setStatus("loading");
    try {

      await fetchAllModels();
      await new Promise(res => setTimeout(res, 2500));
      // Use the latest models from the store after fetching
      const models = useChatStore.getState().allModels;
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
    fetchModels(); 

    const interval = setInterval(async () => {
    }, 500);

    return () => clearInterval(interval);
  }, []);


  // Handle model selection change
  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedModel = e.target.value;
    setCurrentModel(selectedModel);
  };

  return (
    <div className="w-full h-full flex items-center justify-between p-2">
      <div className="flex items-center gap-2 text-gray-500">
        <div className={`w-3 h-3 rounded-full ${statusColor[status]}`} />
        <p>{statusText[status]}</p>
        {error && <p className="ml-4 text-sm text-red-500">{error}</p>}
      </div>

      <div className="flex items-center gap-4">

        {/* Model select */}
        <div className="flex items-center gap-2">
          <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mr-2">Models:</label>
          <select
            id="model-select"
            className="block w-48 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            value={currentModel || ""}
            onChange={handleModelChange}
            disabled={allModels.length === 0 || isModelsLoading}
          >
            <option value="">Select a model ({allModels.length})</option>
            {allModels.map((model) => (
              <option key={model} value={model} title={model}>{model}</option>
            ))}
          </select>
        </div>

        {/* Refresh button */}
        <button
          onClick={fetchModels}
          className="inline-flex items-center p-1.5 border border-transparent rounded-full shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          title="Refresh model lists"
          disabled={isModelsLoading}
        >
          <RefreshCw className={`h-5 w-5 ${isModelsLoading ? "animate-spin" : ""}`} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
