// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import { create } from "zustand";

export type Status = "loading" | "online" | "offline" | "unknown";

export type ChatMessage = {
  role: string;
  message: string;
  timestamp: Date;
  reasoning?: string; // Optional field for reasoning support
};

interface State {

  paiuser: string;
  modelProxyPath: string;
  restServerToken: string;

  allModels: string[];
  currentModel: string | null;

  chatMsgs: ChatMessage[];

  setUser: (paiuser: string) => void;
  setRestServerToken: (token: string) => void;
  setAllModels: (models: string[]) => void;
  setCurrentModel: (model: string | null) => void;
  addChatMessage: (chat: ChatMessage) => void;
  updateLastChatMessage: (lastChat: ChatMessage) => void;
  cleanChat: () => void;
}


export const useChatStore = create<State>((set) => ({
  paiuser: "MSR",
  modelProxyPath: "model-proxy",
  restServerToken: "",

  allModels: [],
  currentModel: null,

  chatMsgs: [],

  setUser: (paiuser) => set({ paiuser }),
  setRestServerToken: (token) => set({ restServerToken: token }),

  setAllModels: (models) => set({ allModels: models }),
  setCurrentModel: (model) => set({ currentModel: model }),

  addChatMessage: (log) => set((state) => ({ chatMsgs: [...state.chatMsgs, log] })),
  updateLastChatMessage: (lastChat) => set((state) => {
    const chatMsgs = [...state.chatMsgs];
    if (chatMsgs.length > 0) {
      chatMsgs[chatMsgs.length - 1] = lastChat;
    } else {
      chatMsgs.push(lastChat);
    }
    return { chatMsgs };
  }),
  cleanChat: () => set({ chatMsgs: [] })
}));
