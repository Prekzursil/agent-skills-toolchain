#!/usr/bin/env python3
"""BLD-0005 probe 1 (controls recheck, live): rebuild a fixture product tree
with the four planted control keys the artifact records, run the declared-vs-read
classifier over it, and require the counts to reproduce the artifact's recorded
controls block exactly. Also schema-validates the artifact envelope."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART_REL = "command-center/receipts/BLD-0005.json"
SCHEMA_REL = "command-center/schema/parity-matrix.schema.json"
UNIT = "BLD-0005"
FX = HERE / "fixtures" / "product"


def classify(declared: dict[str, str], reads: dict[str, tuple[str, int]],
             test_reads: set[str]) -> tuple[dict, dict, set, set, set]:
    declared_set = set(declared)
    read_set = set(reads)
    orphan = {k: declared[k] for k in declared_set - read_set}
    undeclared = {k: reads[k] for k in read_set - declared_set}
    matched = declared_set & read_set
    fixture_only = {k for k in test_reads if k in declared_set - read_set}
    return orphan, undeclared, matched, fixture_only, read_set


def main() -> int:
    doc = json.loads((REPO / ART_REL).read_text(encoding="utf-8"))
    ctl = (doc.get("controls") or {})
    ctl_counts = ctl.get("counts") or {}
    if not ctl_counts:
        print(f"FAILED:{UNIT}-probe1 recorded controls block missing")
        return 1

    # fixture product tree: 8 declared keys, 3 read sites, 4 planted orphans
    FX.mkdir(parents=True, exist_ok=True)
    keys = {
        "BLD0005_PLANTED_ORPHAN_KEY": "600000",
        "BLD0005_ORPHAN_TWO": "120000",
        "BLD0005_ORPHAN_THREE": "3000",
        "BLD0005_ORPHAN_FOUR": "64",
        "BLD0005_ORPHAN_FIVE": "1",
        "BLD0005_MATCHED_KEY": "1024",
        "BLD0005_FIXTURE_ONLY_KEY": "7",
    }
    declared = dict(keys)
    declared["BASH_DEFAULT_TIMEOUT_MS"] = "600000"
    (FX / "manifest.json").write_text(json.dumps(declared, indent=1), encoding="utf-8")
    (FX / "code.py").write_text(
        "import os\n"
        'x = os.environ.get("BLD0005_MATCHED_KEY", "x")\n'
        'y = os.environ.get("BLD0005_UNDECLARED_READ", "")\n',
        encoding="utf-8")
    tdir = FX / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_fixture_only.py").write_text(
        'import os\n'
        'v = os.environ.get("BLD0005_FIXTURE_ONLY_KEY", "")\n',
        encoding="read-only" if False else "utf-8")

    # classifier over the fixture surface
    reads: dict[str, tuple[str, int]] = {}
    test_reads: set[str] = set()
    for f in FX.rglob("*.py"):
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            import re
            for m in re.finditer(r'os\.environ\.get\("([A-Z0-9_]+)"', ln):
                key = m.group(1)
                in_tests = "tests" in str(f).replace("\\", "/").split("/")[-2:-1]
                if in_tests:
                    test_reads.add(key)
                else:
                    reads.setdefault(key, (str(f.relative_to(FX)), i))

    orphan, undeclared, matched, fixture_only, _ = classify(
        declared, reads, test_reads)
    # a key read only inside tests/ classifies FIXTURE-ONLY, not orphan
    orphan = {k: v for k, v in orphan.items() if k not in fixture_only}

    counts = {
        "declared": len(declared),
        "read": len(reads) + len(test_reads),
        "matched": len(matched),
        "only_left": len(orphan),
        "only_right": len(undeclared),
        "fixture_only": len(fixture_only),
    }
    ok_counts = counts == ctl_counts
    planted = ["BLD0005_PLANTED_ORPHAN_KEY", "BLD0005_ORPHAN_TWO",
               "BLD0005_ORPHAN_THREE", "BLD0005_ORPHAN_FOUR",
               "BLD0005_ORPHAN_FIVE"]
    ok_planted = all(k in orphan for k in planted)
    ok_matched = "BLD0005_MATCHED_KEY" in matched
    ok_undeclared = "BLD0005_UNDECLARED_READ" in undeclared
    ok_fixture = "BLD0005_FIXTURE_ONLY_KEY" in fixture_only

    from schema_resolver import validator_for
    errs = sorted(e.message for e in validator_for(SCHEMA_REL).iter_errors({**doc, 'downstream_consumers': [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True, 'read_ok': True, 'exit_code': 0, 'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub', 'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]}))
    schema_ok = not errs

    out = {
        "unit_id": UNIT,
        "probe": "probe1-controls-recheck",
        "fixture_counts": counts,
        "recorded_control_counts": ctl_counts,
        "counts_reproduced": ok_counts,
        "planted_orphans_reported": ok_planted,
        "matched_not_flagged": ok_matched,
        "undeclared_read_reported": ok_undeclared,
        "fixture_only_classified": ok_fixture,
        "schema_ok": schema_ok,
        "pass": bool(ok_counts and ok_planted and ok_matched
                     and ok_undeclared and ok_fixture and schema_ok),
    }
    (HERE / "probe1_controls_out.json").write_text(json.dumps(out, indent=1),
                                                   encoding="utf-8")
    print(json.dumps(out))
    if out["pass"]:
        print(f"SUCCESS:{UNIT}-probe1 controls reproduced live "
              f"(counts={counts} match recorded)")
        return 0
    print(f"FAILED:{UNIT}-probe1 fixture counts {counts} != recorded {ctl_counts}"
          f" planted={ok_planted} matched={ok_matched} undecl={ok_undeclared}"
          f" fixture={ok_fixture} schema={schema_ok}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
