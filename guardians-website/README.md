## Guardians of the Code

An end-to-end React + TypeScript control center for enterprise code-quality operations. The app walks security teams through three steps:

1. **Onboarding / Upload** – drag-drop documentation, monitor upload progress, and kick off AI task generation.
2. **Tasks Dashboard** – review structured QA tasks, slice by category/severity, and export JSON for agents.
3. **PR Monitor** – track live GitHub pull requests, inspect violations, and trigger remediation actions.

### Tech Stack

- React 19 + TypeScript + Vite  
- Tailwind CSS with an enterprise design kit (navy/blue palette, Inter typography)  
- Lucide icons, shadcn-style primitives (`Button`, `Badge`, `Avatar`, `Progress`)  
- Axios for OpenAI integration (with mock fallbacks)

### Getting Started

```bash
npm install
npm run dev
```

Visit http://localhost:5173 to use the experience.

### Environment Variables

Create a `.env` file with the following if you want to call OpenAI:

```
VITE_OPENAI_API_KEY=sk-...
VITE_OPENAI_MODEL=gpt-4o-mini
```

Without credentials, the UI automatically falls back to curated mock data (`MOCK_TASKS` / `MOCK_PRS`) so the flow still works.

### Project Structure

```
src/
├── App.tsx                # State orchestration & page routing
├── components/            # Navigation, Onboarding, TasksDashboard, PRMonitor
├── services/              # taskGenerator (OpenAI) + mock/api helpers
├── types/                 # Shared TypeScript interfaces
├── ui/                    # Reusable shadcn-inspired primitives
├── lib/utils.ts           # Tailwind class merger helper
└── index.tsx/css          # App bootstrap + Tailwind directives
```

### How the Flow Works

1. **Upload Center** – Files land in a queue with live progress. Clicking *Generate Tasks* reads file contents, combines them into the OpenAI prompt, and displays a progress tracker.
2. **Task Generation** – `services/taskGenerator.ts` calls OpenAI Chat Completions (or the mock list) and normalizes the JSON into the `Task[]` shape.
3. **Tasks Dashboard** – Tasks are summarized in stat cards, filterable search pills, and expandable cards with violations/fixes. Export produces a JSON blob for downstream agents.
4. **PR Monitor** – Uses `fetchPullRequests` (mock today) to display GitHub stats, author avatars, violation details, and remediation actions.

### Responsive Design

The layout relies entirely on Tailwind utility classes with a custom theme in `tailwind.config.js`. All cards, pills, and nav elements collapse gracefully down to mobile breakpoints while preserving the enterprise aesthetic.

### Next Steps

- Wire `fetchPullRequests` to your GitHub API.
- Persist uploads/task history in a backend store.
- Replace mock violation actions with real GitHub Automation (merge/comment webhooks).

Guardians of the Code is production-ready for demos and can be extended to power your full RAG + task generation pipeline.
