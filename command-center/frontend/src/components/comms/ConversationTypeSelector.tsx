'use client';

import type { ConversationType } from '@/lib/store';

const TYPES: { id: ConversationType; label: string; icon: string }[] = [
  { id: 'dm', label: 'DMs', icon: '💬' },
  { id: 'agent-channel', label: 'Agent Channels', icon: '🔗' },
  { id: 'brainstorm', label: 'Brainstorms', icon: '💡' },
  { id: 'debate', label: 'Debates', icon: '⚔️' },
  { id: 'group', label: 'Groups', icon: '👥' },
];

interface Props {
  active: ConversationType;
  onChange: (type: ConversationType) => void;
}

export default function ConversationTypeSelector({ active, onChange }: Props) {
  return (
    <div className="flex gap-1 px-3 py-2 border-b border-zinc-700/50">
      {TYPES.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg transition-colors ${
            active === t.id
              ? 'bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/40'
              : 'text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-300'
          }`}
        >
          <span>{t.icon}</span>
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}
