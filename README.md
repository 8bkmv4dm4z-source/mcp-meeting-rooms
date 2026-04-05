# MCP Meeting Rooms

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that gives AI agents the ability to browse, search, and book meeting rooms.

Built with [FastMCP](https://github.com/jlowin/fastmcp), SQLite, and Pydantic. Includes realistic seed data (25 rooms across 3 buildings on a Siemens campus).

## Tools

| Tool | Description |
|------|-------------|
| `list_rooms` | Browse rooms with optional filters (building, floor, capacity, equipment) |
| `search_available_rooms` | Find rooms free for a specific date/time slot |
| `get_room_availability` | See bookings and free slots for a room on a given day |
| `book_room` | Reserve a room — returns success or a conflict with alternatives |
| `cancel_booking` | Cancel an existing booking by ID |
| `my_bookings` | List all bookings for a person, optionally filtered by date |

When a booking conflict occurs, the server returns structured `cross_mcp_context` with ready-to-send Slack/email messages and swap request payloads — designed for multi-agent workflows.

## Quick Start

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Seed the database
python scripts/seed.py

# 3. Run the MCP server (stdio transport)
python -m meeting_rooms.server
```

## Calling the Server

### Option 1 — MCP Inspector (recommended for exploration)

The easiest way to interact with the server — opens a browser UI where you can call any tool without writing JSON.

```bash
./inspect.sh
```

Visit the URL printed in the terminal, then click **Connect**. The server is pre-configured — no command or arguments to fill in.

### Option 2 — GitHub Copilot in VS Code

Open the repo folder in VS Code. The `.vscode/mcp.json` file is already included — VS Code picks it up automatically.

1. Open the **Copilot Chat** panel (`Ctrl+Alt+I`)
2. Switch to **Agent mode** (the `@` dropdown → select your server, or it appears automatically)
3. Ask naturally: *"Find me a room for 8 people with a projector tomorrow at 3pm"*

Copilot will call the MCP tools and show results inline.

> **Note:** Requires VS Code 1.99+ and the GitHub Copilot extension.

### Option 3 — Claude Code / Claude Desktop

Drop a `.mcp.json` file in the project root:

```json
{
  "mcpServers": {
    "meeting-rooms": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "meeting_rooms.server"],
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

Then run `claude` in the project directory and ask naturally:

> *"Find me a room for 10 people with a projector tomorrow at 2pm"*

### Option 4 — Raw stdio (no dependencies)

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_rooms","arguments":{"min_capacity":10}}}' \
  | python -m meeting_rooms.server
```

See `AGENTS.md` for the full tool reference and more example calls.

## Run Tests

```bash
pytest
```

## Project Structure

```
src/meeting_rooms/
├── server.py       # FastMCP server — tool registration & transport
├── tools.py        # Business logic for each tool
├── repository.py   # Data access layer (SQL queries)
├── models.py       # Pydantic models
├── db.py           # SQLite connection & schema init
scripts/
└── seed.py         # Siemens campus seed data (3 buildings, 25 rooms)
tests/
├── conftest.py     # Shared fixtures
└── test_repository.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MR_DB_PATH` | `meeting_rooms.db` | Path to the SQLite database file |

## Equipment Tags

`whiteboard`, `projector`, `video_conf`, `phone`

The `equipment` filter is an AND — every listed tag must be present on the room.
