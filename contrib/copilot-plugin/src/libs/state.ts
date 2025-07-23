import { create } from "zustand";

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
  currentConversationId: `${Math.random().toString(36).substring(2, 9)}`,

  setUser: (paiuser) => set((state) => ({ 
    paiuser,
    currentConversationId: `${Math.random().toString(36).substring(2, 9)}`
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
  
  // Generate a new conversation ID (useful for starting a new conversation)
  generateNewConversationId: () => set((state) => ({ 
    currentConversationId: `${Math.random().toString(36).substring(2, 9)}`,
    chatMsgs: [] // Clear chat messages when starting new conversation
  })),

}));
