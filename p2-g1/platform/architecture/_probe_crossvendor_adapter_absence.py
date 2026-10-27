"""Is there ANY executable vendor dispatch on disk, or is vendor identity purely declarative?

The load-bearing premise of the cross-vendor-adapter architecture is that Wave 1 declares
vendor identity everywhere and can EXECUTE none of it. A grep for the string "codex" cannot
settle that (use-vs-mention). This probe uses the Python AST, so a vendor name inside a string
literal is structurally distinguishable from an `import` or a call.

DETECTOR CONTROL (both-states, per the honesty contract):
  known-PRESENT : `import json` / `subprocess.run` must be FOUND in the same tree.
  known-BROKEN  : a synthetic file containing a real `import anthropic` + `client.messages.create`
                  must be FLAGGED, proving the detector fires when dispatch IS present.
A probe silent in both states measures nothing.

Run:  python platform/architecture/_probe_crossvendor_adapter_absence.py
"""
from __future__ import annotations

import ast
import collections
import json
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIB = os.path.join(REPO, "platform", "lib")

VENDOR_SDK_MODULES = {
    "anthropic", "openai", "google", "google.generativeai", "genai",
    "mistralai", "cohere", "ollama", "litellm", "groq", "xai_sdk",
    "vertexai", "boto3",  # bedrock route
}
VENDOR_CLI_TOKENS = {"codex", "claude", "gemini", "llm", "ollama", "aider"}


def classify(path):
    """Return dict of evidence kinds found in ONE file, via AST (not text)."""
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except Exception as e:
        return {"parse_error": str(e)}

    ev = collections.Counter()
    vendor_imports = []
    subprocess_vendor_spawns = []
    http_vendor_calls = []
    vendor_string_literals = 0

    for node in ast.walk(tree):
        # ---- real imports
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                ev["import:" + root] += 1
                if root in VENDOR_SDK_MODULES or a.name in VENDOR_SDK_MODULES:
                    vendor_imports.append((node.lineno, a.name))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            ev["importfrom:" + root] += 1
            if root in VENDOR_SDK_MODULES or (node.module or "") in VENDOR_SDK_MODULES:
                vendor_imports.append((node.lineno, node.module))

        # ---- calls
        elif isinstance(node, ast.Call):
            fn = node.func
            name = ""
            if isinstance(fn, ast.Attribute):
                name = fn.attr
                if isinstance(fn.value, ast.Name):
                    name = fn.value.id + "." + fn.attr
            elif isinstance(fn, ast.Name):
                name = fn.id
            if name:
                ev["call:" + name] += 1
            # subprocess spawning a vendor CLI: first arg literal/list mentions a vendor cli
            if name in ("subprocess.run", "subprocess.Popen", "subprocess.check_output",
                        "os.system", "run", "Popen"):
                for arg in node.args[:1]:
                    lits = []
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        lits = [arg.value]
                    elif isinstance(arg, (ast.List, ast.Tuple)):
                        lits = [e.value for e in arg.elts
                                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                    for lit in lits:
                        first = lit.strip().split()[0].lower() if lit.strip() else ""
                        base = os.path.basename(first).replace(".exe", "").replace(".cmd", "")
                        if base in VENDOR_CLI_TOKENS:
                            subprocess_vendor_spawns.append((node.lineno, lit[:80]))
            # http POST to a vendor endpoint
            if name.endswith(("post", "request", "urlopen")):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        u = arg.value.lower()
                        if any(v in u for v in ("anthropic.com", "openai.com",
                                                "googleapis.com", "x.ai", "mistral.ai")):
                            http_vendor_calls.append((node.lineno, arg.value[:80]))

        # ---- vendor names that are merely DATA
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            low = node.value.lower()
            if low in ("anthropic", "openai", "google", "xai", "mistral") or \
               low in ("opus", "opus-5", "gpt-5-codex", "gemini-3-pro", "grok-4"):
                vendor_string_literals += 1

    return {
        "vendor_imports": vendor_imports,
        "subprocess_vendor_spawns": subprocess_vendor_spawns,
        "http_vendor_calls": http_vendor_calls,
        "vendor_string_literals": vendor_string_literals,
        "has_import_json": ev.get("import:json", 0),
        "has_subprocess_call": sum(v for k, v in ev.items() if k.startswith("call:subprocess")),
    }


files = []
for root, _d, fs in os.walk(LIB):
    for f in fs:
        if f.endswith(".py"):
            files.append(os.path.join(root, f))

tot = collections.Counter()
per_file_hits = {}
for p in files:
    c = classify(p)
    if c.get("parse_error"):
        tot["parse_error"] += 1
        continue
    tot["files"] += 1
    tot["vendor_string_literals"] += c["vendor_string_literals"]
    tot["import_json_files"] += 1 if c["has_import_json"] else 0
    tot["subprocess_call_files"] += 1 if c["has_subprocess_call"] else 0
    if c["vendor_imports"] or c["subprocess_vendor_spawns"] or c["http_vendor_calls"]:
        per_file_hits[os.path.relpath(p, REPO).replace("\\", "/")] = {
            k: v for k, v in c.items()
            if k in ("vendor_imports", "subprocess_vendor_spawns", "http_vendor_calls") and v
        }
        tot["files_with_real_dispatch"] += 1

out = {
    "scope": "platform/lib/**/*.py (recursive)",
    "files_scanned": tot["files"],
    "parse_errors": tot["parse_error"],
    "vendor_name_STRING_LITERALS": tot["vendor_string_literals"],
    "files_with_REAL_vendor_dispatch": tot["files_with_real_dispatch"],
    "real_dispatch_detail": per_file_hits,
}

# ---------------- DETECTOR CONTROL 1: known-PRESENT
out["control_known_present"] = {
    "files_with_import_json": tot["import_json_files"],
    "files_with_subprocess_call": tot["subprocess_call_files"],
    "detector_sees_ordinary_imports": tot["import_json_files"] > 0,
}

# ---------------- DETECTOR CONTROL 2: known-BROKEN (synthetic dispatch must FIRE)
synth = '''
import anthropic
import subprocess
import requests
def go():
    c = anthropic.Anthropic()
    c.messages.create(model="opus")
    subprocess.run(["codex", "exec", "-"], check=True)
    requests.post("https://api.openai.com/v1/chat/completions", json={})
'''
with tempfile.TemporaryDirectory() as td:
    sp = os.path.join(td, "synthetic_dispatch.py")
    open(sp, "w", encoding="utf-8").write(synth)
    sc = classify(sp)
out["control_known_broken"] = {
    "synthetic_vendor_imports": sc["vendor_imports"],
    "synthetic_subprocess_vendor_spawns": sc["subprocess_vendor_spawns"],
    "synthetic_http_vendor_calls": sc["http_vendor_calls"],
    "detector_FIRES_on_real_dispatch": bool(
        sc["vendor_imports"] and sc["subprocess_vendor_spawns"] and sc["http_vendor_calls"]
    ),
}

ok_present = out["control_known_present"]["detector_sees_ordinary_imports"]
ok_broken = out["control_known_broken"]["detector_FIRES_on_real_dispatch"]
out["detector_validated_both_states"] = bool(ok_present and ok_broken)
out["VERDICT"] = (
    "vendor identity is DECLARATIVE-ONLY: zero executable vendor dispatch in platform/lib"
    if out["detector_validated_both_states"] and out["files_with_REAL_vendor_dispatch"] == 0
    else ("REAL DISPATCH FOUND - premise refuted"
          if out["files_with_REAL_vendor_dispatch"] else "DETECTOR INVALID - do not cite")
)

print(json.dumps(out, indent=2, default=str))
marker = "SUCCESS" if out["detector_validated_both_states"] else "FAILED"
sys.stdout.write("\n%s:crossvendor-adapter-absence\n" % marker)
