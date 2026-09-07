# Claude Code Session Search MCP Server

An MCP (Model Context Protocol) server that provides tools for searching and analyzing Claude Code conversation history.

## Features

- **List Projects**: View all Claude Code projects with session counts
- **List Sessions**: Browse sessions for specific projects
- **List Recent Sessions**: Find recent conversations across all projects
- **Analyze Sessions**: Extract and analyze messages with role filtering
- **Search Conversations**: Search for specific terms with context windows and time ranges
- **Get Message Details**: Retrieve full content for specific messages
- **Summarize Conversations**: summaries of a day or a time range, written for an engineer resuming past work

## Installation

1. Install dependencies:
```bash
uv sync
```

2. Run the server:
```bash
uv run python server.py
```

3. Add to Claude Code MCP config (`~/.config/claude/mcp.json`):
```json
{
  "servers": {
    "cc-session-search": {
      "command": ["uv", "run", "python", "server.py"],
      "cwd": "/path/to/cc-session-search"
    }
  }
}
```

## Requirements

- Standard Claude Code installation (searches `~/.claude/projects/`)
- Python 3.13+
- MCP 1.2.0+

## Usage

The server provides the following tools:

### list_projects()
Lists all Claude Code projects with session counts and recent activity.

### list_sessions(project_name, days_back=7)
Lists sessions for a specific project within the specified time range.

### list_recent_sessions(days_back=1, project_filter=None)
Lists recent sessions across all projects.

### analyze_sessions(days_back=1, role_filter="both", include_tools=False, project_filter=None)
Extracts and analyzes messages from sessions with filtering options.

### search_conversations(query, days_back=2, context_window=1, case_sensitive=False, project_filter=None)
Searches conversations for specific terms with context windows.

### get_message_details(session_id, message_indices)
Retrieves full content for specific messages by session ID and indices.

### summarize_daily_conversations(date, style="journal", project_filter=None)
### summarize_time_range(start_time, end_time, style="journal", project_filter=None)

Both shell out to the `claude` command in headless mode and return a JSON
object with the fields `summary`, `key_topics`, `insights`, `stories`,
`projects_mentioned` and `people_mentioned`.

The summarization prompts are written for software engineering sessions rather
than for a personal journal. They ask for the files, functions, commands and
identifiers a session touched, kept verbatim; the decisions taken and the
reasons given for them; the errors met and how each was resolved; what was left
open; and any measurement, with the command that produced it. They tell the
model to write plain sentences, to invent nothing, and to leave a list empty
rather than fill it with plausible entries.

Three styles, each with a plainer alias:

| Style | Alias | What it asks for |
|---|---|---|
| `journal` | `worklog` | What each session did, what it touched, what it left open |
| `insights` | `decisions` | Decisions with their reasons, measurements, discovered tool behaviour |
| `stories` | `debugging` | One entry per debugging episode: symptom, cause, fix |

The summarization model is **Claude Sonnet 5** (`claude-sonnet-5`). The default
lives in one place, `DEFAULT_MODEL` in `core/summarizer.py`, and
`CC_SESSION_SEARCH_MODEL` overrides it:

```bash
CC_SESSION_SEARCH_MODEL=claude-opus-5 uv run python server.py
```

These summaries are not Anthropic API calls. The model identifier is passed as
`--model` to the `claude` command running in headless mode, so it resolves
against whatever credentials that command already holds; no API key is read
here.

## Development

The server is built using the official MCP Python SDK with low-level Server class for maximum control.

Key features:
- Efficient response handling with content truncation
- Metadata-first approach to minimize token usage
- Support for date ranges and filtering
- Cross-project search capabilities

## License

MIT