import { create } from "zustand";

export type Status = "loading" | "online" | "offline" | "unknown";

export type ChatMessage = {
  role: string;
  message: string;
  timestamp: Date;
  reasoning?: string; // Optional field for reasoning support
};

export type Job = {
  id: string;
  name: string;
  username: string;
  status: Status;
  ip: string;
  port: number;
}

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

  setUser: (paiuser: string) => void;
  setRestServerPath: (path: string) => void;
  setJobServerPath: (path: string) => void;
  setRestServerToken: (token: string) => void;
  setJobServerToken: (token: string) => void;
  setAllJobs: (jobs: Job[]) => void;
  setCurrentJob: (job: Job | null) => void;
  setAllModelsInCurrentJob: (models: string[]) => void;
  setCurrentModel: (model: string | null) => void;
  addChatMessage: (chat: ChatMessage) => void;
  updateLastChatMessage: (lastChat: ChatMessage) => void;
  cleanChat: () => void;
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

  chatMsgs: [],

  setUser: (paiuser) => set({ paiuser }),
  setRestServerPath: (path) => set({ restServerPath: path }),
  setJobServerPath: (path) => set({ jobServerPath: path }),
  setRestServerToken: (token) => set({ restServerToken: token }),
  setJobServerToken: (token) => set({ jobServerToken: token }),
  setAllJobs: (jobs) => set({ allJobs: jobs }),
  setCurrentJob: (job) => set({ currentJob: job }),
  setAllModelsInCurrentJob: (models) => set({ allModelsInCurrentJob: models }),
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
