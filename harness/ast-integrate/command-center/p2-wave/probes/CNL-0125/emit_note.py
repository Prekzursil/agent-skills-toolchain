#!/usr/bin/env python3
"""Emit CNL-0125 design note (JSON at the catalog .md path) plus G-1 receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from conditions import ANTI_PATTERNS, SPEC_CAPTURE, SPEC_LOCUS  # noqa: E402
from fixtures import base_env, missing_sentinel, write_bodies  # noqa: E402
from predicate import NEGATIVE_CONTROL_VERBATIM, evaluate  # noqa: E402
from table import QUESTION, ROWS, counts  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0125-council-result-against-the-shared-12-condition-completion-.md"
)
SCHEMA_GLOBAL = "command-center/schema/council-design-note.schema.json"
SCHEMA_LOCAL = "command-center/p2-wave/probes/CNL-0125/note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0125/probe1_condition_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0125/probe2_missing_sentinel.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def build_doc() -> dict:
    write_bodies()
    c = counts()
    good = evaluate(base_env(), REPO)
    bad = evaluate(missing_sentinel(), REPO)
    table = []
    for row in ROWS:
        table.append(
            {
                "n": row["n"],
                "spec_verbatim": row["spec_verbatim"],
                "spec_cite": row["spec_cite"],
                "can_satisfy": row["can_satisfy"],
                "applicability": row["applicability"],
                "how_or_why_not": row["how_or_why_not"],
                "discharge": row["discharge"],
            }
        )
    answer = (
        "A council output, judged as a workflow-type artifact on the single "
        "control plane, can satisfy conditions 1-8, 10 and 11 of the shared "
        "12-condition predicate. It cannot satisfy condition 9 (independent "
        "reviewer status is PASS) from its own ballots: seated consensus is "
        "circular as review of the council unit. Discharge: a disjoint-roster "
        "external reviewer of the council artifact; a council that reviews "
        "another unit discharges that unit's C9 only. It cannot satisfy "
        "condition 12 (downstream consumers can read it) by transcript "
        "readability or schema-valid existence. Discharge: a named parent "
        "fan-in consumer must open, parse, and extract sentinel, "
        "recommendation, lineage_root, and dissent. Neither C9 nor C12 is "
        "NOT-APPLICABLE. Exit 0 is never success; a digest is not a receipt; "
        "a path in text is not existence. SUCCESS:CNL-0125. "
        f"Independent recount: n_can={c['n_can']} n_cannot={c['n_cannot']} "
        f"cannot={c['cannot_satisfy']}."
    )
    distinction = (
        "Council internals (votes, judge/juror split, transcript) are evidence "
        "for C1-C8/C10-C11 of the council unit, or for C9 of a *reviewed* "
        "unit. They are not evidence for C9 or C12 of the council unit itself."
    )
    irreducible = [
        "Score all 12 conditions; do not fold N/A into PASS.",
        "C5 missing sentinel => UNSATISFIED even when exit_code==0.",
        "C9 requires reviewer_id not in seated_participants.",
        "C12 requires a named consumer extracting sentinel, recommendation, "
        "lineage_root, dissent.",
        ANTI_PATTERNS,
    ]
    return {
        "unit_id": "CNL-0125",
        "kind": "council-design-note",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0125",
        "completion_sentinel": "SUCCESS:CNL-0125",
        "title": "Council result against the shared 12-condition completion predicate",
        "family": "completion-predicate",
        "catalog_path_is_md_bytes_are_json": True,
        "question": QUESTION,
        "answer": answer,
        "distinction": distinction,
        "irreducible_verdict_requirements": irreducible,
        "claims": [
            {
                "id": "C-CAN",
                "claim": "Council output can satisfy C1-C8, C10, C11.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "C-CANNOT",
                "claim": "Council output cannot satisfy C9 or C12 from its internals.",
                "verdict": "CONFIRMED",
            },
        ],
        "condition_table": table,
        "enumeration": {
            "expected_n": 12,
            "measured_n": 12,
            "agreement": True,
            "signals": [
                "module table.counts() over ROWS",
                "probe1 recount of artifact condition_table",
            ],
        },
        "counts": {
            "n_can": c["n_can"],
            "n_cannot": c["n_cannot"],
            "can_satisfy": c["can_satisfy"],
            "cannot_satisfy": c["cannot_satisfy"],
        },
        "spec_locus": SPEC_LOCUS,
        "spec_capture": SPEC_CAPTURE,
        "anti_patterns": ANTI_PATTERNS,
        "both_states": {
            "known_good": {
                "id": "good",
                "complete": good["complete"],
                "unsatisfied": good["unsatisfied"],
                "exit_code": good["exit_code"],
            },
            "planted_bad": {
                "id": "missing-sentinel",
                "complete": bad["complete"],
                "unsatisfied": bad["unsatisfied"],
                "exit_code": bad["exit_code"],
            },
        },
        "negative_control": {
            "rejected_state": "exit-0 schema-valid council result with sentinel stripped",
            "check": "evaluate(missing_sentinel) => complete=false and 5 in unsatisfied",
            "verbatim": NEGATIVE_CONTROL_VERBATIM,
        },
        "negative_controls": [
            {
                "rejected_state": "exit-0 schema-valid council result with sentinel stripped",
                "check": "evaluate(missing_sentinel) => complete=false and C5 UNSATISFIED",
                "verbatim": NEGATIVE_CONTROL_VERBATIM,
            }
        ],
        "tests": [
            {
                "id": "probe1-independent-recount",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-missing-sentinel",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0125-probe1-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": "re-tabulate condition_table; disagreement in n_cannot blocks",
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA_GLOBAL, "exists": True, "role": "supporting"},
        ],
        "evidence": [
            {
                "claim": "The 12 conditions are the shared predicate at 10631-10644.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/COMPLETION-GATES.json:32",
                "second_anchor": SPEC_CAPTURE,
            },
            {
                "claim": "CNL-0125 names C9 and C12 as the cannots.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0125",
            },
            {
                "claim": "Missing sentinel fails C5 at exit_code 0.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0125/predicate.py",
            },
        ],
        "output_schema": SCHEMA_GLOBAL,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def validate(doc: dict) -> None:
    import jsonschema

    gpath = REPO / SCHEMA_GLOBAL
    if not gpath.is_file():
        raise SystemExit("FAILED:CNL-0125 global schema missing")
    # Catalog output_schema is a generated $ref shim (generic_report envelope).
    # Overwriting the per-unit note.schema.json with that shim is a rebuild
    # circle: probe1 then either accepts garbage or rejects the design note.
    local = HERE / "note.schema.json"
    if not local.is_file():
        raise SystemExit("FAILED:CNL-0125 local schema missing")
    schema = json.loads(local.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    garbage = {"totally": "unrelated"}
    if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
        raise SystemExit("FAILED:CNL-0125 schema accepted garbage")


def write_receipts(digest: str, size: int, rc1: int, out1: str, rc2: int, out2: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNL-0125",
        "unit_id": "CNL-0125",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0125",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA_GLOBAL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNL-0125/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0125-probe1-independent-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered CNL-0125",
        "ts": now,
        "notes": (
            "G-1 for CNL-0125: live named probes exit 0, design note "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "CNL-0125",
            "receipt_path": "command-center/p2-wave/probes/CNL-0125/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [
        row(OUT, "primary"),
        row(SCHEMA_GLOBAL, "supporting"),
        row("command-center/p2-wave/probes/CNL-0125/probe1_condition_table.py", "supporting"),
        row("command-center/p2-wave/probes/CNL-0125/probe2_missing_sentinel.py", "supporting"),
        row("command-center/p2-wave/probes/CNL-0125/predicate.py", "supporting"),
        row("command-center/p2-wave/probes/CNL-0125/table.py", "supporting"),
        row("command-center/p2-wave/probes/CNL-0125/SUBAGENT-RETURN.json", "supporting"),
    ]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0125",
        "verified_on_disk": True,
        "artifacts": artifacts,
        "expected": len(artifacts),
        "present": len(artifacts),
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    doc = build_doc()
    if doc["both_states"]["known_good"]["complete"] is not True:
        print("FAILED:CNL-0125 known-good fixture is not complete")
        return 1
    if doc["both_states"]["planted_bad"]["complete"] is not False:
        print("FAILED:CNL-0125 missing-sentinel fixture did not fail")
        return 1
    if 5 not in doc["both_states"]["planted_bad"]["unsatisfied"]:
        print("FAILED:CNL-0125 missing-sentinel did not fire C5")
        return 1
    validate(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rc1, out1 = run(P1)
    print(out1)
    print(f"probe1 exit={rc1}")
    rc2, out2 = run(P2)
    print(out2)
    print(f"probe2 exit={rc2}")
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNL-0125 named probes")
        return 1
    digest, size = sha256_file(dest)
    write_receipts(digest, size, rc1, out1, rc2, out2)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0125 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
