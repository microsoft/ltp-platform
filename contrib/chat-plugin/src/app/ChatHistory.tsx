"use client";

import React, { useEffect, useRef, useState } from "react";
import { IoIosArrowDown, IoIosArrowUp } from 'react-icons/io';
import moment from "moment";
import { Bot, User } from "lucide-react";
import Markdown, { Components } from "react-markdown";

import remarkGfm from "remark-gfm";
import { ChatMessage, useChatStore } from "../libs/state";
import { Pane } from "../components/pane";

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
const Message: React.FC<{ message: ChatMessage, expand?: boolean }> = ({ message, expand = true }) => {
  const [expanded, setExpanded] = useState(expand);
  const [showButton, setShowButton] = useState(true);
  const contentRef = useRef<HTMLDivElement>(null); // Reference to the content div

  useEffect(() => {
    setExpanded(expand); // Set expanded based on prop
  }, [expand]);

  useEffect(() => {
    // Check if the content height is less than a threshold (8 in this case)
    const contentHeight = contentRef.current?.scrollHeight;
    if (contentHeight && contentHeight <= 32) { // Assuming 32px is roughly equivalent to 2 lines of text
      setShowButton(false);
    } else {
      setShowButton(true);
    }
  }, [message]); // Depend on message so it re-checks when message changes

  const toggleExpanded = () => {
    setExpanded(!expanded);
  };

  return (
    <div className="flex-1 container relative mb-1 bg-gray-100 px-2 py-1 rounded word-wrap"    >
      {showButton && (
        <button
          onClick={toggleExpanded}
          className="absolute top-0 right-0 mt-1 mr-1 text-blue-500 text-xs flex items-center justify-center bg-white border border-gray-300 rounded-full h-6 w-6"
        >
          {expanded ? <IoIosArrowUp /> : <IoIosArrowDown />}
        </button>
      )}
      <div 
        ref={contentRef}
        className={`flex-1 ${expanded ? 'overflow-auto' : 'overflow-hidden max-h-12 mx-auto'} ${showButton ? 'pr-6' : ''}`}
      >
        <CustomMarkdown content={message.message} />
      </div>
    </div>
  );
};

// MessageGroup component
const MessageGroup: React.FC<{ index: number, group: MessageGroup, isLast: boolean }> = ({ index, group, isLast = false }) => {
  const isAI = group.sender === "assistant";
  return (
    <div className={`flex mb-4 ${isAI ? "flex-row" : "flex-row-reverse"}`}>
      <div className="w-12 flex-shrink-0">
        {isAI ? (
          <img
            src="https://www.svgrepo.com/show/445500/ai.svg"
            width={40}
            height={40}
            alt="Agent avatar"
            className="rounded"
          />
        ) : (
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
          <Message key={index} message={message} expand={true} />
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
        <Bot size={16} />
        <h2>Chat</h2>
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
