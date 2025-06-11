"use client";

import { useState } from "react";
import { Loader2,  SendHorizonal } from "lucide-react";
import { toast } from "sonner";

import { chatRequest} from "../libs/api";
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
    useChatStore.getState().addChat({
      role: "user",
      message: prompt,
      timestamp: new Date(),
    });
    setPrompt("");
    setLoading(true);
    
    const newMsg = await chatRequest();
    if (!newMsg) {
      toast.error("Failed to get response from Model");
    }
    else {
      useChatStore.getState().addChat(newMsg);
    }
    setLoading(false);
  }      

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!loading && currentModel != null) {
        makeChatRequest(new Event('submit') as unknown as React.FormEvent<HTMLFormElement>);
      }else{
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
          <div className="mr-10">
            <textarea
              value={prompt}
              className="w-full p-2 mr-10 border border-gray-300 rounded-md shadow-sm text-base resize-none"
              placeholder={currentModel? "Your prompt..." : "Please select a model to chat with."}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              // rows={Math.min(8, Math.max(1, Math.ceil(prompt.length/50) ))} // Adjust height based on content
            />
          </div>

            <div className="absolute inset-y-0 right-1 flex items-center justify-center h-full w-8">
            <button type="submit" disabled={loading } className="p-2 rounded-full bg-indigo-500 text-white hover:bg-indigo-600 disabled:bg-gray-300">
            {currentModel ? (
              loading ? (
              <Loader2 className="animate-spin" />
              ) : (
              <SendHorizonal size={20} strokeWidth={1.5} />
              )
            ) : (
              <SendHorizonal size={20} strokeWidth={1.5} className="text-gray-400" />
            )}
              
            </button>
            </div>
        </div>
      </form>
    </div>

  );
}