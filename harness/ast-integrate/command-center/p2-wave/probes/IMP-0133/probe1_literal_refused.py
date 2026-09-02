#!/usr/bin/env python3
"""Probe 1: credential-shaped literal fails export; secret_ref twin passes.

Signals: (1) named violation on the literal fixture; (2) independent grep of
the secret_ref export bytes returns zero hits for the fixture token.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

from agentspec.export import ExportRefused, export_workflow  # noqa: E402
from agentspec.spec import load_workflow  # noqa: E402
from agentspec.violations import PARAM_CREDENTIAL_LITERAL  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0133-probe1 {msg}")
    return 1


def main() -> int:
    literal = load_workflow(HERE / "fixtures" / "literal_param.json")
    secret_ref = load_workflow(HERE / "fixtures" / "secret_ref_param.json")
    if C.TOKEN not in (literal.params[0].default or ""):
        return fail("literal fixture does not carry the fixture token")
    if secret_ref.params[0].secret_ref is None:
        return fail("secret_ref fixture missing env pointer")
    if secret_ref.params[0].secret_ref.name != "IMP0133_FIXTURE_TOKEN":
        return fail("secret_ref pointer is not the env name")

    dest_bad = Path(tempfile.mkdtemp(prefix="imp0133-bad-")) / "wf.json"
    try:
        export_workflow(literal, dest_bad)
        return fail("literal export unexpectedly succeeded")
    except ExportRefused as exc:
        ids = list(exc.ids)
        if PARAM_CREDENTIAL_LITERAL not in ids:
            return fail(f"named violation missing, got {ids}")
        named = PARAM_CREDENTIAL_LITERAL
    if dest_bad.is_file():
        return fail("refused export still wrote a file")

    dest_ok = Path(tempfile.mkdtemp(prefix="imp0133-ok-")) / "wf.json"
    export_workflow(secret_ref, dest_ok)
    if not dest_ok.is_file() or dest_ok.stat().st_size <= 0:
        return fail("secret_ref export wrote nothing")
    blob = dest_ok.read_text(encoding="utf-8")
    doc = json.loads(blob)
    ref = (doc.get("params") or [{}])[0].get("ref") or {}
    if ref.get("source") != "env" or ref.get("name") != "IMP0133_FIXTURE_TOKEN":
        return fail(f"serialized secret_ref is not an env pointer: {ref!r}")
    if "default" in (doc.get("params") or [{}])[0]:
        return fail("secret_ref serialization carried a default/literal field")
    grep_hits = C.independent_grep_hits(dest_ok, C.TOKEN)
    byte_hits = dest_ok.read_bytes().count(C.TOKEN.encode("utf-8"))
    if grep_hits != 0 or byte_hits != 0:
        return fail(f"fixture token leaked into export grep={grep_hits} bytes={byte_hits}")

    payload = {
        "probe": "probe1-literal-refused",
        "unit_id": "IMP-0133",
        "pass": True,
        "literal_refused": True,
        "named_violation": named,
        "refused_file_absent": True,
        "secret_ref_exported": True,
        "independent_grep_hits": grep_hits,
        "byte_hits": byte_hits,
        "serialized_ref": ref,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"literal_refused=True violation={named} secret_ref_ok=True "
        f"grep_hits={grep_hits}"
    )
    print("SUCCESS:IMP-0133-probe1 literal refused; secret_ref export has zero token hits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
