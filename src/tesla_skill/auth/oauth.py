"""Tesla OAuth 2.0 — authorize URL builder, code exchange, refresh.

Endpoints (region-specific, configured via .env):
    Authorize: <TESLA_AUTH_BASE>/oauth2/v3/authorize
    Token:     <TESLA_AUTH_BASE>/oauth2/v3/token

Flow:
    1. build_authorize_url(state) -> user visits, logs in, authorizes
    2. Tesla redirects to TESLA_REDIRECT_URI?code=...&state=...
    3. exchange_code(code) -> TokenBundle, persisted via storage
    4. get_valid_access_token() -> auto-refresh if near expiry
"""
from __future__ import annotations

import logging
import secrets
import time
from urllib.parse import urlencode

import httpx

from tesla_skill.auth import storage
from tesla_skill.auth.storage import TokenBundle
from tesla_skill.config import settings

log = logging.getLogger(__name__)

# Scopes required by this project. If you change this, update the developer
# portal app config too.
SCOPES = [
    "openid",
    "offline_access",          # required to get refresh_token
    "vehicle_device_data",     # read vehicle state
    "vehicle_cmds",            # control commands (lock, climate, signals)
    "vehicle_charging_cmds",   # charging start/stop/limit
]


def build_authorize_url(state: str | None = None, redirect_uri: str | None = None) -> tuple[str, str]:
    """Return (authorize_url, state). User opens the URL in their browser."""
    if state is None:
        state = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": settings.tesla_client_id,
        "redirect_uri": redirect_uri or settings.tesla_redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        "prompt": "login",
    }
    url = f"{settings.tesla_auth_base}/oauth2/v3/authorize?{urlencode(params)}"
    return url, state


def exchange_code(code: str, redirect_uri: str | None = None) -> TokenBundle:
    """Exchange authorization code for tokens and persist them."""
    body = {
        "grant_type": "authorization_code",
        "client_id": settings.tesla_client_id,
        "client_secret": settings.tesla_client_secret,
        "code": code,
        "redirect_uri": redirect_uri or settings.tesla_redirect_uri,
        "audience": settings.tesla_fleet_api_base,
    }
    r = httpx.post(
        f"{settings.tesla_auth_base}/oauth2/v3/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    bundle = TokenBundle(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=int(time.time()) + int(data.get("expires_in", 28800)),
        id_token=data.get("id_token"),
        scope=data.get("scope"),
    )
    storage.save(bundle)
    log.info("Exchanged code -> tokens (scope=%s)", bundle.scope)
    return bundle


def refresh_tokens(existing: TokenBundle) -> TokenBundle:
    """Use refresh_token to get a new access_token. Refresh tokens rotate."""
    body = {
        "grant_type": "refresh_token",
        "client_id": settings.tesla_client_id,
        "refresh_token": existing.refresh_token,
    }
    r = httpx.post(
        f"{settings.tesla_auth_base}/oauth2/v3/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    bundle = TokenBundle(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", existing.refresh_token),
        expires_at=int(time.time()) + int(data.get("expires_in", 28800)),
        id_token=data.get("id_token", existing.id_token),
        scope=data.get("scope", existing.scope),
    )
    storage.save(bundle)
    log.info("Refreshed tokens (new expires_at=%s)", bundle.expires_at)
    return bundle


def get_valid_access_token() -> str:
    """Return a fresh access_token, refreshing if near expiry.

    Raises RuntimeError if no tokens are stored — the user must complete
    the authorize flow first (scripts/authorize.py or callback_server).
    """
    bundle = storage.load()
    if bundle is None:
        raise RuntimeError(
            "No Tesla tokens stored. Run the authorize flow:\n"
            "  python scripts/authorize.py    # local mode\n"
            "or visit /oauth/authorize on your callback server."
        )
    if bundle.is_near_expiry:
        bundle = refresh_tokens(bundle)
    return bundle.access_token
