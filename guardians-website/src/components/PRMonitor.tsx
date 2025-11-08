import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  GitPullRequest,
  Loader2,
  RefreshCw,
  Shield,
} from 'lucide-react';
import type { AgentRunState, PullRequest } from '../types';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Avatar } from '../ui/avatar';
import { Progress } from '../ui/progress';

interface PRMonitorProps {
  pullRequests: PullRequest[];
  agentRuns: Record<string, AgentRunState>;
  onRunAll: () => void;
  onRunSingle: (prId: string) => void;
  onBack: () => void;
  onRefresh: () => void;
}

const defaultRunState: AgentRunState = {
  status: 'idle',
  progress: 0,
  currentStep: 'Awaiting QA run',
};

const stepLabels = [
  'Queueing run',
  'Loading snapshot',
  'Aligning docs',
  'Scanning files',
  'Aggregating',
];

const statusColor = (status: AgentRunState['status']) => {
  switch (status) {
    case 'critical':
      return 'border-l-4 border-l-critical';
    case 'warnings':
      return 'border-l-4 border-l-warning';
    case 'passed':
      return 'border-l-4 border-l-success';
    case 'running':
      return 'border-l-4 border-l-accent';
    default:
      return 'border-l-4 border-l-border';
  }
};

const statusBadge = (status: AgentRunState['status']) => {
  switch (status) {
    case 'critical':
      return <Badge variant="critical">Critical</Badge>;
    case 'warnings':
      return <Badge variant="warning">Warnings</Badge>;
    case 'passed':
      return <Badge variant="outline">Passed</Badge>;
    case 'running':
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-accent">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Running
        </span>
      );
    default:
      return <Badge variant="outline">Idle</Badge>;
  }
};

export function PRMonitor({
  pullRequests,
  agentRuns,
  onRunAll,
  onRunSingle,
  onBack,
  onRefresh,
}: PRMonitorProps) {
  const [active, setActive] = useState<'all' | string>('all');

  const aggregate = useMemo(() => {
    return pullRequests.reduce(
      (acc, pr) => {
        const run = agentRuns[pr.id] ?? defaultRunState;
        acc.total += 1;
        acc.running += run.status === 'running' ? 1 : 0;
        acc.passed += run.status === 'passed' ? 1 : 0;
        acc.warnings += run.status === 'warnings' ? 1 : 0;
        acc.critical += run.status === 'critical' ? 1 : 0;
        return acc;
      },
      { total: 0, running: 0, passed: 0, warnings: 0, critical: 0 },
    );
  }, [pullRequests, agentRuns]);

  const globalProgress = useMemo(() => {
    const runs = Object.values(agentRuns);
    if (!runs.length) return 0;
    const activeRuns = runs.filter((run) => run.status === 'running');
    if (activeRuns.length) {
      return (
        activeRuns.reduce((sum, run) => sum + run.progress, 0) /
        Math.max(activeRuns.length, 1)
      );
    }
    const completed = runs.filter((run) =>
      ['passed', 'warnings', 'critical'].includes(run.status),
    );
    if (completed.length) return 100;
    return 0;
  }, [agentRuns]);

  const activeStep = Math.min(
    stepLabels.length - 1,
    Math.floor(globalProgress / (100 / stepLabels.length)),
  );

  return (
    <section className="mx-auto mt-10 flex max-w-6xl gap-6 px-6 pb-16 text-text">
      <aside className="w-72 rounded-2xl border border-border bg-panel p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-textMuted">
          PR Targets
        </p>
        <p className="mt-1 text-sm text-textMuted">{pullRequests.length} active</p>

        <button
          type="button"
          onClick={() => setActive('all')}
          className={`mt-4 inline-flex w-full items-center justify-center rounded-lg px-4 py-3 text-sm font-semibold transition ${
            active === 'all'
              ? 'bg-accent text-black'
              : 'bg-panelMuted text-textMuted hover:text-text'
          }`}
        >
          <Shield className="mr-2 h-4 w-4" />
          All PR runs
        </button>

        <div className="mt-6 space-y-2">
          {pullRequests.map((pr) => {
            const run = agentRuns[pr.id] ?? defaultRunState;
            const isActive = active === pr.id;
            return (
              <button
                type="button"
                key={pr.id}
                onClick={() => setActive(pr.id)}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-3 text-left transition ${
                  isActive ? 'bg-panelMuted text-text' : 'text-textMuted hover:bg-panelMuted/60'
                }`}
              >
                <div>
                  <p className="text-sm font-semibold">{pr.author.name}</p>
                  <p className="text-xs text-textMuted">PR #{pr.number}</p>
                  <p className="text-xs text-textMuted">
                    {run.status === 'running'
                      ? 'Agent running…'
                      : `Last status: ${run.status.toUpperCase()}`}
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 text-textMuted" />
              </button>
            );
          })}
        </div>
      </aside>

      <div className="flex-1 space-y-6">
        <header className="rounded-2xl border border-border bg-panel px-8 py-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-textMuted">Step 3 · Monitor</p>
              <h1 className="text-[46px] font-semibold leading-tight text-text">
                QA Agent Control Room
              </h1>
              <p className="text-sm text-textMuted">
                Trigger targeted runs per pull request or scan the entire queue.
              </p>
            </div>
            <div className="flex items-center gap-3 text-sm font-medium text-textMuted">
              <button type="button" onClick={onBack} className="hover:text-text">
                Back to tasks
              </button>
              <button
                type="button"
                onClick={onRefresh}
                className="inline-flex items-center gap-2 text-accent hover:text-accentMuted"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh data
              </button>
              <Button className="gap-2" onClick={onRunAll}>
                <Shield className="h-4 w-4" />
                Run all checks
              </Button>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-4">
            {[
              { label: 'Active PRs', value: aggregate.total, icon: <GitPullRequest className="h-4 w-4" /> },
              { label: 'Running', value: aggregate.running, icon: <Loader2 className="h-4 w-4 animate-spin text-accent" /> },
              { label: 'Cleared', value: aggregate.passed, icon: <CheckCircle2 className="h-4 w-4 text-success" /> },
              {
                label: 'Critical / Warn',
                value: aggregate.critical + aggregate.warnings,
                icon: <AlertTriangle className="h-4 w-4 text-warning" />,
              },
            ].map((stat) => (
              <div key={stat.label} className="flex items-center gap-3 text-sm text-textMuted">
                <div className="rounded-full bg-panelMuted p-3 text-textMuted">{stat.icon}</div>
                <div>
                  <p className="text-xs uppercase tracking-[0.35em]">{stat.label}</p>
                  <p className="text-2xl font-semibold text-text">{stat.value}</p>
                </div>
              </div>
            ))}
          </div>
        </header>

        <div className="rounded-2xl border border-border bg-panel p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-textMuted">
            Run timeline
          </p>
          <div className="mt-4 space-y-3">
            <div className="relative h-2 rounded-full bg-border">
              <div
                className="absolute h-full rounded-full bg-text"
                style={{ width: `${globalProgress}%` }}
              />
              <span
                className="absolute -top-1.5 h-4 w-4 rounded-full border-2 border-base bg-accent shadow-[0_0_0_3px_rgba(14,165,233,0.15)] animate-pulse"
                style={{ left: `calc(${globalProgress}% - 8px)` }}
              />
            </div>
            <div className="grid gap-3 text-xs text-textMuted md:grid-cols-5">
              {stepLabels.map((label, index) => (
                <div
                  key={label}
                  className={`rounded-lg border px-3 py-2 text-center ${
                    index <= activeStep ? 'border-accent text-text' : 'border-border'
                  }`}
                >
                  {label}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {pullRequests.map((pr) => {
            const run = agentRuns[pr.id] ?? defaultRunState;
            return (
              <article
                key={pr.id}
                className={`rounded-2xl border border-border bg-panel p-6 transition hover:-translate-y-[2px] hover:bg-panelMuted ${statusColor(run.status)}`}
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <span className="rounded-full bg-panelMuted px-3 py-1 text-xs font-semibold text-textMuted">
                        PR #{pr.number}
                      </span>
                      {statusBadge(run.status)}
                      <button
                        type="button"
                        onClick={() => setActive(pr.id)}
                        className="text-xs font-semibold text-accent hover:text-accentMuted"
                      >
                        View findings
                      </button>
                    </div>
                    <h3 className="text-xl font-semibold text-text">{pr.title}</h3>
                    <p className="text-sm text-textMuted">{pr.repository}</p>
                    <p className="text-xs text-textMuted">
                      Files touched {pr.filesChanged} · ± {pr.linesAdded} / {pr.linesRemoved}
                    </p>
                    <p className="text-xs font-semibold text-critical">
                      {pr.violations} violations
                    </p>
                  </div>
                  <div className="flex flex-col items-start gap-3 md:items-end">
                    <div className="flex items-center gap-3">
                      <Avatar
                        src={pr.author.avatar}
                        alt={pr.author.name}
                        fallback={pr.author.name.charAt(0)}
                      />
                      <div>
                        <p className="text-sm font-semibold text-text">{pr.author.name}</p>
                        <p className="text-xs text-textMuted">Engineer</p>
                      </div>
                    </div>
                    <div className="w-64">
                      <Progress value={run.progress} />
                      <p className="mt-2 text-xs text-textMuted">{run.currentStep}</p>
                    </div>
                    <Button
                      variant="outline"
                      onClick={() => onRunSingle(pr.id)}
                      disabled={run.status === 'running'}
                    >
                      {run.status === 'running' ? 'Running…' : 'Run Policy Check'}
                    </Button>
                  </div>
                </div>
              </article>
            );
          })}
          {!pullRequests.length && (
            <div className="rounded-2xl border border-dashed border-border bg-panel p-12 text-center text-textMuted">
              <GitPullRequest className="mx-auto mb-4 h-12 w-12 text-textMuted" />
              <p className="text-xl font-semibold text-text">No active pull requests</p>
              <p className="text-sm text-textMuted">
                PRs will appear here as soon as your team opens them.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
