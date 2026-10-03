#!/usr/bin/env python3
"""
statusline.py
-------------
ccl status line, re-run every second (refreshInterval) and on every Claude Code event.
Claude Code has no "model changed" hook, so each render reports the active model to the
bridge (GET /api/status/<model>): a new pick is evicted/loaded right away, and the reply
says what the local model is doing — load %, prompt processing, generating, idle expiry.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

BRIDGE_URL = f"http://127.0.0.1:{os.environ.get('BRIDGE_PORT', '11435')}"


def minutes_left(expires_at):
    """Ollama's expires_at (RFC 3339, may carry nanoseconds) → whole minutes from now."""
    try:
        from datetime import datetime
        stamp = expires_at[:19] + expires_at[-6:] if expires_at[-6] in "+-" else expires_at[:19] + "+00:00"
        return max(0, int((datetime.fromisoformat(stamp).timestamp() - time.time()) // 60))
    except Exception:
        return None


def fit_warning(fit):
    if not fit or fit.get("ok"):
        return ""
    lms = f" · LM Studio {fit['lmstudio_gb']} GB" if fit.get("lmstudio_gb") else ""
    return f" · ⚠ needs ~{fit['need_gb']} GB, ~{fit['avail_gb']} GB free{lms}"


def ctx_label(st):
    n = st.get("ctx")
    if not n:
        return ""
    return f" · ctx {n // 1024}k" if n % 1024 == 0 else f" · ctx {n}"


def slow_hint(st):
    """Shown when prompt processing drags: the knobs that actually speed it up, cheapest first."""
    bits = []
    if (st.get("ctx") or 0) > 65536:
        bits.append("ctx↓")
    if not st.get("fa"):
        bits.append("Flash Attention")
    if st.get("kv", "f16") == "f16":
        bits.append("q8 KV")
    tip = ", ".join(bits) or "a smaller model"
    return f" · slow? ccl --tune → {tip}"


def render(model, st):
    phase = st.get("phase")
    if phase == "loading":
        pct = f" %{st['pct']}" if st.get("pct") is not None else ""
        gb = f" · {st['rss_gb']}/{st['size_gb']} GB" if st.get("size_gb") else ""
        return f"⏳ loading {model}{pct}{gb} · {st.get('elapsed', 0)}s{fit_warning(st.get('fit'))}"
    if phase == "prefill":
        hint = slow_hint(st) if st.get("elapsed", 0) >= 20 else ""
        return f"🧠 {model}{ctx_label(st)} · processing prompt {st.get('elapsed', 0)}s{hint}"
    if phase == "generating":
        return f"✍️  {model}{ctx_label(st)} · generating"
    if phase == "ready":
        left = minutes_left(st.get("expires_at") or "")
        expiry = f" · unloads in {left} min" if left is not None else ""
        return f"✓ {model}{ctx_label(st)} · {st.get('size_gb', '?')} GB resident{expiry}"
    if phase == "offline":
        return f"✗ {model} · Ollama unreachable"
    return f"○ {model} · not resident{fit_warning(st.get('fit'))}"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    model = (data.get("model") or {}).get("id") or ""
    shown = (data.get("model") or {}).get("display_name") or model or "ccl"
    try:
        session = urllib.parse.quote(data.get("session_id") or "", safe="")
        url = f"{BRIDGE_URL}/api/status/{urllib.parse.quote(model, safe='')}?session={session}"
        with urllib.request.urlopen(url, timeout=0.8) as resp:
            st = json.load(resp)
        print(f"🦙 {render(st.get('model') or shown, st)}")
    except Exception:
        print(f"🦙 {shown} · bridge not responding")


if __name__ == "__main__":
    main()
