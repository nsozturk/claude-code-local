---
title: System Topology & Architecture
description: Technical design, isolation principles, and bridge execution flow.
---

## Overview

Claude Code Local provides an isolated local execution layer for Claude Code CLI, proxying Anthropic Messages API calls to local Ollama backends while leaving the official Anthropic configuration untouched.

```
+-------------------------------------------------------------+
|                      Claude Code CLI                        |
|   (ccl / claude-isvalorum --dangerously-skip-permissions)   |
|   - Profile: ~/.claude-isvalorum                            |
|   - Settings: --settings ~/.claude-isvalorum/settings.json  |
+------------------------------+------------------------------+
                               | Anthropic Messages API
                               v (HTTP POST /v1/messages)
+-------------------------------------------------------------+
|              claude-ollama-bridge (127.0.0.1:11435)         |
|   - Model router & parameter normalizer                     |
|   - Dynamic memory manager (keep_alive: 0 on switch)        |
|   - Real-time SSE token streamer                            |
+------------------------------+------------------------------+
                               | Ollama API
                               v (HTTP POST /api/generate)
+-------------------------------------------------------------+
|                    Ollama (127.0.0.1:11434)                 |
|   - Metal GPU Acceleration (Apple Silicon Unified Memory)   |
|   - APFS zero-byte hardlinked storage variants              |
+-------------------------------------------------------------+
```

## Profile Segregation

- **Global Claude Code (`claude`)**: Points to `~/.claude/settings.json` and connects to official Anthropic cloud endpoints.
- **Claude Code Local (`ccl`)**: Runs under `CLAUDE_HOME=~/.claude-isvalorum` with `--settings ~/.claude-isvalorum/settings.json`. Zero credentials, session logs, or API keys are shared.
