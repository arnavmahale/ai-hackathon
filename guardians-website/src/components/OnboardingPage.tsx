import { useRef, useState } from 'react';
import { CloudUpload, Loader2, Trash2, Shield } from 'lucide-react';
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
    if (droppedFiles.length) onFilesAdded(droppedFiles);
  };

  const handleBrowse = () => inputRef.current?.click();
  const totalSize = files.reduce((sum, file) => sum + file.size, 0);

  return (
    <section className="mx-auto mt-8 max-w-6xl px-6 pb-20">
      <div className="rounded-[40px] border border-border bg-panel px-12 py-16 text-center shadow-[0_60px_160px_rgba(0,0,0,0.65)]">
        <div className="mb-6 inline-flex items-center gap-2 text-xs uppercase tracking-[0.5em] text-textMuted">
          <Shield className="h-4 w-4 text-text" />
          Guardians of the Code
        </div>
        <h1 className="text-[52px] font-semibold leading-[1.05] text-white">
          Upload your standards once.<br />Turn them into living QA policies.
        </h1>
        <p className="mx-auto mt-4 max-w-3xl text-base text-textMuted">
          Guardians ingests policy docs and transforms them into guardrails the agent enforces on every pull request.
        </p>
        <div className="mt-10 grid gap-6 text-left md:grid-cols-3">
          {[
            { label: 'Teams onboarded', value: '143' },
            { label: 'Policies enforced per repo', value: '50+' },
            { label: 'Violations caught weekly', value: '1,200' },
          ].map((stat) => (
            <div key={stat.label} className="rounded-2xl border border-border bg-panelMuted px-6 py-4">
              <p className="text-xs uppercase tracking-[0.4em] text-textMuted">{stat.label}</p>
              <p className="mt-2 text-2xl font-semibold text-text">{stat.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div
        className={`mt-12 rounded-[32px] border border-dashed border-border bg-panel px-10 py-12 text-center transition ${
          isDragging ? 'border-accent bg-panelMuted' : ''
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
        <CloudUpload className="mx-auto h-12 w-12 text-textMuted" />
        <h2 className="mt-4 text-2xl font-semibold text-text">Drag & drop documentation</h2>
        <p className="mt-2 text-sm text-textMuted">PDF · TXT · Markdown · DOCX · JSON</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3 text-sm text-textMuted">
          {['Security', 'Architecture', 'Runbooks', 'API Specs'].map((chip) => (
            <span key={chip} className="rounded-full border border-border px-4 py-1">
              {chip}
            </span>
          ))}
        </div>
        <Button className="mt-8" onClick={handleBrowse}>
          Browse files
        </Button>
      </div>

      <div className="mt-10 rounded-[32px] border border-border bg-panel p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-textMuted">
              {files.length
                ? `${files.length} files · ${(totalSize / 1024 / 1024).toFixed(2)} MB`
                : 'Add documentation to begin'}
            </p>
            <p className="text-lg font-semibold text-text">File queue</p>
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClearFiles}
              disabled={!files.length}
              className="text-sm font-medium text-accent transition hover:text-accentMuted disabled:cursor-not-allowed disabled:text-border"
            >
              Clear all
            </button>
            <Button onClick={onGenerateTasks} disabled={!files.length || isGenerating} className="gap-2">
              {isGenerating && <Loader2 className="h-4 w-4 animate-spin" />}
              Generate tasks
            </Button>
          </div>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-border">
          <table className="min-w-full border-collapse text-left text-sm text-text">
            <thead className="bg-panelMuted text-xs font-semibold uppercase tracking-[0.2em] text-textMuted">
              <tr>
                <th className="px-4 py-3">File name</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Progress</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-panel">
              {files.length ? (
                files.map((file) => (
                  <tr key={file.id} className="transition hover:bg-panelMuted/60">
                    <td className="px-4 py-3 text-text">{file.name}</td>
                    <td className="px-4 py-3 text-textMuted">{(file.size / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-3 text-textMuted">{file.status}</td>
                    <td className="px-4 py-3">
                      <Progress value={file.progress ?? 0} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        className="text-textMuted transition hover:text-critical"
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
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-textMuted">
                    No files uploaded yet. Drag files above to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {isGenerating && (
          <div className="mt-6 flex items-center gap-3 rounded-2xl border border-border bg-panelMuted px-4 py-3 text-sm text-text">
            <Loader2 className="h-4 w-4 animate-spin text-accent" />
            <div>
              <p className="font-medium">Analyzing documents…</p>
              <p className="text-xs text-textMuted">
                {generationState.currentStep} · File {generationState.processedFiles} of{' '}
                {generationState.totalFiles}
              </p>
            </div>
          </div>
        )}

        {showSuccess && (
          <div className="mt-6 flex items-center justify-between rounded-2xl border border-success/30 bg-panelMuted px-4 py-3 text-success">
            <div className="text-sm">Documents analyzed successfully. View tasks.</div>
            <Button variant="outline" onClick={onViewTasks}>
              View tasks
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
