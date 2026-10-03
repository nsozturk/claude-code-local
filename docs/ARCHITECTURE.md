# CCI Architecture & Technical Specification

> **CCI** is an isolated, local model execution layer for **Claude Code CLI**, enabling seamless integration with local Ollama models (35B MoE, 27B MTP, 9B, 4B, 2B) while preserving official Claude Code (Anthropic Opus) untouched.

---

## 1. System Topology

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
|   - Jinja loop.first system message sanitizer               |
|   - Real-time SSE token streamer                            |
|   - Dynamic memory manager (keep_alive: 0 on switch)        |
+------------------------------+------------------------------+
                               | Ollama API
                               v (HTTP POST /api/generate & /api/ps)
+-------------------------------------------------------------+
|                    Ollama (127.0.0.1:11434)                 |
|   - Metal GPU Acceleration (Apple Silicon Unified Memory)   |
|   - 21 Local Models (APFS zero-byte hardlinked storage)     |
+-------------------------------------------------------------+
```

---

## 2. Core Invariants & Isolation

### Rule 1: Zero Impact on Anthropic Claude Code
- Global Claude Code (`claude`, `cc`, `c`) reads from `~/.claude/settings.json` and connects directly to Anthropic's cloud endpoints (Claude 3.7 Sonnet / Opus 3.5).
- `ccl` operates under `CLAUDE_HOME=~/.claude-isvalorum` and `CLAUDE_CONFIG_DIR=~/.claude-isvalorum`.
- It overrides settings explicitly via `--settings ~/.claude-isvalorum/settings.json`, ensuring the user's primary credentials and session history are completely segregated.

### Rule 2: Dynamic `/model` Picker via `flagSettings`
Claude Code's internal model resolver (`Aie()`) evaluates settings in priority order:
1. `policySettings` (Enterprise managed)
2. `flagSettings` (Loaded via `--settings <file>`)
3. `userSettings` (Hardcoded to `~/.claude/settings.json`)

By passing `--settings ~/.claude-isvalorum/settings.json` upon launch:
- Claude Code registers our 21 local Ollama models into `flagSettings`.
- `replaceBuiltInOptions: true` replaces Anthropic default cloud models with local models.
- When typing `/model`, Claude Code displays the curated list of 21 local models with descriptions and disk sizes.
- Clean model names (`isvalorum-35b`, `swift-27b-mtp`) satisfy `en(v) === v` in Claude Code's validator (`egr`), preventing dropped entries.

---

## 3. Dynamic RAM / VRAM Memory Management

When switching models in an interactive session (or via `-m`):
1. **Ollama Default Behavior:** Retains models in VRAM for 5 minutes (`keep_alive: 5m`). On 36GB-128GB Macs, running two 27B/35B models simultaneously causes memory thrashing or swap exhaustion.
2. **CCI Dynamic Unloading:**
   - On every request sent to `/v1/messages` with a model that differs from currently loaded models, `claude-ollama-bridge` inspects `GET /api/ps`.
   - Any loaded model other than the requested model is immediately evicted via `POST /api/generate` with `keep_alive: 0`.
   - VRAM and Metal unified memory are freed before the new model loads, ensuring instantaneous, stutter-free execution.
3. **Manual Memory Purge:**
   - Run `ccl --unload` or `./scripts/unload-models.sh` to purge all models from RAM at any time.

---

## 4. Message & Template Compatibility

Ollama models utilizing modern Jinja chat templates (e.g. Qwen 2.5 / DeepSeek V3) enforce that `role == 'system'` may only appear at `loop.first`:
```jinja
{% if message['role'] == 'system' and not loop.first %}
    {{ raise_exception("System messages can only appear at loop.first") }}
{% endif %}
```
Claude Code regularly injects multi-turn system reminders during long-running sessions. The `claude-ollama-bridge` intercepts any system message occurring at index > 0 and converts it into a structured user message prefixed with `[System Context / Environment Information]:\n`, eliminating HTTP 500 template evaluation errors.

---

## 5. 1M Context Window Engineering

To prevent Claude Code from prematurely compacting session history:
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW="1000000"`
- `CLAUDE_CODE_MAX_CONTEXT_TOKENS="1000000"`
- `CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT="1"`
- `API_TIMEOUT_MS="3000000"` (50-minute timeout allowing complex local agentic loops)
