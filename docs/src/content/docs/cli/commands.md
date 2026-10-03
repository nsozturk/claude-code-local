---
title: Commands & CLI Reference
description: Complete reference for ccl commands, options, and environment variables.
---

## Primary Commands

### `ccl`
Starts the local Claude Code session. Automatically launches background bridge if not running.

```bash
ccl [claude-flags]
```

### `ccl --status`
Shows the active bridge status, PID, listening port, and resident models in VRAM.

```bash
ccl --status
```

### `ccl --unload`
Immediately evicts all resident models from memory via Ollama's API.

```bash
ccl --unload
```

### `ccl --fix-ctx`
Scans local Ollama models and creates `-ctx128k` variants with zero disk overhead.

```bash
ccl --fix-ctx
```

### `ccl --tune`
Opens an interactive terminal configuration panel for adjusting context sizes, thread counts, and memory limits.

```bash
ccl --tune
```
