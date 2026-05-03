"""Register your Partner domain with Tesla. One-shot, run once after the
public key is hosted.

Precondition: you've already:
    1. Run scripts/generate_virtual_key.py (generates the keypair)
    2. Uploaded the public key so this returns 200:
         https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem

This script:
    1. Uses client_credentials grant to get a partner-level access token
    2. POST /api/1/partner_accounts with your domain
    3. GET /api/1/partner_accounts/public_key to confirm Tesla can fetch
       your public key

After a successful run, OAuth authorization codes from your app will work.
Before this, users would get "app not registered for this domain".
"""
from __future__ import annotations

import sys
from urllib.parse import urlparse

import httpx

from tesla_skill.config import settings


def main() -> None:
    for name in ("tesla_client_id", "tesla_client_secret", "tesla_redirect_uri"):
        if not getattr(settings, name):
            print(f"ERROR: {name.upper()} not set in .env", file=sys.stderr)
            sys.exit(1)

    domain = urlparse(settings.tesla_redirect_uri).hostname
    if not domain:
        print(
            f"ERROR: could not parse hostname from TESLA_REDIRECT_URI={settings.tesla_redirect_uri}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"→ Getting partner access token (audience={settings.tesla_fleet_api_base})")
    r = httpx.post(
        f"{settings.tesla_auth_base}/oauth2/v3/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.tesla_client_id,
            "client_secret": settings.tesla_client_secret,
            "scope": "openid vehicle_device_data vehicle_cmds vehicle_charging_cmds",
            "audience": settings.tesla_fleet_api_base,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    print("  ✅ got partner token")

    print(f"→ Registering domain: {domain}")
    r = httpx.post(
        f"{settings.tesla_fleet_api_base}/api/1/partner_accounts",
        json={"domain": domain},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"  ❌ {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✅ registered: {r.json()}")

    print("→ Verifying Tesla can fetch your public key")
    r = httpx.get(
        f"{settings.tesla_fleet_api_base}/api/1/partner_accounts/public_key",
        params={"domain": domain},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"  ❌ {r.status_code}: {r.text}", file=sys.stderr)
        print(f"     Check that https://{domain}/.well-known/appspecific/com.tesla.3p.public-key.pem returns 200", file=sys.stderr)
        sys.exit(1)
    print(f"  ✅ key verified: {r.json()}")

    print()
    print("🎉 Partner domain registered. OAuth flows will now work.")
    print("   Next: run the authorize flow:")
    print("     - For server install:  python -m tesla_skill.auth.callback_server")
    print("                             then visit https://<your-domain>/oauth/authorize")
    print("     - For local install:   python -m tesla_skill.auth.authorize")


if __name__ == "__main__":
    main()
