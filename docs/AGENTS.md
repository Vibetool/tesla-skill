# Connecting tesla-skill to your agent

The MCP server speaks **stdio** (JSON-RPC over stdin/stdout). Any MCP-compatible client can spawn it as a subprocess.

Find the absolute path to the venv's Python first:

```bash
cd /path/to/tesla-skill
echo "$(pwd)/.venv/bin/python"
# e.g. /Users/you/projects/tesla-skill/.venv/bin/python
```

You'll plug that into each client's config below.

## Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "tesla": {
      "command": "/absolute/path/to/tesla-skill/.venv/bin/python",
      "args": ["-m", "tesla_skill.server"]
    }
  }
}
```

Restart Claude Desktop. The 10 Tesla tools will appear in the tools menu (hammer icon).

## Cursor

Settings → MCP → Add new server:

```json
{
  "tesla": {
    "command": "/absolute/path/to/tesla-skill/.venv/bin/python",
    "args": ["-m", "tesla_skill.server"]
  }
}
```

## Continue.dev

In `.continuerc.json` or your config:

```json
{
  "mcpServers": [
    {
      "name": "tesla",
      "command": "/absolute/path/to/tesla-skill/.venv/bin/python",
      "args": ["-m", "tesla_skill.server"]
    }
  ]
}
```

## Claude Code (CLI)

```bash
claude mcp add tesla \
  --command /absolute/path/to/tesla-skill/.venv/bin/python \
  --args -m tesla_skill.server
```

Or edit `~/.config/claude-code/config.json`:

```json
{
  "mcpServers": {
    "tesla": {
      "command": "/absolute/path/to/tesla-skill/.venv/bin/python",
      "args": ["-m", "tesla_skill.server"]
    }
  }
}
```

## Codex

In Codex's MCP settings, add a stdio server with:
- Command: `/absolute/path/to/tesla-skill/.venv/bin/python`
- Args: `-m tesla_skill.server`

## Custom MCP client (Python SDK)

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(
    command="/absolute/path/to/tesla-skill/.venv/bin/python",
    args=["-m", "tesla_skill.server"],
)

async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("get_car_status", {})
        print(result)
```

## Verifying the connection

After configuring your client, use the **MCP Inspector** to test independently:

```bash
npx @modelcontextprotocol/inspector \
  /absolute/path/to/tesla-skill/.venv/bin/python -m tesla_skill.server
```

Open the URL it prints — you should see all 10 tools and be able to invoke them interactively.

## Sample prompts

Once connected, try:

> "What's my Tesla's battery percentage?"
>
> "Where's my car right now?"
>
> "Open climate to 22°C"
>
> "Lock the car"
>
> "Honk the horn so I can find it"
>
> "How long until charging finishes?"

The agent will pick the right tool, call it, and translate the structured response into natural language for you.

## Multi-client sharing (advanced)

The MCP server is **single-process** — it caches `vehicle_id` and the most recent `vehicle_data` response in memory. If multiple clients spawn their own instance, each gets its own cache and that's fine.

If you want a single shared instance (e.g. one server feeding both Claude Desktop and a phone shortcut), expose it over HTTP/SSE instead of stdio. That's not built in; one approach is to run the stdio server inside a small WebSocket bridge. Open an issue if you want this baked in.
