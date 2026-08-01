# Volley — Drafts-Only MVP Architecture

> **The product**: A user signs in with Google, connects their Gmail once, and from
> then on every real inbound lead gets a reply — written in their own voice —
> waiting in their **Gmail Drafts folder**. Gmail itself is the review UI.
> Volley never sends anything; it can't, by design.
>
> **Scope discipline**: this doc covers the smallest hostable, multi-user,
> trustworthy version. No dashboard, no approval UI, no billing yet. Everything
> here is a prerequisite to charging money; nothing here is speculative polish.

---

## 1. The one big simplification

Drafts-only **deletes the human-in-the-loop interrupt** from the hosted graph.
The current graph pauses at `human_approval` and waits for a terminal keypress;
in the MVP there is nobody at a terminal. The approval *moves into Gmail*:
opening the draft, editing it, and pressing Send (or discarding it) **is** the
human review.

The hosted graph becomes linear:

```
extract_fields → classify ──not a lead──► skip → END
                     │ is_lead
                     ▼
              retrieve_tone → draft_reply → create_draft → END
```

Consequences, all good:

- **No interrupt, no resume, no checkpointer-as-API.** A run either completes
  in one shot or fails and is retried. The LangGraph checkpointer becomes an
  internal durability detail, not a cross-request state store.
- **No real-time web UI** — the hardest 40% of a full SaaS, gone.
- **No `gmail.send` scope.** The app needs only `gmail.readonly` (inbox +
  sent-mail corpus) and `gmail.compose` (create drafts). "Volley cannot send
  email on your behalf" becomes a true, verifiable trust claim and a simpler
  Google-verification story. (`gmail.readonly` is still a restricted scope, so
  verification + possible CASA assessment is unavoidable — see §8.)
- The CLI keeps the interactive graph as-is; the server uses a second compile
  of the same nodes with `route_after_approval` hardwired to `create_draft`.
  One node set, two graph shapes.

---

## 2. System overview

```
                        ┌──────────────────────────────────────────────┐
                        │                 Railway project               │
                        │                                              │
  user's browser ─────► │  ┌──────────── web (FastAPI) ─────────────┐  │
  - landing page        │  │ GET  /            landing + privacy/ToS │  │
  - sign in w/ Google   │  │ GET  /auth/google  start OAuth          │  │
  - status page         │  │ GET  /auth/callback  store tokens,      │  │
                        │  │       create user, enqueue corpus build │  │
                        │  │ GET  /app          status: corpus size, │  │
                        │  │       drafts created, pause/resume      │  │
                        │  │ POST /disconnect   revoke + delete data │  │
                        │  └───────────────┬─────────────────────────┘  │
                        │                  │                            │
                        │                  ▼                            │
                        │  ┌─────────── Postgres (+pgvector) ────────┐  │
                        │  │ users · gmail_accounts (encrypted       │  │
                        │  │ tokens) · processed_messages ·          │  │
                        │  │ corpus_entries (vectors) · draft_log ·  │  │
                        │  │ jobs                                    │  │
                        │  └───────────────▲─────────────────────────┘  │
                        │                  │                            │
                        │  ┌────────────── worker ────────────────────┐ │
   Gmail API ◄────────► │  │ scheduler loop (every ~90s, jittered):   │ │
   per-user quota       │  │   for each active account:               │ │
                        │  │     refresh token → history.list since   │ │
                        │  │     last historyId → new inbox messages  │ │
                        │  │     → run agent graph → create draft     │ │
                        │  │ job runner: corpus indexing on connect   │ │
                        │  └──────────────┬───────────────────────────┘ │
                        └─────────────────┼─────────────────────────────┘
                                          ▼
                                   Groq API (paid tier)
                                   classify: llama-3.1-8b
                                   draft:    llama-3.3-70b
                                   embeddings: local MiniLM (in worker)
```

Two deployed processes (web + worker), one Postgres, one external API (Groq).
That's the whole MVP.

---

## 3. Stack decisions (and why)

| Concern | Choice | Why |
|---|---|---|
| Language/backend | **Python + FastAPI** | The agent, Gmail, and RAG code is all Python and stays. A Next.js frontend would mean a second codebase to serve ~4 pages. |
| Pages | **Jinja templates + a sprinkle of htmx** | Landing, status, privacy, ToS. No SPA, no build step. |
| App auth | **Google OAuth *is* the auth** | Users must do Google consent anyway to connect Gmail — one flow does signup, login, and Gmail connection. No Clerk/Auth0 dependency. Signed session cookie (`itsdangerous`/`starlette` sessions). |
| Database | **Postgres + pgvector** | One database for users, tokens, dedup, jobs, *and* the tone corpus. Replaces SQLite + ChromaDB. `user_id` column + an always-scoped data-access layer = tenant isolation. |
| Embeddings | **Local `all-MiniLM-L6-v2` in the worker** | Same model as today; it's small and CPU-fast. The worker is a real server now, so "local" is fine. No per-token cost, email bodies never leave the box for embedding. |
| LLM | **Groq, paid tier** | Keep the cheap-classify / strong-draft split. Pennies per email (see §9). |
| Inbox watching | **Polling via `history.list`, per account, ~90s jittered** | Gmail API quota is largely *per-user*, so 100 polled inboxes don't compete with each other. Pub/Sub push is the post-MVP upgrade (§10) — it adds GCP infra (topic, webhook, watch renewal) the MVP doesn't need. |
| Hosting | **Railway** (Render/Fly equivalent) | One project = web service + worker service + managed Postgres + cron, deploy from the GitHub repo. Vercel is wrong here: the watcher is an always-on Python process, not request/response functions. |
| Token encryption | **Fernet (AES) with key in Railway env secrets** | Refresh tokens encrypted at rest; key never in the DB or repo. A KMS is post-MVP. |
| Errors/observability | **Sentry free tier + structured logs** | You must know when a real user's agent run fails. Extends the existing `volley/logger.py`. |
| Migrations | **Alembic** | Schema will evolve; migrations from day one. |

---

## 4. Data model (Postgres)

```sql
users
  id            uuid pk
  email         text unique        -- Google account email
  created_at    timestamptz
  status        text               -- active | paused | disconnected

gmail_accounts                     -- 1:1 with users for MVP, table anyway
  user_id       uuid fk → users
  refresh_token_enc  bytea         -- Fernet-encrypted, NEVER logged
  granted_scopes     text[]
  last_history_id    bigint        -- watermark for history.list polling
  watch_status       text          -- ok | auth_revoked | error
  connected_at  timestamptz

processed_messages                 -- dedup (port of volley/gmail/watcher store)
  user_id       uuid fk
  message_id    text
  processed_at  timestamptz
  primary key (user_id, message_id)

corpus_entries                     -- replaces ChromaDB
  user_id       uuid fk
  message_id    text
  body          text
  subject       text
  sent_to       text
  sent_at       timestamptz
  embedding     vector(384)        -- MiniLM dimension
  primary key (user_id, message_id)
  -- index: HNSW on embedding, plus btree on user_id

draft_log                          -- product analytics + user-facing status
  id            bigserial pk
  user_id       uuid fk
  message_id    text               -- incoming email
  gmail_draft_id text              -- created draft
  intent        text
  confidence    real
  created_at    timestamptz

jobs                               -- minimal queue (corpus indexing, retries)
  id            bigserial pk
  user_id       uuid fk
  kind          text               -- index_corpus | process_message
  payload       jsonb
  status        text               -- queued | running | done | failed
  attempts      int
  run_after     timestamptz
```

**Tenant-isolation rule**: all reads/writes go through a `Repo(user_id)`
data-access class whose constructor takes the user and whose methods cannot be
called without it. Tests assert that user A's repo returns nothing for user B's
data. This is the P1 "key risk" from PRODUCTION.md made concrete.

---

## 5. What happens to the existing code

Most of `volley/` survives. The refactor is at the edges:

| Module | Fate |
|---|---|
| `agent/nodes.py`, `classifier.py`, `drafter.py`, `state.py`, `routing.py` | **Keep.** Add `user_id` to `VolleyState`; nodes get their Gmail service + retriever via the state/context instead of module-level singletons. |
| `agent/graph.py` | **Keep + add** a `build_server_graph()`: same nodes, no interrupt, approval routed to `create_draft`. CLI graph untouched. |
| `gmail/auth.py` | **Rewrite** for the server: web OAuth flow (`google-auth-oauthlib` web client, redirect URI) + `credentials_for_user(user_id)` that decrypts the refresh token from Postgres and refreshes in memory. The current file-based version stays for the CLI. |
| `gmail/reader.py`, `sender.py`, `history.py` | **Keep**, parameterized by the per-user service. `sender.py`'s send path is unused on the server (drafts only). Add `history.list`-based incremental fetch using `last_history_id`. |
| `gmail/watcher.py` | **Port** the loop into the worker's scheduler: same dedup logic, but iterating accounts from Postgres. |
| `rag/store.py` | **Rewrite** against pgvector with `user_id` scoping; same public functions (`index_email`, `retrieve_similar`, `corpus_size`) so `nodes.py` barely changes. `embedder.py` unchanged. |
| `rag/corpus.py` | **Keep**, becomes the `index_corpus` job body. |
| `config.py` | Split into infra config (env) and **per-user settings** (DB: confidence threshold, paused). |
| New | `web/` (FastAPI app, ~5 routes + templates), `worker/` (scheduler + job runner), `db/` (models, repo, migrations), `crypto.py` (Fernet helpers). |

---

## 6. Key flows

**Onboarding** (the make-or-break flow — first draft must feel like *them*):
1. Landing page → "Sign in with Google" → consent screen (`gmail.readonly`,
   `gmail.compose`, profile email).
2. Callback: create `users` + `gmail_accounts` rows (token encrypted), set
   session cookie, enqueue `index_corpus` job, redirect to `/app`.
3. `/app` shows corpus-build progress ("indexed 132 of ~400 sent emails…",
   htmx polling). When done: "Volley is watching. Lead replies will appear in
   your Gmail Drafts."
4. Worker records the mailbox's current `historyId` as the watermark — only
   mail arriving *after* connection is processed. No backlog surprises.

**Steady state** (per account, every ~90s):
1. Refresh access token from encrypted refresh token (in memory only).
2. `history.list(startHistoryId=last_history_id)` → new inbox message IDs.
3. Skip anything in `processed_messages`; for each new message run the linear
   graph → if lead: draft created in their Gmail, row in `draft_log`.
4. Advance `last_history_id`. On `invalid_grant` (user revoked in Google
   settings): mark `auth_revoked`, stop polling, email them a reconnect link.

**Disconnect / delete** (required for trust *and* Google verification):
`POST /disconnect` → revoke token with Google, delete corpus_entries,
processed_messages, draft_log, gmail_accounts, user. Hard delete, no soft-keep.

**Failure policy**: any error in a run → job retry with backoff (3 attempts)
→ then Sentry alert + skip-with-log. A missed lead is bad; a crash-looping
worker that misses *everyone's* leads is worse.

---

## 7. Per-user limits (abuse + cost caps)

- Max N agent runs/day per user (e.g. 200) — one pathological inbox can't run
  up the Groq bill.
- Max corpus size at indexing (e.g. 2,000 sent emails).
- Global worker concurrency cap so 50 simultaneous arrivals don't stampede Groq;
  honor 429s with backoff (queue-level, extending the existing retry logic).

---

## 8. The parallel track: Google verification (start week 1)

Code can't ship to strangers until this clears. It runs on Google's calendar,
so it starts alongside the first commit, not after the last one:

1. Buy the domain; put up landing + **privacy policy** + **ToS** (the FastAPI
   app's static pages are enough).
2. Switch the OAuth client from "Desktop" to **"Web application"** with the
   production redirect URI; consent screen branding (logo, domain verification).
3. Record the demo video of the OAuth flow + how each scope is used.
4. Write scope justifications (`gmail.readonly`: classify inbound leads + build
   tone corpus from sent mail; `gmail.compose`: create reply drafts).
5. Submit for verification; expect weeks and follow-up questions. Restricted
   scopes likely require a **CASA security assessment** (budget a few hundred
   dollars and real back-and-forth).
6. **Until verified you have 100 test users** — that's the closed beta. Use it.

---

## 9. Cost sketch (MVP, ~50 active users)

| Item | ~Monthly |
|---|---|
| Railway: web + worker + Postgres | $15–25 |
| Groq paid tier (classify ~every email, draft ~leads only; ≈ fractions of a cent per email) | $5–20 |
| Domain | ~$1 |
| Sentry | $0 (free tier) |
| **Total** | **≈ $25–50/mo** |
| One-time: CASA assessment (if required) | ~$0–600 |

Comfortably under one paying user at $19/mo once billing exists. The
unit economics are not the risk; distribution is.

---

## 10. Build order (3 weeks of evenings-honest, ~1.5 weeks full-time)

**Week 1 — storage + identity (the real rewrite)**
- Postgres schema + Alembic + `Repo(user_id)` layer + tenant-isolation tests.
- Token encryption helpers; port dedup store and `rag/store.py` to Postgres/pgvector.
- `build_server_graph()` (linear, drafts-only) + nodes taking per-user context.
- *Parallel*: buy domain, draft privacy policy + ToS.

**Week 2 — web + onboarding**
- FastAPI app: landing, OAuth web flow, callback, sessions, `/app` status,
  disconnect/delete, privacy + ToS pages.
- `index_corpus` job + progress display.
- Deploy web + Postgres to Railway; OAuth client switched to web type.
- *Parallel*: submit Google verification.

**Week 3 — worker + dogfood**
- Scheduler loop (multi-account polling, watermarks, retries, caps), Sentry.
- Connect **your own Gmail through the production flow**; run for days.
- Then 3–5 trusted users as Google "test users". Watch `draft_log`, fix the
  onboarding rough edges they hit.

**Explicitly out of scope** (post-MVP, in rough order): Stripe billing · Pub/Sub
push watching · settings UI beyond pause/disconnect · custom intents ·
draft-quality feedback loop · approval dashboard · teams.

**Definition of done**: a stranger you've added as a test user can go from the
landing page to a voice-matched draft appearing in their Gmail Drafts without
you touching anything, and you can see it happen in the logs.
