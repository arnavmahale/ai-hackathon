import type { PullRequest, Task } from '../types';
import { MOCK_PRS } from './mockData';

export async function fetchPullRequests(): Promise<PullRequest[]> {
  return new Promise((resolve) =>
    setTimeout(() => resolve(MOCK_PRS), 450),
  );
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
