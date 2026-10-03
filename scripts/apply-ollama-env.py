#!/usr/bin/env python3
"""
apply-ollama-env.py — make the saved Ollama server settings (ccl --tune SERVER section) stick.

`launchctl setenv` does not survive a reboot, so the server knobs (Flash Attention, KV cache type,
…) are lost on restart. The ccl LaunchAgent runs this at login: it pushes the settings saved in
~/.claude-isvalorum/ollama-env.json into the launchd session, and if Ollama is already running
without them, restarts it (and the bridge) so the runner picks them up.

Also runnable by hand. Idempotent: does nothing if the live env already matches.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import ollama_mem  # noqa: E402

ENV_FILE = os.path.expanduser("~/.claude-isvalorum/ollama-env.json")
BRIDGE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "bin", "claude-ollama-bridge")
DEFAULTS = {"OLLAMA_FLASH_ATTENTION": "0", "OLLAMA_KV_CACHE_TYPE": "f16",
            "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_KEEP_ALIVE": "5m"}


def ollama_up(timeout):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(f"{ollama_mem.OLLAMA_HOST}/api/version", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    try:
        want = json.load(open(ENV_FILE))
    except (OSError, ValueError):
        print("no saved ollama-env.json; nothing to apply")
        return
    # 1. Push into the launchd (GUI) session so a freshly-launched Ollama inherits them.
    for k, v in want.items():
        if v == DEFAULTS.get(k):
            subprocess.run(["launchctl", "unsetenv", k])
        else:
            subprocess.run(["launchctl", "setenv", k, v])
    # 2. If Ollama is already running without the desired env, restart it to pick them up.
    running = ollama_mem._pids("Ollama.app/Contents/Resources/ollama serve")
    live = ollama_mem.serve_env()
    # Restart whenever the live server differs from what we want (an unset var means its default).
    drift = {k: v for k, v in want.items() if live.get(k, DEFAULTS.get(k)) != v}
    if running and drift:
        subprocess.run(["pkill", "-x", "Ollama"])          # SIGTERM the menubar app (no dialog)
        for _ in range(40):
            if not ollama_mem._pids("Ollama.app/Contents/Resources/ollama serve"):
                break
            time.sleep(0.25)
        subprocess.run(["open", "-a", "Ollama"])
        if ollama_up(30):
            subprocess.run([BRIDGE, "restart"], capture_output=True)
            print(f"restarted Ollama with: {', '.join(f'{k}={v}' for k, v in drift.items())}")
        else:
            print("Ollama did not come back up within 30 s", file=sys.stderr)
    else:
        active = {k: v for k, v in want.items() if v != DEFAULTS.get(k)}
        print("ollama env set" + (f" ({', '.join(f'{k}={v}' for k, v in active.items())})" if active else ""))


if __name__ == "__main__":
    main()
