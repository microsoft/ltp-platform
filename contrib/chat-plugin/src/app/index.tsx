// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

"use client";
import Logs from "./ChatHistory";
import JobBar from "./JobBar";
import ChatBox from "./ChatBox";
import { useChatStore } from "../libs/state";
import { Toaster } from "../components/sonner";

export default function App({ restUrl, user, restToken }:
  { restUrl: string; user: string; restToken: string }) {
  // Initialize the chat store with the provided parameters
  const { setUser, setRestServerToken } = useChatStore.getState();

  setUser(user);
  setRestServerToken(restToken);

  return (
    <div className="w-full h-full flex flex-col overflow-hidden">
      {/* Status Bar */}
      <div className="flex">
        <JobBar />
      </div>

      <div className="flex-1 flex flex-col overflow-hidden gap-4 p-4 pt-0 flex-grow">
        <Logs />
        <ChatBox />
      </div>
      <Toaster />
    </div>
  );
}