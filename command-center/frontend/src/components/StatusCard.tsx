'use client';

import { clsx } from 'clsx';
import type { HealthStatus } from '@/lib/types';

interface StatusCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  status?: HealthStatus;
  icon?: string;
  children?: React.ReactNode;
}

const STATUS_COLORS: Record<HealthStatus, string> = {
  healthy: 'border-nc-green/30 bg-nc-green/5',
  warning: 'border-nc-yellow/30 bg-nc-yellow/5',
  error: 'border-nc-red/30 bg-nc-red/5',
  unknown: 'border-nc-border bg-nc-surface',
};

const STATUS_DOT: Record<HealthStatus, string> = {
  healthy: 'bg-nc-green',
  warning: 'bg-nc-yellow',
  error: 'bg-nc-red',
  unknown: 'bg-nc-text-dim',
};

export function StatusCard({ title, value, subtitle, status = 'unknown', icon, children }: StatusCardProps) {
  return (
    <div className={clsx('rounded-xl border p-4 transition-colors', STATUS_COLORS[status])}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {icon && <span className="text-lg">{icon}</span>}
          <span className="text-xs font-medium text-nc-text-dim uppercase tracking-wider">{title}</span>
        </div>
        <div className={clsx('w-2 h-2 rounded-full mt-1', STATUS_DOT[status])} />
      </div>
      <div className="text-2xl font-bold text-nc-text mb-0.5">{value}</div>
      {subtitle && <div className="text-xs text-nc-text-dim">{subtitle}</div>}
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}

interface MiniBarProps {
  value: number;
  max: number;
  color?: string;
}

export function MiniBar({ value, max, color = 'bg-nc-accent' }: MiniBarProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-1.5 rounded-full bg-nc-border overflow-hidden">
      <div
        className={clsx('h-full rounded-full transition-all', color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

interface HealthDotProps {
  status: HealthStatus;
  label: string;
  message?: string;
}

export function HealthDot({ status, label, message }: HealthDotProps) {
  return (
    <div className="flex items-center gap-2 py-1">
      <div className={clsx('w-2 h-2 rounded-full shrink-0', STATUS_DOT[status])} />
      <span className="text-xs text-nc-text flex-1">{label}</span>
      {message && (
        <span className="text-xs text-nc-text-dim truncate max-w-[180px]">{message}</span>
      )}
    </div>
  );
}
