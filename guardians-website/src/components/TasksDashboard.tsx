import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  RefreshCw,
  Play,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import type { Task, TaskCategory } from '../types';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { exportTasksAsJson } from '../services/apiService';

interface TasksDashboardProps {
  tasks: Task[];
  onBack: () => void;
  onRefresh: () => void;
  onClearTasks: () => void;
  onStartMonitoring: () => void;
}

const categoryFilters: Array<{ label: string; value: TaskCategory | 'All' }> = [
  { label: 'All', value: 'All' },
  { label: 'Code Quality', value: 'Code Quality' },
  { label: 'Security', value: 'Security' },
  { label: 'Performance', value: 'Performance' },
  { label: 'Documentation', value: 'Documentation' },
];

const severityFilters: Array<{ label: string; value: 'all' | Task['severity'] }> = [
  { label: 'All severities', value: 'all' },
  { label: 'Critical', value: 'critical' },
  { label: 'Warning', value: 'warning' },
  { label: 'Info', value: 'info' },
];

const severityBorder: Record<Task['severity'], string> = {
  critical: 'before:bg-critical',
  warning: 'before:bg-warning',
  info: 'before:bg-border',
};

export function TasksDashboard({
  tasks,
  onBack,
  onRefresh,
  onClearTasks,
  onStartMonitoring,
}: TasksDashboardProps) {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<TaskCategory | 'All'>('All');
  const [severity, setSeverity] = useState<'all' | Task['severity']>('all');
  const [expandedTask, setExpandedTask] = useState<string | null>(null);

  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      const matchesSearch =
        task.title.toLowerCase().includes(search.toLowerCase()) ||
        task.description.toLowerCase().includes(search.toLowerCase());
      const matchesCategory = filter === 'All' || task.category === filter;
      const matchesSeverity = severity === 'all' || task.severity === severity;
      return matchesSearch && matchesCategory && matchesSeverity;
    });
  }, [tasks, search, filter, severity]);

  const criticalCount = tasks.filter((task) => task.severity === 'critical').length;
  const categoriesCovered = new Set(tasks.map((task) => task.category)).size;

  const handleExport = () => {
    const url = exportTasksAsJson(tasks);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'guardians_tasks.json';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="mx-auto mt-10 max-w-6xl px-6 pb-16 text-text">
      <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.45em] text-textMuted">Step 2 · Tasks</p>
          <h1 className="text-[46px] font-semibold leading-tight text-text">Generated Tasks</h1>
          <p className="text-base text-textMuted">
            Fine-tune the QA rules before they go live across every pull request.
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm font-medium text-textMuted">
          <button type="button" onClick={onBack} className="hover:text-text">
            Back
          </button>
          <button type="button" onClick={onClearTasks} className="hover:text-text">
            Clear tasks
          </button>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-2 text-accent hover:text-accentMuted"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </header>

      <div className="mt-10 grid gap-4 md:grid-cols-[2fr_1fr_1fr]">
        <div className="rounded-2xl border border-border bg-panel p-6">
          <p className="text-xs uppercase tracking-[0.35em] text-textMuted">Total tasks</p>
          <p className="mt-3 text-[46px] font-semibold text-text">{tasks.length}</p>
          <p className="text-sm text-textMuted">Rules ready for automation</p>
        </div>
        <div className="rounded-2xl border border-border bg-panel p-6">
          <p className="text-xs uppercase tracking-[0.35em] text-textMuted">Critical issues</p>
          <p className="mt-3 text-[34px] font-semibold text-text">{criticalCount}</p>
          <p className="text-sm text-textMuted">Blocks launches if failing</p>
        </div>
        <div className="rounded-2xl border border-border bg-panel p-6">
          <p className="text-xs uppercase tracking-[0.35em] text-textMuted">Categories</p>
          <p className="mt-3 text-[34px] font-semibold text-text">{categoriesCovered}</p>
          <p className="text-sm text-textMuted">Policy surfaces covered</p>
        </div>
      </div>

      <div className="my-8 h-px bg-border" />

      <div className="flex flex-col gap-4 rounded-2xl border border-border bg-panel p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-1 items-center gap-3 rounded-xl border border-border bg-panelMuted px-4 py-2.5">
            <Search className="h-4 w-4 text-textMuted" />
            <input
              type="text"
              placeholder="Search tasks, descriptions, doc references..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="w-full border-none bg-transparent text-sm text-text placeholder:text-textMuted focus:outline-none"
            />
          </div>
          <div className="flex flex-wrap gap-2 text-sm font-medium">
            {categoryFilters.map((pill) => {
              const active = filter === pill.value;
              return (
                <button
                  key={pill.value}
                  type="button"
                  onClick={() => setFilter(pill.value)}
                  className={`rounded-full border px-4 py-1.5 transition ${
                    active
                      ? 'border-accent bg-accent/20 text-text'
                      : 'border-border text-textMuted hover:text-text'
                  }`}
                >
                  {pill.label}
                </button>
              );
            })}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleExport}
              className="text-sm font-semibold text-accent transition hover:text-accentMuted"
            >
              Export JSON
            </button>
            <Button className="gap-2" onClick={onStartMonitoring}>
              <Play className="h-4 w-4" />
              Begin QA Scan
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-sm font-medium text-textMuted">
          {severityFilters.map((pill) => {
            const active = severity === pill.value;
            return (
              <button
                key={pill.value}
                type="button"
                onClick={() => setSeverity(pill.value)}
                className={`rounded-full border px-4 py-1.5 transition ${
                  active
                    ? 'border-accent bg-accent/20 text-text'
                    : 'border-border text-textMuted hover:text-text'
                }`}
              >
                {pill.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-10 space-y-4">
        <AnimatePresence>
          {filteredTasks.length ? (
            filteredTasks.map((task) => {
              const isExpanded = expandedTask === task.id;
              return (
                <motion.article
                  key={task.id}
                  initial={{ opacity: 0, translateY: 8 }}
                  animate={{ opacity: 1, translateY: 0 }}
                  exit={{ opacity: 0, translateY: -8 }}
                  className={`relative overflow-hidden rounded-2xl border border-border bg-panel p-6 transition hover:-translate-y-[2px] hover:bg-panelMuted ${severityBorder[task.severity]} before:absolute before:left-0 before:top-0 before:h-full before:w-1.5`}
                >
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="text-2xl font-semibold text-text">{task.title}</h3>
                        <Badge variant="outline">{task.category}</Badge>
                      </div>
                      <p className="mt-3 text-sm text-textMuted">{task.description}</p>
                      <p className="mt-4 text-xs font-semibold uppercase tracking-[0.3em] text-textMuted">
                        {task.checkType}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs font-mono text-textMuted">
                        {task.fileTypes.map((ext) => (
                          <span key={ext} className="rounded bg-panelMuted px-3 py-1">
                            {ext}
                          </span>
                        ))}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setExpandedTask(isExpanded ? null : task.id)}
                      className="text-sm font-semibold text-accent transition hover:text-accentMuted"
                    >
                      {isExpanded ? 'Hide details' : 'View details'}
                    </button>
                  </div>

                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                      >
                        <div className="mt-6 grid gap-4 rounded-xl border border-border bg-panelMuted p-5 md:grid-cols-2">
                          <div>
                            <p className="flex items-center gap-2 text-sm font-semibold text-critical">
                              <AlertTriangle className="h-4 w-4" />
                              Example violation
                            </p>
                            <pre className="mt-2 whitespace-pre-wrap font-mono text-[13px] text-textMuted">
                              {task.exampleViolation}
                            </pre>
                          </div>
                          <div>
                            <p className="flex items-center gap-2 text-sm font-semibold text-success">
                              <CheckCircle2 className="h-4 w-4" />
                              Suggested fix
                            </p>
                            <pre className="mt-2 whitespace-pre-wrap font-mono text-[13px] text-textMuted">
                              {task.suggestedFix}
                            </pre>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.article>
              );
            })
          ) : (
            <motion.div
              initial={{ opacity: 0, translateY: 8 }}
              animate={{ opacity: 1, translateY: 0 }}
              className="rounded-2xl border border-dashed border-border bg-panel p-12 text-center text-textMuted"
            >
              No tasks match the current filters.
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
