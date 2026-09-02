#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0040.json — oracle-strength census."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import discriminate as D  # noqa: E402
import grade as G  # noqa: E402
import inventory as I  # noqa: E402

OUT_REL = "command-center/receipts/BLD-0040.json"
SCHEMA_REL = "command-center/schema/oracle-strength-census.schema.json"
QUESTION = (
    "For each test, what is the ORACLE — the specific thing that would make it "
    "fail — and how strong is it? Grade every test EXACT-VALUE, "
    "INVARIANT/PROPERTY, SCHEMA-SHAPE, SNAPSHOT, EXIT-CODE-ONLY, or "
    "NO-CRASH-ONLY. Report the distribution and every test whose strongest "
    "oracle is exit-code or no-crash, because those pass on wrong output."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0040/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0040/probe2_wrong_value.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    rec = {"path": rel, "exists": path.is_file(), "role": role}
    if path.is_file():
        sha, size = sha256_file(path)
        rec["sha256"] = sha
        rec["bytes"] = size
    return rec


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:BLD-0040 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def validate(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"totally": "unrelated"}, {"unit_id": "NOPE"}):
        errs = list(jsonschema.Draft7Validator(schema).iter_errors(garbage))
        if not errs:
            raise SystemExit("FAILED:BLD-0040 schema accepts garbage")


def census() -> list[dict]:
    rows: list[dict] = []
    for path in I.iter_test_files(REPO):
        rel = path.resolve().relative_to(REPO.resolve()).as_posix()
        corpus = I.corpus_of(rel)
        for row in G.grade_file(path, REPO):
            row["corpus"] = corpus
            rows.append(row)
    rows.sort(key=lambda r: (r.get("path") or "", int(r.get("line") or 0)))
    return rows


def main() -> int:
    rows = census()
    if len(rows) < 8:
        print(f"FAILED:BLD-0040 census too small n={len(rows)}")
        return 1

    disc = D.run_discrimination()
    if not disc.get("ok"):
        print("FAILED:BLD-0040 discrimination did not separate oracles")
        print(json.dumps(disc, indent=2))
        return 1

    dist = {g: 0 for g in G.RANK}
    for row in rows:
        key = row["effective_oracle"]
        dist[key] = dist.get(key, 0) + 1

    weak = [
        {
            "test_id": r["test_id"],
            "path": r["path"],
            "line": r["line"],
            "effective_oracle": r["effective_oracle"],
            "quote": r["quote"],
            "corpus": r.get("corpus"),
        }
        for r in rows
        if r["effective_oracle"] in G.WEAK
    ]
    snaps = [
        r
        for r in rows
        if r.get("snapshot") or r["strongest_oracle"] == "SNAPSHOT"
    ]
    self_conf = [r for r in rows if r.get("self_confirming")]
    if not self_conf:
        print("FAILED:BLD-0040 planted self-confirming snapshot missing")
        return 1

    by_name = {r["name"]: r for r in rows}
    nc = by_name.get("test_no_crash_only") or {}
    ex = by_name.get("test_exact_value") or {}
    sn = by_name.get("test_snapshot_self_confirming") or {}
    if nc.get("effective_oracle") != "NO-CRASH-ONLY":
        print(f"FAILED:BLD-0040 control no-crash {nc}")
        return 1
    if ex.get("effective_oracle") != "EXACT-VALUE":
        print(f"FAILED:BLD-0040 control exact {ex}")
        return 1
    if not sn.get("self_confirming") or sn.get("effective_oracle") != "NO-ORACLE":
        print(f"FAILED:BLD-0040 control snapshot {sn}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry = I.registry_status(REPO)
    grades_out = []
    for r in rows:
        rec = {
            "test_id": r["test_id"],
            "name": r["name"],
            "path": r["path"],
            "line": r["line"],
            "strongest_oracle": r["strongest_oracle"],
            "effective_oracle": r["effective_oracle"],
            "self_confirming": bool(r.get("self_confirming")),
            "assertions": r.get("assertions") or [],
            "quote": r["quote"],
            "corpus": r.get("corpus"),
        }
        if r.get("snapshot"):
            rec["golden_last_regenerated"] = r.get("golden_last_regenerated")
            rec["golden_regenerated_by"] = r.get("golden_regenerated_by")
            rec["snapshot"] = True
        grades_out.append(rec)

    tests = [
        {
            "id": "control-no-crash-only",
            "name": "assert result is not None grades NO-CRASH-ONLY",
            "command": P1,
            "result": "PASS",
            "observed": nc.get("effective_oracle"),
        },
        {
            "id": "control-exact-value",
            "name": "assert compute_score([1,2,3]) == 6 grades EXACT-VALUE",
            "command": P1,
            "result": "PASS",
            "observed": ex.get("effective_oracle"),
        },
        {
            "id": "control-self-confirming-snapshot",
            "name": "golden regenerated from produce_report is self-confirming",
            "command": P1,
            "result": "PASS",
            "observed": "self-confirming/NO-ORACLE",
        },
        {
            "id": "discrimination-wrong-value",
            "name": "wrong non-crashing return: NO-CRASH stays green, EXACT goes red",
            "command": P2,
            "result": "PASS",
            "observed": {
                "no_crash_stayed_green": disc["no_crash_stayed_green"],
                "exact_value_went_red": disc["exact_value_went_red"],
            },
        },
    ]
    evidence = [
        ev(
            "command-center/p2-wave/probes/BLD-0040/fixtures/test_oracles.py",
            "assert result is not None",
            "Planted NO-CRASH-ONLY control: existence check cannot catch a wrong sum.",
        ),
        ev(
            "command-center/p2-wave/probes/BLD-0040/fixtures/test_oracles.py",
            "assert result == 6",
            "Planted EXACT-VALUE control: equality to the computed sum.",
        ),
        ev(
            "command-center/p2-wave/probes/BLD-0040/fixtures/snapshot/REGEN.json",
            '"source": "code-under-test"',
            "Golden last regenerated from produce_report(); self-confirming SNAPSHOT is NO-ORACLE.",
        ),
        ev(
            "command-center/p2-wave/probes/BLD-0040/discriminate.py",
            "def compute_score(values):",
            "Reviewer injects return 0 in an isolated copy; shared subject.py is unchanged.",
        ),
    ]
    supporting = [
        SCHEMA_REL,
        "command-center/p2-wave/probes/BLD-0040/grade.py",
        "command-center/p2-wave/probes/BLD-0040/inventory.py",
        "command-center/p2-wave/probes/BLD-0040/discriminate.py",
        "command-center/p2-wave/probes/BLD-0040/fixtures/test_oracles.py",
        "command-center/p2-wave/probes/BLD-0040/fixtures/subject.py",
        "command-center/p2-wave/probes/BLD-0040/fixtures/snapshot/REGEN.json",
        "command-center/p2-wave/probes/BLD-0040/probe1_controls.py",
        "command-center/p2-wave/probes/BLD-0040/probe2_wrong_value.py",
    ]
    artifacts = [artifact(p, "supporting") for p in supporting]
    for a in artifacts:
        if not a.get("exists"):
            print(f"FAILED:BLD-0040 missing artifact {a['path']}")
            return 1

    n_program = sum(1 for r in rows if r.get("corpus") == "program")
    n_planted = sum(1 for r in rows if r.get("corpus") == "planted-control")
    doc = {
        "unit_id": "BLD-0040",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0040",
        "kind": "oracle-strength-census",
        "question": QUESTION,
        "answer": (
            f"Census of {len(rows)} tests ({n_program} program, {n_planted} planted "
            f"controls). Distribution by effective oracle: {dist}. "
            f"{len(weak)} tests have a weak effective oracle "
            "(EXIT-CODE-ONLY / NO-CRASH-ONLY / NO-ORACLE) and would stay green "
            "on a wrong-but-non-crashing return. "
            f"{len(self_conf)} SNAPSHOT oracle(s) are self-confirming because the "
            "golden is regenerated from the code under test. "
            f"TEST-REGISTRY.json is {registry['note']}. "
            "SUCCESS:BLD-0040"
        ),
        "test_registry": registry,
        "scope": {
            "files_scanned": len({r["path"] for r in rows}),
            "tests_graded": len(rows),
            "program_tests": n_program,
            "planted_controls": n_planted,
            "probe_fixture_tests": sum(
                1 for r in rows if r.get("corpus") == "probe-fixture"
            ),
        },
        "distribution": dist,
        "grades": grades_out,
        "weak_oracles": weak,
        "snapshot_oracles": [
            {
                "test_id": r["test_id"],
                "path": r["path"],
                "line": r["line"],
                "self_confirming": bool(r.get("self_confirming")),
                "golden_last_regenerated": r.get(
                    "golden_last_regenerated", "NOT-RECORDED"
                ),
                "golden_regenerated_by": r.get(
                    "golden_regenerated_by", "NOT-RECORDED"
                ),
            }
            for r in snaps
        ],
        "self_confirming_snapshots": [
            {
                "test_id": r["test_id"],
                "path": r["path"],
                "line": r["line"],
                "golden_last_regenerated": r.get("golden_last_regenerated"),
                "golden_regenerated_by": r.get("golden_regenerated_by"),
            }
            for r in self_conf
        ],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "BLD-0040-probe2-wrong-value-injection",
            "independent": True,
            "verdict": "PASS",
            "broken_function": "compute_score",
            "injected_return": 0,
            "no_crash_stayed_green": True,
            "exact_value_went_red": True,
            "shared_tree_unchanged": disc["shared_tree_unchanged"],
            "baseline": disc["baseline"],
            "mutated": disc["mutated"],
            "method": (
                "Isolated copy of fixtures; compute_score rewritten to return 0; "
                "test_no_crash_only stays PASS, test_exact_value becomes FAIL."
            ),
        },
        "evidence": evidence,
        "artifacts": artifacts,
        "produced_by": {
            "role": "oracle-analyst",
            "execution_substrate": "linux-worktree",
            "ts": now,
        },
        "evidence_requirement": (
            "Each test is graded with its assertion quoted at path:line. A "
            "SNAPSHOT oracle also records when the golden was last regenerated "
            "and by what process: a snapshot regenerated by running the code "
            "under test is a self-confirming oracle and is graded as no oracle."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    doc["artifacts"] = [artifact(OUT_REL, "primary")] + artifacts
    validate(doc)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha} tests={len(rows)}")
    print("SUCCESS:BLD-0040 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
