#!/usr/bin/env python3
"""
tune.py — `ccl --tune [model]`
------------------------------
LM Studio-style settings panel for ccl, in curses.

Claude Code talks to Ollama through /v1/messages, which ignores per-request `options`
(measured: a preload with num_ctx 4096 was thrown away and reloaded at the default on the
next /v1/messages call). So settings have to live where /v1/messages still sees them:

  MODEL  section → a variant model: `ollama create <base>-ctx64k` from a Modelfile with
                   `FROM <base>` + PARAMETER lines. Weights are shared (no extra disk);
                   the variant shows up as its own row in /model.
  SERVER section → OLLAMA_* environment of `ollama serve` (launchctl setenv + Ollama
                   restart, after confirmation). Global: affects every Ollama client.

Keys: ↑/↓ move · ←/→ change · Enter on a button · q / Esc quit.
Self-check: python3 scripts/tune.py --self-test
"""

import curses
import json
import os
import subprocess
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
import ollama_mem  # noqa: E402

PROFILE = os.path.expanduser("~/.claude-isvalorum")
VARIANTS_PATH = os.path.join(PROFILE, "variants.json")
SERVER_ENV_PATH = os.path.join(PROFILE, "ollama-env.json")  # desired server env; ccl warns when it drifts
MODELFILE_DIR = os.path.join(PROFILE, "modelfiles")
GB = ollama_mem.GB
AUTO = "auto"

# Ollama defaults for the server knobs we expose (unset == default)
SERVER_DEFAULTS = {"OLLAMA_FLASH_ATTENTION": "0", "OLLAMA_KV_CACHE_TYPE": "f16",
                   "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_KEEP_ALIVE": "5m"}
SHORT = {"num_ctx": "ctx", "num_gpu": "gpu", "num_thread": "t", "num_batch": "b",
         "temperature": "temp", "seed": "seed"}


# ---------------------------------------------------------------- pure helpers

def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def fmt_ctx(n):
    return f"{n // 1024}k" if n >= 1024 and n % 1024 == 0 else str(n)


def variant_name(base, params):
    """Readable, stable name: isvalorum-35b-ctx64k-t8."""
    parts = []
    for key in SHORT:
        if key in params:
            v = params[key]
            parts.append(SHORT[key] + (fmt_ctx(int(v)) if key == "num_ctx" else str(v)))
    return f"{base}-{'-'.join(parts)}" if parts else base


def variant_label(params):
    names = {"num_ctx": lambda v: f"ctx {fmt_ctx(int(v))}", "num_gpu": lambda v: f"GPU {v} layer",
             "num_thread": lambda v: f"{v} thread", "num_batch": lambda v: f"batch {v}",
             "temperature": lambda v: f"temp {v}", "seed": lambda v: f"seed {v}"}
    return " · ".join(names[k](params[k]) for k in SHORT if k in params)


def modelfile(base, params):
    return "".join([f"FROM {base}\n"] + [f"PARAMETER {k} {params[k]}\n" for k in SHORT if k in params])


# ---------------------------------------------------------------- panel model

class Panel:
    def __init__(self, model):
        self.variants = load_json(VARIANTS_PATH)
        self.models = sorted(ollama_mem.tags())
        self.model = model if model in self.models else (self.models[0] if self.models else "")
        self.server_now = {**SERVER_DEFAULTS, **{k: v for k, v in ollama_mem.serve_env().items()
                                                  if k in SERVER_DEFAULTS}}
        self.server = dict(self.server_now)
        self.message = ""
        self.load_model()
        self.row = 0

    def load_model(self):
        """Current values = the model's own PARAMETERs (variants carry their base's too)."""
        v = self.variants.get(self.model)
        self.base = v["base"] if v else self.model
        meta = ollama_mem.show(self.model)
        info, params = meta["info"], meta["params"]
        arch = info.get("general.architecture", "")
        self.max_ctx = info.get(f"{arch}.context_length") or 262144
        blocks = info.get(f"{arch}.block_count") or 32
        cpus = os.cpu_count() or 8
        self.params_now = {k: params[k] for k in SHORT if k in params}
        base_params = ollama_mem.show(self.base)["params"]
        self.base_params = {k: base_params[k] for k in SHORT if k in base_params}
        ctx_opts = [c for c in (2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144) if c <= self.max_ctx]
        self.fields = [
            ("num_ctx", "Context Length", [AUTO] + ctx_opts),
            ("num_gpu", "GPU Offload (layer)", [AUTO] + sorted({0, *range(8, blocks + 1, 8), blocks + 1})),
            ("num_thread", "CPU Thread", [AUTO] + list(range(1, cpus + 1))),
            ("num_batch", "Batch Size", [AUTO, 128, 256, 512, 1024, 2048]),
            ("temperature", "Temperature", [AUTO, 0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]),
            ("seed", "Seed", [AUTO, 0, 42, 1234]),
        ]
        self.values = {}
        for key, _, opts in self.fields:
            cur = self.params_now.get(key, AUTO)
            match = next((o for o in opts if str(o) == str(cur)), None)
            if match is None:  # keep an odd existing value selectable
                opts.insert(1, type(opts[-1])(cur) if cur != AUTO else cur)
                match = opts[1]
            self.values[key] = match

    # rows: model selector, model fields, server fields, buttons
    def rows(self):
        rows = [("model", None)]
        rows += [("param", f[0]) for f in self.fields]
        rows += [("server", k) for k in SERVER_DEFAULTS]
        rows += [("button", "apply"), ("button", "quit")]
        return rows

    def server_options(self, key):
        return {"OLLAMA_FLASH_ATTENTION": ["0", "1"],
                "OLLAMA_KV_CACHE_TYPE": ["f16", "q8_0", "q4_0"],
                "OLLAMA_NUM_PARALLEL": ["1", "2", "3", "4"],
                "OLLAMA_KEEP_ALIVE": ["5m", "15m", "30m", "1h", "-1", "0"]}[key]

    def change(self, delta):
        kind, key = self.rows()[self.row]
        if kind == "model" and self.models:
            i = (self.models.index(self.model) + delta) % len(self.models)
            self.model = self.models[i]
            self.load_model()
        elif kind == "param":
            opts = next(f[2] for f in self.fields if f[0] == key)
            self.values[key] = opts[(opts.index(self.values[key]) + delta) % len(opts)]
        elif kind == "server":
            if key == "OLLAMA_KV_CACHE_TYPE" and self.server["OLLAMA_FLASH_ATTENTION"] != "1":
                self.message = "KV cache quantization needs Flash Attention — enable it first."
                return
            opts = self.server_options(key)
            cur = self.server.get(key, opts[0])
            self.server[key] = opts[(opts.index(cur) + delta) % len(opts)] if cur in opts else opts[0]
            if key == "OLLAMA_FLASH_ATTENTION" and self.server[key] == "0":
                self.server["OLLAMA_KV_CACHE_TYPE"] = "f16"

    def new_params(self):
        """Only what differs from the base model: the variant inherits the rest via FROM."""
        return {k: v for k, v in self.values.items() if v != AUTO and str(v) != self.base_params.get(k)}

    def model_changed(self):
        effective = {**self.base_params, **{k: str(v) for k, v in self.new_params().items()}}
        return effective != self.params_now

    def server_changed(self):
        return self.server != self.server_now

    def fit(self):
        ctx = self.values["num_ctx"] if self.values["num_ctx"] != AUTO else None
        return ollama_mem.fit(self.model, ctx, self.server["OLLAMA_KV_CACHE_TYPE"])


# ---------------------------------------------------------------- side effects

def create_variant(base, params, replaces_base=False, sync=True):
    name = variant_name(base, params)
    os.makedirs(MODELFILE_DIR, exist_ok=True)
    path = os.path.join(MODELFILE_DIR, f"{name}.Modelfile")
    with open(path, "w", encoding="utf-8") as f:
        f.write(modelfile(base, params))
    r = subprocess.run(["ollama", "create", name, "-f", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1])
    variants = load_json(VARIANTS_PATH)
    variants[name] = {"base": base, "params": params, "label": variant_label(params)}
    if replaces_base:
        variants[name]["replaces_base"] = True  # sync-models lists this row instead of the base
    save_json(VARIANTS_PATH, variants)
    if sync:
        resync()
    return name


# Claude Code's opening prompt (system + tools + CLAUDE.md files) is ~26–46k tokens; a model with
# num_ctx 32768 rejects the first message with HTTP 400 "exceeds the available context size".
MIN_CTX = 65536


def fix_ctx():
    """Give every model whose context is too small for Claude Code a -ctx128k variant (-ctx64k if
    128k would not fit in 60% of RAM), and let it replace the base row in /model."""
    budget = 0.6 * int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
    variants = load_json(VARIANTS_PATH)
    done = []
    for name in sorted(ollama_mem.tags()):
        if name in variants:
            continue
        meta = ollama_mem.show(name)
        if int(meta["params"].get("num_ctx", 0) or 0) >= MIN_CTX:
            continue
        if any(v["base"] == name and v.get("replaces_base") for v in variants.values()):
            continue
        for ctx in (131072, 65536):
            weights, kv, ctx = ollama_mem.estimate(name, ctx, "f16")
            if (weights + kv) * 1.05 <= budget:
                break
        new = create_variant(name, {"num_ctx": ctx}, replaces_base=True, sync=False)
        done.append(f"{name} → {new}")
        print(f"✓ {name} → {new}")
    resync()
    print(f"Created {len(done)} variant(s)." if done else "Every model already has enough context.")


def resync():
    """Rebuild /model rows, keeping the user's saved default model."""
    saved = load_json(os.path.join(PROFILE, "settings.json")).get("model", "")
    subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "sync-models.py"), saved,
                    os.path.join(PROFILE, "settings.json")], capture_output=True)


def ollama_up(timeout):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(f"{ollama_mem.OLLAMA_HOST}/api/version", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def apply_server_env(env):
    """Persist desired env, push it to launchd, restart the Ollama app, then the bridge."""
    save_json(SERVER_ENV_PATH, env)
    for key, value in env.items():
        if value == SERVER_DEFAULTS[key]:
            subprocess.run(["launchctl", "unsetenv", key])
        else:
            subprocess.run(["launchctl", "setenv", key, value])
    # The Ollama menu-bar app builds serve's environment at launch, so the app itself restarts.
    quit_ok = subprocess.run(["osascript", "-e", 'quit app "Ollama"'], capture_output=True).returncode == 0
    if not quit_ok:
        subprocess.run(["pkill", "-x", "Ollama"])
    for _ in range(40):  # wait for the old server to exit before relaunching
        if not ollama_mem._pids("Ollama.app/Contents/Resources/ollama serve"):
            break
        time.sleep(0.25)
    subprocess.run(["open", "-a", "Ollama"])
    if not ollama_up(30):
        raise RuntimeError("Ollama did not come up within 30 s")
    subprocess.run([os.path.join(PROJECT_ROOT, "bin", "claude-ollama-bridge"), "restart"], capture_output=True)
    applied = {k: v for k, v in ollama_mem.serve_env().items() if k in SERVER_DEFAULTS}
    missing = [k for k, v in env.items() if v != SERVER_DEFAULTS[k] and applied.get(k) != v]
    if missing:
        raise RuntimeError(f"Ollama restarted but these settings did not reach the server: {', '.join(missing)}")


# ---------------------------------------------------------------- curses UI

def show_value(key, value):
    if value == AUTO:
        return "auto (model default)"
    if key == "num_ctx":
        return f"{value} ({fmt_ctx(value)})"
    if key == "OLLAMA_FLASH_ATTENTION":
        return "on" if value == "1" else "off"
    if key == "OLLAMA_KEEP_ALIVE":
        return {"-1": "forever", "0": "evict now"}.get(value, value)
    return str(value)


def confirm(stdscr, question):
    h, _ = stdscr.getmaxyx()
    stdscr.addstr(h - 2, 2, f"{question} (e/h) ", curses.A_BOLD)
    stdscr.clrtoeol()
    while True:
        ch = stdscr.getch()
        if ch in (ord("e"), ord("E"), ord("y"), ord("Y")):
            return True
        if ch in (ord("h"), ord("H"), ord("n"), ord("N"), 27):
            return False


def draw(stdscr, p):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    put = lambda y, x, text, attr=0: y < h - 1 and stdscr.addnstr(y, x, text, max(0, w - x - 1), attr)
    put(0, 2, "ccl tune — local model settings", curses.A_BOLD)
    put(1, 2, "↑/↓ move · ←/→ change · Enter select · q quit", curses.A_DIM)
    y = 3
    labels = dict((f[0], f[1]) for f in p.fields)
    server_labels = {"OLLAMA_FLASH_ATTENTION": "Flash Attention", "OLLAMA_KV_CACHE_TYPE": "K/V Cache Type",
                     "OLLAMA_NUM_PARALLEL": "Max Parallel Requests", "OLLAMA_KEEP_ALIVE": "Keep In Memory"}
    for i, (kind, key) in enumerate(p.rows()):
        sel = curses.A_REVERSE if i == p.row else 0
        if kind == "model":
            note = f"  (varyant · {p.base})" if p.base != p.model else ""
            put(y, 2, "MODEL — saving creates a variant model, shown as its own /model row", curses.A_BOLD)
            y += 1
            put(y, 4, f"{'Model':22}", 0)
            put(y, 27, f"◀ {p.model} ▶", sel)
            put(y, 29 + len(p.model) + 3, note, curses.A_DIM)
        elif kind == "param":
            extra = f"   (model en fazla {p.max_ctx})" if key == "num_ctx" else ""
            put(y, 4, f"{labels[key]:22}")
            put(y, 27, show_value(key, p.values[key]), sel)
            put(y, 27 + len(show_value(key, p.values[key])) + 1, extra, curses.A_DIM)
        elif kind == "server":
            if key == "OLLAMA_FLASH_ATTENTION":
                y += 1
                put(y, 2, "SERVER — affects every Ollama client; applying restarts Ollama",
                    curses.A_BOLD)
                y += 1
            put(y, 4, f"{server_labels[key]:22}")
            locked = key == "OLLAMA_KV_CACHE_TYPE" and p.server["OLLAMA_FLASH_ATTENTION"] != "1"
            put(y, 27, show_value(key, p.server[key]) + ("  (needs Flash Attention)" if locked else ""), sel)
        elif kind == "button":
            if key == "apply":
                y += 1
                try:
                    f = p.fit()
                    lms = f" · LM Studio {f['lmstudio_gb']} GB" if f["lmstudio_gb"] else ""
                    verdict = "✓ fits" if f["ok"] else "⚠ may not fit"
                    put(y, 2, f"Memory: weights {f['weights_gb']} GB + KV {f['kv_gb']} GB (ctx {f['ctx']}) "
                              f"≈ {f['need_gb']} GB · ~{f['avail_gb']} GB free{lms} · {verdict}",
                        0 if f["ok"] else curses.A_BOLD)
                except Exception as e:
                    put(y, 2, f"Memory estimate failed: {e}", curses.A_DIM)
                y += 2
                pending = []
                if p.model_changed():
                    pending.append(f"varyant {variant_name(p.base, p.new_params())}")
                if p.server_changed():
                    pending.append("server settings")
                put(y, 2, "[ Uygula ]", sel)
                put(y, 14, ("→ " + ", ".join(pending)) if pending else "(no changes)", curses.A_DIM)
            else:
                put(y, 2, "[ Quit ]", sel)
        y += 1
    if p.message:
        put(h - 3, 2, p.message, curses.A_BOLD)
    stdscr.refresh()


def apply(stdscr, p):
    if not (p.model_changed() or p.server_changed()):
        p.message = "No changes."
        return
    if p.model_changed():
        params = p.new_params()
        name = variant_name(p.base, params)
        if name == p.base:
            p.message = f"Settings match the base model — pick '{p.base}' in /model; no variant needed."
        elif confirm(stdscr, f"Create variant '{name}'?"):
            p.message = f"Creating: {name} …"
            draw(stdscr, p)
            try:
                create_variant(p.base, params)
                p.variants = load_json(VARIANTS_PATH)
                p.models = sorted(ollama_mem.tags())
                p.model = name
                p.load_model()
                p.message = f"✓ {name} ready — in the /model list (visible after restarting ccl)."
            except Exception as e:
                p.message = f"✗ ollama create failed: {e}"
    if p.server_changed():
        diff = ", ".join(f"{k.replace('OLLAMA_', '')}={show_value(k, v)}"
                         for k, v in p.server.items() if v != p.server_now[k])
        if confirm(stdscr, f"{diff} — Ollama will restart (loaded models evict). Continue?"):
            p.message = "Restarting Ollama …"
            draw(stdscr, p)
            try:
                apply_server_env(p.server)
                p.server_now = dict(p.server)
                p.message = "✓ Server settings applied; Ollama and the bridge restarted."
            except Exception as e:
                p.message = f"✗ {e}"


def run(stdscr, model):
    curses.curs_set(0)
    stdscr.keypad(True)
    p = Panel(model)
    while True:
        draw(stdscr, p)
        ch = stdscr.getch()
        p.message = ""
        n = len(p.rows())
        if ch in (ord("q"), 27):
            return
        if ch == curses.KEY_UP:
            p.row = (p.row - 1) % n
        elif ch == curses.KEY_DOWN:
            p.row = (p.row + 1) % n
        elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT):
            p.change(-1 if ch == curses.KEY_LEFT else 1)
        elif ch in (10, 13, curses.KEY_ENTER):
            kind, key = p.rows()[p.row]
            if kind == "button" and key == "quit":
                return
            if kind == "button" and key == "apply":
                apply(stdscr, p)


def self_test():
    p = {"num_ctx": 65536, "num_thread": 8}
    assert variant_name("isvalorum-35b", p) == "isvalorum-35b-ctx64k-t8"
    assert variant_name("isvalorum-35b", {}) == "isvalorum-35b"
    assert modelfile("isvalorum-35b", p) == "FROM isvalorum-35b\nPARAMETER num_ctx 65536\nPARAMETER num_thread 8\n"
    assert variant_label(p) == "ctx 64k · 8 thread"
    print("✓ tune self-test passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
        sys.exit(0)
    if "--fix-ctx" in sys.argv:
        fix_ctx()
        sys.exit(0)
    if not sys.stdin.isatty():
        sys.exit("ccl --tune needs an interactive terminal.")
    curses.wrapper(run, sys.argv[1] if len(sys.argv) > 1 else "")
