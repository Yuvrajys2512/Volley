# Volley — To Do

## Google Cloud Setup (do before first real run)

### Step 1 — Create a Google Cloud Project
1. Go to https://console.cloud.google.com
2. Click the project dropdown (top left) → **New Project**
3. Name it `volley` → **Create**

### Step 2 — Enable the Gmail API
1. In the left menu → **APIs & Services** → **Library**
2. Search `Gmail API` → click it → **Enable**

### Step 3 — Configure OAuth Consent Screen
1. **APIs & Services** → **OAuth consent screen**
2. Choose **External** → **Create**
3. Fill in:
   - App name: `Volley`
   - User support email: your Gmail
   - Developer contact: your Gmail
4. Click through **Scopes** (skip for now) → **Save and Continue**
5. On **Test users** → **Add Users** → add your own Gmail address → **Save**

### Step 4 — Create OAuth Credentials
1. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth client ID**
2. Application type: **Desktop app**
3. Name: `Volley Desktop`
4. Click **Create** → **Download JSON**
5. Rename the downloaded file to `credentials.json`
6. Place it in the project root: `volley/credentials.json`

### Step 5 — First Auth Run
Once `credentials.json` is in the project root, run:
```bash
uv run python scripts/test_gmail.py
```
A browser window will open → log in with your Gmail → approve access.
This saves `token.json` in the project root. Gmail is now connected.

---

## API Keys (add to .env)

Copy `.env.example` to `.env` and fill in:

```
OPENAI_API_KEY=sk-...        ← get from https://platform.openai.com/api-keys
```

---

## Test Each Phase in Order

Run these after API keys and credentials are set up:

```bash
# Phase 3 — RAG (no Gmail needed, uses sample data)
uv run python scripts/test_rag.py

# Phase 4 — Classification (needs OPENAI_API_KEY)
uv run python scripts/test_classifier.py

# Phase 5 — Draft generation (needs OPENAI_API_KEY)
uv run python scripts/test_drafter.py

# Phase 2 — Gmail (needs credentials.json)
uv run python scripts/test_gmail.py

# Phase 6 — Full agent graph (needs OPENAI_API_KEY)
uv run python scripts/test_graph.py

# Phase 7 — Human-in-the-loop (needs OPENAI_API_KEY + credentials.json)
uv run python scripts/test_hitl.py
```

---

## Go Live

```bash
# Build tone corpus from your real sent mail (run once)
uv run python -m volley index

# Dry run — verify everything works without sending anything
uv run python -m volley watch --dry-run

# Go live
uv run python -m volley watch
```
