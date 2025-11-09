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
| `GUARDIANS_DATA_DIR` | Custom path for persisted JSON (defaults to `backend/data/`). |
| `GUARDIANS_API_TOKEN` | If set, write endpoints require `Authorization: Bearer <token>`. |

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
