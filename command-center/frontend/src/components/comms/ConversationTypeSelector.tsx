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
    <div className="flex gap-2 px-4 py-3 border-b border-nc-border">
      {TYPES.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-full transition-colors ${
            active === t.id
              ? 'bg-nc-accent text-white'
              : 'text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2'
          }`}
        >
          <span>{t.icon}</span>
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}
