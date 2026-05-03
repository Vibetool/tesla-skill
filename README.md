# tesla-skill

> Connect your Tesla to any AI agent. Voice or chat, any client, official Tesla API + Virtual Key signing.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-stdio-green)](https://modelcontextprotocol.io)

```
You: "What's my Tesla's battery?"
AI:  Calls get_car_status → "78%, range 409 km. Climate is off, doors locked."

You: "Open climate to 22 degrees"
AI:  Calls set_climate(on=true, temp_c=22) → "Started, target 22°C."

You: "Honk so I can find it"
AI:  Calls honk_horn → "Honked. The car is to your right."
```

## Why wearables + Tesla

Your agent goes wherever you go — smart glasses, smartwatch, AI pendant, earbuds. All of them speak MCP. None of them want you fumbling for your phone. With tesla-skill, controlling your car is one sentence away from whatever's on your wrist or collar:

- 🛒 Both hands on a supermarket cart: *"Open the trunk."*
- 🌧️ Kid on one arm, umbrella on the other: *"Unlock the doors, AC to 22°C."*
- ❄️ Office at 4:50pm in January: *"Preheat the car."*
- 🅿️ Stadium parking after a concert: *"Flash the lights so I can spot it."*
- 💬 Mid-conversation, can't grab your phone: *"How much range have I got left?"*

Your phone is busy / wet / dead / left in another room. Your wearable isn't.

## What it is

A **Model Context Protocol (MCP) server** that exposes 10 tools any MCP-compatible AI agent can use to query and control your Tesla:

| 🔍 Read | 🎛️ Control |
|---|---|
| `get_car_status` — battery, range, climate, lock, sentry | `set_climate(on, temp_c)` |
| `get_car_location` — lat/lng/speed/heading | `lock_car` / `unlock_car` |
| `get_charge_info` — SOC, limit, kW, ETA | `start_charging` / `stop_charging` |
| | `flash_lights` / `honk_horn` |

Works with **Claude Desktop, Claude Code, Cursor, Codex, Continue.dev**, and any other MCP-compatible client.

## Install with a coding agent

Send your agent (Claude Code, Codex, …) this repo URL and say **"install this"**:

```
https://github.com/Vibetool/tesla-skill
```

The agent reads [`SKILL.md`](SKILL.md) and walks you through setup — about **30 minutes of work** (plus 1-3 days for Tesla developer review).

Or follow [`docs/SETUP.md`](docs/SETUP.md) yourself.

## What you'll need

- A **Tesla** (2021+ for full Fleet API support)
- A **Tesla owner account** (the one in your Tesla mobile app)
- A **public domain** you control — Tesla requires it for hosting your Virtual Key public key. Free static hosts work (Cloudflare Pages, GitHub Pages w/ custom domain).
- **Python 3.11+** on the machine running the MCP server
- **Go 1.22+** *only if* you want control commands (read-only works without)

## Architecture

```
       Your AI Agent
   (Claude / Cursor / etc.)
            │
            │  MCP over stdio
            ▼
   ┌──────────────────────────┐
   │   tesla_skill.server     │     10 tools (FastMCP)
   └──────────────────────────┘
            │
            ├──► Tesla Fleet API (REST)         → reads
            │
            └──► tesla-control subprocess        → control commands
                 (ECDSA P-256 signing,
                  Tesla's official Go CLI)
```

- **Read commands** call `/api/1/vehicles/{id}/vehicle_data` directly via httpx, with 30-second response caching to stay under Tesla's daily rate limit.
- **Control commands** shell out to [`tesla-control`](https://github.com/teslamotors/vehicle-command/tree/main/cmd/tesla-control), which signs each command locally with your Virtual Key and POSTs to Tesla's `/command/` endpoint. Sleeping cars are auto-woken with one retry.

## Why this exists

Tesla deprecated the unsigned owner-API in 2024 in favor of Fleet API + TVCP signing. Most third-party Tesla integrations broke. This project gives you a clean MCP-shaped re-implementation:

- **No middlemen** — direct Tesla API, your tokens stay on your machine
- **End-to-end encryption** of stored tokens (Fernet at rest, OAuth in flight)
- **Tesla-official signing path** — wraps the same Go CLI Tesla recommends, no DIY crypto
- **Mock mode** for development without a real car
- **Region-aware** — China and global Fleet APIs both supported

See [`ABOUT.md`](ABOUT.md) for the design rationale.

## Quick start (development, no Tesla account needed)

```bash
git clone https://github.com/Vibetool/tesla-skill.git
cd tesla-skill
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Mock mode — fake car responds to all tools
echo "USE_MOCK=true" > .env
python -m tesla_skill.server  # stdio MCP server

# Or with the official MCP Inspector UI
npx @modelcontextprotocol/inspector python -m tesla_skill.server
```

For real-Tesla setup, see [`SKILL.md`](SKILL.md) (agent walkthrough) or [`docs/SETUP.md`](docs/SETUP.md) (manual).

## Documentation

- [`SKILL.md`](SKILL.md) — agent installation walkthrough (auto-followed when you say "install this" to your AI)
- [`docs/SETUP.md`](docs/SETUP.md) — manual setup guide for users without an agent
- [`docs/AGENTS.md`](docs/AGENTS.md) — connecting from Claude Desktop / Cursor / Continue / Codex / etc.
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — optional public server deployment

## Project status

v0.1.0. The 10 tools listed above are implemented and tested against a real 2022 Model Y. Roadmap: data dashboards, multi-vehicle support, scheduling tools (preheat at 8am, etc.).

## Contributing

PRs welcome. The whole thing is ~1000 lines of Python; should be approachable.

## License

MIT — see [LICENSE](LICENSE).

## Disclaimers

Not affiliated with Tesla, Inc. Use at your own risk — control commands physically affect your vehicle. Always double-check with your agent before issuing irreversible commands (unlocking, disabling sentry, summoning).
