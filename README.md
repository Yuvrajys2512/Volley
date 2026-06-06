# Volley

[![CI](https://github.com/Yuvrajys2512/Volley/actions/workflows/ci.yml/badge.svg)](https://github.com/Yuvrajys2512/Volley/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)

**An agentic AI assistant that watches your Gmail inbox, spots real inbound leads, and drafts replies in your own writing voice — then waits for your approval before anything is sent.**

Volley filters out the newsletter/notification noise, recognizes the emails that actually deserve a personal reply, and writes that reply the way *you* would — by learning your tone from your own past sent mail via retrieval-augmented generation. Nothing leaves your outbox without a human saying yes.

<!-- TODO: record a terminal GIF of `volley watch` catching a lead → showing the draft → [A]pprove, and embed it here. This is the single highest-impact thing on the page. -->
<!-- ![Volley demo](docs/demo.gif) -->

---

## Why it's interesting

- **A real agent, not a prompt wrapper.** Classification, retrieval, drafting, approval, and sending are discrete nodes in a [LangGraph](https://github.com/langchain-ai/langgraph) state machine with conditional routing and a true human-in-the-loop *interrupt* — the graph pauses, persists its full state to SQLite, and resumes on your decision.
- **It sounds like you.** Tone matching is done with RAG over your own sent emails, not a generic "write a professional reply" prompt.
- **Survives restarts.** State is checkpointed; processed emails are de-duplicated. Kill it mid-draft and it picks up exactly where it left off.
- **Runs for free.** Inference via Groq's free tier; embeddings run **locally** (`sentence-transformers`) with no API key, no per-token cost, and no rate limits.

## How it works

```
                    ┌─────────────────────────────────────────────────────┐
   Gmail inbox ───► │  watcher: poll unread · de-dupe seen messageIds      │
   (poll every 60s) └───────────────────────────┬─────────────────────────┘
                                                 │  one new email
                                                 ▼
   ┌──────────────┐   ┌──────────┐   not a lead   ┌──────┐
   │extract_fields├──►│ classify ├───────────────►│ skip ├──► END
   └──────────────┘   └────┬─────┘                └──────┘
                           │ is_lead (conf ≥ 0.75)
                           ▼
                  ┌────────────────┐   ┌────────────┐   ┌────────────────┐
                  │ retrieve_tone  ├──►│ draft_reply ├──►│ human_approval │  ◄── interrupt()
                  │ (RAG over your │   │ (few-shot   │   │  [A]/[E]/[S]   │
                  │  sent mail)    │   │  on tone)   │   └───────┬────────┘
                  └────────────────┘   └────────────┘           │
                                            approved ┌───────────┴──────────┐ skipped
                                                     ▼                      ▼
                                              ┌────────────┐              END
                                              │ send_email ├──► END
                                              └────────────┘
```

1. **Watch** — poll the inbox for unread mail; skip anything already processed (SQLite dedup store).
2. **Classify** — an LLM tags intent (`inbound_lead`, `follow_up`, `referral`, `partnership`, `cold_outreach`, `support_request`, `unrelated`) with structured output and a confidence score. Below threshold or not a lead → `skip`.
3. **Retrieve tone** — embed the incoming email and pull your most stylistically similar past replies from ChromaDB.
4. **Draft** — generate a reply, few-shot-conditioned on those examples so it matches your voice.
5. **Approve** — the graph *interrupts* and shows you the draft in the terminal: **[A]pprove / [E]dit / [S]kip**.
6. **Send & learn** — on approval it sends in-thread, then indexes the sent reply back into the corpus so tone matching improves over time.

## Tech stack

| Concern | Choice | Why |
|---|---|---|
| Agent orchestration | **LangGraph** | Stateful graph, conditional edges, native `interrupt()` for human-in-the-loop |
| Durability | **SQLite checkpointer** | State + approvals survive crashes and restarts |
| Inbox I/O | **Gmail API** (OAuth 2.0) | Read, send-in-thread, and fetch sent mail for the corpus |
| Tone retrieval | **ChromaDB** + `all-MiniLM-L6-v2` | Local embeddings — no key, no cost, no rate limit |
| Inference | **Groq** (`llama-3.x`) | Fast and free-tier friendly |
| Validation | **Pydantic** | Structured, typed LLM output for classification |

## Quick start

> Requires Python 3.11+ and [`uv`](https://github.com/astral-sh/uv).

```bash
# 1. Install
uv sync

# 2. Configure
cp .env.example .env          # then add your free Groq key from console.groq.com/keys

# 3. Connect Gmail (one-time OAuth — see to_do.md for the Google Cloud setup)
#    drop your OAuth desktop credentials.json in the project root, then:
uv run python scripts/test_gmail.py

# 4. Learn your writing tone from your sent mail (run once)
uv run python -m volley index

# 5. Try it without sending anything
uv run python -m volley watch --dry-run

# 6. Go live — surfaces leads for your approval
uv run python -m volley watch
```

### Commands

| Command | What it does |
|---|---|
| `volley watch` | Monitor the inbox and process leads (asks before sending) |
| `volley watch --dry-run` | Classify and draft, but never send |
| `volley index` | Build the tone corpus from your sent mail |
| `volley index --incremental` | Index only mail sent since the last run |
| `volley search "<text>"` | Inspect the corpus — show your past emails most similar to a query |

## Configuration

All optional, set in `.env` (defaults shown):

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | **Required.** Inference key |
| `CLASSIFICATION_MODEL` | `llama-3.1-8b-instant` | Fast model for triage |
| `DRAFT_MODEL` | `llama-3.3-70b-versatile` | Stronger model for writing |
| `CONFIDENCE_THRESHOLD` | `0.75` | Min confidence to treat an email as a lead |
| `POLL_INTERVAL_SECONDS` | `60` | Inbox poll cadence |
| `CHROMA_DB_PATH` | `./chroma_db` | Vector store location |

## Project layout

```
volley/
├── gmail/        OAuth, inbox reader, sender, sent-mail history, watcher
├── rag/          local embedder, ChromaDB store, tone-corpus builder
├── agent/        LangGraph state, nodes, routing, graph, classifier, drafter
├── config.py     env-driven configuration
└── __main__.py   CLI entry point (watch · index · search)
scripts/          manual phase-by-phase test runners
documentation/    deeper design notes per subsystem
```

## Development

```bash
uv sync --group dev     # install dev tooling (pytest, ruff)
uv run pytest -q        # run the test suite
uv run ruff check .     # lint
```

Tests cover the pure logic that doesn't need a live LLM or inbox — agent routing,
the tone-corpus filter, the classification schema + review gate, the SQLite
de-duplication store, and body truncation. CI runs lint + tests on every push.

## Design notes

- **Human-in-the-loop is non-negotiable.** Volley never sends autonomously; `interrupt()` hard-stops the graph at `human_approval` every time.
- **Privacy.** Embeddings are computed locally — your email content is never sent to an embedding API. Only the text needed for classification/drafting goes to the inference provider.
- **It learns.** Every reply you approve is indexed back into the corpus, so the tone match sharpens as you use it.

## Roadmap

- [x] Automated test suite + CI
- [ ] Write drafts straight into the Gmail **Drafts** folder (review/edit from any device)
- [ ] Multi-tenant web app + OAuth so others can connect their own inbox

---

*Built as a deep-dive into agentic systems: LangGraph state machines, RAG, structured LLM output, and OAuth-based tool use.*
