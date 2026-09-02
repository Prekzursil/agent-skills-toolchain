"""Ground-truth measurement for the cross-vendor architecture tournament entry.

Counts what is ACTUALLY on disk, and measures the vendor-identity surface the
cross-vendor-adapter architecture claims to be about. No LLM judgement: every number
here comes from a file walk or a JSON key count.

Run:  python platform/architecture/_probe_crossvendor_groundtruth.py
"""
from __future__ import annotations

import collections
import json
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def r(*p):
    return os.path.join(REPO, *p)


out = {}


def sh(cmd):
    try:
        return subprocess.run(
            cmd, cwd=REPO, shell=True, capture_output=True, text=True, timeout=120
        ).stdout.strip()
    except Exception as e:  # pragma: no cover
        return f"ERR:{e}"


# ---------------------------------------------------------------- provenance
out["head_sha"] = sh("git rev-parse HEAD")
out["briefed_sha"] = "dc90d64a"
out["head_is_briefed"] = out["head_sha"].startswith("dc90d64a")
out["commits_since_briefed"] = sh("git rev-list --count dc90d64a..HEAD")
out["briefed_is_ancestor"] = (
    subprocess.run(
        "git merge-base --is-ancestor dc90d64a HEAD",
        cwd=REPO, shell=True, capture_output=True,
    ).returncode
    == 0
)

# ---------------------------------------------------------------- Wave 1 counts
def count(pat_dir, suffix):
    d = r(*pat_dir)
    if not os.path.isdir(d):
        return None
    n = 0
    for root, _dirs, files in os.walk(d):
        for f in files:
            if f.endswith(suffix):
                n += 1
    return n


out["schemas_platform"] = count(("platform", "schema"), ".schema.json")
out["councilspecs_total"] = count(("platform", "council"), ".councilspec.json")
out["lib_py_files"] = count(("platform", "lib"), ".py")
out["lib_packages"] = sorted(
    d for d in os.listdir(r("platform", "lib"))
    if os.path.isdir(r("platform", "lib", d)) and not d.startswith("_")
) if os.path.isdir(r("platform", "lib")) else None
out["cc_schema_shims"] = count(("command-center", "schema"), ".json")

# protocols vs presets: split by directory
cs_by_dir = collections.Counter()
for root, _dirs, files in os.walk(r("platform", "council")):
    rel = os.path.relpath(root, r("platform", "council")).replace("\\", "/")
    for f in files:
        if f.endswith(".councilspec.json"):
            cs_by_dir[rel] += 1
out["councilspec_by_dir"] = dict(cs_by_dir)

# ---------------------------------------------------------------- the catalog
cat_path = r("command-center", "WORK-UNIT-CATALOG.json")
cat = json.load(open(cat_path, encoding="utf-8"))
wus = cat.get("work_units", [])
out["work_units"] = len(wus)
out["catalog_top_keys"] = sorted(cat.keys())
out["register_items"] = len(cat.get("items", []))

# ---------------------------------------------------------------- VENDOR SURFACE
# This is the load-bearing measurement for THIS architecture: does vendor identity
# already exist as a first-class field, and in what shapes?
vendor_field_names = collections.Counter()
for wu in wus:
    for k in wu:
        if "vendor" in k.lower() or "model" in k.lower() or "agent" in k.lower():
            vendor_field_names[k] += 1
out["wu_vendorish_fields"] = dict(vendor_field_names)

# assigned_model_vendor_role: exact value distribution
amvr = collections.Counter()
amvr_type = collections.Counter()
for wu in wus:
    v = wu.get("assigned_model_vendor_role")
    amvr_type[type(v).__name__] += 1
    if isinstance(v, str):
        amvr[v] += 1
    elif isinstance(v, dict):
        amvr["<dict:" + ",".join(sorted(v.keys())) + ">"] += 1
    elif isinstance(v, list):
        amvr["<list len %d>" % len(v)] += 1
out["amvr_type_distribution"] = dict(amvr_type)
out["amvr_distinct_values"] = len(amvr)
out["amvr_top25"] = amvr.most_common(25)

# Which vendor tokens actually appear anywhere in an amvr value?
VENDOR_TOKENS = [
    "claude", "anthropic", "opus", "sonnet", "haiku",
    "codex", "openai", "gpt", "o3", "o4",
    "gemini", "google",
    "grok", "xai",
    "llama", "mistral", "deepseek", "qwen",
    "local", "human", "owner", "deterministic", "script", "tool",
]
tok_hits = collections.Counter()
for v, n in amvr.items():
    low = v.lower()
    for t in VENDOR_TOKENS:
        if t in low:
            tok_hits[t] += n
out["vendor_token_hits_in_amvr"] = dict(tok_hits.most_common())

# canonical shape check: how many are "vendor/model:role" style vs freeform
CANON = re.compile(r"^[a-z0-9.\-]+/[a-z0-9.\-]+:[a-z0-9_\-]+$")
canon = sum(n for v, n in amvr.items() if CANON.match(v))
out["amvr_canonical_matches_slashcolon"] = canon
out["amvr_noncanonical"] = len(wus) - canon

# ---------------------------------------------------------------- councilspec vendor surface
cs_vendor_keys = collections.Counter()
cs_role_vendors = collections.Counter()
cs_files = 0
for root, _dirs, files in os.walk(r("platform", "council")):
    for f in files:
        if not f.endswith(".councilspec.json"):
            continue
        cs_files += 1
        try:
            d = json.load(open(os.path.join(root, f), encoding="utf-8"))
        except Exception:
            continue

        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    lk = k.lower()
                    if "vendor" in lk or "model" in lk:
                        cs_vendor_keys[k] += 1
                        if isinstance(v, str):
                            cs_role_vendors[v] += 1
                        elif isinstance(v, list):
                            for x in v:
                                if isinstance(x, str):
                                    cs_role_vendors[x] += 1
                    walk(v, path + "/" + k)
            elif isinstance(o, list):
                for x in o:
                    walk(x, path)

        walk(d)
out["councilspec_files_scanned"] = cs_files
out["councilspec_vendor_keys"] = dict(cs_vendor_keys.most_common())
out["councilspec_vendor_values"] = dict(cs_role_vendors.most_common(30))

# ---------------------------------------------------------------- adapter surface today
# Is there ANY vendor-dispatch code on disk? Grep the lib tree for vendor tokens.
adapter_hits = collections.Counter()
py_files = []
for root, _dirs, files in os.walk(r("platform", "lib")):
    for f in files:
        if f.endswith(".py"):
            py_files.append(os.path.join(root, f))
for p in py_files:
    try:
        txt = open(p, encoding="utf-8", errors="replace").read().lower()
    except Exception:
        continue
    for t in ["codex", "anthropic", "openai", "subprocess", "mcp__", "http", "requests"]:
        if t in txt:
            adapter_hits[t] += 1
out["lib_py_file_count"] = len(py_files)
out["lib_files_mentioning"] = dict(adapter_hits.most_common())

# ---------------------------------------------------------------- registry
reg_dir = r("platform", "registry")
out["registry_files"] = sorted(os.listdir(reg_dir)) if os.path.isdir(reg_dir) else None
cand = None
for f in (out["registry_files"] or []):
    if f.endswith(".json"):
        try:
            d = json.load(open(r("platform", "registry", f), encoding="utf-8"))
        except Exception:
            continue
        for key in ("candidates", "items", "workflows", "entries"):
            if isinstance(d, dict) and isinstance(d.get(key), list):
                cand = (f, key, len(d[key]))
                break
        if isinstance(d, list):
            cand = (f, "<toplevel list>", len(d))
out["registry_candidate_count"] = cand

# ---------------------------------------------------------------- test count
out["pytest_collect"] = sh("python -m pytest platform/lib -q --collect-only 2>&1 | tail -3")

print(json.dumps(out, indent=2, default=str))
sys.stdout.write("\nSUCCESS:crossvendor-groundtruth\n")
