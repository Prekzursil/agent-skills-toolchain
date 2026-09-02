"""Build the 13-row isolation corpus under tests/fixtures/completion/.

Each fail-k receipt is the all-satisfied control with exactly one mutation.
Sidecar artifacts and per-row manifests are written under runtime/.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import reducer as R

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXDIR = REPO / "tests" / "fixtures" / "completion"
RUNTIME = FIXDIR / "runtime"
UNIT = "ISO-0001"
SENTINEL = f"SUCCESS:{UNIT}"
MIN_BYTES = 128


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def _probes() -> list[dict]:
    return [
        {
            "role": "source",
            "method": "command",
            "command": "python3 -c measure",
            "raw_output": "measured payload.score=42",
            "exit_code": 0,
        },
        {
            "role": "verifier",
            "method": "file-read",
            "command": "read artifact payload.score",
            "raw_output": "score 42 confirmed",
            "exit_code": 0,
        },
    ]


def good_artifact() -> dict:
    return {
        "id": UNIT,
        "type": "completion-subject",
        "payload": {
            "score": 42,
            "note": "padding to exceed the 128-byte min_bytes_threshold " + ("x" * 80),
        },
        "sentinel": SENTINEL,
    }


def write_artifact(row_id: str, doc: dict) -> str:
    rel = f"tests/fixtures/completion/runtime/{row_id}.json"
    dump(REPO / rel, doc)
    return rel


def write_manifest(row_id: str, art_rel: str, sha: str, size: int) -> str:
    rel = f"tests/fixtures/completion/runtime/manifest-{row_id}.json"
    dump(
        REPO / rel,
        {
            "schema_version": 1,
            "contract": "completion-predicate-condition-11-unit-artifact-registration",
            "derivation": "per-row isolation fixture",
            "unit_id": UNIT,
            "verified_on_disk": True,
            "expected": 1,
            "present": 1,
            "artifacts": [
                {
                    "path": art_rel,
                    "sha256": sha,
                    "bytes": size,
                    "present": True,
                    "unit_id": UNIT,
                    "role": "primary",
                }
            ],
        },
    )
    return rel


def base_receipt(row_id: str, art_rel: str, sha: str, size: int, man_rel: str) -> dict:
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [
            {
                "path": art_rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "role": "primary",
                "eol": "LF",
            }
        ],
        "evidence": [
            {
                "claim": "The subject artifact carries payload.score=42.",
                "verdict": "CONFIRMED",
                "anchor": f"{art_rel}:1",
                "probes": _probes(),
            },
            {
                "claim": "The subject artifact parses against artifact.schema.json.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0002/artifact.schema.json:1",
                "probes": _probes(),
            },
        ],
        "tests": [{"id": "t1", "command": "pytest -q", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "c1",
                "kind": "known-broken-fixture",
                "description": "detector fires on the broken tree",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "fixture-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": man_rel,
        },
        "downstream_consumers": [
            {
                "consumer": "TST-0002.reducer._consumer_read",
                "artifact_path": art_rel,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
            }
        ],
        "row_id": row_id,
    }


def _prep(row_id: str, artifact: dict) -> tuple[str, str, int, str]:
    art_rel = write_artifact(row_id, artifact)
    sha, size = digest_file(REPO / art_rel)
    man_rel = write_manifest(row_id, art_rel, sha, size)
    return art_rel, sha, size, man_rel


Mutator = Callable[[dict], None]


def mutations() -> list[tuple[str, int | None, str, Mutator, dict | None]]:
    """(row_id, intended_k_or_None, how, mutator, artifact_or_None_to_use_good)."""
    good = good_artifact()
    no_type = {k: v for k, v in good.items() if k != "type"}
    no_sentinel = dict(good)
    no_sentinel["sentinel"] = "SUCCESS:ISO-9999"
    no_score = copy.deepcopy(good)
    no_score["payload"] = {"note": "schema-valid payload without consumer field"}

    def m1(d: dict) -> None:
        d["state"] = "PARTIAL"

    def m2(d: dict) -> None:
        d["artifacts"][0]["path"] = "tests/fixtures/completion/runtime/ABSENT-ISO.json"
        d["artifacts"][0]["exists"] = True
        d["downstream_consumers"][0]["artifact_path"] = d["artifacts"][0]["path"]

    def m3(d: dict) -> None:
        d["artifacts"][0]["sha256"] = "ab" * 32

    def m4(_d: dict) -> None:
        return

    def m5(d: dict) -> None:
        d["sentinel"] = "SUCCESS:ISO-9999"

    def m6(d: dict) -> None:
        d["evidence"] = d["evidence"][:1]

    def m7(d: dict) -> None:
        d["tests"][0]["result"] = "FAIL"

    def m8(d: dict) -> None:
        d["negative_controls"][0]["fired_on_bad_state"] = False

    def m9(d: dict) -> None:
        d["reviewer"]["verdict"] = "NOT-REVIEWED"

    def m10(d: dict) -> None:
        d["defects"] = [
            {
                "id": "D1",
                "severity": "P0",
                "status": "open",
                "summary": "open blocker attached to a success",
            }
        ]

    def m11(d: dict) -> None:
        d["manifest_registration"]["registered"] = False

    def m12(d: dict) -> None:
        d["downstream_consumers"][0]["read_ok"] = False
        d["downstream_consumers"][0]["executed"] = True

    return [
        ("pass", None, "all 12 conditions satisfied", lambda _d: None, good),
        ("fail-01", 1, "state set to PARTIAL (terminal, not completion)", m1, good),
        (
            "fail-02",
            2,
            "receipt exists=true for a path that is absent on disk",
            m2,
            good,
        ),
        ("fail-03", 3, "declared sha256 disagrees with live bytes", m3, good),
        ("fail-04", 4, "artifact omitted required schema field 'type'", m4, no_type),
        (
            "fail-05",
            5,
            "sentinel and artifact carry SUCCESS:ISO-9999 not SUCCESS:ISO-0001",
            m5,
            no_sentinel,
        ),
        ("fail-06", 6, "evidence reduced to one signal", m6, good),
        ("fail-07", 7, "tests[0].result set to FAIL", m7, good),
        (
            "fail-08",
            8,
            "negative_control.fired_on_bad_state false (inert detector)",
            m8,
            good,
        ),
        ("fail-09", 9, "reviewer.verdict NOT-REVIEWED", m9, good),
        ("fail-10", 10, "OPEN P0 defect attached", m10, good),
        ("fail-11", 11, "manifest_registration.registered false", m11, good),
        (
            "fail-12",
            12,
            "artifact schema-valid but consumer field payload.score absent",
            m12,
            no_score,
        ),
    ]


def ensure_fixtures(repo: Path | None = None) -> list[dict]:
    root = repo or REPO
    FIXDIR.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    schema_dest = FIXDIR / "artifact.schema.json"
    schema_dest.write_text(
        (HERE / "artifact.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    rows = []
    for row_id, intended, how, mut, artifact in mutations():
        art_rel, sha, size, man_rel = _prep(row_id, artifact)
        receipt = base_receipt(row_id, art_rel, sha, size, man_rel)
        mut(receipt)
        receipt["mutation"] = how
        receipt["intended_violation"] = intended
        dump(FIXDIR / f"{row_id}.json", receipt)
        if row_id == "fail-02":
            absent = root / "tests/fixtures/completion/runtime/ABSENT-ISO.json"
            if absent.exists():
                absent.unlink()
        rows.append(
            {
                "row_id": row_id,
                "intended_violation": intended,
                "mutation": how,
                "fixture": f"tests/fixtures/completion/{row_id}.json",
            }
        )
    return rows


def load_receipt(repo: Path, fixture_rel: str) -> dict:
    return json.loads((repo / fixture_rel).read_text(encoding="utf-8"))


def run_corpus(repo: Path | None = None, eval_fn=None) -> list[dict]:
    root = repo or REPO
    meta = ensure_fixtures(root)
    fn = eval_fn or R.evaluate
    out = []
    for row in meta:
        receipt = load_receipt(root, row["fixture"])
        verdict = fn(receipt, root)
        intended = row["intended_violation"]
        unsatisfied = list(verdict.get("unsatisfied") or [])
        if intended is None:
            isolated = (
                verdict.get("verdict") == "PASS"
                and verdict.get("failing_condition_id") is None
                and unsatisfied == []
            )
        else:
            isolated = (
                verdict.get("verdict") == "FAILED"
                and verdict.get("failing_condition_id") == intended
                and unsatisfied == [intended]
            )
        out.append(
            {
                "row_id": row["row_id"],
                "fixture": row["fixture"],
                "mutation": row["mutation"],
                "intended_violation": intended,
                "verdict": verdict.get("verdict"),
                "failing_condition_id": verdict.get("failing_condition_id"),
                "reason": verdict.get("reason"),
                "unsatisfied": unsatisfied,
                "isolated": isolated,
                "conditions": verdict.get("conditions"),
            }
        )
    return out


def coupling_report(rows: list[dict]) -> dict:
    pairs = []
    defects = []
    for row in rows:
        intended = row["intended_violation"]
        if intended is None:
            continue
        extra = [n for n in row["unsatisfied"] if n != intended]
        if extra:
            for n in extra:
                pair = sorted((intended, n))
                if pair not in pairs:
                    pairs.append(pair)
            defects.append(
                {
                    "intended": intended,
                    "also_unsatisfied": extra,
                    "row_id": row["row_id"],
                    "mutation": row["mutation"],
                    "note": (
                        "These conditions could not be violated in isolation on "
                        "this artifact format / reducer pairing."
                    ),
                }
            )
    return {
        "inseparable_pairs": pairs,
        "contract_defects": defects,
        "isolated_count": sum(1 for r in rows if r["intended_violation"] and r["isolated"]),
        "pass_row_ok": next(r["isolated"] for r in rows if r["intended_violation"] is None),
    }


def isolation_ok(rows: list[dict]) -> bool:
    fails = [r for r in rows if r["intended_violation"] is not None]
    pas = next(r for r in rows if r["intended_violation"] is None)
    return (
        len(fails) == 12
        and all(r["isolated"] for r in fails)
        and pas["isolated"] is True
        and {r["failing_condition_id"] for r in fails} == set(range(1, 13))
    )
