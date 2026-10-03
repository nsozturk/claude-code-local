# Models

`ccl` does not ship a fixed model list. It **discovers whatever you have in Ollama** (`ollama list`)
every time it launches, and shows all of them in Claude Code's `/model` picker.

## The optional catalog (`config/models.json`)

This file is **purely cosmetic**. It maps an Ollama model's base name to a nicer label, a short
description and a category, which `ccl` uses when it builds the picker. A model that isn't in the
catalog still appears — it just uses its raw name and a generic description.

```json
[
  {
    "model": "qwen2.5-coder:14b",
    "label": "qwen2.5-coder:14b",
    "description": "Qwen2.5 Coder 14B",
    "category": "coding",
    "behavesAs": "claude-3-5-sonnet-20241022"
  }
]
```

- **`behavesAs`** tells Claude Code which model's client-side handling (prompt profile, capability
  and effort defaults) to apply to a model this version doesn't know. Leave it at a current Claude
  model id.

## Adding models

Any model works as long as Ollama can serve it. See [IMPORTING-MODELS.md](IMPORTING-MODELS.md) for
pulling from the Ollama registry, Hugging Face, or importing a GGUF you already have in LM Studio.

## Context

Claude Code's opening prompt is ~26–46k tokens, so models loaded at the common 32k context fail on
the first message. Run `ccl --fix-ctx` to generate `-ctx128k` variants (weights shared, no extra
disk). See [ARCHITECTURE.md](ARCHITECTURE.md).
