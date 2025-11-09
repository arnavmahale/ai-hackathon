import type { HTMLAttributes } from 'react';
import { cn } from '../lib/utils.ts';
import type { TaskSeverity } from '../types';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'outline' | TaskSeverity;
}

const severityStyles: Record<TaskSeverity, string> = {
  critical: 'border-critical/40 text-critical',
  warning: 'border-warning/40 text-warning',
  info: 'border-border text-textMuted',
};

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  const base =
    'inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em]';

  const variantClass =
    variant === 'outline'
      ? 'border-border text-text'
      : variant === 'default'
        ? 'border-accent text-accent'
        : severityStyles[variant];

  return <span className={cn(base, variantClass, className)} {...props} />;
}
