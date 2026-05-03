"""Local-mode OAuth authorize helper.

For users who don't want to run a public callback server. Spawns a one-shot
HTTP server on http://localhost:8765, opens the user's browser to Tesla's
authorize URL, catches the redirect, exchanges the code, and exits.

Tesla allows http://localhost:* as a registered redirect URI even though
it normally requires HTTPS. Add this to your developer portal app's
"Allowed Redirect URIs" before running:

    http://localhost:8765/callback

Usage:
    python -m tesla_skill.auth.authorize

Or via the script entrypoint installed by `pip install -e .`:
    tesla-skill-authorize
"""
from __future__ import annotations

import http.server
import logging
import secrets
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from typing import Any

from tesla_skill.auth import oauth

LOCAL_PORT = 8765
LOCAL_REDIRECT = f"http://localhost:{LOCAL_PORT}/callback"

log = logging.getLogger(__name__)


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    server_received: dict[str, Any] = {}

    def do_GET(self) -> None:  # noqa: N802 — required by stdlib base class
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = dict(urllib.parse.parse_qsl(parsed.query))
        _CallbackHandler.server_received.update(params)

        body = (
            "<!DOCTYPE html><html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            "<h2>✅ Authorization received</h2>"
            "<p>You can close this tab. Return to your terminal.</p>"
            "</body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 — stdlib name
        pass  # silence default access-log noise


def _wait_for_callback(timeout_sec: int = 300) -> dict[str, Any]:
    """Run the one-shot HTTP server until it gets a /callback hit (or timeout)."""
    httpd = socketserver.TCPServer(("127.0.0.1", LOCAL_PORT), _CallbackHandler)
    httpd.timeout = 1
    deadline_thread_event = threading.Event()

    def serve():
        while not deadline_thread_event.is_set() and not _CallbackHandler.server_received:
            httpd.handle_request()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)
    deadline_thread_event.set()
    httpd.server_close()
    return dict(_CallbackHandler.server_received)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    state = secrets.token_urlsafe(24)
    url, _ = oauth.build_authorize_url(state=state, redirect_uri=LOCAL_REDIRECT)

    print(f"Opening Tesla authorize URL in your browser...")
    print(f"If it doesn't open, paste this:\n  {url}\n")
    print(f"Listening for redirect on {LOCAL_REDIRECT} ...")
    print(f"(Make sure http://localhost:{LOCAL_PORT}/callback is registered as an")
    print(f" Allowed Redirect URI in your Tesla developer portal app.)")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    received = _wait_for_callback(timeout_sec=300)
    if not received:
        print("Timed out waiting for redirect.", file=sys.stderr)
        sys.exit(1)

    if received.get("error"):
        print(f"OAuth error: {received['error']} — {received.get('error_description')}", file=sys.stderr)
        sys.exit(1)

    if received.get("state") != state:
        print(f"State mismatch! Got {received.get('state')[:8]}..., expected {state[:8]}...", file=sys.stderr)
        sys.exit(1)

    code = received.get("code")
    if not code:
        print(f"No code in callback: {received}", file=sys.stderr)
        sys.exit(1)

    print("Code received. Exchanging for tokens...")
    bundle = oauth.exchange_code(code, redirect_uri=LOCAL_REDIRECT)
    print(f"✅ Authorized. Tokens saved (scope={bundle.scope}).")
    print(f"   Expires at: {bundle.expires_at} (auto-refreshes).")


if __name__ == "__main__":
    main()
