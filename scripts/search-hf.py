#!/usr/bin/env python3
"""
search-hf.py — find GGUF models on Hugging Face by keyword, then import one.

No exact repo name needed: search by what you want, pick from the ranked list, pick a quant,
and the printed `import-model.py` command pulls it into Ollama so ccl's /model picker sees it.

    search-hf.py qwen coder               # top GGUF repos for "qwen coder" (by downloads)
    search-hf.py --repo bartowski/Qwen2.5-Coder-7B-Instruct-GGUF   # quants in that repo + import cmds
    search-hf.py qwen coder --json        # machine-readable (used by the /find-model slash command)

Public Hugging Face API, no token required.
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

API = "https://huggingface.co/api"
GB = 1024 ** 3
# Preference order when recommending a quant: good quality/size trade-offs first.
QUANT_PREF = ["Q4_K_M", "IQ4_XS", "Q4_K_S", "Q5_K_M", "Q4_0", "Q6_K", "Q8_0", "Q3_K_M", "IQ3_M"]


def get(path):
    req = urllib.request.Request(f"{API}/{path}", headers={"User-Agent": "ccl-search-hf"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def search(query, limit):
    q = urllib.parse.urlencode({"search": query, "filter": "gguf",
                                "sort": "downloads", "direction": -1, "limit": limit})
    out = []
    for m in get(f"models?{q}"):
        out.append({"id": m["id"], "downloads": m.get("downloads", 0), "likes": m.get("likes", 0)})
    return out


QUANT_RE = re.compile(r"(IQ\d+(?:_[A-Z0-9]+)*|Q\d+(?:_[A-Z0-9]+)*|BF16|FP16|F16|F32)", re.I)

def quants(repo):
    """GGUF files in a repo: {quant, file, size_gb}. Multi-part (…-00001-of-0000N) summed into one."""
    d = get(f"models/{repo}?blobs=true")
    agg = {}
    for s in d.get("siblings", []):
        f = s.get("rfilename", "")
        if not f.lower().endswith(".gguf"):
            continue
        tag = re.sub(r"-\d+-of-\d+", "", f[:-5])  # drop shard suffix before matching the quant
        m = QUANT_RE.findall(tag)
        if not m:
            continue
        quant = m[-1].upper()
        sz = s.get("size", 0)
        e = agg.setdefault(quant, {"quant": quant, "file": f, "size": 0, "shard_sum": 0, "sharded": False})
        if "-of-" in f:          # sum the parts of a sharded quant
            e["shard_sum"] += sz
            e["sharded"] = True
        else:                     # single-file quant: largest wins (avoids double-count)
            e["size"] = max(e["size"], sz)
        e["file"] = f
    out = [{"quant": e["quant"], "file": e["file"],
            "size_gb": round(max(e["size"], e["shard_sum"]) / GB, 1),
            "sharded": e["sharded"]} for e in agg.values()]
    out.sort(key=lambda x: (QUANT_PREF.index(x["quant"]) if x["quant"] in QUANT_PREF else 99, x["size_gb"]))
    return out


def recommend(qs):
    for pref in QUANT_PREF:
        for q in qs:
            if q["quant"] == pref:
                return q["quant"]
    return qs[0]["quant"] if qs else None


def main():
    ap = argparse.ArgumentParser(description="Search Hugging Face for GGUF models.")
    ap.add_argument("query", nargs="*", help="keywords (e.g. qwen coder)")
    ap.add_argument("--repo", help="list the GGUF quants in this repo id")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.repo:
        qs = quants(a.repo)
        rec = recommend(qs)
        if a.json:
            print(json.dumps({"repo": a.repo, "recommended": rec, "quants": qs}))
            return
        print(f"GGUF quants in {a.repo}  (↓ = recommended)\n")
        for q in qs:
            star = " ←" if q["quant"] == rec else ""
            shard = " (multi-part)" if q["sharded"] else ""
            print(f"  {q['quant']:10} {q['size_gb']:>5} GB{shard}{star}")
        print(f"\nImport the recommended one:\n"
              f"  python3 scripts/import-model.py hf.co/{a.repo}:{rec}")
        return

    if not a.query:
        ap.error("give keywords, e.g. `search-hf.py qwen coder`, or --repo <id>")
    results = search(" ".join(a.query), a.limit)
    if a.json:
        print(json.dumps(results))
        return
    if not results:
        print("No GGUF models found. Try different keywords.")
        return
    print(f"Top GGUF models for '{' '.join(a.query)}':\n")
    for i, m in enumerate(results, 1):
        print(f"  {i}. {m['id']}\n     {m['downloads']:,} downloads · {m['likes']} likes")
    print(f"\nSee a model's quants:\n  python3 scripts/search-hf.py --repo {results[0]['id']}")


if __name__ == "__main__":
    main()
