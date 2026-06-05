# Volley — Production Roadmap

> **Where we are**: A working single-user CLI tool. Runs on one machine, with one person's API keys, one OAuth token in a plaintext file, one local database. Every phase of the core agent loop is built and verified.
>
> **Where this doc takes us**: A trustworthy, multi-user, hosted SaaS that real people can sign up for, connect their Gmail to, rely on daily, and pay for.
>
> This is organized into phases like the build plan. Each phase is independently shippable and de-risks the next. Rough effort estimates are included — treat them as order-of-magnitude, not commitments.

---

## The Core Shift

The current build assumes **one user**. Production assumes **many users who must never see each other's data**. That single assumption ripples through auth, storage, the watcher, billing, and trust. Most of this roadmap is a consequence of that shift — plus the non-code work (legal, Google verification, trust) that "reading and sending people's email" demands.

---

## Phase P1 — Multi-Tenancy Foundation

**Goal**: Every piece of data is tied to a `user_id` and isolated. User A can never access User B's emails, drafts, tokens, or tone corpus.

**Why first**: This is the architectural foundation. Everything else (web UI, billing, hosting) assumes it exists. Retrofitting multi-tenancy later means rewriting everything, so it goes first.

**What we build**:
- A `users` table (Postgres) — the source of truth for accounts.
- Add `user_id` as a foreign key to every data structure: tokens, drafts, processed-message IDs, tone corpus entries.
- Replace local SQLite checkpointer with **Postgres checkpointer** (`langgraph-checkpoint-postgres`), partitioned by user.
- Replace single local ChromaDB with a **per-user namespace** in a hosted vector DB (Pinecone namespaces, or Postgres + pgvector with a `user_id` column).
- A data-access layer that *always* scopes queries by `user_id` — no query can accidentally cross tenants.

**Key risk**: Tenant data leakage. Every single query must be scoped. This needs tests that specifically try to access another user's data and confirm it fails.

**Effort**: Large — this is a real rewrite of the storage and identity layers.

---

## Phase P2 — Per-User Authentication & Token Management

**Goal**: Users sign up, log in, and connect their own Gmail. Their OAuth tokens are stored securely, encrypted, and refreshed automatically — never in a plaintext file.

**What we build**:
- **App-level auth**: users create a Volley account (email/password or "Sign in with Google"). Use a managed auth provider (Clerk, Auth0, or Supabase Auth) — do not roll your own.
- **Gmail OAuth per user**: each user runs the Google consent flow once; we store *their* refresh token, encrypted at rest (e.g. with a KMS-managed key), in the database keyed by `user_id`.
- **Token refresh service**: a background process that refreshes access tokens before expiry for every connected user.
- **Disconnect flow**: a user can revoke Gmail access and delete their data at any time.

**Key risk**: A leaked database = leaked access to everyone's Gmail. Tokens must be encrypted, the encryption key must live in a secrets manager (not the DB), and access must be audited.

**Effort**: Large — security-critical, no shortcuts.

---

## Phase P3 — Hosted, Always-On Inbox Watching

**Goal**: The system watches every connected user's inbox 24/7 on a server, not on anyone's laptop.

**Why polling doesn't scale**: Looping over hundreds of inboxes every 60 seconds burns API quota and is slow. Production uses **Gmail Push Notifications**.

**What we build**:
- **Gmail Push via Pub/Sub**: each connected user's mailbox registered with `users.watch()`. Gmail pushes a notification to a Pub/Sub topic the instant an email arrives.
- **A subscriber service**: receives the push, looks up which user it belongs to, and enqueues an agent run for that user's new email.
- **A job queue** (e.g. a task queue / worker pool): agent runs execute as background jobs, so a slow LLM call for one user doesn't block others.
- **`watch()` renewal**: Gmail watches expire after 7 days — a scheduled job re-registers them.
- **Hosting**: a cloud platform that supports always-on background workers and a public webhook endpoint (Vercel functions for the API + a dedicated worker host, or a container platform).

**Key risk**: Missed emails (a dropped notification = a missed lead) and duplicate processing. Need idempotency (dedup by message ID, already built) plus a periodic reconciliation sync as a safety net.

**Effort**: Large — this is the infrastructure backbone.

---

## Phase P4 — Web Application & Approval UI

**Goal**: A real interface. Users log in to a dashboard, see pending drafts, and approve / edit / send with a click. The terminal `[A/E/S]` prompt becomes a web experience.

**What we build**:
- **Web app** (Next.js on Vercel is the natural fit):
  - Onboarding: sign up → connect Gmail → build tone corpus (with a progress bar).
  - **Draft inbox**: pending drafts as cards — original email on one side, editable draft on the other, Approve / Edit / Send / Skip buttons.
  - History: every email processed, what was classified, what was sent.
  - Settings: confidence threshold, which intents to auto-draft, pause/resume, disconnect.
- **Real-time updates**: new drafts appear without refresh (websockets or polling).
- **Approval triggers the existing LangGraph resume** — the web button calls an API that resumes the paused graph with the user's decision. The agent loop you already built stays exactly as-is; the UI just becomes the front-end for the `interrupt`.
- **Optional: email/mobile approval** — drafts pushed to the user's phone or a dedicated label so they can approve on the go.

**Effort**: Large — this is a whole frontend plus the API layer that bridges it to the agent.

---

## Phase P5 — Google OAuth Verification (Trust Gate)

**Goal**: Remove the scary "unverified app" warning so real users will actually connect their Gmail. This is a hard external gate, not optional.

**Why it matters**: Gmail scopes (`gmail.readonly`, `gmail.send`) are **restricted/sensitive scopes**. Until Google verifies the app, users see an alarming "Google hasn't verified this app" screen and you're capped at 100 test users.

**What this requires (Google's checklist)**:
- A published **privacy policy** at a real domain, clearly explaining what data you access and why.
- A **homepage** that explains the app.
- A **demo video** showing the OAuth flow and how each requested scope is used.
- Written **justification** for each restricted scope.
- Domain ownership verification.
- **Possibly a third-party security assessment** (CASA) — restricted scopes can require an annual independent security audit, which costs money and time.

**Key reality**: This takes **weeks**, runs on Google's timeline, and should be **started early and in parallel** with P3/P4 — not at the end. The build can be done while verification is pending.

**Effort**: Medium coding (privacy policy page, homepage), but **long calendar time** and mostly paperwork/process.

---

## Phase P6 — Trust, Privacy & Legal

**Goal**: Everything that makes a stranger comfortable letting Volley read and send their email.

**Why it's non-negotiable**: You are handling people's private correspondence and acting on their behalf. Trust is the entire product. A single mishandled-data incident ends it.

**What we build / write**:
- **Privacy Policy** — what you collect, how it's stored, that you don't sell it, that you don't train models on their email, retention periods, deletion rights.
- **Terms of Service** — acceptable use, liability limits, the fact that the human approves every send.
- **Data handling guarantees**:
  - Encryption in transit (TLS) and at rest (DB + tokens).
  - Clear data retention + a real "delete my account and all data" function.
  - Minimize what's stored — do you need to keep full email bodies, or just embeddings?
- **GDPR / privacy compliance** if you have EU users: right to access, right to deletion, data processing agreement, a lawful basis for processing.
- **A security posture**: secrets in a manager (not env files), least-privilege access, audit logging, dependency scanning.
- **Incident plan**: what you do if there's a breach.

**Key principle**: Collect the minimum, encrypt everything, delete on request, never train on user data, and say all of this plainly.

**Effort**: Medium code, significant writing/process. Consider a lawyer review before taking money.

---

## Phase P7 — Reliability, Observability & Scale

**Goal**: It stays up, you know when it doesn't, and it handles growing load without falling over.

**What we build**:
- **Structured logging + centralized log storage** (beyond the local `volley.log`).
- **Error tracking** (e.g. Sentry) — you get alerted when an agent run fails for a real user.
- **Metrics & dashboards**: emails processed, drafts generated, approval rate, LLM latency, error rate, per-user cost.
- **Rate limit handling**: graceful backoff for Gmail and LLM APIs across all users (basic retry is built; production needs queue-level throttling).
- **Health checks & uptime monitoring** for the watcher and webhook endpoints.
- **Database backups** and a tested restore procedure.
- **Graceful degradation**: if the LLM is down, queue and retry rather than dropping the email.

**Effort**: Medium — mostly wiring in standard tooling, but essential.

---

## Phase P8 — Cost Model & Production LLM Stack

**Goal**: The economics actually work when you're paying per call instead of using free tiers.

**Why it changes**: Groq's free tier and local embeddings are perfect for one user. At scale: free tiers rate-limit, local embeddings need a real server's CPU/RAM, and every classification + draft has a marginal cost.

**What we decide / build**:
- **LLM provider strategy**: paid Groq, or a gateway (e.g. Vercel AI Gateway) for provider fallback and cost tracking. Keep classification on a cheap small model, drafting on a stronger one — the split you already have.
- **Embeddings**: hosted embedding API, or a managed inference endpoint for the local model. Account for the cost of indexing every user's sent history.
- **Vector DB**: a hosted, multi-tenant vector store with per-user namespaces (cost scales with corpus size × users).
- **Per-user cost tracking**: know what each user costs you so pricing makes sense.
- **Caps & abuse protection**: per-user limits so one account can't run up an unbounded bill.

**Effort**: Medium — mostly decisions + instrumentation, but get the math right before pricing.

---

## Phase P9 — Billing & Monetization

**Goal**: People can pay. Subscriptions, plans, limits, upgrades.

**What we build**:
- **Payment processor** (Stripe is standard) — subscriptions, trials, cards, invoices, failed-payment handling.
- **Plan tiers**, e.g.:
  - *Free*: connect 1 inbox, N drafts/month, Volley branding.
  - *Pro*: higher/unlimited volume, faster models, priority.
  - *Team*: multiple inboxes/seats.
- **Usage enforcement**: gate features and volume by plan; the per-user limits from P8 plug in here.
- **Billing portal**: upgrade, downgrade, cancel, view invoices.
- **Free trial** so people experience the value before paying.

**Key principle**: Pricing must clear your per-user cost (P8) with margin. Charge for the value (time saved, leads not dropped), not for tokens.

**Effort**: Medium — Stripe does the heavy lifting; the work is plan logic and enforcement.

---

## Phase P10 — Quality, Polish & Differentiation

**Goal**: The things that make people *keep* paying and tell others.

**What we build**:
- **Draft quality feedback loop**: log approve-unchanged vs. edited vs. rejected. Use it to measure and improve tone matching over time. (The auto-index-on-send from build Phase 10 is the seed of this.)
- **Better onboarding**: the first draft a user sees must feel like *them* — get the tone corpus build right and fast.
- **Smarter classification**: let users define their own intents / what counts as a lead for their business.
- **Analytics for the user**: "Volley drafted 47 replies this month, you approved 41, saving ~6 hours."
- **Regenerate-with-instructions**: "make it shorter / more formal" (the routing for this was sketched in the build).
- **Edge-case hardening**: attachments, calendar invites, threads, multi-language, very long emails.

**Effort**: Ongoing — this is the product, never "done."

---

## Suggested Sequencing

The order that de-risks fastest and keeps slow external processes running in parallel:

```
1. P1  Multi-tenancy          ─┐
2. P2  Auth & tokens           │  Foundation — prove it works for a
3. P3  Hosted watcher          │  small group of real, isolated users
4. P4  Web UI                 ─┘

   ↳ START P5 (Google verification) EARLY, in parallel with P3/P4 —
     it's slow and gated by Google, so kick it off as soon as you
     have a privacy policy + homepage.

5. P6  Trust / legal          ─┐  Required before taking money or
6. P7  Reliability / scale     │  going public
7. P8  Cost model             ─┘

8. P9  Billing                ─┐  Monetize once it's trustworthy
9. P10 Quality / polish       ─┘  and reliable
```

---

## Honest Timeline

| Milestone | Rough effort | Notes |
|-----------|-------------|-------|
| **Personal tool (you)** | Done ✅ | Already built and verified |
| **Handful of trusted users** | ~2–4 weeks | P1–P4, stay under Google's 100-test-user cap to skip verification |
| **Public, trustworthy, paid SaaS** | ~2–4 months | All phases. A big chunk is *waiting* on Google verification and writing legal/trust material — not coding |

The coding is the smaller half. The larger half is **trust, verification, and the operational discipline** of running a service that touches people's private email. That's what separates "a cool project" from "something strangers pay for and rely on."

---

## The One Thing to Never Compromise

Volley's entire premise is **human approval before send**. As you scale, the pressure to add a "fully autonomous mode" will grow. Resist defaulting it on. The approval step is not a limitation to engineer away — it is the trust contract that makes the product safe to hand to strangers. Keep the human in the loop, and Volley stays trustworthy by design.
