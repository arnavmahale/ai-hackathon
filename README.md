# ai-hackathon

## Code guardian validator

`validate_code.py` loads a task definition file and runs a battery of checks over any files you pass in. The repository now understands both the original rules-based format (`{"rules": [...]}`) and the Guardian sample file (`guardians_tasks.json`) that lists compliance tasks directly.

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
