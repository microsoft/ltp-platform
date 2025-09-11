// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

"use client";
import Logs from "./ChatHistory";
import ChatBox from "./ChatBox";
import { useChatStore } from "../libs/state";
import { Toaster } from "../components/sonner";

export default function App({ restUrl, user, restToken, modelToken }:
  { restUrl: string; user: string; restToken: string; modelToken: string }) {
  // Initialize the chat store with the provided parameters
  const { setRestServerPath, setUser, setRestServerToken, setJobServerToken } = useChatStore.getState();

  setRestServerPath(restUrl);
  setUser(user);
  setRestServerToken(restToken);
  setJobServerToken(modelToken);

  return (
    <div className="w-full h-full flex flex-col overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden gap-4 p-4 pt-0 flex-grow">
        <Logs />
        <ChatBox />
      </div>
      <Toaster />
    </div>
  );
}