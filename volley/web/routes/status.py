from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from volley.db.engine import session_scope
from volley.db.repo import Repo
from volley.gmail.auth import credentials_for_user

templates = Jinja2Templates(directory="volley/web/templates")

router = APIRouter()


def _require_user_id(request: Request) -> str:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return user_id


def _status_context(user_id: str) -> dict:
    with session_scope() as session:
        repo = Repo(session, user_id)
        user = repo.get_user()
        account = repo.get_gmail_account()
        if user is None or account is None:
            raise HTTPException(status_code=404, detail="Account not found.")
        return {
            "email": user.email,
            "user_status": user.status,
            "account_status": account.watch_status,
            "corpus_size": repo.corpus_size(),
            "draft_count": repo.draft_count(),
            # Corpus build is considered "done" once steady-state polling has
            # a watermark — set once by the worker after build_corpus finishes.
            "corpus_building": account.last_history_id is None,
        }


@router.get("/app")
def app_status_page(request: Request):
    user_id = _require_user_id(request)
    context = _status_context(user_id)
    return templates.TemplateResponse(request, "status.html", context)


@router.get("/app/status")
def app_status_fragment(request: Request):
    user_id = _require_user_id(request)
    context = _status_context(user_id)
    return templates.TemplateResponse(request, "status_fragment.html", context)


@router.post("/app/toggle-pause")
def toggle_pause(request: Request):
    user_id = _require_user_id(request)
    with session_scope() as session:
        repo = Repo(session, user_id)
        user = repo.get_user()
        if user is None:
            raise HTTPException(status_code=404, detail="Account not found.")
        repo.set_user_status("active" if user.status == "paused" else "paused")
    return RedirectResponse("/app", status_code=303)


@router.post("/disconnect")
def disconnect(request: Request):
    user_id = _require_user_id(request)

    try:
        creds = credentials_for_user(user_id)
        import requests

        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": creds.refresh_token},
            headers={"content-type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except Exception:
        pass  # best-effort revoke — the hard delete below is what actually matters

    with session_scope() as session:
        Repo(session, user_id).delete_all_user_data()

    request.session.clear()
    return RedirectResponse("/", status_code=303)
