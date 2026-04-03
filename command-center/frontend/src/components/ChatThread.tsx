'use client';

import { useEffect, useRef, useState } from 'react';
import type { CommsMessage, Lane, MessageType } from '@/lib/comms-types';
import { fetchMessages, sendMessage, markLaneRead } from '@/lib/comms-api';

interface ChatThreadProps {
  lane: Lane;
  onNewMessage?: (msg: CommsMessage) => void;
}

const MSG_TYPE_OPTIONS: { value: MessageType; label: string; icon: string }[] = [
  { value: 'chat', label: 'Chat', icon: '💬' },
  { value: 'task', label: 'Task', icon: '📋' },
  { value: 'decision', label: 'Decision', icon: '⚖️' },
  { value: 'approval', label: 'Approval', icon: '✅' },
  { value: 'alert', label: 'Alert', icon: '🚨' },
];

const MSG_TYPE_COLORS: Record<string, string> = {
  chat: '',
  task: 'border-l-2 border-amber-500/60',
  decision: 'border-l-2 border-purple-500/60',
  approval: 'border-l-2 border-green-500/60',
  alert: 'border-l-2 border-red-500/60',
  system: 'border-l-2 border-zinc-500/60',
};

const MSG_TYPE_BADGES: Record<string, { label: string; color: string }> = {
  task: { label: 'TASK', color: 'bg-amber-500/20 text-amber-400' },
  decision: { label: 'DECISION', color: 'bg-purple-500/20 text-purple-400' },
  approval: { label: 'APPROVAL', color: 'bg-green-500/20 text-green-400' },
  alert: { label: 'ALERT', color: 'bg-red-500/20 text-red-400' },
  system: { label: 'SYSTEM', color: 'bg-zinc-500/20 text-zinc-400' },
};

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function formatDateSeparator(ts: string): string {
  const d = new Date(ts);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });
}

function shouldShowDateSeparator(
  msg: CommsMessage,
  prevMsg: CommsMessage | null
): boolean {
  if (!prevMsg) return true;
  const d1 = new Date(msg.timestamp).toDateString();
  const d2 = new Date(prevMsg.timestamp).toDateString();
  return d1 !== d2;
}

export default function ChatThread({ lane, onNewMessage }: ChatThreadProps) {
  const [messages, setMessages] = useState<CommsMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [input, setInput] = useState('');
  const [msgType, setMsgType] = useState<MessageType>('chat');
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDescription, setTaskDescription] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load messages when lane changes
  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      try {
        const data = await fetchMessages(lane.id, 50);
        if (mounted) {
          setMessages(data.messages);
          markLaneRead(lane.id).catch(() => {});
        }
      } catch (e) {
        console.error('Failed to load messages:', e);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => { mounted = false; };
  }, [lane.id]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on lane change
  useEffect(() => {
    inputRef.current?.focus();
  }, [lane.id]);

  // Handle incoming WS messages with content dedup
  useEffect(() => {
    function handleWsMessage(event: CustomEvent<CommsMessage>) {
      if (!event.detail?.lane_id) return;
      const msg = event.detail;
      if (msg.lane_id === lane.id) {
        setMessages((prev) => {
          // Dedupe by ID
          if (prev.some((m) => m.id === msg.id)) return prev;
          // Content dedup: if same sender+content within 2 seconds, skip
          const recent = prev.filter(
            (m) =>
              m.sender_id === msg.sender_id &&
              m.content === msg.content &&
              Math.abs(new Date(msg.timestamp).getTime() - new Date(m.timestamp).getTime()) < 2000
          );
          if (recent.length > 0) return prev;
          return [...prev, msg];
        });
      }
    }

    window.addEventListener(
      'cc-chat-message' as string,
      handleWsMessage as EventListener
    );
    return () => {
      window.removeEventListener(
        'cc-chat-message' as string,
        handleWsMessage as EventListener
      );
    };
  }, [lane.id]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    setSending(true);
    setInput('');

    try {
      const result = await sendMessage(lane.id, text, msgType);

      // Add user message immediately (if not already added via WS)
      if (result.user_message) {
        setMessages((prev) => {
          if (prev.some((m) => m.id === result.user_message.id)) return prev;
          return [...prev, result.user_message];
        });
        onNewMessage?.(result.user_message);
      }

      // Add agent response if present
      if (result.agent_message) {
        setMessages((prev) => {
          if (prev.some((m) => m.id === result.agent_message!.id)) return prev;
          return [...prev, result.agent_message!];
        });
        onNewMessage?.(result.agent_message);
      }

      setMsgType('chat');
    } catch (e) {
      console.error('Failed to send message:', e);
      setInput(text); // Restore on failure
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const selectedTypeInfo = MSG_TYPE_OPTIONS.find((t) => t.value === msgType);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-700/50 flex items-center gap-3">
        <span className="text-xl">{lane.avatar || '💬'}</span>
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">{lane.name}</h3>
          {lane.lane_type === 'dm' && lane.participants.length > 0 && (
            <p className="text-xs text-zinc-500">Direct message</p>
          )}
          {lane.lane_type === 'broadcast' && (
            <p className="text-xs text-zinc-500">
              {lane.participants.length} team members
            </p>
          )}
          {lane.lane_type === 'system' && (
            <p className="text-xs text-zinc-500">System notifications</p>
          )}
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1">
        {loading ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
            Loading messages...
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500 text-sm">
            <span className="text-3xl mb-2">{lane.avatar || '💬'}</span>
            <p>No messages yet</p>
            <p className="text-xs text-zinc-600 mt-1">
              Send a message to start the conversation
            </p>
          </div>
        ) : (
          messages.map((msg, i) => {
            const prevMsg = i > 0 ? messages[i - 1] : null;
            const showDate = shouldShowDateSeparator(msg, prevMsg);
            const isUser = msg.sender_type === 'user';
            const isSystem = msg.sender_type === 'system';
            const typeBadge = MSG_TYPE_BADGES[msg.message_type];

            return (
              <div key={msg.id}>
                {/* Date separator */}
                {showDate && (
                  <div className="flex items-center justify-center my-4">
                    <span className="text-[11px] text-zinc-500 bg-zinc-800/80 px-3 py-1 rounded-full">
                      {formatDateSeparator(msg.timestamp)}
                    </span>
                  </div>
                )}

                {/* System message */}
                {isSystem ? (
                  <div className="flex justify-center my-2">
                    <div className="text-xs text-zinc-500 bg-zinc-800/50 px-3 py-1.5 rounded-lg max-w-md text-center">
                      {msg.content}
                    </div>
                  </div>
                ) : (
                  /* Chat bubble */
                  <div
                    className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-1`}
                  >
                    <div
                      className={`max-w-[75%] ${
                        isUser
                          ? 'bg-blue-600/80 text-white rounded-2xl rounded-br-md'
                          : 'bg-zinc-700/60 text-zinc-200 rounded-2xl rounded-bl-md'
                      } px-3.5 py-2 ${MSG_TYPE_COLORS[msg.message_type] || ''}`}
                    >
                      {/* Sender name (for non-user messages) */}
                      {!isUser && (
                        <p className="text-[11px] font-semibold text-blue-400 mb-0.5">
                          {msg.sender_name}
                        </p>
                      )}

                      {/* Type badge */}
                      {typeBadge && (
                        <span
                          className={`inline-block text-[10px] font-bold px-1.5 py-0.5 rounded mb-1 ${typeBadge.color}`}
                        >
                          {typeBadge.label}
                        </span>
                      )}

                      {/* Content */}
                      <p className="text-sm whitespace-pre-wrap break-words">
                        {msg.content}
                      </p>

                      {/* Timestamp */}
                      <p
                        className={`text-[10px] mt-1 ${
                          isUser ? 'text-blue-200/60' : 'text-zinc-500'
                        } text-right`}
                      >
                        {formatTimestamp(msg.timestamp)}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      {lane.lane_type !== 'system' && (
        <div className="px-4 py-3 border-t border-zinc-700/50">
          {/* Type selector dropdown */}
          {showTypeSelector && (
            <div className="mb-2 flex gap-1 flex-wrap">
              {MSG_TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => {
                    setMsgType(opt.value);
                    setShowTypeSelector(false);
                  }}
                  className={`text-xs px-2.5 py-1.5 rounded-lg transition-colors ${
                    msgType === opt.value
                      ? 'bg-blue-600/30 text-blue-400 ring-1 ring-blue-500/50'
                      : 'bg-zinc-700/50 text-zinc-400 hover:bg-zinc-700'
                  }`}
                >
                  {opt.icon} {opt.label}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-end gap-2">
            {/* Type toggle */}
            <button
              onClick={() => setShowTypeSelector(!showTypeSelector)}
              className="flex-shrink-0 p-2 rounded-lg bg-zinc-700/50 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-300 transition-colors"
              title="Message type"
            >
              <span className="text-sm">{selectedTypeInfo?.icon || '💬'}</span>
            </button>

            {/* Input */}
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  lane.lane_type === 'dm'
                    ? `Message ${lane.name}...`
                    : lane.lane_type === 'broadcast'
                    ? 'Message the team...'
                    : 'Type a message...'
                }
                rows={1}
                className="w-full bg-zinc-700/50 text-zinc-200 text-sm px-3.5 py-2.5 rounded-xl border border-zinc-600/50 focus:border-blue-500/50 focus:outline-none resize-none placeholder:text-zinc-500"
                style={{
                  minHeight: '40px',
                  maxHeight: '120px',
                }}
                onInput={(e) => {
                  const t = e.target as HTMLTextAreaElement;
                  t.style.height = 'auto';
                  t.style.height = Math.min(t.scrollHeight, 120) + 'px';
                }}
                disabled={sending}
              />
            </div>

            {/* Assign Task button */}
            <button
              onClick={() => setShowTaskForm(!showTaskForm)}
              className="flex-shrink-0 p-2 rounded-lg bg-zinc-700/50 hover:bg-zinc-700 text-zinc-400 hover:text-amber-400 transition-colors"
              title="Assign Task"
            >
              <span className="text-sm">📋</span>
            </button>

            {/* Send button */}
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className={`flex-shrink-0 p-2.5 rounded-xl transition-colors ${
                input.trim() && !sending
                  ? 'bg-blue-600 hover:bg-blue-500 text-white'
                  : 'bg-zinc-700/50 text-zinc-500 cursor-not-allowed'
              }`}
            >
              {sending ? (
                <svg
                  className="w-4 h-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
              ) : (
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              )}
            </button>
          </div>

          {/* Assign Task form */}
          {showTaskForm && (
            <div className="mt-2 p-3 bg-zinc-800/60 rounded-lg border border-zinc-700/50 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-amber-400">📋 Assign Task</span>
                <button
                  onClick={() => setShowTaskForm(false)}
                  className="text-xs text-zinc-500 hover:text-zinc-400"
                >
                  ✕
                </button>
              </div>
              <input
                type="text"
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                placeholder="Task title..."
                className="w-full bg-zinc-700/50 text-zinc-200 text-xs px-3 py-2 rounded-lg border border-zinc-600/50 focus:border-amber-500/50 focus:outline-none placeholder:text-zinc-500"
              />
              <textarea
                value={taskDescription}
                onChange={(e) => setTaskDescription(e.target.value)}
                placeholder="Description (optional)..."
                rows={2}
                className="w-full bg-zinc-700/50 text-zinc-200 text-xs px-3 py-2 rounded-lg border border-zinc-600/50 focus:border-amber-500/50 focus:outline-none resize-none placeholder:text-zinc-500"
              />
              <button
                onClick={async () => {
                  if (!taskTitle.trim()) return;
                  const content = `**Task:** ${taskTitle.trim()}${taskDescription.trim() ? `\n${taskDescription.trim()}` : ''}`;
                  try {
                    const result = await sendMessage(lane.id, content, 'task');
                    if (result.user_message) {
                      setMessages((prev) => {
                        if (prev.some((m) => m.id === result.user_message.id)) return prev;
                        return [...prev, result.user_message];
                      });
                      onNewMessage?.(result.user_message);
                    }
                    if (result.agent_message) {
                      setMessages((prev) => {
                        if (prev.some((m) => m.id === result.agent_message!.id)) return prev;
                        return [...prev, result.agent_message!];
                      });
                      onNewMessage?.(result.agent_message);
                    }
                    setTaskTitle('');
                    setTaskDescription('');
                    setShowTaskForm(false);
                  } catch (e) {
                    console.error('Failed to assign task:', e);
                  }
                }}
                disabled={!taskTitle.trim() || sending}
                className="w-full text-xs px-3 py-2 rounded-lg bg-amber-600/80 hover:bg-amber-500/80 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Send Task
              </button>
            </div>
          )}

          {/* Type indicator */}
          {msgType !== 'chat' && (
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-[11px] text-zinc-500">
                Sending as {selectedTypeInfo?.icon} {selectedTypeInfo?.label}
              </span>
              <button
                onClick={() => setMsgType('chat')}
                className="text-[11px] text-zinc-500 hover:text-zinc-400"
              >
                ✕
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
