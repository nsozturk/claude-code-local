---
title: Dynamic Memory & VRAM Eviction
description: Preventing swap thrashing and managing Apple Silicon unified memory.
---

## The Unified Memory Challenge

When running large 27B or 35B models on Apple Silicon (36GB to 128GB unified RAM), loading two models simultaneously quickly causes swap storms and OS sluggishness.

By default, Ollama retains models in VRAM for 5 minutes (`keep_alive: 5m`). If you switch models in Claude Code, both models may briefly reside in memory.

## Dynamic Eviction Mechanism

The `claude-ollama-bridge` monitors every incoming request:
1. When a request for Model B arrives, it queries `GET /api/ps` to check loaded models.
2. If Model A is currently resident, it sends `POST /api/generate` with `keep_alive: 0` targeting Model A.
3. Metal unified memory is instantly reclaimed before Model B begins weight allocation.
4. Switching is immediate, stutter-free, and avoids macOS memory compression thrash.

## Zero-Byte APFS Context Variants

Claude Code's initialization prompt consumes ~26k–46k tokens. A 32k context model immediately rejects the first turn.

Running `ccl --fix-ctx` automatically creates 128k context variants (`-ctx128k`) via APFS clonefile / hardlinks. Weights are shared, so 0 additional disk space is consumed.
