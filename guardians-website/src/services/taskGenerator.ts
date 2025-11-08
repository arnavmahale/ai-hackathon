import axios from 'axios';
import type { Task } from '../types';
import { readFileAsText } from './documentParser';
import { MOCK_TASKS } from './mockData';

const OPENAI_API_KEY = import.meta.env.VITE_OPENAI_API_KEY;
const OPENAI_MODEL = import.meta.env.VITE_OPENAI_MODEL ?? 'gpt-4o-mini';

const SYSTEM_PROMPT = `You are an expert code quality engineer and standards architect.
Your job is to analyze company documentation and convert it into specific, actionable tasks
that an AI code quality agent can automatically check for in pull requests.

Important:
- Tasks must be MEASURABLE and SPECIFIC (not vague)
- Each task must be something an AI can programmatically detect
- Focus on patterns that prevent bugs, security issues, and technical debt
- Prioritize high-impact checks that catch 80% of common problems`;

const ANALYSIS_INSTRUCTIONS = `STEP 1: Extract Key Standards
First, read through ALL the provided documentation and extract:
- Naming conventions (camelCase, snake_case, PascalCase, etc.)
- Architecture patterns (MVC, microservices, layered, etc.)
- Error handling requirements
- Security policies (authentication, authorization, data protection)
- Performance requirements (response times, memory limits, etc.)
- Testing requirements (unit tests, integration tests, coverage %)
- Documentation requirements (docstrings, comments, README sections)
- Code style (indentation, line length, imports organization)

STEP 2: Generate Tasks
For each standard, create ONE task that is:
✓ SPECIFIC: Describes exactly what to check
✓ MEASURABLE: Can be detected with pattern matching or AST analysis
✓ ACTIONABLE: Developer can fix it in 5 minutes
✓ COMPLETE: Includes bad example AND good example

STEP 3: Return ONLY Valid JSON
Return exactly this format as a JSON array. No markdown, no explanations:
[
  {
    "id": "task_001",
    "title": "Enforce camelCase for function names",
    "description": "All function names must use camelCase (e.g., getUserData, calculateTotal). This improves code consistency and readability.",
    "category": "Code Quality",
    "severity": "warning",
    "checkType": "Naming Convention Pattern",
    "fileTypes": ["*.py", "*.js", "*.ts"],
    "exampleViolation": "def get_user_data():\\n    pass",
    "suggestedFix": "def getUserData():\\n    pass",
    "docReference": "Section: Naming Conventions in style-guide.md"
  },
  {
    "id": "task_002",
    "title": "All API endpoints must validate JWT tokens",
    "description": "Every API endpoint must verify JWT authentication before processing requests. This prevents unauthorized access.",
    "category": "Security",
    "severity": "critical",
    "checkType": "Security Pattern Detection",
    "fileTypes": ["*.py", "*.js", "*.go"],
    "exampleViolation": "@app.route('/api/users')\\ndef get_users():\\n    return users",
    "suggestedFix": "@app.route('/api/users')\\n@require_auth\\ndef get_users():\\n    return users",
    "docReference": "Section: API Security in security-guidelines.pdf"
  }
]

CRITICAL:
- Generate 8-12 tasks (not just 5, we need comprehensive coverage)
- Order by severity (critical first, then warning, then info)
- Make sure tasks are INDEPENDENT (don't duplicate checks)
- Each task should be doable by pattern matching or simple AST inspection
- Return VALID JSON only (no code blocks, no markdown)`;

const USER_PROMPT = (documentationContent: string) => `
Analyze the following company documentation and generate code quality tasks:

${documentationContent}

Remember:
1. Extract the KEY standards from the docs above
2. Create specific, measurable tasks
3. Return ONLY valid JSON array
4. No explanations, no markdown, just JSON
`;

function debugLog(...args: unknown[]) {
  if (import.meta.env.DEV) {
    console.debug('[taskGenerator]', ...args);
  }
}

function safeParseTasks(payload: string | undefined): Task[] {
  if (!payload) {
    debugLog('No payload received from OpenAI, falling back to mock tasks.');
    return MOCK_TASKS;
  }

  try {
    debugLog('Raw OpenAI payload:', payload);
    const data = JSON.parse(payload);
    if (Array.isArray(data)) {
      debugLog(`Parsed ${data.length} tasks from OpenAI response.`);
      return data as Task[];
    }
    debugLog('Parsed payload was not an array, using mock tasks.');
  } catch (error) {
    console.warn('[taskGenerator] Unable to parse OpenAI response, using mock tasks.', error);
  }

  return MOCK_TASKS;
}

export async function generateTasksFromDocuments(files: File[]): Promise<Task[]> {
  if (!files.length) {
    return MOCK_TASKS;
  }

  const serialized = await Promise.all(
    files.map(async (file) => {
      const content = await readFileAsText(file);
      debugLog('Including file in prompt:', {
        name: file.name,
        size: file.size,
        preview: content.slice(0, 200),
      });
      return `### ${file.name}\n${content}`;
    }),
  );

  const docs = serialized.join('\n\n');
  const userPrompt = `${ANALYSIS_INSTRUCTIONS}\n\n${USER_PROMPT(docs)}`;
  debugLog('Compiled prompt length (chars):', userPrompt.length);

  if (!OPENAI_API_KEY) {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    debugLog('No OpenAI API key set, returning mock tasks.');
    return MOCK_TASKS;
  }

  try {
    const response = await axios.post(
      'https://api.openai.com/v1/chat/completions',
      {
        model: OPENAI_MODEL,
        temperature: 0.2,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: userPrompt },
        ],
      },
      {
        headers: {
          Authorization: `Bearer ${OPENAI_API_KEY}`,
          'Content-Type': 'application/json',
        },
      },
    );

    const content = response.data?.choices?.[0]?.message?.content?.trim();
    return safeParseTasks(content);
  } catch (error) {
    console.error('[taskGenerator] OpenAI API failed, falling back to mock tasks.', error);
    return MOCK_TASKS;
  }
}
