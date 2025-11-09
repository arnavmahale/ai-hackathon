import { cn } from '../lib/utils';

interface ProgressProps {
  value: number;
}

export function Progress({ value }: ProgressProps) {
  return (
    <div className="w-full overflow-hidden rounded-full bg-panelMuted">
      <div
        className={cn(
          'h-2 rounded-full bg-accent transition-all duration-300 ease-out',
          value > 95 && 'bg-success',
        )}
        style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
      />
    </div>
  );
}
