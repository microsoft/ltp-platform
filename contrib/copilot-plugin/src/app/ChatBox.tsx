"use client";

import { useState } from "react";
import { Loader2, SendHorizonal } from "lucide-react";
import { toast } from "sonner";
import { useChatStore } from "../libs/state";

export default function ChatBox() {
  const [prompt, setPrompt] = useState<string>("");
  const [loading, setLoading] = useState(false);

  // Get user information from the chat store
  const { paiuser, restServerToken, jobServerToken, currentJob, currentConversationId } = useChatStore();
  
  // Values needed by Lucia Agent API Server
  const TRACE_ID = 'cafe66d8-f37b-42b4-b765-bca9b1f09c2b';
  const REMOTE_SERVER_URL = `/copilot/api/operation`;

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
    try {
      const payload = {
        async_: false,
        stream: false,
        data: {
          user: prompt,
          userInfo: {
            paiuser: paiuser,
            username: paiuser,
            restToken: restServerToken,
            jobToken: jobServerToken,
            currentJob: null // currentJob ? { id: currentJob.id, name: currentJob.name, username: currentJob.username, status: currentJob.status, ip: currentJob.ip, port: currentJob.port } : null
          },
          messageInfo: {
            userId: paiuser,
            convId: currentConversationId,
            turnId: Math.random().toString(36).substring(2, 10), // first 8 characters
            timestamp: Math.floor(Date.now()),
            timestampUnit: "ms",
            type: "question",
          }
        }
      };
      const response = await fetch(REMOTE_SERVER_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Lucia-TraceId": TRACE_ID
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("Remote server error");
      const data = await response.json();
      useChatStore.getState().addChat({
        role: "assistant",
        message: data?.data?.answer ?? "No answer found",
        timestamp: new Date(),
        messageInfo: data?.data?.message_info, // Store the message_info from response
      });
    } catch (err) {
      toast.error("Failed to get response from remote server");
    }
    setLoading(false);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!loading) {
        makeChatRequest(new Event('submit') as unknown as React.FormEvent<HTMLFormElement>);
      }
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <form onSubmit={makeChatRequest} className="flex flex-col gap-2">
        <div className="relative flex-1 text-base">
          <div className="mr-10">
            <textarea
              value={prompt}
              className="w-full p-2 mr-10 border border-gray-300 rounded-md shadow-sm text-base resize-none"
              placeholder={"Your prompt..."}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
            />
          </div>
          <div className="absolute inset-y-0 right-1 flex items-center justify-center h-full w-8">
            <button type="submit" disabled={loading} className="p-2 rounded-full bg-indigo-500 text-white hover:bg-indigo-600 disabled:bg-gray-300">
              {loading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <SendHorizonal size={20} strokeWidth={1.5} />
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}