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

## Connect Your AI Client

### Remote (hosted — shared database)

The server is hosted on Railway. No local setup needed, no API key required. All remote clients share the same database — a booking made in Copilot is visible in Claude, opencode, ChatGPT, and vice versa.

**SSE endpoint:**
```
https://web-production-e9fc5.up.railway.app/sse
```

#### VS Code / GitHub Copilot

> Requires VS Code 1.99+ and the GitHub Copilot extension.

**If you cloned this repo** — already configured. Skip to step 4.

**If you're adding it to an existing project:**

1. Open your project in VS Code
2. Create `.vscode/mcp.json` in your project root (or open it if it exists):
   - **Windows:** `C:\Users\<you>\<project>\.vscode\mcp.json`
   - **macOS/Linux:** `~/projects/<project>/.vscode/mcp.json`
3. Add (or merge into existing `servers`):
   ```json
   {
     "servers": {
       "meeting-rooms": {
         "type": "sse",
         "url": "https://web-production-e9fc5.up.railway.app/sse"
       }
     }
   }
   ```
4. Open **Copilot Chat** — press `Ctrl+Alt+I` (Windows/Linux) or `Cmd+Alt+I` (macOS)
5. Switch to **Agent mode** (dropdown at top of chat panel)
6. You should see "meeting-rooms" in the tools list. Ask:
   > *"Find me a room for 8 people with a projector tomorrow at 3pm"*

**Verify it connected:** Press `Ctrl+Shift+P` → type `MCP: List Servers` → you should see `meeting-rooms` with status "Running".

---

#### Claude Code (CLI)

1. Navigate to any project directory where you want the MCP server available
2. Create or edit `.mcp.json` in that directory:
   ```bash
   # From your project root
   cat > .mcp.json << 'EOF'
   {
     "mcpServers": {
       "meeting-rooms": {
         "type": "sse",
         "url": "https://web-production-e9fc5.up.railway.app/sse"
       }
     }
   }
   EOF
   ```
3. Start Claude Code:
   ```bash
   claude
   ```
4. Claude will auto-detect the MCP server. Ask:
   > *"List all meeting rooms in the R&D Center"*

**Verify it connected:** Inside Claude Code, type `/mcp` — you should see `meeting-rooms` listed with 6 tools.

---

#### Claude Desktop

1. Open the config file for your OS:
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
     - Usually: `C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json`
   - **Linux:** `~/.config/Claude/claude_desktop_config.json`
2. Add `meeting-rooms` to the `mcpServers` object (create the file if it doesn't exist):
   ```json
   {
     "mcpServers": {
       "meeting-rooms": {
         "type": "sse",
         "url": "https://web-production-e9fc5.up.railway.app/sse"
       }
     }
   }
   ```
3. Restart Claude Desktop (fully quit and reopen — not just close the window)
4. Click the **hammer icon** in the chat input — you should see 6 meeting-rooms tools
5. Ask:
   > *"Book a room for 10 people tomorrow at 2pm"*

---

#### opencode

1. Run the MCP add wizard:
   ```bash
   opencode mcp add
   ```
2. Answer the prompts:
   - **Location:** Global
   - **Name:** `meeting-rooms`
   - **Type:** Remote
   - **URL:** `https://web-production-e9fc5.up.railway.app/sse`
   - **OAuth:** No
3. Verify it connected:
   ```bash
   opencode mcp list
   ```
   You should see: `meeting-rooms — connected`
4. Test with any model:
   ```bash
   opencode run --model "opencode/minimax-m2.5-free" "list all meeting rooms"
   ```

**Config location:** `~/.config/opencode/opencode.json` (managed by the CLI — no need to edit manually).

---

#### ChatGPT Desktop

> Requires ChatGPT desktop app with MCP support enabled.

1. Open ChatGPT desktop → **Settings** → **Developer** (or **Beta Features**)
2. Find the MCP servers section and click **Add Server**
3. Enter:
   - **Name:** `meeting-rooms`
   - **URL:** `https://web-production-e9fc5.up.railway.app/sse`
4. Save and start a new chat. Ask:
   > *"What rooms are available tomorrow morning?"*

---

#### CLI (bash)

No AI client needed — call tools directly from the terminal.

**Requires:** `python3` and `httpx` (`pip install httpx`)

```bash
# List all rooms
./cli.sh list_rooms

# Filter by building
./cli.sh list_rooms '{"building": "R&D Center"}'

# Find available rooms
./cli.sh search_available_rooms '{"date": "2026-04-25", "start_time": "09:00", "end_time": "10:00"}'

# Book a room
./cli.sh book_room '{"room_id": 3, "date": "2026-04-25", "start_time": "14:00", "end_time": "15:00", "booked_by": "nir@example.com", "title": "Standup"}'

# Check room schedule
./cli.sh get_room_availability '{"room_id": 5, "date": "2026-04-25"}'

# My bookings
./cli.sh my_bookings '{"booked_by": "nir@example.com"}'

# Cancel
./cli.sh cancel_booking '{"booking_id": 12}'
```

Override the server URL with `MCP_URL`:
```bash
MCP_URL=http://localhost:8000 ./cli.sh list_rooms
```

---

#### Any OpenAI-compatible client

Any MCP client that supports SSE transport can connect. Point it to:

```
https://web-production-e9fc5.up.railway.app/sse
```

No API key or authentication required. The server follows the standard MCP protocol.

---

### Local (your machine only — separate database)

These options run the server on your machine via stdio. Bookings made locally stay local — they do **not** sync with the hosted server or other machines.

#### Setup

```bash
git clone <this-repo>
cd mcp-meeting-rooms
pip install -e ".[dev]"
python scripts/seed.py
```

#### Local stdio with any AI client

Add to your client's MCP config (`.mcp.json`, `claude_desktop_config.json`, `.vscode/mcp.json`, etc.):

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

---

#### MCP Inspector (browser UI)

A visual interface where you can browse tools, fill in parameters, and see responses — no AI client or JSON needed.

**Requires:** Node.js (for `npx`)

1. Launch the inspector:
   ```bash
   ./inspect.sh
   ```
   This runs `npx @modelcontextprotocol/inspector` and starts the MCP server locally via stdio.
2. Open the URL printed in the terminal (usually `http://localhost:5173`)
3. Click **Connect** — the server is pre-configured, no command or arguments to fill in
4. Browse the **Tools** tab — click any tool, fill in the form, and hit **Run**

---

#### Raw stdio (testing)

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
| `MR_TRANSPORT` | `stdio` | Transport mode: `stdio`, `sse`, or `streamable-http` |
| `MR_HOST` | `0.0.0.0` | Host to bind when using SSE transport |
| `PORT` | `8000` | Port to listen on (Railway injects this automatically) |

## Known Limitations

- **SQLite is per-instance.** Local stdio uses a file on your machine. The Railway deployment uses a persistent volume. Bookings don't sync between them.
- **No authentication.** The SSE endpoint is open — anyone with the URL can book and cancel rooms. Fine for a demo, not for production.
- **No concurrent write scaling.** SQLite serializes writes via `BEGIN IMMEDIATE`. Reads are fully concurrent, but heavy write loads (100+ simultaneous bookings) will queue up. Adequate for ~50 concurrent users.

## Equipment Tags

`whiteboard`, `projector`, `video_conf`, `phone`

The `equipment` filter is an AND — every listed tag must be present on the room.
