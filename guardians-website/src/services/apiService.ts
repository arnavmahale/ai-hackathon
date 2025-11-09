import type { PullRequest, Task, TaskSetMetadata } from '../types';
import { MOCK_PRS } from './mockData';

const API_BASE_URL = import.meta.env.VITE_GUARDIANS_API_URL;
const API_TOKEN = import.meta.env.VITE_GUARDIANS_API_TOKEN;
const hasApi = Boolean(API_BASE_URL);

export async function fetchPullRequests(): Promise<PullRequest[]> {
  if (!hasApi) {
    return new Promise((resolve) =>
      setTimeout(() => resolve(MOCK_PRS), 450),
    );
  }

  try {
    const response = await fetch(`${API_BASE_URL}/pull-requests`);
    if (!response.ok) {
      throw new Error('Failed to fetch pull requests');
    }
    const data = await response.json();
    return data.items ?? [];
  } catch (error) {
    console.warn('[apiService] Falling back to mock PRs:', error);
    return MOCK_PRS;
  }
}

export async function refreshPullRequest(
  prId: string,
): Promise<PullRequest | undefined> {
  const prs = await fetchPullRequests();
  return prs.find((pr) => pr.id === prId);
}

export function exportTasksAsJson(tasks: Task[]): string {
  const blob = new Blob([JSON.stringify(tasks, null, 2)], {
    type: 'application/json',
  });
  return URL.createObjectURL(blob);
}

export async function saveTaskSet(tasks: Task[]): Promise<TaskSetMetadata | null> {
  if (!hasApi) {
    console.info('[apiService] No API base URL configured; skipping task sync.');
    return null;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/tasks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
      },
      body: JSON.stringify({ tasks }),
    });

    if (!response.ok) {
      throw new Error(`Failed to save task set (${response.status})`);
    }

    const payload = await response.json();
    return normalizeTaskMetadata(payload);
  } catch (error) {
    console.warn('[apiService] Unable to persist task set:', error);
    return null;
  }
}

function normalizeTaskMetadata(payload: any): TaskSetMetadata {
  return {
    taskSetId: payload.task_set_id,
    createdAt: payload.created_at,
    taskCount: payload.task_count,
    path: payload.path,
  };
}

export async function fetchLatestTaskSet(): Promise<{ tasks: Task[]; metadata: TaskSetMetadata } | null> {
  if (!hasApi) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/tasks/current`);
    if (!response.ok) {
      throw new Error(`Failed to fetch current tasks (${response.status})`);
    }
    const payload = await response.json();
    return {
      tasks: payload.tasks,
      metadata: normalizeTaskMetadata(payload.metadata),
    };
  } catch (error) {
    console.warn('[apiService] Unable to fetch latest task set:', error);
    return null;
  }
}
