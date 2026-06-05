# Volley — Implementation Plan

> **How to use this doc**: We work phase by phase, in order. Each phase produces working, testable code before the next begins. Nothing is built on an untested foundation.

---

## Phase 1: Project Scaffolding

**Goal**: A clean, runnable Python project with the right structure, dependency management, and environment variable loading. Nothing AI-related yet — just a solid foundation.

**What we build**:
- Initialize the project with `uv` (`pyproject.toml`, lockfile, virtual env)
- Define the folder structure (`volley/`, `volley/gmail/`, `volley/agent/`, `volley/rag/`)
- Create a `.env.example` listing every required key
- Set up `python-dotenv` to load env vars
- Verify the project runs (`uv run python -m volley` prints "Volley starting...")

**Folder structure at end of phase**:
```
volley/
├── volley/
│   ├── __init__.py
│   ├── __main__.py        ← entry point
│   ├── config.py          ← env var loading
│   ├── gmail/
│   │   └── __init__.py
│   ├── agent/
│   │   └── __init__.py
│   └── rag/
│       └── __init__.py
├── pyproject.toml
├── .env.example
├── .env                   ← gitignored
└── README.md
```

**Done when**: `uv run python -m volley` runs without errors.

---

## Phase 2: Gmail API Integration

**Goal**: Authenticate with Gmail via OAuth 2.0 and be able to read emails from the inbox and send emails. No AI, no agent — pure Gmail API plumbing.

**What we build**:
- `volley/gmail/auth.py` — OAuth 2.0 flow, token persistence (`token.json`)
- `volley/gmail/reader.py` — fetch emails from inbox, parse headers + body (handle MIME multipart), return clean dicts
- `volley/gmail/sender.py` — compose and send a reply in a thread
- `volley/gmail/history.py` — fetch sent mail for tone corpus building
- A small test script: authenticate → fetch 5 inbox emails → print them → send a test email to yourself

**Key concepts practiced**: OAuth 2.0, MIME parsing, Gmail API pagination, `messageId` / `threadId` distinction.

**Done when**: Script fetches real emails from your inbox and sends a test reply, all printed to console.

---

## Phase 3: RAG — Tone Corpus & Retrieval

**Goal**: Build the tone-matching system. Fetch your sent emails, embed them, store in ChromaDB, and retrieve the most stylistically similar ones given a query email.

**What we build**:
- `volley/rag/embedder.py` — wraps OpenAI embedding API (`text-embedding-3-small`)
- `volley/rag/store.py` — ChromaDB setup, `index_email()`, `retrieve_similar()`
- `volley/rag/corpus.py` — fetch sent mail via Gmail API, filter short/auto emails, index all of them
- A CLI command: `uv run python -m volley index` — indexes your sent mail and reports how many were stored
- A test: `uv run python -m volley search "looking to hire a consultant"` — prints the top 3 most similar past emails you've sent

**Key concepts practiced**: embeddings, vector similarity, ChromaDB collections, corpus filtering.

**Done when**: `volley search <query>` returns real emails from your sent history that are stylistically relevant.

---

## Phase 4: LLM Classification

**Goal**: Given a raw email, use an LLM to classify its intent and determine whether it's a lead worth responding to. Structured output only — no free-text parsing.

**What we build**:
- `volley/agent/classifier.py` — `EmailClassification` Pydantic model, classification prompt, `classify_email()` function
- Intent taxonomy: `inbound_lead`, `follow_up`, `referral`, `partnership`, `cold_outreach`, `support_request`, `unrelated`
- Confidence threshold logic (high confidence → auto-proceed, low confidence → flag)
- A test script: paste an email body → get back `{intent, is_lead, confidence, reasoning}` printed as JSON

**Key concepts practiced**: structured output / tool calling, Pydantic models, prompt engineering for classification, model selection (mini/haiku for cost).

**Done when**: Classifier correctly categorizes 5 test emails (mix of leads, cold outreach, spam) with `confidence > 0.8`.

---

## Phase 5: Draft Generation

**Goal**: Given an incoming email + retrieved tone examples, generate a reply draft that sounds like the user wrote it.

**What we build**:
- `volley/agent/drafter.py` — `generate_draft()` function that takes `(email, tone_examples)` and returns a reply string
- Draft prompt that injects tone examples as few-shot context and instructs the LLM to match style
- A test script: pick a real inbound email from your inbox → retrieve tone examples → generate draft → print it

**Key concepts practiced**: few-shot prompting, RAG-augmented generation, prompt structure for style imitation.

**Done when**: Generated draft for a real email reads naturally and matches your writing style recognizably.

---

## Phase 6: LangGraph Agent Graph

**Goal**: Wire classification, retrieval, and drafting into a single stateful LangGraph graph with proper conditional routing. No human approval yet — it runs to completion automatically (skipping sending).

**What we build**:
- `volley/agent/state.py` — `VolleyState` TypedDict with all fields
- `volley/agent/nodes.py` — all node functions: `classify`, `retrieve_tone`, `draft_reply`, `skip`
- `volley/agent/graph.py` — assemble the graph, add edges, conditional routing, compile
- `volley/agent/routing.py` — `route_after_classify()` conditional function
- A test: feed one real email into `graph.invoke({"email": ...})` → trace the state at each step → print final draft

**Graph at end of phase**:
```
classify ──(is_lead=True)──▶ retrieve_tone ──▶ draft_reply ──▶ [END]
         ──(is_lead=False)─▶ skip ──▶ [END]
```

**Key concepts practiced**: LangGraph `StateGraph`, node functions, conditional edges, state accumulation.

**Done when**: Graph processes a real email end-to-end, state is visible at each node, draft is in final state.

---

## Phase 7: Human-in-the-Loop Approval

**Goal**: Add the `human_approval` node with LangGraph's `interrupt()` mechanism. The graph pauses, shows the draft in the terminal, waits for user input, then resumes and either sends or skips.

**What we build**:
- `volley/agent/nodes.py` — add `human_approval` node using `interrupt()`
- `volley/agent/nodes.py` — add `send_email` node using `volley/gmail/sender.py`
- `volley/agent/routing.py` — `route_after_approval()` function
- SQLite checkpointer setup (state survives restarts)
- CLI approval interface: prints draft, prompts `[A]pprove / [E]dit / [S]kip`, resumes graph with `Command(resume=...)`
- `volley/agent/graph.py` — updated graph with approval node wired in

**Updated graph**:
```
classify ──▶ retrieve_tone ──▶ draft_reply ──▶ human_approval ──(approved)──▶ send_email ──▶ [END]
                                                               ──(skipped)──▶ [END]
```

**Key concepts practiced**: `interrupt()`, `Command(resume=...)`, SQLite checkpointer, thread IDs for state isolation.

**Done when**: Full flow works — real email in → draft shown in terminal → you type A → email is sent to yourself as a test.

---

## Phase 8: Inbox Watcher

**Goal**: The system runs continuously, polling Gmail for new unread emails and triggering the agent graph for each one automatically.

**What we build**:
- `volley/gmail/watcher.py` — polling loop with configurable interval (default 60s)
- Deduplication: persist processed `messageId`s to a local SQLite table so restarts don't reprocess old emails
- Entry point: `uv run python -m volley watch` — starts the watch loop
- Graceful shutdown: Ctrl+C cleanly stops the watcher

**Key concepts practiced**: polling loops, deduplication, process lifecycle, combining all prior components.

**Done when**: Leave `volley watch` running, send yourself a test email that looks like a lead, watch it get classified, drafted, and surfaced for approval — all automatically.

---

## Phase 9: End-to-End Testing & Hardening

**Goal**: The system is reliable enough for real daily use. Catch edge cases, add error handling at system boundaries, and verify the full flow with real emails.

**What we build**:
- Error handling for Gmail API failures (token expiry, network issues, rate limits)
- Error handling for LLM failures (timeouts, API errors) with retry logic
- MIME edge cases: HTML-only emails, attachments, forwarded threads
- Logging: structured logs for every email processed (classified as X, draft generated, approved/skipped)
- A `volley/gmail/watcher.py` dry-run mode: `--dry-run` flag — classifies and drafts but never sends
- Manual test: run for 2 real days, review every draft surfaced

**Done when**: System runs for 48 hours without crashing, handles all real email formats gracefully, dry-run mode works.

---

## Phase 10: Incremental Corpus Indexing

**Goal**: The tone corpus stays up to date. New sent emails are automatically added to ChromaDB after each successful send, so the system learns from its own approved outputs over time.

**What we build**:
- After `send_email` node: trigger re-indexing of the newly sent email into ChromaDB
- `last_indexed_at` timestamp stored in config, used to only index emails since last run
- `volley index --incremental` command for manual corpus refresh

**Done when**: A draft you approved and sent appears in retrieval results for future similar emails.

---

## Current Status

| Phase | Status |
|-------|--------|
| 1 — Project Scaffolding | ✅ Complete |
| 2 — Gmail API Integration | ⬜ Not started |
| 3 — RAG Tone Corpus | ✅ Complete |
| 4 — LLM Classification | ✅ Complete |
| 5 — Draft Generation | ✅ Complete |
| 6 — LangGraph Agent Graph | ✅ Complete |
| 7 — Human-in-the-Loop | ⬜ Not started |
| 8 — Inbox Watcher | ⬜ Not started |
| 9 — E2E Testing & Hardening | ⬜ Not started |
| 10 — Incremental Indexing | ⬜ Not started |
