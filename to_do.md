# Volley — To Do

> **Status (last updated 2026-08-01):** Phase 1 (multi-tenant hosted MVP for
> friends/volunteers) is code-complete — Stages A–D done. 56/56 tests passing,
> ruff clean. What's left is account/infra setup only (Stage E), which needs
> your Google Cloud + Railway access, not more code. Full plan:
> `MVP_ARCHITECTURE.md`.

---

## ▶ Pick up here next session — Stage E (accounts & deploy, not code)

1. **Register a Web application OAuth client** in Google Cloud Console
   (separate from the CLI's existing Desktop client — don't reuse it).
   Redirect URIs to add: `http://localhost:8000/auth/callback` and your future
   Railway domain's `/auth/callback`. Put the client ID/secret in `.env` as
   `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`.
2. **Local end-to-end test** before touching Railway:
   - `docker compose up -d` (local Postgres+pgvector, port 5433)
   - `uv run alembic upgrade head` (if not already applied)
   - `uv run uvicorn volley.web.app:app --reload` (web)
   - `uv run python -m volley.worker.run` (worker, separate terminal)
   - Connect your own Gmail through `http://localhost:8000`, confirm a draft
     actually lands in your Gmail Drafts folder.
3. **Railway**: new project → web service + worker service + managed
   Postgres. **Verify the `pgvector` extension is actually available** on
   whichever Postgres plan/template you pick before relying on it — this is
   the one real infra risk flagged in the architecture doc. Set all env vars
   (see `.env.example`), then run `alembic upgrade head` against it before
   first boot.
4. **Dogfood**: connect your own Gmail through the production URL, watch it
   run for a few days (check `draft_log` / worker logs), then add 3–5 friends
   as Google OAuth test users — no Google app verification needed yet, you're
   under the 100-test-user cap.

Ask Claude to walk through any of these steps live, especially #2 (fastest
way to see it working end to end).

---

## What's already built (Stages A–D, this session)

- **Storage**: Postgres + pgvector schema (`volley/db/models.py`), Alembic
  migration `0001_initial_schema` (hand-written HNSW index), `Repo(user_id)` /
  `SchedulerRepo` tenant isolation, Fernet token encryption
  (`volley/db/crypto.py`). Tested against a real local Postgres.
- **Agent**: `build_server_graph()` in `volley/agent/graph.py` — drafts-only,
  no human-approval interrupt, no checkpointer. `volley/rag/store.py` now
  serves both the legacy single-user ChromaDB path (CLI, unchanged) and the
  new pgvector multi-tenant path.
- **Web**: FastAPI app (`volley/web/`) — landing/privacy/tos,
  `/auth/google` → `/auth/callback` (forces consent+offline access so a
  refresh token is never silently missing), `/app` status page with
  pause/resume, `/disconnect` with hard delete.
- **Worker**: `volley/worker/scheduler.py` — multi-account polling via
  Gmail's `history.list` watermark (with historyId-expiry re-anchoring),
  dedup via `processed_messages`, retry/backoff, poison-message safety
  (a permanently-failing message is still marked processed so it doesn't
  retry forever), one account's failure never stops the sweep for others.

Full design reasoning, data model, and risk list: `MVP_ARCHITECTURE.md`.
Detailed build plan (already executed through Stage D): see the approved plan
from this session, or re-derive from the architecture doc if needed.

---

## Later (after phase 1 friends-test succeeds) — Phase 2, real launch

Out of scope until phase 1 is validated with real friend usage:
- Google app verification submission (needed once you go past 100 users).
- Billing (Stripe).
- A polished dashboard beyond the bare-bones status page.
- Sentry / real observability.
- Per-user settings beyond pause/disconnect, Pub/Sub push watching (instead
  of polling).

---

## Optional smaller improvements (nice-to-have, not blocking)

- [ ] **Grow the tone corpus.** Currently only ~8 sent emails passed the filter,
      which caps draft quality. Check whether `filter_for_corpus` in
      `volley/gmail/history.py` (min 20 words, drops noreply) is too aggressive,
      or just pull more sent mail.
- [ ] **Record the demo GIF** for the README's portfolio presentation (single
      biggest gap in the repo's first impression) — send yourself a lead-shaped
      email, record `uv run python -m volley watch` catching it, save to
      `docs/demo.gif`, uncomment the image line in `README.md`.
- [ ] **`ruff format` + a pre-commit hook** — extra hygiene signal (5 min).
- [ ] **A `--once` flag** for `watch` (single pass instead of the infinite loop).

---

## Reference — Setup & Run (already completed, kept for re-setup / new machine)

### Google Cloud / Gmail OAuth — CLI (✅ done)

<details>
<summary>One-time Google Cloud setup steps (CLI Desktop client)</summary>

1. **Create a project** — https://console.cloud.google.com → project dropdown →
   New Project → name `volley` → Create.
2. **Enable Gmail API** — APIs & Services → Library → search `Gmail API` → Enable.
3. **OAuth consent screen** — APIs & Services → OAuth consent screen → External →
   fill app name/support email/developer contact → Save. Add your own Gmail under
   **Test users**.
4. **Create credentials** — APIs & Services → Credentials → Create Credentials →
   OAuth client ID → **Desktop app** → Create → Download JSON → rename to
   `credentials.json` → place in project root.
5. **First auth run** — `uv run python scripts/test_gmail.py` → approve in browser
   → saves `token.json`.
</details>

### API key (✅ done — in `.env`)

```
GROQ_API_KEY=gsk_...         ← free key from https://console.groq.com/keys
```
> Embeddings run locally via `sentence-transformers` — no embedding API key needed.

### Per-phase test scripts

```bash
uv run python scripts/test_rag.py          # RAG (no Gmail needed)
uv run python scripts/test_classifier.py   # Classification (needs GROQ_API_KEY)
uv run python scripts/test_drafter.py      # Draft generation (needs GROQ_API_KEY)
uv run python scripts/test_gmail.py        # Gmail (needs credentials.json)
uv run python scripts/test_graph.py        # Full agent graph (needs GROQ_API_KEY)
uv run python scripts/test_hitl.py         # Human-in-the-loop
```

### Dev tooling

```bash
uv sync --group dev     # install pytest + ruff
uv run pytest -q        # run the full test suite (56 tests)
uv run ruff check .     # lint
```

### Run it — single-user CLI (still works, untouched by phase 1)

```bash
uv run python -m volley index           # build tone corpus from sent mail (run once)
uv run python -m volley watch --dry-run # verify pipeline, sends nothing
uv run python -m volley watch           # live — surfaces leads for [A]/[E]/[D]/[S]
```

### Run it — phase 1 multi-tenant server (local dev)

```bash
docker compose up -d                          # local Postgres + pgvector
uv run alembic upgrade head                   # apply schema
uv run uvicorn volley.web.app:app --reload    # web (landing, OAuth, status)
uv run python -m volley.worker.run            # worker (separate terminal)
```
