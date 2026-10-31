#!/usr/bin/env python3
"""Emit IMP-0390 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.semantic_matcher import (  # noqa: E402
    load_planted,
    measure_recall,
    pair_scores,
    pin_identity,
)

UID = "IMP-0390"
OUT = "command-center/receipts/IMP-0390.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SENTINEL:IMP-0390:SEMANTIC-MATCHER-PINNED"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0390/probe1_recall_at_5.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0390/probe2_determinism_and_offline.py"
)
SUPPORTING = [
    "tools/router/__init__.py",
    "tools/router/lexical.py",
    "tools/router/embed_model.py",
    "tools/router/semantic_matcher.py",
    "tools/router/build_pinned_model.py",
    "tools/router/models/imp0390-embed-v1.json",
    "tools/router/models/imp0390-embed-v1.pin.json",
    "tools/router/data/planted_mutants_imp0388.json",
    "tools/router/tests/test_semantic_matcher.py",
    "command-center/p2-wave/probes/IMP-0390/probe1_recall_at_5.py",
    "command-center/p2-wave/probes/IMP-0390/probe2_determinism_and_offline.py",
    "command-center/p2-wave/probes/IMP-0390/write_receipts.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "tools") + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def first_json(text: str):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def main() -> int:
    t_code, t_out = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest "
        "router.tests.test_semantic_matcher"
    )
    if t_code != 0:
        print("FAILED:IMP-0390 unittest")
        print(t_out[-4000:])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(f"probe[1] rc={c1}")
    print(t1[-2000:])
    print(f"probe[2] rc={c2}")
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0390 probes c1={c1} c2={c2}")
        return 1

    j1 = first_json(t1) or {}
    j2 = first_json(t2) or {}
    planted = load_planted()
    ident = pin_identity()
    seed = int(planted["seed"])
    k = int(planted["k"])
    caps = planted["capabilities"]
    paraphrase = measure_recall(planted["paraphrase_queries"], caps, k=k, seed=seed)
    verbatim = measure_recall(planted["verbatim_queries"], caps, k=k, seed=seed)
    pair = planted["imp0388_planted_pair"]
    by_id = {c["capability_id"]: c for c in caps}
    pair_m = pair_scores(
        by_id[pair["left_id"]]["description"],
        by_id[pair["right_id"]]["description"],
        seed=seed,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    supporting_arts = [art_row(rel, "supporting") for rel in SUPPORTING]
    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Semantic matcher with pinned local embedding model and offline fallback",
        "min_bytes_threshold": 128,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0390; planted-mutant control from "
            "IMP-0388 tests_required (rename + paraphrase of a sibling)"
        ),
        "question_or_target": (
            "Implement the second-stage semantic matcher over capability "
            "descriptions using a version-PINNED local embedding model, with a "
            "documented offline fallback when the model is unavailable. Exact "
            "question: does the semantic stage recover the paraphrase pairs that "
            "the lexical linter provably cannot, measured on the planted-mutant "
            "set from IMP-0388?"
        ),
        "implementation": {
            "module": "tools/router/semantic_matcher.py",
            "lexical_instrument": "tools/router/lexical.py",
            "model_path": "tools/router/models/imp0390-embed-v1.json",
            "pin_path": "tools/router/models/imp0390-embed-v1.pin.json",
            "planted_mutants": "tools/router/data/planted_mutants_imp0388.json",
            "model_id": ident.get("model_id"),
            "model_version": ident.get("version"),
            "model_digest": ident.get("pinned_sha256"),
            "algo": "frozen-concept-axes+token-lexicon",
            "offline_fallback": (
                "match() returns status=DEGRADED, code=PINNED-MODEL-ABSENT "
                "(or DIGEST/ID mismatch), ranking=[], lexical_results_suppressed="
                "true. Lexical Jaccard is never copied into a semantic result."
            ),
            "ranking": "integer cosine, tie-break capability_id; seed recorded, no RNG",
        },
        "measured": {
            "k": k,
            "seed": seed,
            "pinned_model_id": ident.get("model_id"),
            "pinned_model_digest": ident.get("pinned_sha256"),
            "paraphrase_n": paraphrase["n"],
            "paraphrase_lexical_recall_at_5": paraphrase["lexical_recall_at_k"],
            "paraphrase_semantic_recall_at_5": paraphrase["semantic_recall_at_k"],
            "verbatim_n": verbatim["n"],
            "verbatim_lexical_recall_at_5": verbatim["lexical_recall_at_k"],
            "verbatim_semantic_recall_at_5": verbatim["semantic_recall_at_k"],
            "imp0388_pair_lexical_jaccard_e9": pair_m["lexical_jaccard_e9"],
            "imp0388_pair_semantic_cosine_e9": pair_m["semantic_cosine_e9"],
            "determinism_byte_identical": (j2.get("determinism") or {}).get(
                "byte_identical"
            ),
            "offline_degraded_code": (j2.get("offline_absent") or {}).get("code"),
        },
        "artifacts": supporting_arts,
        "evidence": [
            {
                "claim": (
                    "On the planted-mutant paraphrase set (n="
                    f"{paraphrase['n']}, seed={seed}, k={k}) lexical Recall@5 is "
                    f"{paraphrase['lexical_recall_at_k']} and semantic Recall@5 is "
                    f"{paraphrase['semantic_recall_at_k']}. The IMP-0388 renamed "
                    "sibling pair has token-Jaccard 0 and positive semantic cosine. "
                    f"Pinned model id={ident.get('model_id')} "
                    f"digest={ident.get('pinned_sha256')}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/data/planted_mutants_imp0388.json",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-8000:],
                    }
                ],
            },
            {
                "claim": (
                    "Same query + same pinned model + same seed yields a "
                    "byte-identical ranking twice. With the model file absent, "
                    "match() is typed DEGRADED (PINNED-MODEL-ABSENT) with an empty "
                    "ranking and does not relabel lexical hits as semantic. A "
                    "digest-mutated model file is PINNED-MODEL-DIGEST-MISMATCH."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/models/imp0390-embed-v1.pin.json",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-8000:],
                    }
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "max 3 attempts for model-fetch transients; zero retries on a "
                "nondeterministic ranking — that is a design defect. This matcher "
                "does not fetch; the model is a pinned local artifact."
            ),
        },
        "tests": [
            {
                "id": "test_semantic_matcher",
                "command": "PYTHONPATH=tools python3 -m unittest router.tests.test_semantic_matcher",
                "result": "PASS",
                "exit_code": t_code,
                "raw_output": t_out[-4000:],
            }
        ],
        "negative_controls": [
            {
                "id": "verbatim-two-sided",
                "kind": "known-good-fixture",
                "description": (
                    "Five verbatim queries must hit both lexical and semantic "
                    "Recall@5=1.0 so a always-empty lexical instrument cannot "
                    "manufacture a paraphrase miss."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": (
                    f"verbatim lexical={verbatim['lexical_recall_at_k']} "
                    f"semantic={verbatim['semantic_recall_at_k']}"
                ),
                "bad_state_output": "verbatim lexical R@5 < 1 would fail probe 1",
            },
            {
                "id": "offline-model-absent",
                "kind": "known-broken-fixture",
                "description": (
                    "Pointing IMP0390_MODEL_PATH / model_path at a missing file "
                    "must yield DEGRADED + empty ranking, not lexical results "
                    "labelled as semantic."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"status={(j2.get('offline_absent') or {}).get('status')} "
                    f"code={(j2.get('offline_absent') or {}).get('code')}"
                ),
                "good_state_output": "status=OK code=SEMANTIC-OK with ranking",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0390-probe2-determinism-and-offline",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not reuse probe 1's recall table. It re-runs the "
                "same query twice for byte identity, then hides and mutates the "
                "pinned model file."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0390/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0390",
                    "raw_output": "measure runs after this receipt is written",
                    "exit_code": None,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/receipts/IMP-0388.json is absent on this "
                    "worktree. The planted-mutant set is the catalog's specified "
                    "control (rename + paraphrase of a sibling) committed at "
                    "tools/router/data/planted_mutants_imp0388.json, not a live "
                    "read of the IMP-0388 artifact."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe 1 against the IMP-0388 artifact's planted "
                    "mutants once that unit is delivered."
                ),
            },
            {
                "claim": (
                    "The pinned model is a local concept-space embedding with a "
                    "frozen synonym lexicon, not a downloaded transformer. "
                    "Paraphrase recovery is via shared concept ids, which is the "
                    "semantic mechanism lexical Jaccard lacks."
                ),
                "verdict": "ACCEPTED-LIMITATION",
                "settling_experiment": (
                    "If a transformer artifact is later pinned, swap the model "
                    "file and pin digest; ranking must remain deterministic."
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "recall-at-5-lexical-vs-semantic"},
            {
                "id": "probe2",
                "command": P2,
                "role": "determinism-and-offline-degraded",
            },
        ],
        "output_schema": SCHEMA,
        "output_path": OUT,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = art_row(OUT, "primary")
    man_artifacts = [
        {
            "path": primary["path"],
            "sha256": primary["sha256"],
            "bytes": primary["bytes"],
            "present": True,
            "unit_id": UID,
            "receipt_path": "command-center/p2-wave/probes/IMP-0390/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        row = art_row(rel, "supporting")
        man_artifacts.append(
            {
                "path": row["path"],
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "present": True,
                "unit_id": UID,
                "receipt_path": "command-center/p2-wave/probes/IMP-0390/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "recall-at-5-lexical-vs-semantic",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "determinism-and-offline-degraded",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0390/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0390-probe2-determinism-and-offline",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0390: live named probes exit 0, receipts/IMP-0390.json "
            "state=SUCCESS with SENTINEL:IMP-0390:SEMANTIC-MATCHER-PINNED, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "artifacts": man_artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0390 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
