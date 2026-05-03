"""FastAPI OAuth callback service.

Use this when running tesla-skill on a public server with your own domain.
For purely-local install, use `python -m tesla_skill.auth.authorize` instead.

Reverse proxy recommendation (e.g. nginx):

    server {
        listen 443 ssl;
        server_name your.domain.com;
        # ... cert config ...

        # Static — serve directly
        location ^~ /.well-known/ {
            root /var/www/your.domain.com;
        }
        location = /privacy.html {
            root /var/www/your.domain.com;
        }

        # Dynamic — proxy to this app
        location / {
            proxy_pass http://127.0.0.1:8001;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

Routes:
    GET /                  → index page (Tesla auditor crawls this)
    GET /healthz           → {"status": "ok"}
    GET /oauth/authorize   → redirect user to Tesla login
    GET /oauth/callback    → receive code from Tesla, exchange, persist
"""
from __future__ import annotations

import logging
import secrets

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from tesla_skill.auth import oauth

log = logging.getLogger(__name__)

app = FastAPI(title="tesla-skill OAuth Callback", version="0.1.0")

# In-memory state store for CSRF protection. Sufficient for single-user
# single-process. For multi-replica, switch to Redis or signed cookies.
_pending_states: set[str] = set()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Root page — must return 200 so Tesla's auditor can verify the domain."""
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>tesla-skill</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:60px auto;padding:0 20px">
<h1>tesla-skill</h1>
<p>Personal Tesla integration service.</p>
<p>See <a href="/privacy.html">Privacy Policy</a>.</p>
</body></html>"""


@app.get("/oauth/authorize")
def authorize() -> RedirectResponse:
    """Generate state, redirect user to Tesla login."""
    state = secrets.token_urlsafe(24)
    _pending_states.add(state)
    url, _ = oauth.build_authorize_url(state=state)
    log.info("Starting OAuth flow with state=%s...", state[:8])
    return RedirectResponse(url, status_code=302)


@app.get("/oauth/callback", response_class=HTMLResponse)
def callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
) -> str:
    if error:
        log.error("OAuth error from Tesla: %s — %s", error, error_description)
        raise HTTPException(status_code=400, detail=f"{error}: {error_description}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code or state")

    if state not in _pending_states:
        log.error("State mismatch: %s... not in pending set", state[:8])
        raise HTTPException(status_code=400, detail="invalid state (possible CSRF)")
    _pending_states.discard(state)

    try:
        bundle = oauth.exchange_code(code)
    except Exception as e:
        log.exception("Code exchange failed")
        raise HTTPException(status_code=500, detail=f"token exchange failed: {e}")

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Authorized</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:60px auto;padding:0 20px">
<h1>✅ Authorized</h1>
<p>Your Tesla account is now linked. You can close this page.</p>
<p>Token has been encrypted and stored on the server. It will auto-refresh.</p>
<p style="color:#888;font-size:13px">Scope: {bundle.scope or 'n/a'}</p>
</body></html>"""


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


def main() -> None:
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    uvicorn.run(
        "tesla_skill.auth.callback_server:app",
        host="127.0.0.1",
        port=8001,
        reload=False,
    )


if __name__ == "__main__":
    main()
