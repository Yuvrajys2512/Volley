from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="volley/web/templates")

router = APIRouter()

PRIVACY_HTML = """
<p>Volley reads your Gmail inbox and sent mail to classify inbound leads and
learn your writing tone, and creates draft replies in your Gmail Drafts
folder. Volley cannot send email on your behalf — it only has permission to
read your mail and create drafts.</p>
<p>Your data (tone corpus, processed-message records, draft log) is deleted
immediately and permanently when you disconnect your account from the
status page.</p>
<p>This is an early, invite-only version of Volley for a small group of
testers. Questions? Ask whoever invited you.</p>
"""

TOS_HTML = """
<p>Volley is provided as-is, for a small group of invited testers, with no
uptime or accuracy guarantees. Drafts are suggestions only — you are always
responsible for reviewing and sending (or not sending) anything from your
Gmail account.</p>
<p>You can disconnect and delete your data at any time from the status page.</p>
"""


@router.get("/")
def landing(request: Request):
    return templates.TemplateResponse(request, "landing.html", {})


@router.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(
        request, "legal.html", {"title": "Privacy", "content": PRIVACY_HTML}
    )


@router.get("/tos")
def tos(request: Request):
    return templates.TemplateResponse(
        request, "legal.html", {"title": "Terms", "content": TOS_HTML}
    )
