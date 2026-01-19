# ElevenLabs MCP Server Setup

## Prerequisites

1. ElevenLabs API key
2. `uvx` installed (from `uv` package manager)

## API Key

The API key is stored in the environment variable:
```
ELEVENLABS_API_KEY=a6d2cfbfd1a92e769e175942121161a0469d4338ed1204bb223c33f95ec3feb4
```

## Current Setup

### Claude Desktop
The ElevenLabs MCP server is configured in Claude Desktop at:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Configuration:
```json
{
  "mcpServers": {
    "ElevenLabs": {
      "command": "uvx",
      "args": ["elevenlabs-mcp"],
      "env": {
        "ELEVENLABS_API_KEY": "a6d2cfbfd1a92e769e175942121161a0469d4338ed1204bb223c33f95ec3feb4"
      }
    }
  }
}
```

### Claude Code (CLI)
The server is manually configured in `~/.claude.json` under the project-specific `mcpServers` section.

## Manual Configuration for Claude Code

To manually add or update the ElevenLabs MCP server in Claude Code, edit the `~/.claude.json` file and add to your project's `mcpServers` object:

```json
"ElevenLabs": {
  "type": "stdio",
  "command": "uvx",
  "args": [
    "elevenlabs-mcp"
  ],
  "env": {
    "ELEVENLABS_API_KEY": "a6d2cfbfd1a92e769e175942121161a0469d4338ed1204bb223c33f95ec3feb4"
  }
}
```

## Check Server Status

```bash
claude mcp list
```

Or for specific server details:
```bash
claude mcp get ElevenLabs
```

## Remove Server

```bash
claude mcp remove ElevenLabs -s local
```

## Notes

- The same API key is used for both Claude Desktop and Claude Code
- Changes to Claude Code configuration do not affect Claude Desktop
- The `uvx` command runs the `elevenlabs-mcp` package automatically without manual installation
