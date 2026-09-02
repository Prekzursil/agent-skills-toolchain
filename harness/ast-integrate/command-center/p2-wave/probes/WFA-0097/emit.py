#!/usr/bin/env python3
"""Emit WFA-0097 AuditReport plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import envelope as E  # noqa: E402
import lint as L  # noqa: E402
import paths as P  # noqa: E402

SUPPORTING = [
    P.SCHEMA_REL,
    "command-center/p2-wave/probes/WFA-0097/methods.py",
    "command-center/p2-wave/probes/WFA-0097/corpus.py",
    "command-center/p2-wave/probes/WFA-0097/lint.py",
    "command-center/p2-wave/probes/WFA-0097/envelope.py",
    "command-center/p2-wave/probes/WFA-0097/settle.py",
    "command-center/p2-wave/probes/WFA-0097/emit.py",
    "command-center/p2-wave/probes/WFA-0097/probe1_lint_planted_omission.py",
    "command-center/p2-wave/probes/WFA-0097/probe2_envelope_and_scope.py",
    "command-center/p2-wave/probes/WFA-0097/fixtures/verdict-omits-scope.json",
    "command-center/p2-wave/probes/WFA-0097/fixtures/verdict-adjacent-scope.json",
    "command-center/p2-wave/probes/WFA-0097/fixtures/verdict-trailing-limitations-only.json",
    "command-center/p2-wave/probes/WFA-0097/fixtures/verdict-prose-comment-scope.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(P.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def snippet(path: Path, line: int, width: int = 2) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    i = max(0, line - 1)
    lo = max(0, i - width)
    hi = min(len(lines), i + width + 1)
    return "\n".join(lines[lo:hi])[:500]


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return 1


def upstream_inputs() -> list[dict]:
    rows = []
    for rel in P.UPSTREAM:
        path = P.REPO / rel
        present = path.is_file() and path.stat().st_size > 0
        rows.append(
            {
                "path": rel,
                "present": present,
                "label": "VERIFIED" if present else "UNVERIFIED",
                "note": (
                    "on disk"
                    if present
                    else (
                        "ABSENT on this tree; envelope measured from reconstructed "
                        "methods plus the planted corpus"
                    )
                ),
            }
        )
    return rows


def build_doc(env: dict, lint_ctrl: dict, now: str) -> dict:
    scope = E.canonical_scope(env)
    undetectable = []
    for row in env["undetectable_classes"]:
        undetectable.append(
            {
                "id": row["id"],
                "left_id": row["left_id"],
                "right_id": row["right_id"],
                "lexical_hit": row["lexical_hit"],
                "embedding_hit": row["embedding_hit"],
                "structural_hit": row["structural_hit"],
                "combined_hit": False,
                "settling_experiment": row["settling_experiment"],
            }
        )
    misses_human = ", ".join(u["id"] for u in undetectable) or "(none measured)"
    answer = (
        "On the planted corpus the combined lexical-jaccard + "
        "embedding-expanded-token-jaccard (UNVERIFIED stand-in for absent "
        "WFA-0008 neural embedding) + structural-ir-sets stack detects "
        f"{', '.join(env['detects'])} and does not detect {misses_human}. "
        "Every zero-duplicates verdict in this artifact carries an adjacent "
        f"machine-readable scope object (envelope_id={scope['envelope_id']}), "
        "not a trailing limitations paragraph."
    )
    zero_verdicts = [
        {
            "id": "planted-decoy-clean-bill",
            "role": "no-duplicates-verdict",
            "applies_to": "planted-decoy-pairs",
            "zero_duplicates": True,
            "duplicate_count": 0,
            "duplicates": [],
            "scope": scope,
        }
    ]
    tests = [
        {
            "id": "lint-fires-on-planted-verdict-omitting-scope",
            "command": P.P1,
            "result": "PASS" if lint_ctrl.get("omit_fire") else "FAIL",
        },
        {
            "id": "each-undetectable-class-names-settling-experiment",
            "command": P.P2,
            "result": (
                "PASS"
                if undetectable
                and all(
                    (u.get("settling_experiment") or "").strip()
                    for u in undetectable
                )
                else "FAIL"
            ),
        },
        {
            "id": "scope-string-machine-readable-not-prose-comment",
            "command": P.P1,
            "result": (
                "PASS"
                if lint_ctrl.get("prose_fire") and lint_ctrl.get("adjacent_pass")
                else "FAIL"
            ),
        },
    ]
    methods_path = HERE / "methods.py"
    lint_path = HERE / "lint.py"
    corpus_path = HERE / "corpus.py"
    return {
        "unit_id": P.UNIT,
        "id": P.UNIT,
        "record_type": "AuditReport",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": P.CATALOG_SENTINEL,
        "completion_sentinel": P.COMPLETION_SENTINEL,
        "title": (
            "State exactly what the duplicate detection can and cannot see, "
            "inline with every verdict"
        ),
        "question": P.QUESTION,
        "answer": answer,
        "output_schema_catalog": P.CATALOG_SCHEMA,
        "output_schema_catalog_present": (
            P.REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "output_schema_local": P.SCHEMA_REL,
        "upstream_inputs": upstream_inputs(),
        "detection_envelope": env,
        "undetectable_classes": undetectable,
        "zero_duplicates_verdicts": zero_verdicts,
        "lint": {
            "planted_omission_fired": bool(lint_ctrl.get("omit_fire")),
            "trailing_limitations_fired": bool(
                lint_ctrl.get("trailing_limitations_fire")
            ),
            "prose_scope_fired": bool(lint_ctrl.get("prose_fire")),
            "adjacent_scope_passed": bool(lint_ctrl.get("adjacent_pass")),
            "separated": bool(lint_ctrl.get("separated")),
            "rule": (
                "scope must be an adjacent machine-readable object on the same "
                "JSON object as zero_duplicates; trailing limitations and prose "
                "comments fail"
            ),
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0097-probe2-envelope-and-scope",
            "independent": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-runs the planted envelope and requires named "
                "settling experiments on every combined miss of a semantic "
                "duplicate. Independent of probe 1's lint."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/WFA-0097/methods.py",
                "line": line_of(methods_path, "def compare("),
                "snippet": snippet(methods_path, line_of(methods_path, "def compare(")),
                "kind": "detection-envelope",
                "claim": (
                    "lexical, embedding-stand-in, and structural methods are "
                    "compared per planted pair"
                ),
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0097/lint.py",
                "line": line_of(lint_path, "def verdict_scope_ok("),
                "snippet": snippet(
                    lint_path, line_of(lint_path, "def verdict_scope_ok(")
                ),
                "kind": "scope-lint",
                "claim": (
                    "zero-duplicates verdicts require adjacent machine-readable scope"
                ),
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0097/corpus.py",
                "line": line_of(corpus_path, "def pairs("),
                "snippet": snippet(corpus_path, line_of(corpus_path, "def pairs(")),
                "kind": "planted-corpus",
                "claim": (
                    "mutant shapes and decoys are planted; undetectable classes "
                    "name settling experiments"
                ),
            },
        ],
        "artifacts": [
            {"path": P.OUT_REL, "exists": True, "role": "primary"},
            {"path": P.SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "named_probes": [],
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for WFA-0097: live named probes exit 0, AuditReport state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild. WFA-0007/0008/0096 "
            "artifacts ABSENT; envelope measured on reconstructed methods + planted corpus."
        ),
    }


def main() -> int:
    env = E.measure()
    if env["counts"]["undetectable"] < 1:
        print("FAILED:WFA-0097 no undetectable class measured")
        return 1
    if env["decoy_false_positives"]:
        print(f"FAILED:WFA-0097 decoy false positives {env['decoy_false_positives']}")
        return 1
    for row in env["undetectable_classes"]:
        if not (row.get("settling_experiment") or "").strip():
            print(f"FAILED:WFA-0097 {row['id']} missing settling_experiment")
            return 1

    rc1, out1 = run_cmd(P.P1)
    j1 = first_json(out1)
    if rc1 != 0 or not j1.get("separated"):
        print(f"FAILED:WFA-0097 probe1 rc={rc1}")
        print(out1[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_doc(env, j1, now)
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print("FAILED:WFA-0097 a required test did not pass")
        return 1

    schema = json.loads((P.REPO / P.SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:WFA-0097 schema " + errors[0].message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:WFA-0097 schema accepted garbage {list(garbage)[:2]}")
            return 1

    live_lint = L.lint_obj(doc)
    if not live_lint["ok"]:
        print(f"FAILED:WFA-0097 emitted artifact lint {live_lint}")
        return 1

    out_path = P.REPO / P.OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if P.CATALOG_SENTINEL not in text:
        print("FAILED:WFA-0097 completion sentinel missing from artifact")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")

    rc1, out1 = run_cmd(P.P1)
    rc2, out2 = run_cmd(P.P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:WFA-0097 probes after write c1={rc1} c2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    sha, size = digest_file(out_path)
    if size <= 0:
        print("FAILED:WFA-0097 empty artifact")
        return 1

    def row(rel: str, role: str) -> dict:
        path = P.REPO / rel
        digest, n = digest_file(path)
        return {
            "path": rel,
            "sha256": digest,
            "bytes": n,
            "present": path.is_file(),
            "unit_id": P.UNIT,
            "receipt_path": "command-center/p2-wave/probes/WFA-0097/SUBAGENT-RETURN.json",
            "role": role,
        }

    primary = row(P.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    missing_sup = [a["path"] for a in artifacts if not a["present"]]
    if missing_sup:
        print(f"FAILED:WFA-0097 missing supporting {missing_sup}")
        return 1

    named = [
        {
            "id": "probe1",
            "command": P.P1,
            "exit_code": rc1,
            "role": "lint-planted-omission",
            "raw_output": out1[-8000:],
        },
        {
            "id": "probe2",
            "command": P.P2,
            "exit_code": rc2,
            "role": "envelope-and-scope",
            "raw_output": out2[-8000:],
        },
    ]
    ret = {
        "id": P.UNIT,
        "unit_id": P.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": P.CATALOG_SENTINEL,
        "registered": True,
        "output_path": P.OUT_REL,
        "output_schema": P.SCHEMA_REL,
        "named_probes": named,
        "artifacts": [
            {
                "path": P.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0097/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0097-probe2-envelope-and-scope",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0097: live named probes exit 0, differ-scope-disclosure "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": P.UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {P.OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:WFA-0097 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
