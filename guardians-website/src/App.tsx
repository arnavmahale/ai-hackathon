import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigation } from './components/Navigation';
import { OnboardingPage } from './components/OnboardingPage';
import { TasksDashboard } from './components/TasksDashboard';
import { PRMonitor } from './components/PRMonitor';
import type {
  AgentRunState,
  AgentRunSummary,
  AppState,
  GenerationState,
  PageKey,
  PullRequest,
  Task,
  TaskSetMetadata,
  UploadedFile,
} from './types';
import { generateTasksFromDocuments } from './services/taskGenerator';
import { fetchLatestTaskSet, fetchPullRequests, saveTaskSet } from './services/apiService';
import { MOCK_PRS, MOCK_TASKS } from './services/mockData';

const initialState: AppState = {
  uploadedFiles: [],
  tasks: MOCK_TASKS,
  pullRequests: [],
  currentPage: 'onboarding',
};

const generateId = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2));

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const defaultAgentRunState: AgentRunState = {
  status: 'idle',
  progress: 0,
  currentStep: 'Awaiting QA run',
};

function App() {
  const [state, setState] = useState<AppState>(initialState);
  const [fileLibrary, setFileLibrary] = useState<Record<string, File>>({});
  const [generationState, setGenerationState] = useState<GenerationState>({
    isRunning: false,
    currentStep: 'Idle',
    processedFiles: 0,
    totalFiles: 0,
  });
  const [showSuccess, setShowSuccess] = useState(false);
  const [agentRuns, setAgentRuns] = useState<Record<string, AgentRunState>>({});
  const [taskSetMetadata, setTaskSetMetadata] = useState<TaskSetMetadata | null>(null);
  const uploadTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const ensureAgentRuns = (prs: PullRequest[]) => {
    setAgentRuns((prev) => {
      let changed = false;
      const next = { ...prev };
      prs.forEach((pr) => {
        if (!next[pr.id]) {
          next[pr.id] = { ...defaultAgentRunState };
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  };

  useEffect(() => {
    void hydrateTasks();
    fetchPullRequests()
      .then((prs) => {
        setState((prev) => ({
          ...prev,
          pullRequests: prs,
        }));
        ensureAgentRuns(prs);
      })
      .catch(() => {
        setState((prev) => ({
          ...prev,
          pullRequests: MOCK_PRS,
        }));
        ensureAgentRuns(MOCK_PRS);
      });
  }, []);

  useEffect(() => {
    if (state.pullRequests.length) {
      ensureAgentRuns(state.pullRequests);
    }
  }, [state.pullRequests]);

  useEffect(
    () => () => {
      Object.values(uploadTimers.current).forEach((timer) => clearInterval(timer));
    },
    [],
  );

  const simulateUpload = (fileId: string) => {
    const timer = setInterval(() => {
      let shouldStop = false;
      setState((prev) => {
        const uploadedFiles = prev.uploadedFiles.map((file) => {
          if (file.id !== fileId) return file;
          const nextProgress = Math.min((file.progress ?? 0) + 15, 100);
          if (nextProgress >= 100) {
            shouldStop = true;
          }
          return {
            ...file,
            progress: nextProgress,
            status: nextProgress >= 100 ? 'complete' : file.status,
          };
        });
        return { ...prev, uploadedFiles };
      });
      if (shouldStop) {
        clearInterval(timer);
        delete uploadTimers.current[fileId];
      }
    }, 300);

    uploadTimers.current[fileId] = timer;
  };

  const addFiles = (files: File[]) => {
    if (!files.length) return;
    setShowSuccess(false);
    const payload: UploadedFile[] = files.map((file) => {
      const id = generateId();
      return {
        id,
        name: file.name,
        type: file.type || 'text/plain',
        size: file.size,
        status: 'uploading',
        progress: 5,
      };
    });

    setState((prev) => ({
      ...prev,
      uploadedFiles: [...prev.uploadedFiles, ...payload],
    }));
    setFileLibrary((prev) => {
      const next = { ...prev };
      payload.forEach((meta, index) => {
        next[meta.id] = files[index];
        simulateUpload(meta.id);
      });
      return next;
    });
  };

  const removeFile = (fileId: string) => {
    clearInterval(uploadTimers.current[fileId]);
    delete uploadTimers.current[fileId];
    setState((prev) => ({
      ...prev,
      uploadedFiles: prev.uploadedFiles.filter((file) => file.id !== fileId),
    }));
    setFileLibrary((prev) => {
      const next = { ...prev };
      delete next[fileId];
      return next;
    });
  };

  const clearFiles = () => {
    Object.keys(uploadTimers.current).forEach((key) => clearInterval(uploadTimers.current[key]));
    uploadTimers.current = {};
    setState((prev) => ({ ...prev, uploadedFiles: [] }));
    setFileLibrary({});
    setShowSuccess(false);
  };

  const clearTasks = () => {
    setState((prev) => ({
      ...prev,
      tasks: [],
      currentPage: 'onboarding',
    }));
    setShowSuccess(false);
  };

  const navigate = (page: PageKey) => {
    setState((prev) => ({ ...prev, currentPage: page }));
  };

  const syncTasksToBackend = async (tasks: Task[]) => {
    const metadata = await saveTaskSet(tasks);
    if (metadata) {
      setTaskSetMetadata(metadata);
    }
  };

  const hydrateTasks = async () => {
    const latest = await fetchLatestTaskSet();
    if (latest) {
      setState((prev) => ({
        ...prev,
        tasks: latest.tasks,
      }));
      setTaskSetMetadata(latest.metadata);
    }
  };

  const handleGenerateTasks = async () => {
    if (generationState.isRunning) return;
    const files = state.uploadedFiles
      .map((file) => fileLibrary[file.id])
      .filter((file): file is File => Boolean(file));
    if (!files.length) return;

    setGenerationState({
      isRunning: true,
      currentStep: 'Analyzing documents...',
      processedFiles: 0,
      totalFiles: files.length,
    });

    files.forEach((_, index) => {
      setTimeout(() => {
        setGenerationState((prev) => ({
          ...prev,
          processedFiles: Math.min(index + 1, files.length),
        }));
      }, (index + 1) * 500);
    });

    const tasks = await generateTasksFromDocuments(files);
    setState((prev) => ({
      ...prev,
      tasks,
      currentPage: 'tasks',
    }));
    setGenerationState({
      isRunning: false,
      currentStep: 'Complete',
      processedFiles: files.length,
      totalFiles: files.length,
    });
    setShowSuccess(true);

    void syncTasksToBackend(tasks);
  };

  const handleRefreshTasks = () => {
    setState((prev) => ({
      ...prev,
      tasks: [...prev.tasks],
    }));
  };

  const handleStartMonitoring = () => navigate('monitor');

  const handleRefreshPRs = async () => {
    try {
      const prs = await fetchPullRequests();
      setState((prev) => ({ ...prev, pullRequests: prs }));
      ensureAgentRuns(prs);
      return prs;
    } catch (error) {
      console.warn('Failed to refresh PRs, using mock data.', error);
      setState((prev) => ({ ...prev, pullRequests: MOCK_PRS }));
      ensureAgentRuns(MOCK_PRS);
      return MOCK_PRS;
    }
  };

  const summarizeRun = (pr: PullRequest): AgentRunSummary => {
    return {
      totalChecks: state.tasks.length || 8,
      violations: pr.violations,
      severity: pr.status,
      notes:
        pr.status === 'ready'
          ? 'No violations detected across required tasks.'
          : `Detected ${pr.violations} violation(s) tied to ${pr.violationDetails.length} tasks.`,
    };
  };

  const startAgentRunForPr = async (prId: string) => {
    const pr = state.pullRequests.find((item) => item.id === prId);
    if (!pr) return;

    setAgentRuns((prev) => {
      const current = prev[prId] ?? { ...defaultAgentRunState };
      if (current.status === 'running') return prev;
      return {
        ...prev,
        [prId]: {
          ...current,
          status: 'running',
          progress: 5,
          currentStep: 'Queueing run',
          startedAt: new Date().toISOString(),
          completedAt: undefined,
          summary: undefined,
        },
      };
    });

    const timeline = [
      { progress: 25, step: 'Loading repository snapshot' },
      { progress: 45, step: 'Aligning docs → task matrix' },
      { progress: 65, step: 'Scanning files for violations' },
      { progress: 85, step: 'Scoring checks & preparing report' },
    ];

    for (const stage of timeline) {
      await wait(800);
      setAgentRuns((prev) => {
        const current = prev[prId];
        if (!current || current.status !== 'running') return prev;
        return {
          ...prev,
          [prId]: {
            ...current,
            progress: stage.progress,
            currentStep: stage.step,
          },
        };
      });
    }

    const summary = summarizeRun(pr);
    const finalStatus: AgentRunState['status'] =
      pr.status === 'ready'
        ? 'passed'
        : pr.status === 'violations'
          ? 'warnings'
          : 'critical';

    await wait(600);

    setAgentRuns((prev) => {
      const current = prev[prId];
      if (!current) return prev;
      return {
        ...prev,
        [prId]: {
          ...current,
          status: finalStatus,
          progress: 100,
          currentStep: 'Run complete',
          completedAt: new Date().toISOString(),
          summary,
        },
      };
    });
  };

  const startAgentRunForAll = () => {
    state.pullRequests.forEach((pr, index) => {
      setTimeout(() => {
        void startAgentRunForPr(pr.id);
      }, index * 250);
    });
  };

  const currentPage = useMemo(() => {
    switch (state.currentPage) {
      case 'tasks':
        return (
          <TasksDashboard
            tasks={state.tasks}
            onBack={() => navigate('onboarding')}
            onRefresh={handleRefreshTasks}
            onClearTasks={clearTasks}
            onStartMonitoring={handleStartMonitoring}
          />
        );
      case 'monitor':
        return (
          <PRMonitor
            pullRequests={state.pullRequests}
            agentRuns={agentRuns}
            onRunAll={startAgentRunForAll}
            onRunSingle={startAgentRunForPr}
            onBack={() => navigate('tasks')}
            onRefresh={handleRefreshPRs}
          />
        );
      default:
        return (
          <OnboardingPage
            files={state.uploadedFiles}
            onFilesAdded={addFiles}
            onRemoveFile={removeFile}
            onClearFiles={clearFiles}
            onGenerateTasks={handleGenerateTasks}
            onViewTasks={() => navigate('tasks')}
            isGenerating={generationState.isRunning}
            generationState={generationState}
            showSuccess={showSuccess}
          />
        );
    }
  }, [state, generationState, showSuccess, agentRuns]);

  return (
    <div className="min-h-screen bg-base font-inter text-text">
      <Navigation currentPage={state.currentPage} onNavigate={navigate} />
      <main className="bg-base">{currentPage}</main>
    </div>
  );
}

export default App;
