// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import { create } from "zustand";
import { v4 as uuidv4 } from "uuid";

export type Status = "loading" | "online" | "offline" | "unknown";

export type ChatMessage = {
  role: string;
  message: string;
  timestamp: Date;
  messageInfo?: any; // Store the message_info from API response
};

export type Job = {
  id: string;
  name: string;
  username: string;
  status: Status;
  ip: string;
  port: number;
}

var init_msg = `
Welcome to the Copilot Plugin!
`;


interface State {

  paiuser: string;
  restServerPath: string;
  jobServerPath: string;
  restServerToken: string;
  jobServerToken: string;

  allJobs: Job[];
  currentJob: Job | null;
  allModelsInCurrentJob: string[];
  currentModel: string | null;

  chatMsgs: ChatMessage[];
  
  // Conversation management
  currentConversationId: string;

  setUser: (paiuser: string) => void;
  setRestServerPath: (path: string) => void;
  setJobServerPath: (path: string) => void;
  setRestServerToken: (token: string) => void;
  setJobServerToken: (token: string) => void;
  setAllJobs: (jobs: Job[]) => void;
  setCurrentJob: (job: Job | null) => void;
  setAllModelsInCurrentJob: (models: string[]) => void;
  setCurrentModel: (model: string | null) => void;
  addChat: (chat: ChatMessage) => void;
  appendToLastAssistant: (chunk: string) => void;
  replaceLastAssistant: (text: string) => void;
  
  // Conversation management actions
  generateNewConversationId: () => void;
}


export const useChatStore = create<State>((set) => ({
  paiuser: "MSR",
  restServerPath: "rest-server",
  jobServerPath: "job-server",
  restServerToken: "",
  jobServerToken: "",
  allJobs: [],
  currentJob: null,
  allModelsInCurrentJob: [],
  currentModel: null,


  // chatMsgs: [{
  //   role: "welcome",
  //   message: init_msg,
  //   requiresAnswer: false,
  //   timestamp: new Date()
  // }],
  chatMsgs: [],
  
  // Initialize with a unique conversation ID (will be updated when user is set)
  currentConversationId: uuidv4(),

  setUser: (paiuser) => set((state) => ({ 
    paiuser,
    currentConversationId: uuidv4()
  })),
  setRestServerPath: (path) => set({ restServerPath: path }),
  setJobServerPath: (path) => set({ jobServerPath: path }),
  setRestServerToken: (token) => set({ restServerToken: token }),
  setJobServerToken: (token) => set({ jobServerToken: token }),
  setAllJobs: (jobs) => set({ allJobs: jobs }),
  setCurrentJob: (job) => set({ currentJob: job }),
  setAllModelsInCurrentJob: (models) => set({ allModelsInCurrentJob: models }),
  setCurrentModel: (model) => set({ currentModel: model }),

  addChat: (log) => set((state) => ({ chatMsgs: [...state.chatMsgs, log] })),
  appendToLastAssistant: (chunk: string) => set((state) => {
    const msgs = [...state.chatMsgs];
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        msgs[i] = { ...msgs[i], message: (msgs[i].message || '') + chunk };
        break;
      }
    }
    return { chatMsgs: msgs };
  },),
  replaceLastAssistant: (text: string) => set((state) => {
    const msgs = [...state.chatMsgs];
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        msgs[i] = { ...msgs[i], message: text };
        break;
      }
    }
    return { chatMsgs: msgs };
  }),

  // Generate a new conversation ID (useful for starting a new conversation)
  generateNewConversationId: () => set((state) => ({ 
    currentConversationId: uuidv4(),
    chatMsgs: [] // Clear chat messages when starting new conversation
  })),

}));
