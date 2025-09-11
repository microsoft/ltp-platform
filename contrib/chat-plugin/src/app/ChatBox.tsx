// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

"use client";

import { useState } from "react";
import { Loader2, SendHorizonal, CircleStop } from "lucide-react";
import { toast } from "sonner";

import {
  chatRequest,
  currentAbortController,
  createChatAbortController,
  chatStreamRequest
} from "../libs/api";
import { useChatStore } from "../libs/state";


export default function ChatBox() {
  const [prompt, setPrompt] = useState<string>(
    ""
  );
  const [loading, setLoading] = useState(false);

  const currentModel = useChatStore((state) => state.currentModel);


  const makeChatRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() === "") {
      toast.info("Prompt cannot be empty");
      return;
    }
    useChatStore.getState().addChatMessage({
      role: "user",
      message: prompt,
      timestamp: new Date(),
    });
    setPrompt("");
    setLoading(true);

    createChatAbortController();
    await chatStreamRequest(currentAbortController?.signal);
    setLoading(false);
  }

  const stopChatRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (currentAbortController) {
      currentAbortController.abort();
      toast.info("Chat request stopped");
    } else {
      toast.info("No chat request to stop.");
    }
    setLoading(false);
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!loading && currentModel != null) {
        makeChatRequest(new Event('submit') as unknown as React.FormEvent<HTMLFormElement>);
      } else {
        toast.info("Please select a model to chat with.");
      }
    }
  };


  return (
    <div className="flex flex-col gap-2">
      {/* {loading ?
        <div className="text-yellow-400 flex gap-2 items-center">
          <GridLoader width="18" height="18" fill="currentColor" />
          <span className="text-sm font-medium">...</span>
        </div> :
        null
      } */}

      <form onSubmit={makeChatRequest} className="flex flex-col gap-2">
        <div className="relative flex-1 text-base">
          <div className="mr-20">
            <textarea
              value={prompt}
              className="w-full p-2 mr-20 border border-gray-300 rounded-md shadow-sm text-base resize-none"
              placeholder={currentModel ? "Your prompt..." : "Please select a model to chat with."}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
            // rows={Math.min(8, Math.max(1, Math.ceil(prompt.length/50) ))} // Adjust height based on content
            />
          </div>

          <div className="absolute inset-y-0 right-1 flex items-center justify-center h-full w-16">
            {currentModel ? (
              !loading ? (
                <button type="submit" className="p-2 rounded-full bg-indigo-500 text-white hover:bg-indigo-600 disabled:bg-gray-300">
                  <SendHorizonal size={20} strokeWidth={1.5} />
                </button>
              ) : (
                <button type="button" onClick={stopChatRequest} className="ml-2 p-1 rounded-full bg-red-500 text-white hover:bg-red-600 flex items-center gap-1">
                  <Loader2 className="animate-spin" size={30} strokeWidth={1.5} />
                  <CircleStop size={30} strokeWidth={1.5} />
                </button>
              )
            ) : (
              <button type="button" disabled className="p-2 rounded-full bg-gray-300 text-gray-500 hover:bg-gray-400">
                <SendHorizonal size={20} strokeWidth={1.5} className="text-gray-400" />
              </button>
            )}
          </div>
        </div>
      </form>
    </div>

  );
}