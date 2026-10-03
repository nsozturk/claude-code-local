#!/usr/bin/env python3
"""
verify-picker.py
----------------
Smoke test run after a Claude Code update: launches ccl in a pseudo-terminal,
opens /model and checks that the local modelPicker rows are listed.
Exit 0 = picker shows local models, 1 = it does not (output printed).
"""

import json
import os
import pty
import re
import select
import signal
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(PROJECT_ROOT, "bin", "ccl")
SETTINGS = os.path.expanduser("~/.claude-isvalorum/settings.json")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[\]P_^][^\x07\x1b]*(\x07|\x1b\\)|\x1b[@-Z\\-_]")


def read_for(fd, seconds, until=None):
    out, end = b"", time.time() + seconds
    while time.time() < end:
        if select.select([fd], [], [], 0.1)[0]:
            try:
                out += os.read(fd, 65536)
            except OSError:
                break
            if until and until in ANSI.sub("", out.decode("utf-8", "replace")):
                break
    return ANSI.sub("", out.decode("utf-8", "replace"))


def main():
    options = json.load(open(SETTINGS)).get("modelPicker", {}).get("options", [])
    if len(options) < 2:
        print("✗ settings.json has fewer than 2 modelPicker options — run scripts/sync-models.py")
        return 1
    # Any row other than the active model: the active one is also printed in the banner.
    probe = options[1].get("label") or options[1]["model"]

    pid, fd = pty.fork()
    if pid == 0:
        os.environ.update(CCL_SKIP_VERIFY="1", TERM="xterm-256color")
        os.chdir(os.path.expanduser("~"))
        os.execv(LAUNCHER, [LAUNCHER])

    try:
        read_for(fd, 20, until="❯")
        os.write(fd, b"/model")
        read_for(fd, 1.5)
        os.write(fd, b"\r")
        screen = read_for(fd, 8, until=probe)
        os.write(fd, b"\x1b")
    finally:
        # Claude Code ignores SIGTERM while its TUI is up; SIGKILL is the reliable exit.
        # Close the pty first: on macOS a dying process blocks draining an unread pty.
        os.kill(pid, signal.SIGKILL)
        os.close(fd)
        os.waitpid(pid, 0)

    if "Select model" in screen and probe in screen:
        print(f"✓ /model picker lists local models (found '{probe}')")
        return 0
    print(f"✗ /model picker did not list local model '{probe}'. Captured screen:\n{screen[-3000:]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
