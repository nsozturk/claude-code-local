#!/usr/bin/env python3
"""
sync-opencode.py
----------------
Mirror every local Ollama model into opencode's config (~/.config/opencode/opencode.json),
under the existing `ollama` provider. opencode needs each model declared explicitly; this keeps
that list in sync with `ollama list` without hand-editing the (comment-bearing) JSON.

Per model `limit.context` = the context Ollama actually serves (the model's num_ctx). Setting it
higher does not give more context: Ollama rejects a request past num_ctx with HTTP 400
("exceeds the available context size"), and opencode never compacts because it thinks there is room.
A model whose served context is below opencode's ~61k opening prompt is marked unusable in its name.

- Only the ollama provider's `models` block is rewritten; comments elsewhere are preserved.
- :test / :backup tags are skipped. A timestamped backup is written first.
- Run after adding/removing Ollama models, or after `ccl --fix-ctx`.
"""

import datetime
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import ollama_mem  # noqa: E402

CONFIG = os.path.expanduser("~/.config/opencode/opencode.json")
OPENCODE_PROMPT = 61000  # measured opening prompt; a model below this 400s on the first turn
NAMES = {  # friendly labels; variants and unknown models fall back to the model id
    "isvalorum-35b": "IsValorum 35B MoE (Coder Abliterated)",
    "cyber-tiel-coder-35b": "Cyber Tiel Coder 35B MoE",
    "titus-cybersecurity-35b": "Titus Cybersecurity 35B",
    "ravenx-cyberagent-35b": "RavenX CyberAgent 35B",
    "swift-27b-mtp": "Swift 27B MTP Dynamic",
}


def served_ctx(model):
    """What Ollama will load this model at: its num_ctx parameter, else its trained ceiling."""
    meta = ollama_mem.show(model)
    n = meta["params"].get("num_ctx")
    if n:
        return int(n)
    info = meta["info"]
    arch = info.get("general.architecture", "")
    return int(info.get(f"{arch}.context_length") or 32768)


def build_models():
    models = {}
    for name in sorted(ollama_mem.tags()):
        ctx = served_ctx(name)
        label = NAMES.get(name, name)
        if name.endswith("-ctx128k"):
            label = f"{NAMES.get(name[:-8], name[:-8])} · 128k ctx"
        elif name.endswith("-ctx256k"):
            label = f"{NAMES.get(name[:-8], name[:-8])} · 256k ctx"
        if ctx < OPENCODE_PROMPT:
            label += f" (32k ctx — too small for opencode's ~61k prompt; use -ctx128k)"
        models[name] = {
            "name": label,
            "limit": {"context": ctx, "output": min(32768, ctx // 2)},
            "modalities": {"input": ["text"], "output": ["text"]},
        }
    return models


def splice(text, models):
    """Replace the ollama provider's `models: {...}` object, leaving the rest of the file intact."""
    prov = text.index('"ollama"')
    m_key = text.index('"models"', prov)
    brace = text.index("{", m_key)
    depth, i = 0, brace
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    indent = " " * (text.rfind("\n", 0, m_key) and (m_key - text.rfind("\n", 0, m_key) - 1))
    body = json.dumps(models, indent=4, ensure_ascii=False)
    body = "\n".join((indent + line if line else line) for line in body.splitlines()).lstrip()
    return text[:brace] + body + text[i + 1:]


def main():
    if not os.path.exists(CONFIG):
        sys.exit(f"opencode config not found: {CONFIG}")
    text = open(CONFIG, encoding="utf-8").read()
    models = build_models()
    new = splice(text, models)
    # Validate: the file is JSONC (// comments); strip them before parsing.
    parsed = json.loads(re.sub(r"^\s*//.*$", "", new, flags=re.M))
    assert parsed["provider"]["ollama"]["models"] == models, "round-trip mismatch"
    backup = f"{CONFIG}.bak-sync-{datetime.datetime.now():%Y%m%d_%H%M%S}"
    shutil.copy2(CONFIG, backup)
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"✓ synced {len(models)} Ollama models into opencode (backup: {backup})")


if __name__ == "__main__":
    main()
