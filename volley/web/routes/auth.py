import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from volley.db.crypto import encrypt
from volley.db.engine import session_scope
from volley.db.repo import Repo, get_or_create_user_by_email
from volley.gmail.auth import SCOPES_WEB, build_web_flow

router = APIRouter()


@router.get("/auth/google")
def start_google_auth(request: Request):
    state = secrets.token_urlsafe(24)
    flow = build_web_flow(state=state)
    # access_type=offline + prompt=consent are required to get a refresh_token
    # back — Google only issues one on first consent or when both are forced,
    # so a repeat-consent user would otherwise silently get no refresh_token.
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="false",
    )
    request.session["oauth_state"] = state
    return RedirectResponse(auth_url)


@router.get("/auth/callback")
def google_auth_callback(request: Request, code: str | None = None, state: str | None = None):
    expected_state = request.session.pop("oauth_state", None)
    if not code or not state or state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state or missing code.")

    flow = build_web_flow(state=state)
    flow.fetch_token(code=code)
    creds = flow.credentials

    if not creds.refresh_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google did not return a refresh token. This can happen if you've "
                "already granted access before — revoke Volley's access in your Google "
                "account settings and try connecting again."
            ),
        )

    import requests

    userinfo = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=10,
    ).json()
    email = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Could not read account email from Google.")

    with session_scope() as session:
        user = get_or_create_user_by_email(session, email)
        repo = Repo(session, user.id)
        repo.upsert_gmail_account(
            refresh_token_enc=encrypt(creds.refresh_token),
            granted_scopes=list(creds.scopes or SCOPES_WEB),
        )
        repo.enqueue_job("index_corpus", payload={})
        user_id = str(user.id)

    request.session["user_id"] = user_id
    return RedirectResponse("/app")
