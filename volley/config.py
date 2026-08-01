import os

from dotenv import load_dotenv

load_dotenv()


def require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


# LLM — Groq (free tier)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Gmail OAuth
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")

# RAG — embeddings run locally via sentence-transformers (no API key needed)
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

# Agent
CLASSIFICATION_MODEL = os.getenv("CLASSIFICATION_MODEL", "llama-3.3-70b-versatile")
DRAFT_MODEL = os.getenv("DRAFT_MODEL", "llama-3.3-70b-versatile")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# Watcher
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

# Phase 1 — multi-tenant server (web + worker)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://volley:volley@localhost:5433/volley")
FERNET_KEY = os.getenv("FERNET_KEY", "")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "")

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback"
)

WORKER_POLL_INTERVAL_SECONDS = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "90"))
MAX_RUNS_PER_DAY_PER_USER = int(os.getenv("MAX_RUNS_PER_DAY_PER_USER", "200"))
