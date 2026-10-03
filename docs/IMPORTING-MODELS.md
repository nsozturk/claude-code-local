# Importing models

`ccl` runs **everything through Ollama**. So "adding a model" — whether it came from the Ollama
registry, Hugging Face, or LM Studio — always means *register it with Ollama once*. After that,
`sync-models.py` lists it in Claude Code's `/model` picker and (optionally) `sync-opencode.py`
mirrors it into opencode, automatically.

```
model source ──► Ollama (one model store) ──► ccl /model picker + opencode
```

The helper is `scripts/import-model.py` (also reachable as the examples below assume it's on PATH).

## 1. Ollama registry

Nothing to do — `ccl` discovers every `ollama list` entry on launch.

```bash
ollama pull qwen2.5-coder:14b
ccl            # it's already in /model
```

## 2. Hugging Face

Modern Ollama can pull a GGUF straight from Hugging Face:

```bash
python3 scripts/import-model.py hf.co/TheUser/TheRepo-GGUF:Q4_K_M
# equivalently: ollama pull hf.co/TheUser/TheRepo-GGUF:Q4_K_M
```

Or, if you already downloaded the `.gguf`, import it as a local file (next section).

## 3. LM Studio

LM Studio stores each model as a plain `.gguf` under
`~/.lmstudio/models/<publisher>/<repo>-GGUF/<file>.gguf`. Point the importer at that file — Ollama
**reuses the blob in place**, so there is no second multi-GB download:

```bash
python3 scripts/import-model.py --list-lmstudio          # see what LM Studio already has
python3 scripts/import-model.py ~/.lmstudio/models/Qwen/Qwen2.5-Coder-7B-GGUF/model-Q4_K_M.gguf
```

## 4. Any loose GGUF

```bash
python3 scripts/import-model.py /path/to/model.gguf --name my-coder --ctx 131072
```

### Options

| flag | meaning |
|---|---|
| `--name NAME` | Ollama model name (default: derived from the file/folder) |
| `--ctx N` | bake in `num_ctx` (e.g. `131072`) |
| `--template-from MODEL` | copy `TEMPLATE`/`PARAMETER`s from an existing Ollama model of the same family — use this if a bare GGUF answers with wrong roles or no stop tokens |
| `--dry-run` | print the Modelfile and commands, change nothing |

## Context matters

Claude Code's opening prompt (system + tools + any `CLAUDE.md`) is **~26–46k tokens**. A model loaded
at the common `num_ctx 32768` rejects the very first message with HTTP 400
(`exceeds the available context size`). After importing, if the tool warns about this, run:

```bash
ccl --fix-ctx          # creates <model>-ctx128k variants (weights are shared — no extra disk)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for why per-request context options don't work and variants do.
