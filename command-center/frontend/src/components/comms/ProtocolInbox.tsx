'use client';

import { useState, useEffect } from 'react';
import { fetchProtocolHistory } from '@/lib/protocol-api';
import type { ProtocolMessage, ProtocolIntent } from '@/lib/protocol-types';

const INTENT_COLORS: Record<ProtocolIntent, string> = {
  inform: 'bg-blue-500/20 text-blue-400',
  challenge: 'bg-red-500/20 text-red-400',
  propose: 'bg-emerald-500/20 text-emerald-400',
  critique: 'bg-orange-500/20 text-orange-400',
  decide: 'bg-purple-500/20 text-purple-400',
  request: 'bg-amber-500/20 text-amber-400',
  acknowledge: 'bg-slate-500/20 text-slate-400',
  escalate: 'bg-red-600/20 text-red-300',
  delegate: 'bg-indigo-500/20 text-indigo-400',
  withdraw: 'bg-zinc-500/20 text-zinc-400',
  chat: 'bg-zinc-600/20 text-zinc-300',
};

function IntentBadge({ intent }: { intent: ProtocolIntent }) {
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium uppercase ${INTENT_COLORS[intent]}`}>
      {intent}
    </span>
  );
}

function ConfidenceDot({ confidence }: { confidence: number }) {
  const color = confidence >= 0.8 ? 'bg-emerald-400' : confidence >= 0.6 ? 'bg-amber-400' : 'bg-red-400';
  return (
    <span className="flex items-center gap-1">
      <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
      <span className="text-[10px] text-zinc-500">{(confidence * 100).toFixed(0)}%</span>
    </span>
  );
}

export default function ProtocolInbox() {
  const [messages, setMessages] = useState<ProtocolMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<ProtocolIntent | ''>('');

  useEffect(() => {
    fetchProtocolHistory(200)
      .then(({ messages: m }) => setMessages(m))
      .catch(() => setMessages([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter ? messages.filter(m => m.intent === filter) : messages;

  const intents: ProtocolIntent[] = ['inform', 'challenge', 'propose', 'critique', 'decide', 'request', 'escalate'];

  if (loading) {
    return <div className="flex items-center justify-center h-full text-zinc-500 text-sm">Loading protocol messages...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-zinc-700/50">
        <h2 className="text-sm font-semibold text-zinc-200 mb-2">Agent-to-Agent Protocol</h2>
        <div className="flex gap-1 flex-wrap">
          <button
            onClick={() => setFilter('')}
            className={`px-2 py-1 text-[10px] rounded-lg transition-colors ${
              !filter ? 'bg-blue-600/20 text-blue-400' : 'text-zinc-400 hover:bg-zinc-700/50'
            }`}
          >All ({messages.length})</button>
          {intents.map((intent) => {
            const count = messages.filter(m => m.intent === intent).length;
            if (count === 0) return null;
            return (
              <button
                key={intent}
                onClick={() => setFilter(intent)}
                className={`px-2 py-1 text-[10px] rounded-lg transition-colors capitalize ${
                  filter === intent ? 'bg-blue-600/20 text-blue-400' : 'text-zinc-400 hover:bg-zinc-700/50'
                }`}
              >{intent} ({count})</button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {filtered.map((msg) => (
          <div key={msg.id} className="px-4 py-3 border-b border-zinc-700/30 hover:bg-zinc-800/30 transition-colors">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-blue-400">{msg.sender_name}</span>
              <span className="text-[10px] text-zinc-500">&rarr;</span>
              <span className="text-xs text-zinc-400">{msg.recipients.join(', ') || 'channel'}</span>
              <IntentBadge intent={msg.intent} />
              <ConfidenceDot confidence={msg.confidence} />
            </div>
            <p className="text-sm text-zinc-200 whitespace-pre-wrap">{msg.content}</p>
            {msg.references.length > 0 && (
              <div className="flex gap-1 mt-1">
                {msg.references.map((ref, i) => (
                  <span key={i} className="text-[10px] text-zinc-500 bg-zinc-800/50 px-1.5 py-0.5 rounded">
                    📎 {ref}
                  </span>
                ))}
              </div>
            )}
            <div className="text-[10px] text-zinc-500 mt-1">
              {new Date(msg.timestamp).toLocaleString()} &middot; {msg.channel_id}
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="text-center py-12 text-sm text-zinc-500">
            No protocol messages {filter ? `with intent "${filter}"` : ''}
          </div>
        )}
      </div>
    </div>
  );
}
