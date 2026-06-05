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
