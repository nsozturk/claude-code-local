#!/usr/bin/env python3
"""
sync-models.py
--------------
Synchronizes installed Ollama models with Claude Code ccl configuration.
Generates an isolated settings.json with full /model picker support,
setting replaceBuiltInOptions=true and clean base model names.
"""

import json
import os
import sys
import urllib.request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
BRIDGE_PORT = os.environ.get("BRIDGE_PORT", "11435")
BRIDGE_URL = f"http://127.0.0.1:{BRIDGE_PORT}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MODELS_CATALOG_PATH = os.path.join(PROJECT_ROOT, "config", "models.json")
DEFAULT_SETTINGS_OUT = os.path.join(PROJECT_ROOT, "config", "settings.json")
PROFILE_SETTINGS_OUT = os.path.expanduser("~/.claude-isvalorum/settings.json")
STATS_PATH = os.path.expanduser("~/.claude-isvalorum/stats.jsonl")
VARIANTS_PATH = os.path.expanduser("~/.claude-isvalorum/variants.json")  # written by ccl --tune

def load_variants():
    try:
        with open(VARIANTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def measured_speed():
    """{model: " · 23 tok/s · first token 11s"} from the bridge's warm turns (median of the last 20)."""
    rows = {}
    try:
        with open(STATS_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not r.get("cold") and r.get("tok_s"):
                    rows.setdefault(r["model"], []).append(r)
    except OSError:
        return {}
    median = lambda xs: sorted(xs)[len(xs) // 2]
    out = {}
    for model, rs in rows.items():
        rs = rs[-20:]
        out[model] = (f" · {median([r['tok_s'] for r in rs]):.0f} tok/s"
                      f" · first token {median([r['ttft_s'] for r in rs]):.0f}s")
    return out

def load_catalog():
    if os.path.exists(MODELS_CATALOG_PATH):
        try:
            with open(MODELS_CATALOG_PATH, "r", encoding="utf-8") as f:
                return {item["model"]: item for item in json.load(f)}
        except Exception as e:
            sys.stderr.write(f"Warning: could not read models.json: {e}\n")
    return {}

def fetch_ollama_tags():
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.load(resp)
            return data.get("models", [])
    except Exception as e:
        sys.stderr.write(f"Warning: could not connect to Ollama ({OLLAMA_HOST}): {e}\n")
        return []

def generate_settings(active_model=None, output_path=None):
    catalog = load_catalog()
    tags = fetch_ollama_tags()
    variants = load_variants()
    speed = measured_speed()
    
    seen = set()
    model_options = []
    
    # A base model that has a "replaces_base" variant (ccl --fix-ctx) cannot serve Claude Code's
    # opening prompt; list the variant in its place. The base stays in Ollama for other clients.
    replaced = {v["base"] for v in variants.values() if v.get("replaces_base")}

    # 1. Process Ollama tags
    for m in tags:
        name = m.get("name", "")
        base = name.split(":")[0]
        tag = name.split(":")[1] if ":" in name else "latest"
        
        # Skip duplicate internal tags like :test or :backup if base is already registered
        if tag in ("test", "backup") and base in seen:
            continue
        if base in replaced:
            continue
        seen.add(base)
        
        size_gb = m.get("size", 0) / (1024**3)
        size_str = f"{size_gb:.1f} GB"
        
        variant = variants.get(base)
        cat_info = catalog.get(variant["base"] if variant else base, {})
        desc = cat_info.get("description", f"Local Ollama Model ({size_str})")
        if variant and variant.get("replaces_base"):
            desc = f"{desc} · {variant['label']}"
        elif variant:
            desc = f"{variant['label']} · {variant['base']}"
        desc += speed.get(base, "")
        behaves_as = cat_info.get("behavesAs", "claude-3-5-sonnet-20241022")
        
        model_options.append({
            "model": base,
            "label": base,
            "description": desc,
            "behavesAs": behaves_as
        })
        
    # 2. If Ollama was offline, fall back to models.json catalog
    if not model_options and catalog:
        for base, cat_info in catalog.items():
            model_options.append({
                "model": base,
                "label": base,
                "description": cat_info.get("description", "Local Ollama Model"),
                "behavesAs": cat_info.get("behavesAs", "claude-3-5-sonnet-20241022")
            })

    # Pick default active model
    if not active_model:
        active_model = "isvalorum-35b"
        
    clean_active = active_model.replace(":latest", "").replace("[1m]", "").strip()
    
    # Re-order options so the active model is first
    model_options.sort(key=lambda x: 0 if x["model"] == clean_active else 1)
    
    settings = {
        "env": {
            "ANTHROPIC_BASE_URL": BRIDGE_URL,
            "ANTHROPIC_AUTH_TOKEN": "ollama-local",
            "ANTHROPIC_MODEL": clean_active,
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000",
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1000000",
            "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "API_TIMEOUT_MS": "3000000"
        },
        "autoCompactWindow": 1000000,
        "permissions": {
            "defaultMode": "auto",
            # WebSearch runs on Anthropic's servers: locally it errors and the model then invents sources
            "deny": ["WebSearch"]
        },
        "model": clean_active,
        "modelPicker": {
            "replaceBuiltInOptions": True,
            "options": model_options
        },
        # Status line pings the bridge on every render, so a /model pick unloads/loads immediately
        "statusLine": {
            "type": "command",
            "command": f"python3 {os.path.join(SCRIPT_DIR, 'statusline.py')}",
            "refreshInterval": 1  # live load % / prefill timer while a model loads
        },
        "skipDangerousModePermissionPrompt": True,
        "skipAutoPermissionPrompt": True,
        "theme": "dark"
    }
    
    target_files = [DEFAULT_SETTINGS_OUT]
    if output_path:
        target_files = [output_path]
    else:
        # Also sync to ~/.claude-isvalorum/settings.json
        os.makedirs(os.path.dirname(PROFILE_SETTINGS_OUT), exist_ok=True)
        target_files.append(PROFILE_SETTINGS_OUT)
        
    for p in target_files:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
            
    print(f"✓ Synced {len(model_options)} local models to {', '.join(target_files)}")
    return settings

if __name__ == "__main__":
    active = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else None
    generate_settings(active_model=active, output_path=out)
