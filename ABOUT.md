# About tesla-skill

## The problem

If you wanted to build a Tesla integration for an AI assistant before 2024, you'd hit a wall:

- **The "Tesla Owner API"** that powered every third-party tool (TeslaFi, Teslamate, dozens of voice integrations) was a quietly tolerated leak — Tesla never officially supported it, and over 2023-2024 they tightened it: rate limits, then auth changes, then in 2024 a hard cutover to a new system requiring **registered partner apps + ECDSA-signed commands**.
- **The new official "Fleet API"** is fine, but the documentation assumes you're a fleet operator (Hertz, Uber for Business). For an individual who just wants to ask Claude "what's my battery?" the path is paved with: developer portal forms, Virtual Key generation, BLE pairing, partner domain registration, Bluetooth proximity setup, public key hosting, and OAuth callback infrastructure.
- **Most third-party libraries broke** when the TVCP (Tesla Vehicle Command Protocol) deadline hit. The ones that adapted ended up building bespoke clients that don't compose — they're tied to Home Assistant or to a specific dashboard, not usable from any AI agent.

I built tesla-skill because none of the existing options worked for "I want my AI agent (any of them) to talk to my Tesla, end-to-end, with reasonable security."

## The design choices

**Why MCP instead of an HTTP API?**

The Model Context Protocol is the emerging lingua franca for AI tool use. Claude Desktop, Cursor, Codex, Continue.dev, Claude Code — they all speak it. Building a single MCP server gets us into all of them at once, instead of writing N integrations.

**Why stdio transport?**

For personal use, stdio is the simplest and safest: the MCP server is spawned as a child process by the agent client, communicates over the parent's stdin/stdout, and dies when the agent dies. No open ports, no auth between agent and server, no network attack surface. The agent runs locally; the server runs locally; only the OAuth callback (one-time setup) needs to be reachable from Tesla's servers.

**Why Python + Go?**

Python for everything except command signing. ECDSA P-256 signing per TVCP isn't hard, but Tesla maintains an official Go CLI (`tesla-control`) that handles every edge case — Virtual Key key derivation, session cache, auto-wake. Reimplementing that in pure Python would be reinventing risk for no benefit. Shelling out costs ~50ms per command, well within "voice command latency" tolerance.

**Why two OAuth modes?**

The "register a public domain, host the public key, run a callback service" path is the only one that scales beyond a single user, but it's overkill for someone with a laptop and a Cloudflare Pages account. So we support both:

- **Server mode**: full FastAPI callback at `https://your.domain.com/oauth/callback`
- **Local mode**: a one-shot script (`tesla-skill-authorize`) that catches `http://localhost:8765/callback` — Tesla allows `http://localhost` as a redirect URI even though they normally require HTTPS.

The Virtual Key public key still has to be hosted on a public domain (Tesla won't accept localhost for partner registration), but a static-only host works — GitHub Pages, Cloudflare Pages, Netlify, Vercel.

**Why English tool descriptions?**

The MCP tool descriptions are what the LLM uses for routing ("user said 'lock the car' — which tool matches?"). LLMs route best in English, regardless of what language the user is speaking. Tool *outputs* are language-neutral structured JSON; the LLM rephrases for the user.

## What's intentionally not here

- **No web dashboard.** This is a tool layer for AI agents, not a UI app. If you want a dashboard, plug the MCP into a Claude artifact or feed `vehicle_data` to Grafana — both straightforward.
- **No background polling.** The MCP only fires when the agent calls a tool. Keeps API quota healthy and battery undrained. If you want "alert me when battery drops below 20%", run a separate cron that calls `get_charge_info` and notifies you.
- **No multi-tenancy.** Single user, single set of tokens, single Tesla account. The MCP server is per-machine. No secret rotation, no audit logging, no admin panel — because there's one user and they ARE the admin.
- **No phone-side BLE pairing.** Virtual Key pairing requires the official Tesla mobile app (in person, near the car). No third-party can replicate that, and frankly we shouldn't try — that's the user's last line of defense if their server is compromised.

## What it owes to the ecosystem

- [@teslamotors/vehicle-command](https://github.com/teslamotors/vehicle-command) — the Go CLI we shell out to for command signing. Without this, this project couldn't exist.
- [Tesla Fleet API](https://developer.tesla.com/) — the underlying HTTP surface.
- [@modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) (FastMCP) — handles all the JSON-RPC plumbing.
- [httpx](https://www.python-httpx.org/) — async HTTP client.
- [cryptography](https://cryptography.io/) — Fernet for token-at-rest encryption, P-256 keypair generation.

## Future direction

Things on the table for v0.2+:

- **Scheduling tools** — `schedule_climate(time, temp_c)`, `schedule_charge_at(off_peak_start)`. Currently the user can ask their agent's calendar to remind them and call manually.
- **Multi-vehicle** — pick by VIN or display_name. Currently picks the first vehicle on the account.
- **Sentry / window / trunk tools** — easy adds, just more `tesla-control` commands wrapped.
- **Telemetry stream** — Tesla's WebSocket telemetry API for real-time updates (vs. polling vehicle_data). Would enable cool things like "tell me when I arrive home."
- **HTTP/SSE transport option** — for shared MCP server scenarios (one server, multiple agents/devices).

PRs and ideas welcome.

## Author's note

This project was built to scratch a personal itch: I wanted to ask my voice AI "is my car still charging?" without rolling my own auth proxy. It turned into a complete reference implementation of the modern Tesla Fleet API path, hopefully useful for anyone in the same spot.

The codebase is intentionally small and well-commented — about 1000 lines of Python. If you want to learn how Tesla's TVCP, partner registration, and Virtual Key flow actually work end-to-end, reading [`src/tesla_skill/`](src/tesla_skill/) start to finish is probably the fastest path.

Have fun, drive safe.
