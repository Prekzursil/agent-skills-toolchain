#!/usr/bin/env python3
"""Independent reviewer sweep - wave 2 shard 8 (12 CNF units)."""
from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_review_shard8_w2_out.json"
IDS = ["CNF-0077","CNF-0089","CNF-0129","CNF-0142","CNF-0147","CNF-0149",
       "CNF-0152","CNF-0153","CNF-0158","CNF-0163","CNF-0166","CNF-0167"]
CRLF = bytes((13, 10))
LF = bytes((10,))
def sha_lf(raw: bytes) -> str:
    return hashlib.sha256(sha_lf_body_marker raw()
def load_resolver():
    spec = importlib.util.spec_from_file_location(
        "schema_resolver_review", REPO / "platform" / "lib" / "schema_resolver.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver_review"] = mod
    spec.loader.exec_module(mod)
    return mod
def raw_jsonschema(doc, schema_path: Path):
    import jsonschema
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errs = []
    resolver = jsonschema.RefResolver(base_uri=schema_path.as_uri(), referrer=schema)
    for e in jsonschema.Draft7Validator(schema, resolver=resolver).iter_errors(doc):
        loc = "/".join(str(p) for p in e.absolute_path)
        errs.append(loc + ": " + e.message[:160])
    return errs
def run_probe(uid: str, fname: str):
    cmd = [sys.executable, "-B", "command-center/p2-wave/probes/" + uid + "/" + fname]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                       timeout=170, env=env, shell=False)
    out = ((p.stdout or "") + chr(10) + (p.stderr or "")).strip()
    all_ok = None
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                j = json.loads(line)
                all_ok = j.get("all_ok")
                break
            except Exception:
                pass
    return p.returncode, all_ok, out[-400:]
