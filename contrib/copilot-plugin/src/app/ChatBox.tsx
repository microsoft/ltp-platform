// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

"use client";

import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
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
  // Use local backend when running the dev server (npm start),
  // and use the relative path for production builds (npm run build).
  const REMOTE_SERVER_URL = process.env.NODE_ENV === 'development'
    ? 'http://127.0.0.1:60000/copilot/api/stream'
    : '/copilot/api/stream';

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
      // create a stable turnId and include it in the payload so server will echo/use it
      const turnId = uuidv4();
      const messageInfo = {
        userId: paiuser,
        convId: currentConversationId,
        turnId: turnId,
        timestamp: Math.floor(Date.now()),
        timestampUnit: "ms",
        type: "question",
      };

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
            currentJob: null
          },
          messageInfo: messageInfo
        }
      };
      
      // Create assistant placeholder and attach the same messageInfo (turnId) so feedback maps to this response
      useChatStore.getState().addChat({ role: "assistant", message: "", timestamp: new Date(), messageInfo });
      const response = await fetch(REMOTE_SERVER_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Lucia-TraceId": TRACE_ID
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("Remote server error");

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body for streaming');
      const decoder = new TextDecoder();
      // Buffer incoming bytes and parse SSE-style messages (separated by '\n\n')
      let buffer = '';
      while (true) {
        const { value, done: readerDone } = await reader.read();
        if (value) {
          buffer += decoder.decode(value, { stream: true });
        }

        // Process all complete SSE messages in buffer
        let sepIndex;
        while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
          const rawEvent = buffer.slice(0, sepIndex);
          const newBuffer = buffer.slice(sepIndex + 2);
          
          // Safety check: ensure buffer is actually being modified to prevent infinite loops
          if (newBuffer.length >= buffer.length) {
            console.warn('Buffer not decreasing, breaking to prevent infinite loop');
            break;
          }
          buffer = newBuffer;

          // Extract data: lines and join with newline to preserve original formatting
          const lines = rawEvent.split(/\n/);
          const dataParts: string[] = [];
          let isDoneEvent = false;
          for (const line of lines) {
            if (line.startsWith('data:')) {
              dataParts.push(line.slice(5));
            } else if (line.startsWith('event:')) {
              const ev = line.slice(6).trim();
              if (ev === 'done') isDoneEvent = true;
            }
          }

          if (dataParts.length > 0) {
            const dataStr = dataParts.join('\n');
            // If the server sent a JSON 'append' event, append to last assistant message
            let handled = false;
            const trimmed = dataStr.trim();
            if (trimmed.startsWith('{')) {
              try {
                const parsed = JSON.parse(trimmed);
                if (parsed && parsed.type === 'append' && typeof parsed.text === 'string') {
                  useChatStore.getState().appendToLastAssistant(parsed.text);
                  handled = true;
                }
                else if (parsed && parsed.type === 'meta' && parsed.messageInfo) {
                  // attach backend-generated messageInfo (turnId etc.) to the last assistant message
                  useChatStore.getState().setLastAssistantMessageInfo(parsed.messageInfo);
                  handled = true;
                }
              } catch (e) {
                // not JSON, fall through to full replace
              }
            }

            if (!handled) {
              // If server sent a full snapshot repeatedly (common when backend doesn't send structured append events),
              // detect the already-displayed prefix and append only the new suffix. This avoids blinking and missing lines
              // during rapid streaming of many list items.
              const store = useChatStore.getState();
              const msgs = store.chatMsgs;
              let lastAssistant = "";
              for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].role === 'assistant') {
                  lastAssistant = msgs[i].message || '';
                  break;
                }
              }

              if (lastAssistant && dataStr.startsWith(lastAssistant)) {
                const suffix = dataStr.slice(lastAssistant.length);
                if (suffix.length > 0) store.appendToLastAssistant(suffix);
              } else {
                // Fallback: replace the last assistant message with the full reconstructed text
                store.replaceLastAssistant(dataStr);
              }
             }
          }

          if (isDoneEvent) {
            // stream finished
            break;
          }
        }

        if (readerDone) break;
      }

      // After the streaming loop, do not alter the assembled markdown so newlines are preserved
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