#!/usr/bin/env python3
"""Named probe 2: identical NO-OP, NEEDS-RECONCILE refuse, naive destroy, apply fail."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classify import IDENTICAL, NEEDS_RECONCILE, NO_OP, REFUSE  # noqa: E402
from fixtures import IDENTICAL as IDENTICAL_PATHS  # noqa: E402
from fixtures import NEEDS_RECONCILE as RECONCILE_PATHS  # noqa: E402
from fixtures import materialize  # noqa: E402
from rollback import APPLY_FORBIDDEN, plan_rollback  # noqa: E402

ART = HERE.parents[3] / "command-center/confirmation/CNF-0045-deploy-target-rollback.json"


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0045-probe2 {msg}")
    return 1


def main() -> int:
    apply_plan = plan_rollback(Path("/tmp"), Path("/tmp"), dry_run=False, apply=True)
    if not apply_plan.get("hard_failure"):
        return _fail("apply was not a hard failure")
    if APPLY_FORBIDDEN not in str(apply_plan.get("error")):
        return _fail("apply error missing premature-write classification")

    with tempfile.TemporaryDirectory(prefix="cnf0045-p2-") as tmp:
        spec = materialize(Path(tmp))
        plan = plan_rollback(
            Path(spec["repo_root"]),
            Path(spec["live_root"]),
            dry_run=True,
            apply=False,
        )

    table = plan["classification_table"]
    by_path = {r["path"]: r for r in table["rows"]}

    for rel in IDENTICAL_PATHS:
        row = by_path.get(rel)
        if row is None:
            return _fail(f"missing identical fixture {rel}")
        if row["classification"] != IDENTICAL or row["rollback_action"] != NO_OP:
            return _fail(f"identical not no-op: {rel} -> {row['classification']}")

    for rel in RECONCILE_PATHS:
        row = by_path.get(rel)
        if row is None:
            return _fail(f"missing both-unique fixture {rel}")
        if row["classification"] != NEEDS_RECONCILE:
            return _fail(f"{rel} classified {row['classification']} not NEEDS-RECONCILE")
        if row["rollback_action"] != REFUSE:
            return _fail(f"{rel} auto-resolved as {row['rollback_action']}")
        if not row["naive_would_destroy_live_unique"]:
            return _fail(f"{rel} naive plan does not destroy live-unique (control silent)")
        if row["live_unique_line_count"] < 1 or row["repo_unique_line_count"] < 1:
            return _fail(f"{rel} is not both-unique")

    if all(r["rollback_action"] != NO_OP for r in table["rows"]):
        return _fail("classifier flagged everything; identical control failed")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"artifact self-declared {doc.get('state')}")
        findings = doc.get("findings")
        if not isinstance(findings, dict) or not findings:
            report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
            findings = report.get("findings") if isinstance(report.get("findings"), dict) else {}
        if findings.get("naive_rollback_destroys_live_only_content") is not True:
            return _fail("artifact missing naive-destroy finding")
        if findings.get("procedure_detects_two_directional_before_write") is not True:
            return _fail("artifact missing two-directional-before-write finding")
        tests = {
            t.get("id"): t.get("result")
            for t in (doc.get("tests") or [])
            if isinstance(t, dict)
        }
        if tests.get("identical-noop") != "PASS":
            return _fail("artifact identical-noop test not PASS")
        if tests.get("needs-reconcile-not-autoresolved") != "PASS":
            return _fail("artifact needs-reconcile test not PASS")

    out = {
        "probe": "probe2-controls",
        "unit_id": "CNF-0045",
        "identical_noop": True,
        "needs_reconcile_refused": True,
        "naive_would_destroy_both_unique": True,
        "apply_hard_failure": True,
        "classifier_not_flagging_everything": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "identical_noop=True needs_reconcile=REFUSE naive_destroy=True "
        "apply_hard_failure=True not_flagging_everything=True"
    )
    print("SUCCESS:CNF-0045-probe2 identical no-op and NEEDS-RECONCILE controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
