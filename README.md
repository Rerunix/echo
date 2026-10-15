# ECHO

A tiny agent debugger. Point it at a program that is failing; it replays the run,
finds the exact step that went wrong, searches for the smallest real fix, and
proves the fix by re-running.

It ships as an MCP server, so Claude Desktop, Claude Code, or any MCP client can
use it as a tool.

## The idea

AI coding agents are fast at writing code and hopeless at explaining why it broke.
Teams now spend more time debugging AI-written code than writing it. ECHO is the
missing piece: it turns "the agent broke" into "the agent broke because of X, and
here is the one-line fix - verified."

## Tools

| Tool | What it does |
|------|--------------|
| echo_capture | Run a target Python file, record every step, report pass/fail |
| echo_diagnose | Find the first wrong step in the recorded run |
| echo_autofix | Search for the smallest real fix and prove it by re-running |
| echo_report | Write autopsy.html and return its path |
| echo_demo | Do all of the above in one call |

## Quick start

    pip install mcp
    python3 echo_mcp_server.py

Connect it to Claude Desktop by adding an echo entry to claude_desktop_config.json,
or to Claude Code:

    claude mcp add echo -- python3 /full/path/to/echo_mcp_server.py

Then ask the agent: run echo_demo

## What is real

The server really runs the program, captures the true output, finds the true
failure, searches real candidate fixes by executing them, and proves the fix by
re-running.

The full product would add: an AI model proposing the fixes, recording a real
coding agent, proof by repetition, and a team failure atlas.

## Status

Early prototype, built in the open.

## License

MIT
