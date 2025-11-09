# ai-hackathon

## Code guardian validator

`validate_code.py` loads a task definition file and runs a battery of checks over any files you pass in. The repository now understands both the original rules-based format (`{"rules": [...]}`) and the Guardian sample file (`guardians_tasks.json`) that lists compliance tasks directly.

## Guardians API backend

The `backend/` directory hosts a FastAPI service that stores generated tasks, pull-request metadata, and agent run results. To run it locally:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Optional environment variables:

| Variable | Purpose |
| --- | --- |
| `GUARDIANS_DATA_DIR` | Base folder for data files (default `backend/data/`). |
| `GUARDIANS_API_TOKEN` | If set, write endpoints require `Authorization: Bearer <token>`. |
| `DATABASE_URL` | SQL database connection string (defaults to `sqlite:///backend/data/guardians.db`). |
| `GITHUB_WEBHOOK_SECRET` | Secret for verifying GitHub webhook signatures (falls back to `GUARDIANS_API_TOKEN`). |
| `GITHUB_ACCESS_TOKEN` | PAT/installation token used to call GitHub’s REST API for PR files. |

### GitHub Action integration

`.github/workflows/pr_trigger.yaml` now posts PR metadata to the Guardians API whenever a pull request is opened/reopened/synchronized. Configure these repo secrets so the workflow can reach your backend:

| Secret | Description |
| --- | --- |
| `GUARDIANS_API_URL` | Base URL to the FastAPI server (e.g., `https://guardians.example.com`). |
| `GUARDIANS_API_TOKEN` | Bearer token matching the backend’s `GUARDIANS_API_TOKEN` (optional if auth disabled). |

The workflow sends payloads like:

```json
{
  "repo": "acme/project",
  "pr_number": 128,
  "title": "Refactor logging pipeline",
  "author": "ava-martinez",
  "baseBranch": "main",
  "headBranch": "feature/logging",
  "filesChanged": 12,
  "linesAdded": 542,
  "linesRemoved": 132,
  "changedFiles": ["src/log/logger.ts", "..."]
}
```

The backend persists that data so the React PR monitor can fetch `/pull-requests` and `/pull-requests/{id}` for live statuses once the agent runs are wired up.

### GitHub Webhook (alternative to Actions)

If you prefer direct webhooks, deploy the FastAPI service (e.g., Render) and add a repo webhook pointing to:

- **Payload URL:** `https://your-backend/github/webhook`
- **Content type:** `application/json`
- **Secret:** any string; set the same value in the backend env var `GITHUB_WEBHOOK_SECRET` (falls back to `GUARDIANS_API_TOKEN` if unset)
- **Events:** “Let me select” → “Pull requests”

The `/github/webhook` route only processes `opened`, `reopened`, or `synchronize` actions, verifies the signature, and stores the PR data just like the Action step. Use ngrok for local testing if needed (`ngrok http 8000` then register the HTTPS URL as the payload endpoint).

To capture the per-file list for agent runs, set `GITHUB_ACCESS_TOKEN` (PAT or GitHub App token with `repo` scope). The webhook handler calls `GET /repos/{owner}/{repo}/pulls/{number}/files` behind the scenes, immediately enriches the payload, and stores only the **final scan record** (metadata + violations) in the database specified by `DATABASE_URL`. You can inspect the consolidated records via:

- `GET /pull-requests` (JSON)
- `GET /pull-requests/{repo}#PR-{number}` (if calling manually, encode the `#` as `%23`; slashes are now handled by the route)
- `GET /debug/pull-requests` (HTML table)

Because we persist only the finished scan rows (or pending placeholders), you never have to read intermediate JSON files—everything lives in the SQL database (Postgres on Render or SQLite locally).

> **Breaking change:** If you were using the previous `pullrequest`/`agentrun` tables, drop/recreate the database (or start a new one). The schema now centers on a single `scanresult` table that stores both the PR metadata and the latest agent findings.

### Running the validator

```bash
python validate_code.py --tasks guardians_tasks.json --files path/to/changed/file.py
```

You can also validate a git diff instead of explicit paths:

```bash
python validate_code.py --tasks guardians_tasks.json --git-diff origin/main HEAD
```

Add `--out-file report.txt` if you want the formatted report (which now includes a "Tasks Passed: X/Y" summary line plus the names of the tasks that passed) written to disk instead of the terminal. If you point `--out-file` at a `.json` path (e.g., `--out-file report.json`), the script automatically emits the JSON payload even without `--json`.

### Built-in task types

The script currently supports:

- JWT auth enforcement on API routes (decorator analysis and JS/Go heuristics)
- Mandatory exception logging inside `try/except`
- Minimum coverage threshold extracted from reports (e.g., `Coverage: 78%`)
- Function length limit, cyclomatic complexity limit, and camelCase enforcement
- PascalCase class names, `UPPER_SNAKE_CASE` constants, kebab-case filenames
- Required docstrings for every function definition

Extend `guardians_tasks.json` or create your own tasks file to fine-tune messages, file globs, and thresholds.
