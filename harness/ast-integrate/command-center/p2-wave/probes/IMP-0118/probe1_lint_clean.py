#!/usr/bin/env python3
"""Probe 1: index linter is clean on the fixture and fires on planted defects.

Signal 1 of IMP-0118: the fixture registry passes the index linter with zero
findings. Both-states: a dangling-blob mutant and a digest-mismatch mutant
each produce findings in the same process.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.fixture import build  # noqa: E402
from tools.marketplace.index_linter import lint_index, lint_registry  # noqa: E402
from tools.marketplace.storage import read_json, registry_dir  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0118.json"


def main() -> int:
    build(REPO)
    findings = lint_registry(REPO)
    if findings:
        print(json.dumps({"findings": findings}, indent=2)[:4000])
        print("FAILED:IMP-0118-probe1 fixture is not lint-clean")
        return 1

    src = registry_dir(REPO)
    dangling_codes: set[str] = set()
    digest_codes: set[str] = set()
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "registry"
        shutil.copytree(src, dest)
        index = read_json(dest / "index.json")
        victim = next(p for p in index["packages"] if p["id"] == "hello-skill@1.0.0")
        (dest / str(victim["blob"])).unlink()
        dangling_codes = {f["code"] for f in lint_index(dest, index)}

    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "registry"
        shutil.copytree(src, dest)
        index = read_json(dest / "index.json")
        victim = next(p for p in index["packages"] if p["id"] == "hello-skill@1.1.0")
        blob = dest / str(victim["blob"])
        raw = blob.read_bytes().replace(b"\r\n", b"\n")
        patched = raw.replace(b"Newer skill version", b"Never skill version", 1)
        if patched == raw:
            print("FAILED:IMP-0118-probe1 digest mutant did not change bytes")
            return 1
        blob.write_bytes(patched)
        digest_codes = {f["code"] for f in lint_index(dest, index)}

    dangling_ok = "DANGLING_BLOB" in dangling_codes
    digest_ok = "DIGEST_MISMATCH" in digest_codes
    report = {
        "probe": "probe1-lint-clean",
        "unit_id": "IMP-0118",
        "clean_findings": findings,
        "clean_zero": True,
        "dangling_codes": sorted(dangling_codes),
        "digest_codes": sorted(digest_codes),
        "fired_on_dangling": dangling_ok,
        "fired_on_digest_mismatch": digest_ok,
        "silent_on_good": True,
        "pass": dangling_ok and digest_ok,
    }
    print(json.dumps(report, sort_keys=True))
    if not dangling_ok:
        print("FAILED:IMP-0118-probe1 dangling mutant silent")
        return 1
    if not digest_ok:
        print("FAILED:IMP-0118-probe1 digest mutant silent")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0118-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0118-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0118" not in text:
        print("FAILED:IMP-0118-probe1 sentinel absent")
        return 1
    print("SUCCESS:IMP-0118-probe1 lint-clean and both-states mutants fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
