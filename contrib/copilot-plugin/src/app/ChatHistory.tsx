// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

"use client";

import { v4 as uuidv4 } from "uuid";
import React, { useEffect, useRef, useState } from "react";
import { IoIosArrowDown, IoIosArrowUp } from 'react-icons/io';
import moment from "moment";
import { Bot, User, ThumbsUp, ThumbsDown } from "lucide-react";
import ReactMarkdown from "react-markdown";

import remarkGfm from "remark-gfm";
import rehypeRaw from 'rehype-raw';
import { ChatMessage, useChatStore } from "../libs/state";
import { Pane } from "../components/pane";

// API constants for feedback
const IP_ADDRESS = 'copilot.openpai.org';
const PORT = 8443;
const TRACE_ID = 'cafe66d8-f37b-42b4-b765-bca9b1f09c2b';
// Use local backend when running the dev server (npm start),
// and use the relative path for production builds (npm run build).
const REMOTE_SERVER_URL = process.env.NODE_ENV === 'development'
  ? 'http://127.0.0.1:60000/copilot/api/operation'
  : '/copilot/api/operation';

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

const fixStreamingMarkdown = (raw: string): string => {
  // During streaming an unfinished code fence (``` without closing) prevents proper formatting.
  // Detect an odd number of fenced code blocks and temporarily close it for rendering only.
  const fenceRegex = /```/g;
  const count = (raw.match(fenceRegex) || []).length;
  if (count % 2 === 1) {
    return raw + "\n```"; // append a closing fence (not persisted in state)
  }
  return raw;
};

const CustomMarkdown: React.FC<{ content: string }> = ({ content }) => {
  const renderText = fixStreamingMarkdown(content);
  return (
    <div className={"prose prose-sm max-w-none break-words"}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw as any]}
        components={{
          pre({ node, ...props }: any) {
            return <PreWithLineNumbers>{props.children}</PreWithLineNumbers>;
          },
          ol({ node, ...props }: any) {
            return <ol className="list-decimal pl-6 my-2" {...props} />;
          },
          ul({ node, ...props }: any) {
            return <ul className="list-disc pl-6 my-2" {...props} />;
          },
          table({ node, ...props }: any) {
            return <table className="table-auto border-collapse my-3" {...props} />;
          },
          th({ node, ...props }: any) {
            return <th className="border px-2 py-1 bg-gray-100" {...props} />;
          },
          td({ node, ...props }: any) {
            return <td className="border px-2 py-1 align-top" {...props} />;
          },
          code({ inline, className, children, ...props }: any) {
            const language = /language-(\w+)/.exec(className || "")?.[1];
            if (inline) {
              return <code className="px-1 py-0.5 rounded bg-gray-100" {...props}>{children}</code>;
            }
            return (
              <pre className="relative bg-gray-900 text-gray-100 rounded-md p-3 overflow-auto text-sm">
                <code className={className}>{children}</code>
                {language && (
                  <span className="absolute top-1 right-2 text-xs text-gray-400 select-none">{language}</span>
                )}
              </pre>
            );
          }
        }}
      >
        {renderText}
      </ReactMarkdown>
    </div>
  );
};

// Message component
const Message: React.FC<{ message: ChatMessage, expand?: boolean, isAssistant?: boolean }> = ({ message, expand = true, isAssistant = false }) => {
  const [expanded, setExpanded] = useState(expand);
  const [showButton, setShowButton] = useState(true);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const contentRef = useRef<HTMLDivElement>(null); // Reference to the content div
  
  // Get user information from the chat store
  const { paiuser, currentConversationId } = useChatStore();

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

  const sendFeedback = async (like: boolean, dislike: boolean) => {
    try {
      const payload = {
        async_: false,
        stream: false,
        data: {
          feedback: {
            like: like,
            dislike: dislike,
            responseUserId: paiuser,
            responseConvId: currentConversationId,
            responseTurnId: message.messageInfo?.turnId || "0", // Use message's turnId or fallback to "0"
          },
          messageInfo: {
            userId: paiuser,
            convId: currentConversationId,
            turnId: message.messageInfo?.turnId || "0",
            timestamp: Math.floor(Date.now()),
            timestampUnit: "ms",
            type: "feedback",
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

      if (!response.ok) {
        console.error("Failed to send feedback:", response.statusText);
      }
    } catch (error) {
      console.error("Error sending feedback:", error);
    }
  };

  const handleThumbsUp = () => {
    const newFeedback = feedback === 'up' ? null : 'up';
    setFeedback(newFeedback);
    
    if (newFeedback === 'up') {
      sendFeedback(true, false);
    } else {
      // If deselecting, send neutral feedback
      sendFeedback(false, false);
    }
  };

  const handleThumbsDown = () => {
    const newFeedback = feedback === 'down' ? null : 'down';
    setFeedback(newFeedback);
    
    if (newFeedback === 'down') {
      sendFeedback(false, true);
    } else {
      // If deselecting, send neutral feedback
      sendFeedback(false, false);
    }
  };

  return (
    <div className="flex-1 container relative mb-1 bg-gray-100 px-2 py-1 rounded word-wrap">
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
      {isAssistant && (
        <div className="flex gap-2 mt-2 pt-2 border-t border-gray-200">
          <button 
            className="flex items-center justify-center p-1 rounded hover:bg-gray-200 transition-colors"
            onClick={handleThumbsUp}
          >
            <ThumbsUp 
              size={16} 
              className={`transition-colors ${
                feedback === 'up' 
                  ? 'text-green-600 fill-green-600' 
                  : 'text-gray-600 hover:text-green-600'
              }`}
            />
          </button>
          <button 
            className="flex items-center justify-center p-1 rounded hover:bg-gray-200 transition-colors"
            onClick={handleThumbsDown}
          >
            <ThumbsDown 
              size={16} 
              className={`transition-colors ${
                feedback === 'down' 
                  ? 'text-red-600 fill-red-600' 
                  : 'text-gray-600 hover:text-red-600'
              }`}
            />
          </button>
        </div>
      )}
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
          <Message key={index} message={message} expand={true} isAssistant={isAI} />
        ))}

      </div>
    </div>
  );
};

// Main component
const GroupedChatMessages: React.FC = () => {
  const messages = useChatStore((state) => state.chatMsgs);
  const scrollRef = useRef<HTMLDivElement>(null);

  // compute grouped messages and helper values early so effects can reference them
  const groupedMessages = groupMessages(messages);
  const lastText = groupedMessages.length
    ? groupedMessages[groupedMessages.length - 1].messages.map((m) => m.message).join('\n')
    : ''
  const NEAR_BOTTOM_THRESHOLD = 120

   // Reliable auto-scroll for both new messages and streaming updates.
   const prevCountRef = React.useRef<number>(0);
   const lastTextRef = React.useRef<string>('');

   // Scroll helper: find nearest scrollable element that actually overflows, otherwise fallback to window
   const scrollToBottom = (startTarget?: HTMLElement | null) => {
     const startEl = startTarget || scrollRef.current
     if (!startEl) return
     let cur: HTMLElement | null = startEl
     while (cur && cur !== document.body) {
       try {
         const style = window.getComputedStyle(cur)
         const overflowY = style.overflowY
         if ((overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay') && cur.scrollHeight > cur.clientHeight) {
           cur.scrollTop = cur.scrollHeight
           return
         }
       } catch (e) {
         // ignore
       }
       cur = cur.parentElement
     }

     // fallback to window/document
     try {
       window.scrollTo(0, document.documentElement.scrollHeight)
     } catch (e) {
       // ignore
     }
   }

   useEffect(() => {
     const el = scrollRef.current
     if (!el) return

     const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
     const shouldScroll =
       distanceFromBottom < NEAR_BOTTOM_THRESHOLD &&
       (prevCountRef.current != groupedMessages.length || lastTextRef.current != lastText)

     if (shouldScroll) {
       // try smooth scrolling in next frame
       requestAnimationFrame(() => {
         try {
           scrollToBottom(el)
         } catch (e) {
           // ignore
         }
       })

       // fallback: ensure scroll after a short delay
       setTimeout(() => {
         try {
           scrollToBottom(el)
         } catch (e) {
           // ignore
         }
       }, 120)
     }

     prevCountRef.current = groupedMessages.length
     lastTextRef.current = lastText
   }, [groupedMessages.length, lastText])

   // observe DOM changes to catch streaming incremental updates
   useEffect(() => {
     const el = scrollRef.current
     if (!el) return

     const observer = new MutationObserver((mutations) => {
       try {
         const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
         if (distanceFromBottom < NEAR_BOTTOM_THRESHOLD) {
           requestAnimationFrame(() => {
             try {
               scrollToBottom(el)
             } catch (e) {
               // ignore
             }
           })
         }
       } catch (e) {
         // ignore
       }
     })

     observer.observe(el, { childList: true, subtree: true, characterData: true })
     return () => observer.disconnect()
   }, [scrollRef]);

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
