import { useRef, useState } from 'react';
import { CloudUpload, Loader2, Trash2, ShieldCheck, CheckCircle2 } from 'lucide-react';
import type { GenerationState, UploadedFile } from '../types';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';

interface OnboardingPageProps {
  files: UploadedFile[];
  onFilesAdded: (files: File[]) => void;
  onRemoveFile: (id: string) => void;
  onClearFiles: () => void;
  onGenerateTasks: () => void;
  onViewTasks: () => void;
  isGenerating: boolean;
  generationState: GenerationState;
  showSuccess: boolean;
}

export function OnboardingPage({
  files,
  onFilesAdded,
  onRemoveFile,
  onClearFiles,
  onGenerateTasks,
  onViewTasks,
  isGenerating,
  generationState,
  showSuccess,
}: OnboardingPageProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(event.dataTransfer.files || []);
    if (droppedFiles.length) {
      onFilesAdded(droppedFiles);
    }
  };

  const handleBrowse = () => inputRef.current?.click();

  const totalSize = files.reduce((sum, file) => sum + file.size, 0);

  return (
    <section className="mx-auto mt-10 max-w-6xl px-6 pb-16">
      <header className="grid gap-8 rounded-[32px] border border-slate-100 bg-panel px-10 py-8 shadow-card md:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <p className="text-xs uppercase tracking-[0.45em] text-slate-400">Step 1 · Intake</p>
          <h1 className="text-[44px] font-semibold leading-tight text-graphite">
            Upload documentation. Generate the playbook.
          </h1>
          <p className="text-base text-slate-500">
            Guardians ingests your policy docs and converts them into enforceable QA guardrails across
            every pull request.
          </p>
          <div className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-500">
            <ShieldCheck className="h-4 w-4 text-accent" />
            Enforcing 50+ policy rules per repo
          </div>
        </div>
        <div className="self-start rounded-2xl border border-slate-100 bg-white/80 px-6 py-5 text-center shadow-card-soft">
          <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Upload queue</p>
          <p className="mt-3 text-[36px] font-semibold text-graphite">{files.length}</p>
          <p className="text-sm text-slate-500">
            {files.length
              ? `${(totalSize / 1024 / 1024).toFixed(2)} MB staged`
              : 'Drop policy docs to begin'}
          </p>
        </div>
      </header>

      <div
        className={`mt-10 rounded-[32px] border border-dashed border-slate-200 bg-white px-10 py-12 text-center shadow-card transition ${
          isDragging ? 'border-accent bg-slate-50' : ''
        }`}
        onDrop={handleDrop}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.txt,.md,.docx,.json"
          onChange={(event) => {
            const list = event.target.files;
            if (list) {
              onFilesAdded(Array.from(list));
              event.target.value = '';
            }
          }}
        />
        <CloudUpload className="mx-auto h-12 w-12 text-slate-400" />
        <h2 className="mt-4 text-2xl font-semibold text-graphite">
          Drag & drop documentation
        </h2>
        <p className="mt-2 text-sm text-slate-500">PDF · TXT · Markdown · DOCX · JSON</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {['Security', 'Architecture', 'Runbooks', 'API Specs'].map((chip) => (
            <span
              key={chip}
              className="rounded-full border border-slate-200 px-4 py-1 text-sm font-medium text-slate-500"
            >
              {chip}
            </span>
          ))}
        </div>
        <Button className="mt-8" onClick={handleBrowse}>
          Browse files
        </Button>
      </div>

      <div className="mt-10 rounded-[32px] border border-slate-100 bg-panel p-6 shadow-card">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-slate-500">
              {files.length
                ? `${files.length} files • ${(totalSize / 1024 / 1024).toFixed(2)} MB`
                : 'Add documentation to begin'}
            </p>
            <p className="text-lg font-semibold text-graphite">File queue</p>
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClearFiles}
              disabled={!files.length}
              className="text-sm font-medium text-accent transition hover:text-accentMuted disabled:cursor-not-allowed disabled:text-slate-300"
            >
              Clear all
            </button>
            <Button
              onClick={onGenerateTasks}
              disabled={!files.length || isGenerating}
              className="gap-2"
            >
              {isGenerating && <Loader2 className="h-4 w-4 animate-spin" />}
              Generate tasks
            </Button>
          </div>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-slate-100">
          <table className="min-w-full border-collapse text-left text-sm text-graphite">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              <tr>
                <th className="px-4 py-3">File name</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Progress</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white text-slate-600">
              {files.length ? (
                files.map((file) => (
                  <tr key={file.id} className="transition hover:bg-slate-50/80">
                    <td className="px-4 py-3 text-graphite">{file.name}</td>
                    <td className="px-4 py-3">{(file.size / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-3 py-0.5 text-xs font-semibold ${
                          file.status === 'complete'
                            ? 'bg-success/10 text-success'
                            : file.status === 'error'
                              ? 'bg-critical/10 text-critical'
                              : 'bg-warning/10 text-warning'
                        }`}
                      >
                        {file.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Progress value={file.progress ?? 0} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        className="text-slate-400 transition hover:text-critical"
                        onClick={() => onRemoveFile(file.id)}
                        aria-label={`Remove ${file.name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-slate-500">
                    No files uploaded yet. Drag files above to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {isGenerating && (
          <div className="mt-6 flex items-center gap-3 rounded-2xl border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-accent">
            <Loader2 className="h-4 w-4 animate-spin" />
            <div>
              <p className="font-medium">Analyzing documents…</p>
              <p className="text-xs text-slate-500">
                {generationState.currentStep} · File {generationState.processedFiles} of{' '}
                {generationState.totalFiles}
              </p>
            </div>
          </div>
        )}

        {showSuccess && (
          <div className="mt-6 flex items-center justify-between rounded-2xl border border-success/30 bg-success/5 px-4 py-3 text-success">
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4" />
              Documents analyzed successfully. View all generated tasks.
            </div>
            <Button variant="outline" onClick={onViewTasks}>
              View tasks
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
