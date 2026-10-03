#!/usr/bin/env python3
"""
ollama_mem.py
-------------
Shared memory facts for ccl (bridge /api/status, `ccl --tune`, launcher check).
Ollama reports nothing while a model loads, so everything here is measured from
the outside: runner RSS, GGUF metadata from /api/show, vm_stat, and the serve
process environment.

Run directly for a self-check: python3 scripts/ollama_mem.py [model]
"""

import json
import os
import re
import subprocess
import urllib.request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
GB = 1024 ** 3
# Bytes per KV element (llama.cpp block formats: q8_0 = 34 B / 32 values, q4_0 = 18 B / 32 values)
KV_BYTES = {"f16": 2.0, "q8_0": 34 / 32, "q4_0": 18 / 32}
_SHOW_CACHE = {}


def _get(path, payload=None, timeout=3):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{OLLAMA_HOST}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def base(name):
    return (name or "").split(":")[0]


def tags():
    """{base name: blob size in bytes} for every installed model."""
    return {base(m["name"]): m.get("size", 0) for m in _get("/api/tags").get("models", [])}


def loaded():
    """Models resident in Ollama right now: [{name, size, size_vram, expires_at, context_length}]."""
    return _get("/api/ps", timeout=2).get("models", [])


def show(name):
    """GGUF metadata + Modelfile parameters, cached per model (they only change via ollama create)."""
    key = base(name)
    if key not in _SHOW_CACHE:
        d = _get("/api/show", {"model": key})
        params = {}
        for line in (d.get("parameters") or "").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                params[parts[0]] = parts[1].strip().strip('"')
        blob = re.search(r"^FROM (\S+/blobs/\S+)", d.get("modelfile") or "", re.M)
        _SHOW_CACHE[key] = {"info": d.get("model_info", {}), "params": params,
                            "blob": blob.group(1) if blob else None}
    return _SHOW_CACHE[key]


def _pids(pattern):
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out]


def rss(pid):
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) * 1024 if out else 0


def runner_rss(name):
    """RSS of the Ollama runner serving `name` (matched by its blob path; an evicted model's
    runner can still be alive for a moment, so 'newest runner' is not good enough)."""
    blob = show(name).get("blob")
    pids = _pids(re.escape(blob)) if blob else _pids("Ollama.app/Contents/Resources/llama-server")
    return rss(max(pids)) if pids else 0


def lmstudio_rss():
    """Memory held by LM Studio's own llama-server runners — invisible to Ollama's eviction."""
    return sum(rss(p) for p in _pids(r"\.lmstudio/.*llama-server"))


def serve_env():
    """OLLAMA_* / LLAMA_ARG_* variables the running `ollama serve` actually has."""
    pids = _pids("Ollama.app/Contents/Resources/ollama serve")
    if not pids:
        return {}
    out = subprocess.run(["ps", "eww", "-o", "command=", "-p", str(pids[0])],
                         capture_output=True, text=True).stdout
    return dict(m.groups() for m in re.finditer(r"\b((?:OLLAMA|LLAMA_ARG)_[A-Z_]+)=(\S*)", out))


def available():
    """Reclaimable memory: free + inactive + speculative + purgeable pages."""
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    page = int(re.search(r"page size of (\d+)", out).group(1))
    pages = {k: int(v) for k, v in re.findall(r"Pages (\w+):\s+(\d+)", out)}
    return sum(pages.get(k, 0) for k in ("free", "inactive", "speculative", "purgeable")) * page


def estimate(name, num_ctx=None, kv_type=None):
    """(weights_bytes, kv_bytes, num_ctx) the model will need once loaded.

    KV per token = 2 (K+V) x attention layers x kv heads x head dim x bytes. Hybrid models
    (e.g. qwen35moe) only keep KV on every `full_attention_interval`-th layer.
    """
    meta = show(name)
    info, params = meta["info"], meta["params"]
    arch = info.get("general.architecture", "")
    a = lambda k: info.get(f"{arch}.{k}")
    env = serve_env()
    max_ctx = a("context_length") or 0
    ctx = int(num_ctx or params.get("num_ctx") or env.get("OLLAMA_CONTEXT_LENGTH") or 4096)
    ctx = min(ctx, max_ctx) if max_ctx else ctx
    kv_type = kv_type or env.get("OLLAMA_KV_CACHE_TYPE") or "f16"
    layers = a("block_count") or 0
    if a("full_attention_interval"):
        layers = layers // a("full_attention_interval")
    heads = a("attention.head_count_kv") or a("attention.head_count") or 0
    if isinstance(heads, list):  # some archs store a per-layer list
        heads = max(heads)
    head_dim = a("attention.key_length") or ((a("embedding_length") or 0) // (a("attention.head_count") or 1))
    kv = 2 * layers * heads * head_dim * KV_BYTES.get(kv_type, 2.0) * ctx
    return tags().get(base(name), 0), int(kv), ctx


def fit(name, num_ctx=None, kv_type=None):
    """Will `name` fit if loaded now? Memory of other Ollama models counts as free (ccl evicts them)."""
    weights, kv, ctx = estimate(name, num_ctx, kv_type)
    evictable = sum(m.get("size", 0) for m in loaded() if base(m["name"]) != base(name))
    # ponytail: compute buffers modelled as +5% +0.3 GB (measured: isvalorum 16.2→17.0 GB, qwen-2b 1.6→1.9 GB)
    need, avail = (weights + kv) * 1.05 + 0.3 * GB, available() + evictable
    return {"need_gb": round(need / GB, 1), "weights_gb": round(weights / GB, 1), "kv_gb": round(kv / GB, 1),
            "ctx": ctx, "avail_gb": round(avail / GB, 1), "lmstudio_gb": round(lmstudio_rss() / GB, 1),
            "ok": need <= avail}


if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "isvalorum-35b"
    w, kv, ctx = estimate(model)
    print(f"{model}: weights {w / GB:.1f} GB + KV {kv / GB:.2f} GB @ ctx {ctx}")
    print(json.dumps(fit(model)))
    # isvalorum-35b at ctx 131072: 10 attention layers x 2 heads x 256 dim x 2 B x 2 = 20 KiB/token
    if model == "isvalorum-35b":
        _, kv131k, _ = estimate(model, num_ctx=131072, kv_type="f16")
        assert kv131k == 20480 * 131072, kv131k
        _, kvq8, _ = estimate(model, num_ctx=131072, kv_type="q8_0")
        assert kvq8 < kv131k * 0.55
        print("✓ KV formula self-check passed")
