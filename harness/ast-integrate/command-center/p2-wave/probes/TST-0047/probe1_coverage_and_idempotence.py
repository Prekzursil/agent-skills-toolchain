#!/usr/bin/env python3
"""Probe 1: every declared schema_version transition has a migration; each
migration is applied twice on a disposable tree; the second run is
byte-identical. Repo source artifacts must be unchanged (isolation)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import good_registry, sha256_bytes  # noqa: E402
from fixtures import REAL_ARTIFACTS, all_conforming_sources  # noqa: E402
from suite import evaluate  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0047-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    before = {}
    for rel, _dest in REAL_ARTIFACTS:
        path = REPO / rel
        if not path.is_file():
            return fail(f"real artifact absent {rel}")
        before[rel] = sha256_bytes(path.read_bytes())

    report = evaluate(good_registry(), all_conforming_sources())
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "registry_id": report["registry_id"],
                "migrations_run": report["migrations_run"],
                "source_count": len(report["sources"]),
                "double_apply_rows": len(report["double_apply"]),
                "transformed_first": report["transformed_first"],
                "rules": {k: v["ok"] for k, v in report["rules"].items()},
            },
            sort_keys=True,
        )
    )

    after = {rel: sha256_bytes((REPO / rel).read_bytes()) for rel, _ in REAL_ARTIFACTS}
    if after != before:
        return fail("disposable-tree isolation broken; repo artifacts mutated", after)

    if not report["ok"]:
        return fail("conforming registry did not pass the suite", report["rules"])
    if len(report["migrations_run"]) < 2:
        return fail("need at least two schema_version transitions", report["migrations_run"])
    if len(report["sources"]) < 6:
        return fail(f"need fixture+real artifacts, got {len(report['sources'])}")

    from_rows = [r for r in report["double_apply"] if r.get("was_from_version")]
    if len(from_rows) < 6:
        return fail(f"too few from_version applies {len(from_rows)}", from_rows[:4])
    for row in from_rows:
        if not row.get("first_run_mutated"):
            return fail("first apply did not mutate a from_version artifact", row)
        if not row.get("second_run_unchanged"):
            return fail("second apply mutated bytes", row)
        if row.get("status_first") != "TRANSFORMED":
            return fail("first apply was not TRANSFORMED", row)
        if row.get("status_second") != "NOOP":
            return fail("second apply was not NOOP", row)
        if row.get("sha_after_first") != row.get("sha_after_second"):
            return fail("byte-comparison after second run failed", row)

    rules = report["rules"]
    if not rules["coverage"]["ok"]:
        return fail("coverage")
    if rules["coverage"]["missing"]:
        return fail("coverage missing", rules["coverage"])
    declared = rules["coverage"]["declared_transitions"]
    if declared != ["1->2", "2->3"]:
        return fail("declared transitions", declared)

    print(
        f"migrations={report['migrations_run']} from_rows={len(from_rows)} "
        f"second_run_unchanged={all(r['second_run_unchanged'] for r in from_rows)} "
        f"repo_unchanged=True"
    )
    print("SUCCESS:TST-0047-probe1 coverage and double-apply idempotence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
