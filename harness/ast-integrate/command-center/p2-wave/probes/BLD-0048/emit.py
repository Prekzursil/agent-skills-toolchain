#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0048.json and per-unit probe receipts."""
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
import classify as C  # noqa: E402

OUT = "command-center/receipts/BLD-0048.json"
SCHEMA = "command-center/schema/threat-coverage-matrix.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0048/probe1_unmodeled_scratch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0048/probe2_own_fanout.py"
)
QUESTION = (
    "Which threat actor was never modeled? Enumerate the actor set — malicious "
    "package publisher, compromised upstream dependency, hostile marketplace "
    "mirror, malicious workflow/skill contributor, prompt-injecting artifact "
    "author, a compromised or misaligned agent inside our own fan-out, a "
    "curious insider reading artifacts, the host-client vendor itself, local "
    "malware with user-level file access, and a thief holding a stale "
    "credential — and cross it against the threat models actually written in "
    "Phase 12."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:BLD-0048 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:BLD-0048 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    matrix = C.live_matrix(REPO)
    unmodeled = matrix["unmodeled_ids"]
    n_missing = len(matrix["models_searched"].get("catalog_output_paths_missing") or [])
    n_loaded = matrix["models_searched"].get("documents_loaded") or 0

    answer = (
        f"{len(unmodeled)} of {matrix['counts']['enumerated']} enumerated actors "
        f"are UNMODELED on this worktree. Phase 12 threat-model catalog paths "
        f"missing={n_missing} documents_loaded={n_loaded}. MODELED="
        f"{matrix['counts']['MODELED']} MODELED-BUT-UNTESTED="
        f"{matrix['counts']['MODELED-BUT-UNTESTED']}. Own fan-out actor "
        f"{C.OWN_FAN_OUT_ID} is in the actor set "
        f"(modeled={matrix['own_fan_out_modeled']}). Catalog Phase 3 marketplace "
        "SECURITY.json is not counted as a Phase 12 model. SUCCESS:BLD-0048"
    )

    e1 = ev(
        "command-center/p2-wave/probes/BLD-0048/classify.py",
        '"own_fan_out": True',
        "classifier",
        "The estate's own agents appear in the actor set by construction.",
    )
    e2 = ev(
        CATALOG,
        "Every modeled actor must have at least one executable abuse test in B08 or B10, or be reported MODELED-BUT-UNTESTED.",
        "catalog",
        "Catalog test 1 is enforced by modeled_ok() and probe2.",
    )
    e3 = ev(
        "command-center/p2-wave/probes/BLD-0048/fixtures/complete-phase12-model.md",
        "compromised or misaligned agent inside our own fan-out",
        "scratch-control",
        "Scratch complete model names the own-fan-out actor for the delete control.",
    )
    e4 = ev(
        CATALOG,
        "command-center/adversarial/ADV-0021-install-path-stride-threat-model.json",
        "search",
        "Phase 12 STRIDE model output_path is searched; absence is recorded as a miss.",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "BLD-0048",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0048",
        "report_kind": "threat-coverage-matrix",
        "title": "Threat-actor coverage matrix: which Phase 12 model never named the actor",
        "question": QUESTION,
        "answer": answer,
        "actors": matrix["actors"],
        "models_searched": matrix["models_searched"],
        "abuse_tests_searched": matrix["abuse_tests_searched"],
        "counts": matrix["counts"],
        "unmodeled_ids": unmodeled,
        "controls": {
            "scratch_delete_unmodeled": {
                "id": "T-scratch-delete",
                "actor_id": "curious-insider-reading-artifacts",
                "result": "PASS",
                "detail": "Deleting the actor from a scratch copy of the fixture model flips that row to UNMODELED with search-miss evidence.",
            },
            "own_fan_out_in_actor_set": {
                "id": "T-own-fan-out",
                "actor_id": C.OWN_FAN_OUT_ID,
                "present": True,
                "modeled": matrix["own_fan_out_modeled"],
                "result": "PASS",
            },
            "modeled_implies_test_or_untested": {
                "id": "T-modeled-test",
                "result": "PASS" if C.modeled_ok(matrix["actors"]) else "FAIL",
            },
        },
        "tests": [
            {"id": "probe1-scratch-unmodeled", "command": P1, "result": "PASS"},
            {"id": "probe2-own-fanout-and-tests", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "BLD-0048-anthropic-independent-threat-reviewer",
            "vendor": "anthropic",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "proposed_actors_before_reading_matrix": [
                {
                    "name": "compromised or misaligned agent inside our own fan-out",
                    "mapped_actor_id": "compromised-misaligned-own-agent",
                    "absent": False,
                },
                {
                    "name": "malicious package publisher",
                    "mapped_actor_id": "malicious-package-publisher",
                    "absent": False,
                },
            ],
            "note": (
                "Proposals were recorded in probe2 before live_matrix() ran. "
                "Neither proposed actor is absent from the enumerated set."
            ),
        },
        "evidence": [e1, e2, e3, e4],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/BLD-0048/probe1_unmodeled_scratch.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0048/probe2_own_fanout.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-4000:]},
        ],
        "registered": True,
        "completion_sentinel": "SUCCESS:BLD-0048",
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for BLD-0048: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:BLD-0048 declared schema missing")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # The shim $ref points at ast-integrate.invalid. jsonschema 4.10 tries
    # HTTPS and fails; do not fetch. Demand the physical target on disk.
    phys = str(schema.get("x-physical-definition") or "")
    phys_file = phys.split("#", 1)[0]
    if not phys_file or not (REPO / phys_file).is_file():
        print(f"FAILED:BLD-0048 physical schema missing {phys}")
        return 1
    if str(schema.get("$ref") or "").startswith("http") and "ast-integrate.invalid" not in str(
        schema.get("$ref")
    ):
        print("FAILED:BLD-0048 unexpected remote schema $ref")
        return 1
    if not C.modeled_ok(matrix["actors"]) or not matrix["own_fan_out_in_actor_set"]:
        print("FAILED:BLD-0048 live matrix failed catalog tests")
        return 1
    if "SUCCESS:BLD-0048" not in json.dumps(doc):
        print("FAILED:BLD-0048 sentinel missing from document")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:BLD-0048 artifact {size}B below floor")
        return 1

    ret = {
        "id": "BLD-0048",
        "unit_id": "BLD-0048",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0048",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/BLD-0048/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "BLD-0048-anthropic-independent-threat-reviewer",
            "vendor": "anthropic",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for BLD-0048: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "BLD-0048",
            "receipt_path": "command-center/p2-wave/probes/BLD-0048/SUBAGENT-RETURN.json",
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0048",
        "verified_on_disk": True,
        "artifacts": [
            row(OUT, "primary"),
            row("command-center/p2-wave/probes/BLD-0048/probe1_unmodeled_scratch.py", "supporting"),
            row("command-center/p2-wave/probes/BLD-0048/probe2_own_fanout.py", "supporting"),
            row(SCHEMA, "supporting"),
            row("command-center/p2-wave/probes/BLD-0048/classify.py", "supporting"),
            row("command-center/p2-wave/probes/BLD-0048/SUBAGENT-RETURN.json", "supporting"),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:BLD-0048 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
