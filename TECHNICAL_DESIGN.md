# Guardians: AI-Powered Code Compliance System — Technical Design Document

**Author:** Daniel
**Project:** Guardians (AI Hackathon)
**Date:** March 2026
**Repository:** [github.com/arnavmahale/ai-hackathon](https://github.com/arnavmahale/ai-hackathon)

---

## 1. Problem Statement

Enterprise engineering teams maintain internal compliance policies — security standards, naming conventions, documentation requirements, error handling practices — that every pull request must follow. Traditional enforcement relies on static linters and regex-based rules, which work well for syntactic checks but fail on **semantic** policies like *"every API endpoint must verify JWT tokens"* or *"exception handlers must log errors with context."*

**Guardians** solves this by combining **Retrieval-Augmented Generation (RAG)** with **LLM-based code analysis** to validate pull requests against natural-language policy documents. The system:

1. **Ingests** policy documents (PDF, text) and automatically extracts concrete compliance rules
2. **Grounds** every compliance decision in retrieved policy excerpts — not LLM hallucination
3. **Integrates** with GitHub webhooks for real-time PR validation
4. **Reports** violations with line-level precision, citations, and suggested fixes

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────┐
│               FRONTEND  (React + TypeScript + Vite)      │
│   Onboarding (doc upload) → Task Review → PR Monitor     │
└────────────────────────┬─────────────────────────────────┘
                         │  Axios
┌────────────────────────▼─────────────────────────────────┐
│               BACKEND  (FastAPI + SQLModel)               │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │         DOCUMENT INGESTION PIPELINE                  │ │
│  │  POST /documents                                     │ │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │ │
│  │  │ Chunker  │→ │ Embedder  │→ │ FAISS VectorStore│  │ │
│  │  │(recursive│  │(OpenAI    │  │ (Flat/IVF/HNSW)  │  │ │
│  │  │/semantic)│  │ 1536-dim) │  │                   │  │ │
│  │  └──────────┘  └───────────┘  └──────────────────┘  │ │
│  │        │                                             │ │
│  │        ▼                                             │ │
│  │  ┌──────────────────┐  ┌──────────────────────────┐  │ │
│  │  │ Task Extractor   │→ │ Deduplicator             │  │ │
│  │  │ (LLM per-chunk)  │  │ (embedding cosine sim)   │  │ │
│  │  └──────────────────┘  └──────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │         VALIDATION PIPELINE                          │ │
│  │  GitHub Webhook → Fetch PR Files → For each file:    │ │
│  │  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  │ │
│  │  │ Linked Chunks │  │ FAISS      │  │ Cross-      │  │ │
│  │  │ (from task   │+ │ Similarity │→ │ Encoder     │  │ │
│  │  │  metadata)   │  │ Search     │  │ Reranker    │  │ │
│  │  └──────────────┘  └────────────┘  └──────┬──────┘  │ │
│  │                                           │          │ │
│  │                              ┌────────────▼───────┐  │ │
│  │                              │ LLM Validator      │  │ │
│  │                              │ (GPT-4o-mini)      │  │ │
│  │                              │ + RAG context       │  │ │
│  │                              └────────────────────┘  │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  Database: SQLModel (SQLite dev / PostgreSQL prod)        │
└──────────────────────────────────────────────────────────┘
```

**Tech Stack:**
| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI, SQLModel, Pydantic |
| Vector Search | FAISS (faiss-cpu), NumPy |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` (sentence-transformers) |
| LLM | GPT-4o-mini (validation + task extraction) |
| Integration | GitHub Webhooks + REST API |

---

## 3. RAG Pipeline — Deep Dive

The RAG pipeline is the core ML component. It transforms raw policy documents into a queryable knowledge base, then retrieves relevant context at validation time to ground the LLM's compliance decisions.

### 3.1 Document Chunking

**Two strategies implemented** (selectable per ingestion):

#### Recursive Character Splitting (Default)
Hierarchically splits text using progressively finer separators:
```
"\n\n\n" → "\n\n" → "\n" → ". " → " "
```
- **Chunk size:** 1000 chars, **Overlap:** 200 chars
- Overlap re-attaches the tail of the previous chunk to preserve cross-boundary context
- O(n) complexity, deterministic, no API calls needed
- Handles abbreviations (Dr., e.g., Inc.) to avoid false sentence splits

#### Semantic Chunking (Optional)
Embedding-based splitting that respects topic boundaries:
1. Split document into sentences (regex-based, abbreviation-aware)
2. Embed each sentence via OpenAI
3. Compute cosine similarity between consecutive sentence pairs
4. Identify breakpoints where similarity drops below the **25th percentile** (topic shift)
5. Group sentences between breakpoints into chunks
6. Post-process: merge chunks < 100 chars, recursively split chunks > 2000 chars

**Trade-off:** Semantic chunking produces higher-quality boundaries but requires N embedding API calls per document (one per sentence). Recursive splitting is free and fast, making it the better default for most policy documents where section headers already provide natural boundaries.

### 3.2 Embedding

- **Model:** OpenAI `text-embedding-3-small` — 1536-dimensional vectors
- **Batching:** Up to 512 texts per API call, auto-splits larger batches
- **Normalization:** L2-normalized before storage so L2 distance in FAISS is equivalent to cosine distance

### 3.3 Vector Store (FAISS)

Auto-scaling index selection based on corpus size:

| Corpus Size | Index Type | Search Complexity | Notes |
|-------------|-----------|-------------------|-------|
| < 1,000 | **Flat** (brute-force) | O(n) | Exact search, no training |
| 1K – 100K | **IVF** (inverted file) | O(n/nlist) | nlist = sqrt(n), trained with k-means |
| > 100K | **HNSW** (graph-based) | O(log n) | Higher memory, approximate |

The store starts Flat and rebuilds when the corpus crosses thresholds. Raw vectors are retained for IVF training and seamless index migration.

**Persistence:** FAISS binary index + metadata.json + config.json, enabling load/save across server restarts.

### 3.4 Task Extraction

Rather than sending entire documents to the LLM (which suffers from the "lost in the middle" problem), we extract compliance rules **per-chunk**:

1. Each chunk is sent to GPT-4o-mini with a structured extraction prompt
2. The LLM returns concrete, checkable rules with fields: title, description, category, severity, checkType, fileTypes, exampleViolation, suggestedFix
3. Each task retains a `source_chunk` reference — a direct pointer back to the policy text it came from

**Deduplication** across chunks (since overlapping chunks produce duplicate rules):
- **Primary:** Embedding-based — embed all task descriptions, compute pairwise cosine similarity, greedy clustering at 0.85 threshold
- **Fallback:** Lexical word-overlap similarity (> 80% = duplicate), used when the embedding API is unavailable

### 3.5 Multi-Source Retrieval + Cross-Encoder Reranking

At validation time, the system assembles evidence from **two sources** before asking the LLM to judge compliance:

```
Source 1: Linked Chunks (direct lookup)
  → Each task carries a source_chunk from extraction
  → Zero-latency, guaranteed-relevant baseline

Source 2: FAISS Similarity Search (top-10)
  → Query = code snippet + task descriptions
  → Retrieves additional supporting/related policy text

         ┌──────────────────┐
         │   All Candidates  │  (deduplicated by text hash)
         └────────┬─────────┘
                  │
         ┌────────▼─────────┐
         │  Cross-Encoder    │  ms-marco-MiniLM-L-6-v2
         │  Reranker         │  scores each (query, chunk) pair
         └────────┬─────────┘
                  │
         ┌────────▼─────────┐
         │   Top 3 Chunks    │  → injected as REFERENCE DOCUMENTATION
         └──────────────────┘
```

**Why rerank?** Bi-encoder (embedding) similarity is fast but coarse — it encodes query and document independently. The cross-encoder processes the (query, document) pair jointly, achieving significantly higher relevance discrimination. The two-stage approach gives us FAISS speed for candidate generation and cross-encoder accuracy for final selection.

The reranker model is **lazy-loaded** on first use to avoid cold-start overhead when RAG isn't needed.

---

## 4. Validation Engine

The validator (`validate_code.py`) orchestrates per-file compliance checks:

1. **Filter** rules by file type (glob matching: `*.py`, `*.js`, etc.)
2. **Assemble RAG context** (linked chunks + FAISS + rerank → top 3)
3. **Build prompt** with system role ("You are CodeGuardian"), task JSON, reference documentation, and code (truncated to 8KB)
4. **Call LLM** with `response_format: json_object` for structured output
5. **Parse** per-task verdicts: compliant/non-compliant, violations with line numbers, citations, suggested fixes

**Prompt structure:**
```
System: "You are CodeGuardian, an exacting code-compliance reviewer.
         When REFERENCE DOCUMENTATION is provided, ground your
         decisions in those specific policy excerpts..."

User:   Tasks JSON: [...]
        REFERENCE DOCUMENTATION:
        --- [security-policy.pdf] (relevance: 0.87) ---
        "All API endpoints must validate JWT tokens..."
        ---
        File: src/api/routes.py
        Source code (python):
        ```
        [code here]
        ```
```

The LLM returns structured JSON with `compliant`, `explanation`, `citations` (doc IDs used), and `violations` (line/column/message/fix).

---

## 5. Evaluation Framework

We built a comprehensive evaluation suite to measure pipeline quality across two dimensions:

### 5.1 Retrieval Quality

Metrics computed at K = {1, 3, 5, 10}:

| Metric | What It Measures |
|--------|-----------------|
| **Precision@K** | % of top-K results that are relevant |
| **Recall@K** | % of all relevant docs found in top-K |
| **F1@K** | Harmonic mean of P@K and R@K |
| **NDCG@K** | Ranking quality (position-aware, rewards relevant docs ranked higher) |
| **MRR** | Position of the first relevant result |
| **MAP** | Average precision across all queries |

The `EvaluationSuite` class runs labeled test queries against the retriever and produces per-query breakdowns + aggregate metrics, with automatic PASS/FAIL based on Recall@K thresholds.

### 5.2 LLM Verdict Accuracy

Binary classification metrics for compliance verdicts:
- **Accuracy, Precision, Recall, F1**
- **Confusion matrix** (TP/TN/FP/FN) to identify whether the system errs toward false positives (over-flagging) or false negatives (missing violations)

Test cases are labeled with expected compliance status and specific violations, enabling measurement of both detection rate and false alarm rate.

---

## 6. Key Architectural Trade-offs

### Trade-off 1: LLM-Based Semantic Validation vs. Deterministic Rules

**Decision:** Use GPT-4o-mini for compliance decisions instead of regex/AST-based rules.

**What we gained:** The ability to enforce policies written in natural language ("every public function must be documented") without writing a parser for every rule and language. A single prompt handles Python, JavaScript, Go, etc.

**What we traded:** Determinism, latency, and cost. LLM responses are non-deterministic — the same code can produce slightly different verdicts across runs. Each file validation requires an API call (~1-2s), compared to milliseconds for a regex check. We mitigate non-determinism with `response_format: json_object` and structured prompting, and keep latency acceptable by running validations async with the webhook receiver returning 202 immediately.

### Trade-off 2: Two-Stage Retrieval (Bi-Encoder + Cross-Encoder) vs. Single-Stage

**Decision:** FAISS bi-encoder retrieval for candidate generation (top 10), then cross-encoder reranking for final selection (top 3).

**Why not just embeddings?** Bi-encoders encode query and document independently — fast (O(1) per document at search time) but they miss fine-grained semantic interactions. For compliance checking, the difference between "functions must have docstrings" and "functions must have type annotations" is critical. The cross-encoder (`ms-marco-MiniLM-L-6-v2`) processes the full (query, document) pair, capturing these nuances.

**Why not just cross-encoder?** Cross-encoders are O(n) per query (must score every candidate). At 10K+ chunks, this becomes prohibitively slow. The bi-encoder narrows to ~10 candidates in milliseconds; the cross-encoder then does fine-grained ranking on just those 10.

**Cost:** Added model dependency (sentence-transformers), ~50ms extra latency per file, and memory for the cross-encoder model. Mitigated with lazy loading — the model only loads when RAG is active.

### Trade-off 3: Per-Chunk Task Extraction vs. Whole-Document Extraction

**Decision:** Extract compliance rules from each chunk individually, then deduplicate.

**Why not send the whole document?** Two reasons: (1) **Context window limits** — policy documents can be 50+ pages, exceeding even large context windows, and (2) the **"lost in the middle" problem** — LLMs attend disproportionately to the beginning and end of long contexts, missing rules buried in the middle.

**What we traded:** More API calls (one per chunk) and the need for deduplication (overlapping chunks produce duplicate rules). We handle dedup with embedding-based cosine similarity clustering (0.85 threshold), which catches semantically identical rules even when worded differently across chunks.

---

## 7. Data Flow: End-to-End Example

```
1. Admin uploads "security-policy.pdf"
   → Chunked into 45 chunks (1000 chars, 200 overlap)
   → 45 × 1536-dim embeddings stored in FAISS
   → 12 unique compliance tasks extracted (from 31 raw, after dedup)
   → Each task linked to its source chunk

2. Developer opens PR #42 (modifies src/api/auth.py)
   → GitHub webhook hits POST /github/webhook
   → Backend fetches changed files via GitHub API
   → ScanResult created (status: "pending"), 202 returned

3. Async validation runner picks up PR #42
   → Loads latest task set (12 rules)
   → For auth.py: 8 rules match *.py file glob
   → RAG assembly:
     - 8 linked chunks from task metadata
     - FAISS search "JWT authentication error handling" → 10 results
     - Deduplicate → 14 unique candidates
     - Cross-encoder rerank → top 3 chunks (scores: 0.92, 0.87, 0.71)
   → LLM prompt with 8 tasks + 3 reference docs + code
   → Response: 6 compliant, 2 violations found
     - Line 34: Missing JWT validation on /api/users endpoint
     - Line 89: Exception caught but not logged

4. Frontend polls /pull-requests, displays violations with
   suggested fixes and citations to security-policy.pdf
```

---

## 8. Project Structure

```
ai-hackathon/
├── validate_code.py              # Standalone validator (CLI + library)
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, all endpoints
│   │   ├── storage.py            # SQLModel database layer
│   │   └── rag/
│   │       ├── chunker.py        # Recursive + semantic chunking
│   │       ├── embeddings.py     # OpenAI embedding client
│   │       ├── vector_store.py   # FAISS vector store (Flat/IVF/HNSW)
│   │       ├── retriever.py      # Orchestrates ingest + query
│   │       ├── reranker.py       # Cross-encoder reranking
│   │       └── task_extractor.py # Per-chunk LLM extraction + dedup
│   ├── evaluation/
│   │   ├── eval_retrieval.py     # Retrieval metrics (P@K, NDCG, MAP...)
│   │   ├── eval_llm.py          # Verdict accuracy metrics
│   │   └── run_eval.py          # Evaluation runner
│   └── tests/                    # Unit tests (mocked API calls)
└── guardians-website/            # React frontend
    └── src/
        ├── App.tsx               # State management + routing
        ├── OnboardingPage.tsx    # Document upload flow
        ├── TasksDashboard.tsx    # Compliance rule review
        └── PRMonitor.tsx         # Live PR validation status
```

---

## 9. Future Work

- **GPU-accelerated FAISS** for larger policy corpora (100K+ chunks)
- **Streaming validation** — return partial results as each file completes
- **Fine-tuned reranker** on compliance-specific query-document pairs
- **Caching layer** for repeated code patterns to reduce LLM API costs
- **Multi-model evaluation** — compare GPT-4o-mini vs Claude for verdict consistency
