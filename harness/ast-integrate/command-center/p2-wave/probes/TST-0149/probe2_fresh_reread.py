#!/usr/bin/env python3
"""Probe 2: fresh process re-reads the receipt+manifest; writer-trust negative control.

Signal (b): a second Python process json-loads the fixture receipt and runs
platform/lib/completion_predicate.evaluate, which re-reads ARTIFACT-MANIFEST.json.
FIX-0149 is absent in the unpersisted tree and present after persist.
Negative control: a check that trusts writer_return.registered SATISFIES the
unregistered tree and therefore must not be accepted as condition 11.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0149.json"
REREAD = HERE / "reread_manifest.py"
UNIT = "TST-0149"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0149-probe2 {msg}")
    return 1


def reread(root: Path, meta: dict) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [
        sys.executable,
        "-B",
        str(REREAD),
        str(root / S.RECEIPT_REL),
        str(root),
        S.SCHEMA_REL,
    ]
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode != 0:
        raise RuntimeError(f"reread rc={p.returncode} tail={text[-800:]}")
    try:
        payload = json.loads(text.splitlines()[-1] if text else "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"reread unparseable: {exc} tail={text[-800:]}") from exc
    if payload.get("ok") is not True:
        raise RuntimeError(f"reread instrument failed {payload}")
    return payload


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0149-p2-unreg-") as unreg_s:
        unreg_root = Path(unreg_s)
        unreg = S.populate(unreg_root, persist_manifest=False)
        unreg_fresh = reread(unreg_root, unreg)
    with tempfile.TemporaryDirectory(prefix="tst0149-p2-reg-") as reg_s:
        reg_root = Path(reg_s)
        registered = S.populate(reg_root, persist_manifest=True)
        reg_fresh = reread(reg_root, registered)

    unreg_outcome = unreg_fresh["result"]["outcome"]
    reg_outcome = reg_fresh["result"]["outcome"]
    trust = unreg["c11_writer_trust"]["outcome"]
    disk = unreg["c11_disk"]["outcome"]

    print(
        json.dumps(
            {
                "probe": "probe2-fresh-reread",
                "unit_id": UNIT,
                "reducer_id": unreg_fresh.get("reducer_id"),
                "fresh_unregistered_c11": unreg_outcome,
                "fresh_registered_c11": reg_outcome,
                "fresh_unregistered_c2": unreg_fresh.get("c2"),
                "fresh_unregistered_c4": unreg_fresh.get("c4"),
                "fresh_unregistered_c5": unreg_fresh.get("c5"),
                "writer_trust_unregistered": trust,
                "in_process_disk_unregistered": disk,
                "negative_control_writer_trust_wrongly_satisfies": trust
                == "SATISFIED",
                "fresh_process_confirms_absence": unreg_outcome == "UNSATISFIED",
                "fresh_process_confirms_presence_after_register": reg_outcome
                == "SATISFIED",
            },
            indent=2,
            sort_keys=True,
        )
    )

    if unreg_outcome != "UNSATISFIED":
        return fail("fresh process did not confirm absence from on-disk manifest")
    if reg_outcome != "SATISFIED":
        return fail("fresh process did not see the row after persist")
    if trust != "SATISFIED":
        return fail("writer-trust negative control did not wrongly pass")
    if disk != "UNSATISFIED":
        return fail("in-process disk check did not fail unregistered")
    if trust == disk:
        return fail("writer-trust and disk check agreed; negative control inert")
    if unreg_fresh.get("c2") != "SATISFIED" or unreg_fresh.get("c5") != "SATISFIED":
        return fail("fresh process lost C2/C5 on the unregistered tree")

    if not ART.is_file():
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0149" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    print("SUCCESS:TST-0149-probe2 fresh-reread writer-trust-negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
