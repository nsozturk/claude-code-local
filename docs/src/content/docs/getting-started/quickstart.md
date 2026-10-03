---
title: Quick Start
description: Start your first local Claude Code session in seconds.
---

## Launching Local Claude Code

Run `ccl` to start Claude Code connected to your default local model:

```bash
ccl
```

This starts the lightweight proxy bridge in the background and launches Claude Code with the isolated profile `~/.claude-isvalorum`.

## Switching Models Interactively

Inside Claude Code, run the standard slash command:

```text
/model
```

You will see your curated list of local models. When you choose a new model:
1. The currently loaded model is immediately evicted from GPU unified memory.
2. The new model is loaded into VRAM.
3. Your conversation resumes seamlessly with zero swap storms.

## Quick CLI Inspection

To check active background bridge status and loaded models:

```bash
ccl --status
```

To purge all models from unified memory:

```bash
ccl --unload
```
