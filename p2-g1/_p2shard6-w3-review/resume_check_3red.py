#!/usr/bin/env python3
"""w3s6 resume: quick strict+outschema re-check of the 3 previously-FAIL units.

Read-only. Reuses the shard-6 verifier's own schema loaders for comparability.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json


def hashlib_norm(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()

spec = importlib.util.spec_from_file_location(
    "v", r"C:/Users/Prekzursil/p2-g1/_p2shard6-w3-review/verify_shard6_w3.py"
)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
REPO = v.REPO

core_v = v.load_core_validator()
reg = v.make_file_uri_registry()
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in cat["work_units"] if isinstance(u, dict)}

for uid in ("BLD-0037", "BLD-0042", "BLD-0049"):
    cu = byid[uid]
    out = REPO / str(cu["output_path"]).replace("\\", "/")
    receipt = json.loads(out.read_text(encoding="utf-8"))
    errs = sorted(core_v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
    print(f"{uid} strict-errors = {len(errs)}")
    for e in errs[:6]:
        print("   ", list(e.absolute_path) or "<root>", "->", e.message[:100])
    cv, err = v.load_class_validator(cu["output_schema"], reg)
    if err:
        print(f"{uid} outschema-loader-error: {err}")
    else:
        oerrs = sorted(cv.iter_errors(receipt), key=lambda e: list(e.absolute_path))
        print(f"{uid} outschema-errors = {len(oerrs)}")
        for e in oerrs[:6]:
            print("   ", list(e.absolute_path) or "<root>", "->", e.message[:100])
    # manifest digest recompute (CRLF-normalized sha + raw bytes convention)
    mdir = REPO / "command-center/p2-wave/probes" / uid
    man = json.loads((mdir / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    bad = []
    for row in man.get("artifacts", []):
        p = REPO / str(row.get("path", "")).replace("\\", "/")
        if not p.is_file():
            bad.append(f"{row.get('path')}:absent")
            continue
        raw = p.read_bytes()
        norm = hashlib_norm(raw)
        ok_sha = norm == row.get("sha256")
        ok_bytes = len(raw) == row.get("bytes")
        if not (ok_sha and ok_bytes):
            bad.append(f"{row.get('path')}:sha_ok={ok_sha},bytes_ok={ok_bytes}")
    print(f"{uid} manifest rows = {len(man.get('artifacts', []))}, mismatched = {len(bad)}")
    for b in bad:
        print("   ", b)

print("resume-check done")
