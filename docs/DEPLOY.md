# Optional: server deployment

Most users will run tesla-skill locally with their MCP client (see [AGENTS.md](AGENTS.md)). This document is for users who want to:

- Host the OAuth callback on a public domain (Phase 6 in SETUP.md)
- Run the MCP server 24/7 on a server (rather than a laptop)
- Share access across multiple devices/agents

## Minimum hardware

A $5/month VPS is plenty: 1 vCPU, 512MB RAM, 10GB disk. The MCP server idles at ~80MB memory and milliseconds of CPU.

## Architecture on a server

```
                ┌─────────────────────────┐
                │  https://your-domain    │
                │   (nginx + Let's        │
                │    Encrypt cert)        │
                └────────┬────────────────┘
                         │
            ┌────────────┴───────────────┐
            │                            │
   /  /privacy.html      /oauth/*    /.well-known/*
   ▼      (static)        (proxy)       (static)
   │                          │
   │                          ▼
   │              tesla_skill.auth.callback_server
   │              (uvicorn on 127.0.0.1:8001)
   │                          │
   │                          └─► tokens.db
   │                              ~/.tesla-skill/
   │
   └──► (optional) tesla_skill.server (MCP, stdio)
        spawned by remote agent client over SSH or
        local agent client on the server
```

## nginx config

```nginx
server {
    listen 443 ssl http2;
    server_name your.domain.com;

    ssl_certificate     /etc/letsencrypt/live/your.domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your.domain.com/privkey.pem;

    root /var/www/your.domain.com;

    # Static — let nginx serve directly
    location ^~ /.well-known/ {
        try_files $uri =404;
    }
    location = /privacy.html {
        try_files $uri =404;
    }

    # Dynamic — proxy to the FastAPI callback service
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}

# HTTP → HTTPS
server {
    listen 80;
    server_name your.domain.com;
    return 301 https://$host$request_uri;
}
```

## systemd unit for callback server

`/etc/systemd/system/tesla-skill-oauth.service`:

```ini
[Unit]
Description=tesla-skill OAuth Callback
After=network.target

[Service]
Type=simple
User=tesla-skill
WorkingDirectory=/opt/tesla-skill
EnvironmentFile=/opt/tesla-skill/.env
ExecStart=/opt/tesla-skill/.venv/bin/python -m tesla_skill.auth.callback_server
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tesla-skill-oauth
sudo journalctl -u tesla-skill-oauth -f
```

## Hardening checklist

- [ ] Run as a non-root user (`tesla-skill` system user)
- [ ] `chmod 600 ~/.tesla-skill/tesla_keys/private.pem`
- [ ] `chmod 600 .env` (contains client_secret + Fernet key)
- [ ] Firewall: only 80/443 open inbound; deny 8001 from public
- [ ] Enable Let's Encrypt auto-renewal (certbot timer)
- [ ] Backup the Fernet key to a password manager (without it, encrypted tokens are unreadable)

## Running the MCP server on the server vs locally

Two patterns:

**Pattern A — agent on laptop, OAuth callback on server:** Simplest. The MCP server (`tesla_skill.server`) runs locally on your laptop, your laptop's agent client (Claude Desktop, etc.) spawns it as a subprocess. Only the OAuth callback service needs to be public-facing because that's what Tesla redirects to. The MCP server reads `tokens.db` from `~/.tesla-skill/` on your laptop — but tokens were saved on the server during OAuth. Either:
  - Run OAuth flow with `tesla_skill.auth.authorize` locally (uses `localhost:8765` redirect, works on laptop)
  - Or scp `tokens.db` from server to laptop after authorize

**Pattern B — everything on the server:** MCP server runs there too, accessed remotely. Trickier because MCP-stdio needs the subprocess to be locally spawnable. Options:
  - Use `ssh` as the "command" in your agent client config:
    ```json
    {
      "mcpServers": {
        "tesla": {
          "command": "ssh",
          "args": ["user@your-server", "cd /opt/tesla-skill && .venv/bin/python -m tesla_skill.server"]
        }
      }
    }
    ```
  - Or run an MCP-over-SSE bridge (not currently included)

Pattern A is recommended. Server only needs to host the static files + OAuth callback; everything else runs where your agent runs.
