---
name: tesla-skill
description: Install and configure a Tesla Fleet API integration on the user's machine, exposing 10 MCP tools (status reads + signed control commands) so any MCP-compatible agent can query and control the user's Tesla. Use when the user asks "install this" pointing to the tesla-skill repo, asks to connect their Tesla to Claude/Cursor/etc., or wants remote climate/lock/charge control via voice or chat.
---

# Tesla Skill — Agent Installation Guide

You are installing this skill on the user's machine. Goal: by the end, the user can ask their agent (you, or any MCP-compatible client) things like "what's my battery?" or "open the climate to 22°C" and you can answer/act.

This walkthrough is for **you, the agent**. Read top to bottom and execute. Ask the user the marked **[ASK USER]** questions; everything else you can do autonomously.

## Phase 0 — Sanity check & prerequisites

**[ASK USER]** Confirm before continuing:

1. Do you own a Tesla? Roughly what year/model? (Need 2021+ for full Fleet API support.)
2. Do you have a **public domain** you control (e.g. via Cloudflare/Namecheap/aliyun)? You'll need to host one tiny static file at `https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem`.
3. Where do you want the MCP server to run?
   - **(A)** Local machine — simplest. You'll need a tunnel (or the OAuth callback on localhost, see below).
   - **(B)** A small Linux server / VPS — recommended. Always-on. ~$5/month.
4. Which agent client will you use this with? (Claude Code, Claude Desktop, Cursor, Codex, custom?) Will be needed at the end for client config.

If the user has no Tesla → stop. If they have no domain → suggest registering one (~$10/yr at Cloudflare or Porkbun, `.com`/`.app`/`.dev` all fine).

## Phase 1 — Tesla Developer registration

This is the only step that is partly out-of-band (needs ~1-3 days for Tesla review).

**[ASK USER]** Direct them to the Tesla developer portal:
- 🇨🇳 China-region vehicles: <https://developer.tesla.cn>
- 🌍 Global: <https://developer.tesla.com>

(Region matters — China-built/sold cars are accessible only via the `.cn` portal + `fleet-api.prd.cn.vn.cloud.tesla.cn` API host.)

Tell them to:

1. Sign in with their **Tesla owner account** (the one in their Tesla mobile app)
2. **Register Application** with these fields:

   | Field | Value |
   |---|---|
   | Application Name | (free choice, e.g. `Tesla Skill for <name>`) |
   | Description | "Personal Tesla control via AI agents" |
   | Purpose | Personal Use / Developer |
   | Allowed Origin URL | `https://<their-domain>` (root, no path, no trailing slash) |
   | Allowed Redirect URI | `https://<their-domain>/oauth/callback` |
   | Allowed Returned URL | leave blank |
   | Privacy Policy URL | `https://<their-domain>/privacy.html` (you'll generate this in Phase 3) |
   | OAuth Grant Type | **Authorization Code and Machine to Machine** (the left option) |
   | Scopes | check: `openid`, `offline_access`, `vehicle_device_data`, `vehicle_cmds`, `vehicle_charging_cmds` |

3. Submit. Approval is usually 1-3 business days.

⚠️ Tesla rejects redirect URIs and origins that contain the literal word "tesla" — pick a neutral subdomain like `car.<their-domain>` or `auto.<their-domain>`.

**[ASK USER]** Once approved, get them to copy these from the developer console (don't paste them here — they go straight into `.env`):

- **Client ID** (public)
- **Client Secret** (treat as a password)

## Phase 2 — Clone & install dependencies

```bash
git clone https://github.com/Vibetool/tesla-skill.git
cd tesla-skill

# Use uv if available, otherwise venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify:

```bash
tesla-skill-mcp --help 2>&1 | head -3
# or:
python -m tesla_skill.server --help 2>&1 | head -3
```

(Output should at least show no ImportError.)

## Phase 3 — Configure environment

```bash
cp .env.example .env
```

Generate a Fernet key for token-at-rest encryption:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Have the user edit `.env` and fill in:

```bash
TESLA_CLIENT_ID=<from Phase 1>
TESLA_CLIENT_SECRET=<from Phase 1>
TESLA_REDIRECT_URI=https://<their-domain>/oauth/callback
TESLA_FLEET_API_BASE=https://fleet-api.prd.cn.vn.cloud.tesla.cn   # or .na/.eu for global
TESLA_AUTH_BASE=https://auth.tesla.cn                              # or auth.tesla.com for global
TOKEN_ENCRYPTION_KEY=<generated above>
```

`USE_MOCK=true` is the safe default — leave it for now, switch to `false` after Phase 6.

## Phase 4 — Generate Virtual Key

```bash
python scripts/generate_virtual_key.py
```

This produces:

- `~/.tesla-skill/tesla_keys/private.pem` — keep this secret, never commit, never share
- `./public/.well-known/appspecific/com.tesla.3p.public-key.pem` — public, must be hosted on the user's domain

**[ASK USER]** Upload the public key file to their domain so this URL returns 200:

```
https://<their-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem
```

Options:

- If they have a server: copy file to nginx webroot, ensure `.well-known` isn't blocked
- If they use Cloudflare Pages / GitHub Pages: commit the file at `/.well-known/appspecific/com.tesla.3p.public-key.pem` in their static repo
- Verify with `curl -I https://<their-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem` — must be 200, content-type `application/x-pem-file` or `text/plain`

Also have them put a small `privacy.html` at `https://<their-domain>/privacy.html` (template in `docs/SETUP.md`).

## Phase 5 — Register Partner domain with Tesla

Once the public key URL is live:

```bash
python scripts/register_partner.py
```

Expected output:

```
✅ got partner token
✅ registered: {...}
✅ key verified: {...}
🎉 Partner domain registered.
```

If `key verified` fails, the public key URL isn't reachable yet — debug that before proceeding (most likely: nginx blocks `.well-known`, or DNS not propagated).

## Phase 6 — OAuth: link the user's Tesla account

There are two paths depending on Phase 0 decision:

### 6a. Server-deployed callback

The user's domain points at their server. Run the callback service:

```bash
python -m tesla_skill.auth.callback_server
# Listens on 127.0.0.1:8001 by default
```

Behind nginx (or any reverse proxy) at `https://<their-domain>/oauth/*` → `127.0.0.1:8001`.

Have the user open `https://<their-domain>/oauth/authorize` in a browser. They'll log into Tesla, approve, and land on a "✅ Authorized" page.

### 6b. Local with auto-callback helper

If running locally, use the bundled helper that registers `http://localhost:8765/callback` (Tesla allows `http://localhost` as a redirect URI for local development, even though they usually require HTTPS):

```bash
python scripts/authorize.py
```

This:
1. Spawns a tiny HTTP server on port 8765
2. Opens the user's browser to Tesla's authorize URL
3. Catches the redirect, exchanges the code, saves encrypted tokens, exits

Note: for this path the user needs to add `http://localhost:8765/callback` as an additional Redirect URI in their Tesla developer portal app config.

After either path, verify:

```bash
ls -la ~/.tesla-skill/tokens.db
# Should exist
```

## Phase 7 — Pair Virtual Key with the vehicle (BLE, requires phone)

The car must trust your public key. This is done via the Tesla mobile app, in person, near the car (Bluetooth range, ~5m).

**[ASK USER]** Walk them through:

1. Open Tesla app on their phone, signed in to their owner account
2. Open this URL in their phone's **system browser** (not in-app):
   ```
   https://tesla.com/_ak/<their-domain>
   ```
   (Use `https://www.tesla.cn/_ak/...` if China-region.)
3. Phone hands off to Tesla app, which prompts "Add Virtual Key from <their-domain>?"
4. They tap **Add**, enter their **Tesla PIN** (the 4-digit pin-to-drive code, not their account password)
5. Tesla app pulls the public key from their domain, writes it to the car over BLE

Verify in the Tesla app: **Vehicle → Security → Keys** should now list a third-party key with their domain.

## Phase 8 — Switch off mock + smoke test

In `.env` change:

```
USE_MOCK=false
```

Restart the MCP server (or the user's agent client will start it on next use).

Quick check via CLI before involving the agent:

```bash
python -c "
from tesla_skill.fleet import get_client
c = get_client()
print(c.get_car_status())
"
```

Expected: a dict with real `battery_percent`, `range_km`, etc.

If you get `{'is_online': False, 'reason': '...Virtual Key...'}` — Tesla's backend hasn't propagated the pairing yet, wait 5-10 minutes and retry. If you get `{'is_online': False, 'reason': '...休眠...'}` — car is asleep, ask user to wake it via Tesla app.

## Phase 9 — Build `tesla-control` (only needed for control commands)

Read commands work without this. To enable control commands (climate/lock/charge/lights/horn):

```bash
# Install Go (1.22+)
# macOS:    brew install go
# Linux:    https://go.dev/dl/
# Verify:   go version

# Build the official Tesla command CLI
git clone https://github.com/teslamotors/vehicle-command.git /tmp/vehicle-command
cd /tmp/vehicle-command
go build -o tesla-control ./cmd/tesla-control

# Move into place
mkdir -p "$HOME/.tesla-skill/bin"
mv tesla-control "$HOME/.tesla-skill/bin/"
chmod +x "$HOME/.tesla-skill/bin/tesla-control"
```

Update `.env`:

```
TESLA_CONTROL_BINARY=~/.tesla-skill/bin/tesla-control
TESLA_PRIVATE_KEY_PATH=~/.tesla-skill/tesla_keys/private.pem
```

(Tilde expansion is handled by `tesla_skill.config`.)

CLI smoke test (safe — just blinks the lights):

```bash
TOKEN=$(python -c "from tesla_skill.auth.oauth import get_valid_access_token; print(get_valid_access_token())")
echo "$TOKEN" > /tmp/tt.token
chmod 600 /tmp/tt.token

~/.tesla-skill/bin/tesla-control \
  -key-file ~/.tesla-skill/tesla_keys/private.pem \
  -vin <THEIR_VIN> \
  -token-file /tmp/tt.token \
  flash-lights

rm /tmp/tt.token
```

Their car's lights should flash. If yes, signing chain is good.

## Phase 10 — Connect to the user's agent client

**[ASK USER]** which client they're using, then configure accordingly. See [`docs/AGENTS.md`](docs/AGENTS.md) for the full list. Quick examples:

### Claude Desktop
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tesla": {
      "command": "/full/path/to/tesla-skill/.venv/bin/python",
      "args": ["-m", "tesla_skill.server"]
    }
  }
}
```

Restart Claude Desktop. The 10 tools should appear in the tools menu.

### Cursor / Continue / Codex
Similar config, see `docs/AGENTS.md`.

### Generic MCP client
Run the server directly:
```bash
python -m tesla_skill.server   # stdio transport
```

## Done

Tell the user to try:

> "What's my Tesla's battery?"
> "Turn on climate to 22°C"
> "Honk the horn"

If something fails, the most common issues and their fixes are in [`docs/SETUP.md`](docs/SETUP.md). Show the agent (you) the error message and it'll diagnose.

---

## File map (for your reference, agent)

```
tesla-skill/
├── README.md                  ← user-facing
├── SKILL.md                   ← this file
├── .env.example               ← config template
├── pyproject.toml             ← package metadata; entry point: tesla-skill-mcp
├── src/tesla_skill/
│   ├── server.py              ← FastMCP entry, 10 tools
│   ├── config.py              ← env loader (settings dataclass)
│   ├── auth/
│   │   ├── oauth.py           ← authorize URL builder, code/refresh exchange
│   │   ├── storage.py         ← SQLite + Fernet token storage
│   │   └── callback_server.py ← FastAPI for /oauth/* endpoints
│   └── fleet/
│       ├── base.py            ← FleetClient Protocol
│       ├── mock.py            ← in-memory fake car (USE_MOCK=true)
│       ├── real.py            ← Tesla Fleet API client (USE_MOCK=false)
│       └── signer.py          ← tesla-control subprocess wrapper for control commands
├── scripts/
│   ├── generate_virtual_key.py  ← one-shot, EC P-256 keypair
│   ├── register_partner.py      ← one-shot, POST /api/1/partner_accounts
│   └── authorize.py             ← local OAuth flow (alternative to callback_server)
└── docs/
    ├── SETUP.md               ← detailed setup (overlap with this file, for users solo)
    ├── AGENTS.md              ← per-client config (Claude Desktop / Cursor / etc)
    └── DEPLOY.md              ← optional server deployment notes
```

## Important behavioral notes

- `~/.tesla-skill/` is the data directory: tokens.db, tesla_keys/, bin/. Override with `TESLA_SKILL_DATA_DIR`.
- All secrets (refresh_token, access_token) are encrypted at rest with Fernet; the key lives in `.env` only.
- Control commands auto-wake a sleeping car (one retry). Read commands don't (battery preservation).
- Locale: tool docstrings are English so any-locale LLM can route correctly. Tool *outputs* are language-neutral structured JSON.
