import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build

from volley.config import (
    GOOGLE_CREDENTIALS_FILE,
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
    GOOGLE_TOKEN_FILE,
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service():
    """Authenticate and return an authorized Gmail API service client.

    CLI-only: a Desktop-app OAuth flow reading/writing a single local
    token.json/credentials.json pair. Unrelated to the server's per-user web
    OAuth flow below — the two use separate Google Cloud OAuth clients.
    """
    creds = None

    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
            raise FileNotFoundError(
                f"credentials.json not found at '{GOOGLE_CREDENTIALS_FILE}'.\n"
                "Download it from Google Cloud Console → APIs & Services → Credentials."
            )
        flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    with open(GOOGLE_TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ── Phase 1 — multi-tenant web OAuth flow ───────────────────────────────────────
# Drafts-only: no gmail.send scope, so the server can never send on a user's
# behalf — only read their inbox/sent mail and create drafts.

SCOPES_WEB = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def _web_client_config() -> dict:
    return {
        "web": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_OAUTH_REDIRECT_URI],
        }
    }


def build_web_flow(state: str | None = None) -> Flow:
    """Build the web OAuth `Flow` used by /auth/google and /auth/callback."""
    flow = Flow.from_client_config(
        _web_client_config(),
        scopes=SCOPES_WEB,
        redirect_uri=GOOGLE_OAUTH_REDIRECT_URI,
        state=state,
    )
    return flow


def credentials_for_user(user_id) -> Credentials:
    """Rebuild live Credentials for a connected user from their encrypted,
    stored refresh token, refreshing the access token in memory. The access
    token is never persisted — only the refresh token is stored (encrypted).
    """
    from volley.db import crypto
    from volley.db.engine import session_scope
    from volley.db.repo import Repo

    with session_scope() as session:
        repo = Repo(session, user_id)
        account = repo.get_gmail_account()
        if account is None:
            raise LookupError(f"No connected Gmail account for user {user_id}")
        refresh_token = crypto.decrypt(account.refresh_token_enc)
        scopes = account.granted_scopes

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_OAUTH_CLIENT_ID,
        client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=scopes,
    )
    creds.refresh(Request())
    return creds


def gmail_service_for_user(user_id):
    """Build an authorized Gmail API service client for a connected user."""
    return build("gmail", "v1", credentials=credentials_for_user(user_id))
