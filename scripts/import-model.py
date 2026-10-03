#!/usr/bin/env python3
"""
import-model.py — bring a model from LM Studio, Hugging Face, or a loose GGUF into ccl.

ccl runs everything through Ollama, so "adding a model" always means "register it with Ollama";
then sync-models / --fix-ctx pick it up in the /model picker and opencode automatically.

    # a GGUF on disk (LM Studio download, HF download, anywhere)
    import-model.py ~/.lmstudio/models/pub/Repo-GGUF/model-Q4_K_M.gguf
    import-model.py model.gguf --name my-coder --ctx 131072

    # straight from Hugging Face (Ollama downloads it)
    import-model.py hf.co/TheUser/TheRepo-GGUF:Q4_K_M

    # list GGUFs LM Studio has already downloaded, so you can import one
    import-model.py --list-lmstudio

A loose GGUF carries no chat template unless it is embedded; most modern GGUFs embed one. If a
model answers oddly (no stop tokens, wrong roles), re-import with --template-from <an-ollama-model>
of the same family to copy its TEMPLATE and PARAMETERs.

After import this runs sync-models.py (and sync-opencode.py if present) and tells you whether the
model needs `ccl --fix-ctx` (context below Claude Code's ~46k-token opening prompt).
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import ollama_mem  # noqa: E402

LMSTUDIO_MODELS = os.path.expanduser("~/.lmstudio/models")
MIN_CTX = 65536  # below this, Claude Code's opening prompt overflows → needs a -ctx variant


def sanitize(name):
    """A filename/repo into a clean Ollama model name: lowercase, no spaces, no quant/gguf noise."""
    name = re.sub(r"\.gguf$", "", name, flags=re.I)
    name = re.sub(r"[-_.](GGUF|Q\d[_A-Z0-9]*|IQ\d[_A-Z0-9]*|UD|imatrix|fromq8|no-?mtp|plus-?mtp)", "",
                  name, flags=re.I)
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return re.sub(r"-{2,}", "-", name) or "imported-model"


def name_from_gguf(path):
    """Prefer the LM Studio repo folder (…/<publisher>/<Repo-GGUF>/file.gguf) over the file name."""
    parent = os.path.basename(os.path.dirname(path))
    base = parent if parent and parent.lower() not in ("models", "gguf") else os.path.basename(path)
    return sanitize(base)


def run(cmd, dry):
    print(("DRY  " if dry else "RUN  ") + " ".join(cmd))
    if dry:
        return 0
    return subprocess.run(cmd).returncode


def list_lmstudio():
    if not os.path.isdir(LMSTUDIO_MODELS):
        print(f"No LM Studio models dir at {LMSTUDIO_MODELS}")
        return
    rows = []
    for root, _, files in os.walk(LMSTUDIO_MODELS):
        for f in files:
            if f.endswith(".gguf"):
                p = os.path.join(root, f)
                rows.append((os.path.getsize(p), name_from_gguf(p), p))
    for size, name, p in sorted(rows):
        print(f"{size / 1024**3:5.1f} GB  {name:40}  {p}")
    print(f"\n{len(rows)} GGUF(s). Import one with:\n  import-model.py <path> [--name NAME] [--ctx N]")


def resync(dry):
    if run([sys.executable, os.path.join(SCRIPT_DIR, "sync-models.py")], dry) == 0 and not dry:
        print("✓ /model picker synced")
    oc = os.path.join(SCRIPT_DIR, "sync-opencode.py")
    if os.path.exists(oc) and os.path.exists(os.path.expanduser("~/.config/opencode/opencode.json")):
        run([sys.executable, oc], dry)


def import_gguf(path, name, ctx, template_from, dry):
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(path):
        sys.exit(f"GGUF not found: {path}")
    name = name or name_from_gguf(path)
    lines = [f"FROM {path}"]
    if template_from:
        mf = subprocess.run(["ollama", "show", "--modelfile", template_from],
                            capture_output=True, text=True).stdout
        for ln in mf.splitlines():
            if ln.startswith(("TEMPLATE", "PARAMETER", "SYSTEM")) or ln.startswith('"""'):
                lines.append(ln)
    if ctx:
        lines.append(f"PARAMETER num_ctx {ctx}")
    modelfile = "\n".join(lines) + "\n"
    print(f"→ importing '{name}' from {path}")
    print("--- Modelfile ---\n" + modelfile + "-----------------")
    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False) as f:
        f.write(modelfile)
        mf_path = f.name
    try:
        if run(["ollama", "create", name, "-f", mf_path], dry) != 0:
            sys.exit("ollama create failed")
    finally:
        os.unlink(mf_path)
    return name


def import_hf(ref, name, ctx, dry):
    ref = ref.replace("hf:", "hf.co/", 1) if ref.startswith("hf:") else ref
    if run(["ollama", "pull", ref], dry) != 0:
        sys.exit("ollama pull failed")
    pulled = ref.split("/")[-1].split(":")[0]
    if name and name != pulled and not dry:
        run(["ollama", "cp", pulled, name], dry)
        return name
    return pulled


def report_ctx(name, dry):
    if dry:
        return
    try:
        ollama_mem._SHOW_CACHE.pop(ollama_mem.base(name), None)
        params = ollama_mem.show(name)["params"]
        n = int(params.get("num_ctx", 0) or 0)
    except Exception:
        return
    if n and n < MIN_CTX:
        print(f"\n⚠ {name} context is {n}; Claude Code's opening prompt (~46k) will 400. "
              f"Run:  ccl --fix-ctx   (creates {name}-ctx128k)")
    else:
        print(f"\n✓ {name} ready. Pick it with /model in ccl, or `ccl -m {name}`.")


def main():
    ap = argparse.ArgumentParser(description="Import a model into ccl (via Ollama).")
    ap.add_argument("source", nargs="?", help="a .gguf path, hf.co/<repo>:<quant>, or an ollama name")
    ap.add_argument("--name", help="Ollama model name (default: derived from the source)")
    ap.add_argument("--ctx", type=int, help="num_ctx to bake in (e.g. 131072)")
    ap.add_argument("--template-from", help="copy TEMPLATE/PARAMETERs from this existing ollama model")
    ap.add_argument("--list-lmstudio", action="store_true", help="list GGUFs LM Studio has downloaded")
    ap.add_argument("--dry-run", action="store_true", help="print what would run, change nothing")
    a = ap.parse_args()

    if a.list_lmstudio:
        list_lmstudio()
        return
    if not a.source:
        ap.error("give a source (.gguf path, hf.co/<repo>:<quant>, ollama name) or --list-lmstudio")

    if a.source.endswith(".gguf") or os.path.isfile(os.path.expanduser(a.source)):
        name = import_gguf(a.source, a.name, a.ctx, a.template_from, a.dry_run)
    elif a.source.startswith(("hf.co/", "hf:")):
        name = import_hf(a.source, a.name, a.ctx, a.dry_run)
    elif ollama_mem.base(a.source) in ollama_mem.tags():
        name = ollama_mem.base(a.source)  # already in Ollama; just re-sync
        print(f"'{name}' is already in Ollama; syncing.")
    else:
        sys.exit(f"Unrecognized source: {a.source} (not a .gguf, hf ref, or known ollama model)")

    resync(a.dry_run)
    report_ctx(name, a.dry_run)


if __name__ == "__main__":
    main()
