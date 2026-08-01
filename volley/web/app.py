from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from volley.config import SESSION_SECRET_KEY
from volley.web.routes import auth, public, status


def create_app() -> FastAPI:
    if not SESSION_SECRET_KEY:
        raise RuntimeError(
            "SESSION_SECRET_KEY is not set. Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    app = FastAPI(title="Volley")
    app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY, https_only=False)

    app.include_router(public.router)
    app.include_router(auth.router)
    app.include_router(status.router)

    return app


app = create_app()
