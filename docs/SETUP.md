# Setup Guide (manual reference)

This is a fuller version of [SKILL.md](../SKILL.md) for users running the install themselves without an agent. If you're using an AI agent to install, skip this — the agent will read SKILL.md and walk you through.

## Prerequisites

- A Tesla you own (2021+ for full Fleet API support including TVCP control commands)
- Tesla account credentials (the one in your Tesla mobile app)
- A public domain you control
- Python 3.11+
- Go 1.22+ *(only needed for control commands — Phase 9)*

## Phase 1 — Tesla Developer registration

1. Go to <https://developer.tesla.com> (or <https://developer.tesla.cn> for China-region vehicles)
2. Sign in with your Tesla owner account
3. **Register Application** with these fields:

   | Field | Value |
   |---|---|
   | Application Name | (anything, e.g. "Tesla Skill for Alex") |
   | Description | "Personal Tesla control via AI agents" |
   | Purpose | Personal Use |
   | Allowed Origin URL | `https://<your-domain>` (no path, no trailing slash) |
   | Allowed Redirect URI | `https://<your-domain>/oauth/callback` |
   | Privacy Policy URL | `https://<your-domain>/privacy.html` |
   | OAuth Grant Type | "Authorization Code and Machine to Machine" |
   | Scopes | `openid` `offline_access` `vehicle_device_data` `vehicle_cmds` `vehicle_charging_cmds` |

4. Submit → wait 1–3 business days for review

⚠️ Tesla rejects URLs containing the literal word "tesla". Use a neutral subdomain: `car.<your-domain>`, `auto.<your-domain>`, `garage.<your-domain>`, etc.

5. Once approved, copy from the developer console:
   - **Client ID** (public)
   - **Client Secret** (treat like a password — never commit, never share)

## Phase 2 — Clone & install

```bash
git clone https://github.com/Vibetool/tesla-skill.git
cd tesla-skill
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Phase 3 — Configure

```bash
cp .env.example .env
```

Edit `.env`:

```bash
USE_MOCK=false
TESLA_CLIENT_ID=<from Phase 1>
TESLA_CLIENT_SECRET=<from Phase 1>
TESLA_REDIRECT_URI=https://<your-domain>/oauth/callback

# Region — pick one:
# China:  TESLA_FLEET_API_BASE=https://fleet-api.prd.cn.vn.cloud.tesla.cn
#         TESLA_AUTH_BASE=https://auth.tesla.cn
# Global: TESLA_FLEET_API_BASE=https://fleet-api.prd.na.vn.cloud.tesla.com
#         TESLA_AUTH_BASE=https://auth.tesla.com

TOKEN_ENCRYPTION_KEY=<generate one>
```

Generate a Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Phase 4 — Generate Virtual Key

```bash
python scripts/generate_virtual_key.py
```

Two files appear:
- `~/.tesla-skill/tesla_keys/private.pem` — secret, never share
- `./public/.well-known/appspecific/com.tesla.3p.public-key.pem` — public

## Phase 5 — Host the public key

The public key must be served at `https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem`.

### Option A — Your own server (nginx/Apache)

Copy the file to your webroot and ensure your web server doesn't block `.well-known`:

```nginx
# In your nginx server block, BEFORE any catch-all locations:
location ^~ /.well-known/ {
    root /var/www/<your-domain>;
}
```

Verify:
```bash
curl -I https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem
# Expect: HTTP/2 200
```

### Option B — Static hosting (Cloudflare Pages / GitHub Pages / Netlify / Vercel)

1. Create a static repo
2. Place file at `<repo>/public/.well-known/appspecific/com.tesla.3p.public-key.pem`
   (or `<repo>/.well-known/appspecific/...` depending on the host's webroot convention)
3. Configure custom domain (`<your-domain>`)
4. Verify the URL returns 200

Also place a small `privacy.html` at the domain root (Tesla's auditor crawls this):

```html
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Privacy Policy</title></head>
<body style="font-family:sans-serif;max-width:720px;margin:60px auto;padding:0 20px">
<h1>Privacy Policy</h1>
<p>This personal application uses Tesla's Fleet API to read state and send commands
to vehicles owned by the authenticated user. No data is shared with third parties.</p>
<p>Tokens are stored encrypted on the server and used only to make API calls on the
user's behalf. The user can revoke access at any time via the Tesla mobile app
(Account → Authorized Apps).</p>
<p>Contact: privacy@<your-domain></p>
</body></html>
```

## Phase 6 — Register your domain with Tesla

Once the public key URL returns 200:

```bash
python scripts/register_partner.py
```

This is one-shot — only re-run if you change domains or rotate the keypair.

## Phase 7 — OAuth authorize

Two paths:

### 7a. Server-deployed callback

Run `python -m tesla_skill.auth.callback_server` on your server (listens on `127.0.0.1:8001` by default), behind nginx that proxies `/oauth/*` to it. Then visit:

```
https://<your-domain>/oauth/authorize
```

### 7b. Local install + `localhost` redirect

Add `http://localhost:8765/callback` as an additional Redirect URI in your developer portal app config, then:

```bash
python -m tesla_skill.auth.authorize
# (or:  tesla-skill-authorize)
```

This opens your browser, catches the redirect on `http://localhost:8765`, exchanges the code, and saves encrypted tokens to `~/.tesla-skill/tokens.db`.

## Phase 8 — Pair the Virtual Key with your vehicle

The car needs to trust your public key. This is a one-time BLE pairing via the Tesla mobile app, in person, near the car.

1. Open Tesla app on your phone (logged in as the car's owner)
2. Walk to within ~5m of the car
3. Open this URL in your phone's **system browser** (not in-app browser):
   ```
   https://tesla.com/_ak/<your-domain>
   ```
   (Use `https://www.tesla.cn/_ak/<your-domain>` for China-region cars.)
4. Phone hands off to Tesla app → "Add Virtual Key from <your-domain>?"
5. Tap **Add**, enter your **Tesla PIN** (the 4-digit pin-to-drive code, NOT account password)
6. App fetches public key from your domain, writes it to the car over BLE

Verify: Tesla app → Vehicle → Security → Keys should now list a third-party entry.

## Phase 9 — Build `tesla-control` (only for control commands)

Reading status works without this. Adding control commands requires Tesla's official Go CLI:

```bash
# Install Go (1.22+)
# macOS:  brew install go
# Linux:  https://go.dev/dl/

# Build
git clone https://github.com/teslamotors/vehicle-command.git /tmp/vehicle-command
cd /tmp/vehicle-command
go build -o tesla-control ./cmd/tesla-control

# Install
mkdir -p "$HOME/.tesla-skill/bin"
mv tesla-control "$HOME/.tesla-skill/bin/"
chmod +x "$HOME/.tesla-skill/bin/tesla-control"
```

Verify with a safe smoke test (just blinks lights):

```bash
TOKEN=$(python -c "from tesla_skill.auth.oauth import get_valid_access_token; print(get_valid_access_token())")
echo "$TOKEN" > /tmp/tt.token
chmod 600 /tmp/tt.token

~/.tesla-skill/bin/tesla-control \
  -key-file ~/.tesla-skill/tesla_keys/private.pem \
  -vin <YOUR_VIN> \
  -token-file /tmp/tt.token \
  flash-lights
# Lights should flash if your car is awake nearby
rm /tmp/tt.token
```

## Phase 10 — Connect to your agent client

See [AGENTS.md](AGENTS.md).

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `403 Forbidden` on `/vehicle_data` | Virtual Key not paired (or pairing not yet propagated) | Phase 8, then wait 5–10 min |
| `register_partner.py` says public key not accessible | nginx blocks `.well-known/`; or domain not propagated | Add `location ^~ /.well-known/`; check `dig` |
| `set_climate` returns "tesla-control not found" | `TESLA_CONTROL_BINARY` path wrong | `chmod +x` the binary, fix `.env` |
| `vehicle_data?endpoints=...` returns 403 with `%3B` in URL | httpx URL-encoded the `;` separators | (Already fixed in `real.py`. If you see this on a fork, build URL with literal `;`.) |
| OAuth says `invalid_redirect_uri` | Mismatch between Tesla portal config and `.env` | Must be character-for-character identical (slashes count) |
| Token always invalid after a few days | refresh_token expired (Tesla expires tokens unused for ~3 months) | Re-run authorize flow |
| Repeated `asleep` even after wake | Car in deep sleep, can't reach LTE | Open Tesla app on phone, view vehicle to force wake; or wait |

## Security notes

- `tesla_keys/private.pem` is your signing key — `chmod 600` on Linux, never commit, never paste in chat
- If your server is compromised, immediately revoke the third-party key from the Tesla mobile app → Vehicle → Security → Keys → tap the entry → Remove. Even with the private key, an attacker can't sign commands for your car after revocation.
- `tokens.db` contains encrypted refresh_token — needs the Fernet key in your `.env` to decrypt
