"use client";

import React, { useEffect, useRef, useState } from "react";
import moment from "moment";
import { Bot, User, Trash2, ClipboardCopy } from "lucide-react";
import Markdown, { Components } from "react-markdown";

import remarkGfm from "remark-gfm";
import { ChatMessage, useChatStore } from "../libs/state";
import { Pane } from "../components/pane";

const sigmaLogo = "data:image/png;base64,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"

type MessageGroup = {
  sender: "assistant" | "user";
  messages: ChatMessage[];
  timestamp: Date;
};

// Helper function to group messages
const groupMessages = (messages: ChatMessage[]): MessageGroup[] => {
  const groups: MessageGroup[] = [];
  let currentGroup: MessageGroup | null = null;

  messages.forEach((message) => {
    const messageTimestamp = message.timestamp;
    const sender = message.role === "assistant" ? "assistant" : "user";

    if (
      !currentGroup ||
      currentGroup.sender !== sender ||
      moment(messageTimestamp).diff(moment(currentGroup.timestamp), "minutes") >
      0
    ) {
      if (currentGroup) {
        groups.push(currentGroup);
      }
      currentGroup = {
        sender,
        messages: [message],
        timestamp: messageTimestamp,
      };
    } else {
      currentGroup.messages.push(message);
    }
  });

  if (currentGroup) {
    groups.push(currentGroup);
  }

  return groups;
};

// Custom renderer for <pre> tags
const PreWithLineNumbers: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Assuming the children is an array with a single <code> element
  const codeElement = React.Children.only(children) as React.ReactElement<{ children: string }>;

  // Extract the code content
  const codeContent = codeElement.props.children as string;

  if (!codeContent) {
    return null;
  }
  // Split the code content into lines
  const lines = codeContent.split('\n');

  return (
    <pre className="font-mono text-sm">
      {/* <div className="font-mono text-sm"> */}

      {lines.map((line, lineIndex) => (
        <div key={lineIndex}>
          <span className="text-gray-400 w-8 text-right mr-6 select-none">
            {lineIndex + 1}
          </span>
          <span style={{ flex: 1 }}>{line}</span>
        </div>
      ))}
      {/* </div> */}
    </pre>
  );
};

const CustomMarkdown: React.FC<{ content: string }> = ({ content }) => {
  return (
    <div className={`prose-sm text-base break-words word-wrap`}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          pre({ node, ...props }: any) {
            return <PreWithLineNumbers>{props.children}</PreWithLineNumbers>;
          },
          ol({ node, ...props }: any) {
            return <ol className="list-decimal" {...props} />;
          }
        }}
      >
        {content}
      </Markdown>
    </div>
  );
}

// Message component
const Message: React.FC<{ message: ChatMessage }> = ({ message }) => {
  const [expanded, setExpanded] = useState(true);
  const [isHovered, setIsHovered] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null); // Reference to the content div

  const handleToggle = () => {
    setExpanded((prev) => !prev);
  };

  const hasExpandedRef = useRef(false);

  useEffect(() => {
    if (message.message.length > 0 && !hasExpandedRef.current) {
      setExpanded(false);
      hasExpandedRef.current = true;
    }
  }, [message.message.length])

  return (
    <div
      className="flex-1 container relative overflow-hidden"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        className="flex-1 container relative mb-1 bg-gray-100 px-2 py-1 rounded word-wrap overflow-hidden"
      >
        {/* Reasoning part with fold/unfold */}
        {message.reasoning && (
          <div className="bg-gray-50 border-l-4 border-gray-400 px-2 py-1 mb-2 rounded text-gray-700 overflow-hidden">
            <details open={expanded}>
              <summary
                className="cursor-pointer font-semibold"
                onClick={e => {
                  e.preventDefault();
                  handleToggle();
                }}
              >
                Reasoning
              </summary>
              <div
                className="mt-1 overflow-auto max-w-full"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit' }}
              >
                <CustomMarkdown content={message.reasoning} />
              </div>
            </details>
          </div>
        )}
        <div
          ref={contentRef}
          className="flex-1 overflow-auto max-w-full"
          style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit' }}
        >
          <CustomMarkdown content={message.message} />
        </div>
      </div>
      <div className="flex justify-end">
        {isHovered ? (
          <div>
            <button
              onClick={() => {
                const textToCopy = message.reasoning
                  ? `<think>\n${message.reasoning}\n</think>\n\n${message.message}`
                  : message.message;
                navigator.clipboard.writeText(textToCopy);
              }}
              className="text-gray-500 hover:text-gray-700 transition-opacity"
              title="Copy message"
            >
              <ClipboardCopy size={16} />
            </button>
          </div>) :
          (<div style={{ height: '24px' }}></div>)
        }
      </div>
    </div>
  );
};

// MessageGroup component
const MessageGroup: React.FC<{ index: number, group: MessageGroup, isLast: boolean }> = ({ index, group, isLast = false }) => {
  // Get the current model 
  const currentModel = useChatStore((state) => state.currentModel);
  let imageUrl = "https://www.svgrepo.com/show/445500/ai.svg";
  if (currentModel && currentModel.toLowerCase().includes("sigma")) {
    imageUrl = sigmaLogo;
  }
  const isAI = group.sender === "assistant";
  const isSigma = currentModel && currentModel.toLowerCase().includes("sigma");
  return (
    <div className={`flex mb-4 ${isAI ? "flex-row" : "flex-row-reverse"}`}>
      <div className="w-12 flex-shrink-0">
        {isAI ? (isSigma ? (
          <img
            src={imageUrl}
            width={40}
            height={40}
            alt="Agent avatar"
            className="rounded"
          />
        ) : (
          <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center">
            <Bot size={24} />
          </div>
        )) : (
          <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center">
            <User size={24} />
          </div>
        )}
      </div>
      <div className={`overflow-auto ${isAI ? "ml-2" : "mr-2"}`}>
        <div className="text-xs text-gray-500 mb-1">
          {moment(group.timestamp).format('LT')}
        </div>
        {group.messages.map((message, index) => (
          // <Message key={index} message={message} expand={isLast} />
          <Message key={index} message={message} />
        ))}

      </div>
    </div>
  );
};

// Main component
const GroupedChatMessages: React.FC = () => {
  const messages = useChatStore((state) => state.chatMsgs);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const groupedMessages = groupMessages(messages);
  return (
    <Pane className="p-0">
      <div className="bg-white top-0 sticky p-2 px-4 pb-2 border-b text-sm flex items-center gap-1">
        <Bot size={20} />
        <h2>Chat</h2>
        <button
          onClick={() => useChatStore.getState().cleanChat()}
          className="ml-auto text-xs px-2 py-1 bg-gray-200 hover:bg-gray-300 rounded transition-colors flex items-center gap-1"
        >
          <Trash2 size={20} strokeWidth={1.5} />
          Clean History
        </button>
      </div>
      <div className="bg-white flex-1 overflow-auto p-4" ref={scrollRef}>
        {groupedMessages.map((group, index) => (
          <MessageGroup key={index} group={group} index={index} isLast={index == (groupedMessages.length - 1)} />
        ))}
      </div>
    </Pane>
  );
};

export default GroupedChatMessages;
