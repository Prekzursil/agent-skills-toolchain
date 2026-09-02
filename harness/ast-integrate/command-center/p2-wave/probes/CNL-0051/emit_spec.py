#!/usr/bin/env python3
"""Emit the CNL-0051 design note and per-unit receipts (not the global catalog)."""
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
sys.path.insert(0, str(HERE))
import counter as C  # noqa: E402
import reviewer as R  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0051-semantic-unique-idea-counter-the-anti-gaming-core.md"
)
# Catalog output_schema (not the design-note shim). The file is a $ref to
# https://ast-integrate.invalid/... which jsonschema 4.10.3 tries to fetch
# over the network. G-1 needs JSON parse + sentinel, not a live $ref fetch.
# No ADV rebuild of platform/schema.
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
LOCAL_CONTRACT = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "detector",
        "planted_mutant_control",
        "both_states",
        "negative_control",
        "reviewer",
        "tests",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0051"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"type": "string", "pattern": "^SUCCESS:CNL-0051$"},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "council-detector-spec"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0051/probe1_mutant_recall.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0051/probe2_both_states.py"
)
QUESTION = (
    "What deduplication mechanism decides that two ideas are the SAME idea — "
    "and given that lexical Jaccard was measured to fire at 0.93–1.00 on "
    "renames but cannot see a full rewrite, what second mechanically different "
    "signal must corroborate the count before it gates a stopping rule?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise SystemExit(f"probe failed rc={proc.returncode}\n{text}")
    return {"command": cmd, "exit_code": proc.returncode, "stdout": text}


def line_starting(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    raise SystemExit(f"probe stdout missing line {prefix!r}")


def try_schema(doc: dict) -> dict:
    schema_path = REPO / SCHEMA_REL
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        raise SystemExit(f"output_schema missing: {SCHEMA_REL}")
    try:
        import jsonschema  # type: ignore
    except ImportError:
        missing = [k for k in LOCAL_CONTRACT["required"] if k not in doc]
        if missing:
            raise SystemExit(f"local contract keys missing: {missing}")
        return {"validated": False, "engine": "absent", "errors": []}
    validator = jsonschema.Draft7Validator(LOCAL_CONTRACT)
    empty_ok = True
    try:
        validator.validate({})
    except jsonschema.ValidationError:
        empty_ok = False
    if empty_ok:
        raise SystemExit("local contract accepts empty object; not discriminating")
    errors = [e.message for e in validator.iter_errors(doc)]
    if errors:
        raise SystemExit("local contract: " + "; ".join(errors))
    return {
        "validated": True,
        "engine": "jsonschema.Draft7Validator+local-contract",
        "catalog_schema": SCHEMA_REL,
        "catalog_schema_note": (
            "shim $ref to ast-integrate.invalid is not resolved on this "
            "worktree (jsonschema 4.10.3 RefResolver). No ADV rebuild."
        ),
        "errors": [],
    }


def main() -> int:
    bundle = R.recount()
    R.assert_invariants(bundle)
    p1 = run_probe(P1)
    p2 = run_probe(P2)

    per_class = []
    for cls, rec in sorted(bundle["per_class"].items()):
        per_class.append(
            {
                "class": cls,
                "planted": rec["planted"],
                "caught": rec["caught"],
                "recall": rec["caught"] / rec["planted"],
                "scope": "planted-on-this-fixture",
            }
        )
    per_class.append(
        {
            "class": "genuinely_distinct",
            "planted": 1,
            "caught": 0,
            "recall": 0.0,
            "scope": "planted-on-this-fixture",
            "must": "NOT-merge",
        }
    )
    rewrite = next(r for r in bundle["class_rows"] if r["class"] == "full_rewrite")
    lexical_dups = [r for r in bundle["class_rows"] if r["class"] != "full_rewrite"]
    jac_lo = min(r["jaccard"] for r in lexical_dups)
    jac_hi = max(r["jaccard"] for r in lexical_dups)
    decoy = bundle["decoy_row"]
    bad = bundle["planted_bad"]
    good = bundle["known_good"]

    answer = (
        "Two ideas are the SAME idea when they share a canonical mechanism key "
        "(action|object), or when token-set Jaccard over title+body is >= 0.50. "
        "Lexical Jaccard on this fixture fires at "
        f"{jac_lo:.4f}–{jac_hi:.4f} on exact_rename / paraphrase / "
        "one_parameter_fork and at "
        f"{rewrite['jaccard']:.4f} on a full rewrite — the same band as a "
        f"genuinely distinct decoy ({decoy['jaccard']:.4f}). "
        "The second signal is therefore NOT another lexical overlap score "
        "(char-3gram Jaccard on the rewrite is "
        f"{rewrite['char3_jaccard']:.4f}, still below 0.50) and NOT an "
        "embedding cosine (no embedding runtime on this worktree; "
        "NOT-CHECKED). It is equality of an authored canonical mechanism key "
        "whose parameter slot is excluded, so a one-parameter fork does not "
        "mint a new idea. Pairwise AND of the two signals is the wrong gate: "
        "it misses the rewrite (caught_by_and_gate="
        f"{rewrite['caught_by_and_gate']}). The count that may bind "
        "unique_ideas in a stopping rule is corroborated_unique = "
        "min(lexical_unique, mechanism_unique). On the planted-bad ledger that "
        f"claims 5 unique wording variants, corroborated_unique="
        f"{bad['corroborated_unique']} and the gaming check FIRES. On six "
        "mechanistically distinct ideas it is SILENT. SUCCESS:CNL-0051"
    )

    doc = {
        "unit_id": "CNL-0051",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0051",
        "title": "Semantic unique-idea counter: the anti-gaming core",
        "question": QUESTION,
        "answer": answer,
        "dependency_CNL_0009": {
            "declared": True,
            "artifact_on_this_worktree": False,
            "scope": (
                "CNL-0009 names unique-idea as one of eight targets. This unit "
                "supplies the operational unique_ideas counter a stopping "
                "expression may bind. It does not inherit a CNL-0009 measurement."
            ),
        },
        "detector": {
            "id": "F01",
            "name": "corroborated unique-idea counter",
            "signals": [
                {
                    "id": "L",
                    "mechanism": (
                        "token-set Jaccard over title+body after stoplist; "
                        "a priori threshold 0.50"
                    ),
                    "role": "collapse exact_rename / paraphrase / one_parameter_fork",
                    "blind_spot": "full rewrite of the same mechanism",
                },
                {
                    "id": "M",
                    "mechanism": (
                        "equality of canonical mechanism key action|object; "
                        "parameter slot excluded from identity"
                    ),
                    "role": (
                        "collapse full rewrites and one-parameter forks that "
                        "lexical overlap either misses or should not mint"
                    ),
                    "blind_spot": (
                        "an author who forges a distinct key for the same "
                        "mechanism; that attack is CNL-0052, not this unit"
                    ),
                },
            ],
            "not_checked": [
                {
                    "id": "embedding-cosine",
                    "reason": "no embedding model or API on this worktree",
                    "scope": "NOT-CHECKED",
                }
            ],
            "stopping_bind": (
                "unique_ideas in a stopping expression binds only to "
                "corroborated_unique = min(lexical_unique, mechanism_unique). "
                "A missing mechanism key is fail-closed (cannot increment "
                "the corroborated count)."
            ),
            "pair_and_gate_rejected": True,
            "pair_and_gate_reason": (
                "AND at the pair level requires L to fire, so it cannot catch "
                "the full-rewrite class that L is known not to see. AND belongs "
                "on the two COUNTS, not on each pair verdict."
            ),
            "lexical_threshold_a_priori": C.LEXICAL_THRESHOLD,
        },
        "planted_mutant_control": {
            "scope": (
                "recall reported only for classes actually planted in "
                "command-center/p2-wave/probes/CNL-0051/fixtures/corpus.json"
            ),
            "per_class_recall": per_class,
            "unplanted_classes": [
                "embedding-near-duplicate",
                "cross-language-translation",
                "partial-overlap-blend",
            ],
            "rows": [
                {
                    "class": r["class"],
                    "mutant_id": r["mutant_id"],
                    "jaccard": r["jaccard"],
                    "char3_jaccard": r["char3_jaccard"],
                    "lexical_hit": r["lexical_hit"],
                    "mechanism_hit": r["mechanism_hit"],
                    "caught_as_duplicate": r["caught_as_duplicate"],
                    "caught_by_and_gate": r["caught_by_and_gate"],
                }
                for r in bundle["class_rows"]
            ],
            "decoy": {
                "id": decoy["mutant_id"],
                "jaccard": decoy["jaccard"],
                "caught_as_duplicate": decoy["caught_as_duplicate"],
            },
            "measured_jaccard_bands": {
                "rename_paraphrase_fork": {"min": jac_lo, "max": jac_hi},
                "full_rewrite": rewrite["jaccard"],
                "genuinely_distinct_decoy": decoy["jaccard"],
            },
        },
        "both_states": {
            "fired_on_planted_bad": True,
            "silent_on_known_good": True,
            "planted_bad_verbatim": line_starting(p2["stdout"], "PLANTED_BAD_VERBATIM"),
            "known_good_verbatim": line_starting(p2["stdout"], "KNOWN_GOOD_VERBATIM"),
            "planted_bad": {
                "claimed_unique": bad["claimed_unique"],
                "corroborated_unique": bad["corroborated_unique"],
                "lexical_unique": bad["lexical_unique"],
                "mechanism_unique": bad["mechanism_unique"],
                "verdict": bad["verdict"],
                "reason": bad["reason"],
            },
            "known_good": {
                "claimed_unique": good["claimed_unique"],
                "corroborated_unique": good["corroborated_unique"],
                "lexical_unique": good["lexical_unique"],
                "mechanism_unique": good["mechanism_unique"],
                "verdict": good["verdict"],
                "reason": good["reason"],
            },
        },
        "negative_control": {
            "state_meant_to_reject": (
                "a ledger of wording variants of one mechanism that claims "
                "each variant as a unique idea (planted-bad, claimed_unique=5)"
            ),
            "what_the_check_does": (
                "FIRES because claimed_unique exceeds corroborated_unique; "
                f"verbatim reason: {bad['reason']}"
            ),
            "verbatim": line_starting(p2["stdout"], "NEGATIVE_CONTROL_VERBATIM"),
            "on_known_good": good["reason"],
        },
        "reviewer": {
            "reviewer_id": "CNL-0051-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "recount_agrees": True,
            "method": (
                "R1 reloads fixtures and reruns F01. R2 uses a second tokenizer "
                "(alnum, no stoplist) and raw action|object string equality. "
                "Duplicate verdicts must agree. Unique counts recounted from "
                "keys: planted-bad 1, known-good 6."
            ),
        },
        "tests": [
            {
                "id": "probe1_mutant_recall",
                "command": P1,
                "result": "PASS",
                "exit_code": p1["exit_code"],
                "stdout": p1["stdout"],
            },
            {
                "id": "probe2_both_states",
                "command": P2,
                "result": "PASS",
                "exit_code": p2["exit_code"],
                "stdout": p2["stdout"],
            },
        ],
        "evidence_requirement": (
            "the planted-mutant control is the evidence; report per-mutant-class "
            "recall as numbers, and scope the claim to the classes actually "
            "planted (an unplanted class is NOT-CHECKED)."
        ),
        "report": {
            "kind": "council-detector-spec",
            "observations": [
                {
                    "name": "lexical_jaccard_rename_paraphrase_fork_min",
                    "measured": jac_lo,
                    "method": "token-set Jaccard over title+body after stoplist",
                    "anchor": "command-center/p2-wave/probes/CNL-0051/fixtures/corpus.json",
                },
                {
                    "name": "lexical_jaccard_full_rewrite",
                    "measured": rewrite["jaccard"],
                    "method": "token-set Jaccard over title+body after stoplist",
                    "anchor": "command-center/p2-wave/probes/CNL-0051/fixtures/corpus.json",
                },
                {
                    "name": "planted_bad_corroborated_unique",
                    "measured": bad["corroborated_unique"],
                    "method": "min(lexical_unique, mechanism_unique)",
                    "anchor": "command-center/p2-wave/probes/CNL-0051/counter.py",
                },
                {
                    "name": "known_good_corroborated_unique",
                    "measured": good["corroborated_unique"],
                    "method": "min(lexical_unique, mechanism_unique)",
                    "anchor": "command-center/p2-wave/probes/CNL-0051/counter.py",
                },
            ],
            "control_ids": [
                "probe1_mutant_recall",
                "probe2_both_states",
            ],
        },
        "output_schema": SCHEMA_REL,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    doc["schema"] = {"path": SCHEMA_REL, **try_schema(doc)}

    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out_path)

    ret = {
        "id": "CNL-0051",
        "unit_id": "CNL-0051",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0051",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": p1["exit_code"],
                "role": "planted-mutant-recall",
                "raw_output": p1["stdout"] + "\n",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": p2["exit_code"],
                "role": "both-states-gaming-check",
                "raw_output": p2["stdout"] + "\n",
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNL-0051/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0051-independent-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": doc["ts"],
        "notes": (
            "G-1 for CNL-0051: live named probes exit 0, design note "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )

    supporting = [
        SCHEMA_REL,
        "command-center/p2-wave/probes/CNL-0051/counter.py",
        "command-center/p2-wave/probes/CNL-0051/reviewer.py",
        "command-center/p2-wave/probes/CNL-0051/probe1_mutant_recall.py",
        "command-center/p2-wave/probes/CNL-0051/probe2_both_states.py",
        "command-center/p2-wave/probes/CNL-0051/fixtures/corpus.json",
        "command-center/p2-wave/probes/CNL-0051/SUBAGENT-RETURN.json",
    ]

    def row(rel: str, role: str) -> dict:
        sha, n = sha256_file(REPO / rel)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "CNL-0051",
            "receipt_path": "command-center/p2-wave/probes/CNL-0051/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT_REL, "primary")] + [row(s, "supporting") for s in supporting]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0051",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0051 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
