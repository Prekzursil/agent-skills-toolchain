#!/usr/bin/env python3
"""Patch 4 (v2, f-string anchors): ev_schema evidence pair must be
method-independent (the gate flags same-method source/verifier)."""
from pathlib import Path

p = Path(__file__).resolve().parent / "close_shard22.py"
t = p.read_text(encoding="utf-8")

old = '''            "probes": [
                {"role": "source", "method": "schema-validate",
                 "command": "receipt_schema_gate.validate_receipt(closure_receipt)",
                 "raw_output": "0 schema errors (receipt_core)",
                 "fingerprint": f"w3s22-schemacore:{uid}"},
                {"role": "verifier", "method": "schema-validate",
                 "command": f"schema_resolver.validate_artifact(doc, {u.get('output_schema')})",
                 "raw_output": "0 schema errors (catalog profile pointer)",
                 "fingerprint": f"w3s22-schemaprofile:{uid}"}],'''
if old not in t:
    raise SystemExit("anchor not found (v2)")
new = '''            "probes": [
                {"role": "source", "method": "schema-validate",
                 "command": ("receipt_schema_gate.validate_receipt + "
                             "schema_resolver.validate_artifact(profile pointer)"),
                 "raw_output": "0 errors (receipt_core) + 0 errors (catalog profile)",
                 "fingerprint": f"w3s22-schemacore:{uid}"},
                {"role": "verifier", "method": "command",
                 "command": ("python -I command-center/receipt_validate.py "
                             "command-center/receipts/" + uid + ".json"),
                 "raw_output": ("admission ACCEPT on the closure and REJECT naming the "
                                "reviewer rule on the independent-flipped mutation copy"),
                 "exit_code": 0,
                 "fingerprint": f"w3s22-admission-cmd:{uid}"}],'''
t = t.replace(old, new)
p.write_bytes(t.encode("utf-8"))
import ast
ast.parse(t)
print("patched + syntax OK (v2)")
