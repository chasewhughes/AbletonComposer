# Ableton MCP Server Setup

## Prerequisites

1. Ableton Live running with the Remote Script loaded (listening on port 9877)
2. Python virtual environment with `mcp` package installed

## Virtual Environment Location

```
/Users/chasehughes/ableton-mcp-extended/MCP_Server/.venv
```

## Adding the MCP Server to Claude Code

```bash
claude mcp add --transport stdio ableton -- /Users/chasehughes/ableton-mcp-extended/MCP_Server/.venv/bin/python /Users/chasehughes/ableton-mcp-extended/MCP_Server/server.py
```

## Check Server Status

```bash
claude mcp get ableton
```

## Remove Server

```bash
claude mcp remove ableton -s local
```

## Reinstall Dependencies (if needed)

```bash
/Users/chasehughes/ableton-mcp-extended/MCP_Server/.venv/bin/pip install mcp
```

## Recreate Virtual Environment (if needed)

```bash
python3 -m venv /Users/chasehughes/ableton-mcp-extended/MCP_Server/.venv
/Users/chasehughes/ableton-mcp-extended/MCP_Server/.venv/bin/pip install mcp
```
