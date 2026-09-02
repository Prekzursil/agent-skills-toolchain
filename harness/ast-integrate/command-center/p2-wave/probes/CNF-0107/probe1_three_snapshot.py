#!/usr/bin/env python3
"""Probe 1: three-point snapshot (pre-install, post-install, post-uninstall) + reinstall.

Signal: filesystem inventory hashes. Orphans and user-data loss must be empty;
the out-of-scope control must be byte-identical; reinstall after uninstall must
succeed. Also checks the confirmation artifact when present.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from compare import compare  # noqa: E402
from lifecycle import OOS_CONTROL, OWNED, USER_DATA, run_cycle  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0107-uninstall-completeness.json"
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0107 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all three snapshots are "
    "attached and the post-uninstall reinstall was attempted and its result "
    "recorded. Any other terminal state is FAILED:CNF-0107 <classification> "
    "with the diagnostic tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0107-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0107-p1-") as tmp:
        cycle = run_cycle(Path(tmp) / "home", mode="healthy")
    findings = compare(cycle["pre"], cycle["post_install"], cycle["post_uninstall"])
    reinstall = cycle["reinstall"]

    if findings["pre_file_count"] < 1:
        return fail("pre-install snapshot empty")
    if findings["post_install_file_count"] <= findings["pre_file_count"]:
        return fail("install did not add owned files")
    missing_owned = [p for p in OWNED if p not in {r["path"] for r in cycle["post_install"]["files"]}]
    if missing_owned:
        return fail(f"install missed owned {missing_owned}")
    missing_user = [p for p in USER_DATA if p not in {r["path"] for r in cycle["post_install"]["files"]}]
    if missing_user:
        return fail(f"user-data seed missing {missing_user}")
    if findings["orphans"]:
        return fail(f"orphans {findings['orphans']}")
    if findings["data_loss"]:
        return fail(f"data-loss {findings['data_loss']}")
    if not findings["out_of_scope_intact"]:
        return fail(f"out-of-scope {findings['out_of_scope_damage']}")
    if findings["out_of_scope_control_path"] != OOS_CONTROL:
        return fail("control path mismatch")
    if not reinstall.get("attempted"):
        return fail("reinstall not attempted")
    if not reinstall.get("succeeded"):
        return fail(f"reinstall poisoned-or-failed {reinstall}")
    if reinstall.get("poisoned"):
        return fail("healthy uninstall left a poisoned marker")

    if ART.is_file() and ART.stat().st_size > 0:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != "CNF-0107":
            return fail(f"artifact unit_id {doc.get('unit_id')}")
        labels = [s.get("label") for s in doc.get("snapshots") or []]
        if labels != ["pre-install", "post-install", "post-uninstall"]:
            return fail(f"artifact snapshots {labels}")
        if CATALOG_SENTINEL not in json.dumps(doc):
            return fail("catalog completion_sentinel absent from artifact")
        if not (doc.get("reinstall") or {}).get("attempted"):
            return fail("artifact reinstall.attempted is not true")
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"artifact self-declared {doc.get('state')}")

    summary = {
        "probe": "probe1-three-snapshot",
        "unit_id": "CNF-0107",
        "orphans": 0,
        "data_loss": 0,
        "out_of_scope_intact": True,
        "reinstall_ok": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "pre={pre} post_install={pi} post_uninstall={pu} reinstall_ok=True oos={oos}".format(
            pre=findings["pre_file_count"],
            pi=findings["post_install_file_count"],
            pu=findings["post_uninstall_file_count"],
            oos=OOS_CONTROL,
        )
    )
    print("SUCCESS:CNF-0107-probe1 three-snapshot completeness and non-destruction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
