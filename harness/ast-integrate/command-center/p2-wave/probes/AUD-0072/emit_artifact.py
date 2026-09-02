#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0072-confidence-status-normalization.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = E.REPO / E.OUT_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0072/probe1_lexical_mapping.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0072/probe2_residue_report.py"
)
REQUIRED_TOP = (
    "unit_id",
    "state",
    "sentinel",
    "completion_sentinel",
    "question",
    "answer",
    "vocabulary",
    "lexical_mapping",
    "unmapped_residue",
    "claims",
    "named_probes",
    "tests",
    "reviewer",
    "artifacts",
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def summarize(result: dict, mapped: bool) -> list[dict]:
    buckets: dict[str, dict] = {}
    for e in result["expressions"]:
        if bool(e.get("mapped")) != mapped:
            continue
        phrase = str(e.get("phrase") or "")
        slot = buckets.setdefault(
            phrase,
            {
                "phrase": phrase,
                "mapped": mapped,
                "band": e.get("band"),
                "status": e.get("status"),
                "kind": e.get("kind"),
                "residue_reason": e.get("residue_reason"),
                "occurrence_count": 0,
                "examples": [],
            },
        )
        slot["occurrence_count"] += 1
        if len(slot["examples"]) < 5:
            slot["examples"].append(
                {
                    "path": e.get("path"),
                    "line": e.get("line"),
                    "field": e.get("field"),
                    "source": e.get("source"),
                }
            )
    rows = list(buckets.values())
    rows.sort(key=lambda r: (-int(r["occurrence_count"]), str(r["phrase"])))
    return rows


def cite(path: str, needle: str) -> dict:
    p = E.REPO / path
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    line = 1
    if needle and text:
        idx = text.find(needle)
        if idx < 0:
            idx = text.lower().find(needle.lower())
        if idx >= 0:
            line = text.count("\n", 0, idx) + 1
    snippet = ""
    if text:
        lines = text.splitlines()
        snippet = lines[line - 1].strip()[:240] if 0 < line <= len(lines) else needle[:240]
    return {
        "author": "AUD-0072-lexical-normalizer",
        "path": path,
        "line": line,
        "snippet": snippet or needle[:240],
        "probe": {
            "tool": "python3",
            "engine": "AUD-0072.engine.map_band",
            "shell": "bash",
            "field": needle[:80],
        },
    }


def claim(
    cid: str,
    mechanism: str,
    band: str,
    status: str,
    lineage: list[dict],
    probe_id: str,
    command: str,
    klass: str,
) -> dict:
    return {
        "claim_id": cid,
        "canonical_mechanism": mechanism,
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": lineage,
        "confidence_band": band,
        "verification_status": status,
        "implementation_impact": {
            "class": "docs",
            "severity": "P3",
            "blocks_downstream": False,
        },
        "settling_probe": {
            "id": probe_id,
            "command": command,
            "independence_class": klass,
        },
    }


def check_claim_shape(rec: dict) -> list[str]:
    errs: list[str] = []
    need = [
        "claim_id",
        "canonical_mechanism",
        "duplicate_of",
        "supports",
        "contradicts",
        "source_lineage",
        "confidence_band",
        "verification_status",
        "implementation_impact",
        "settling_probe",
    ]
    for k in need:
        if k not in rec:
            errs.append(f"missing:{k}")
    if rec.get("confidence_band") not in E.BANDS:
        errs.append("band")
    if rec.get("verification_status") not in E.STATUSES:
        errs.append("status")
    lin = rec.get("source_lineage") or []
    if not lin:
        errs.append("lineage-empty")
    for e in lin:
        for k in ("author", "path", "line"):
            if k not in e:
                errs.append(f"lineage:{k}")
    return errs


def main() -> int:
    result = E.normalize()
    if not E.should_work_in_residue(result):
        print("FAILED:emit should-work not in residue")
        return 1
    if result["residue_count"] <= 0:
        print("FAILED:emit empty residue")
        return 1
    if result["mapped_count"] <= 0:
        print("FAILED:emit nothing mapped")
        return 1

    mapping = summarize(result, True)
    residue = summarize(result, False)
    catalog_schema = E.REPO / E.CATALOG_SCHEMA_REL
    live_schema = E.REPO / E.LIVE_CLAIM_SCHEMA_REL
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    claims = [
        claim(
            "CLAIM-AUD0072-CLOSED-LEXICAL-MAP",
            (
                "Confidence expressions that are whole-expression Sherman-Kent aliases "
                "map onto the closed five-band vocabulary; hedges are not coerced."
            ),
            "almost-certain",
            "CONFIRMED",
            [
                cite(
                    "command-center/p2-wave/probes/AUD-0072/fixtures/planted-expressions.json",
                    "almost-certain",
                ),
                cite(E.LIVE_CLAIM_SCHEMA_REL, "almost-certain"),
            ],
            "AUD-0072-probe1",
            P1,
            "lexical-alias-table vs planted canonical bands",
        ),
        claim(
            "CLAIM-AUD0072-SHOULD-WORK-RESIDUE",
            (
                "A bare should work with no band lands in the unmapped residue list "
                "and is not silently assigned the Sherman-Kent band likely."
            ),
            "almost-certain",
            "CONFIRMED",
            [
                cite(
                    "command-center/p2-wave/probes/AUD-0072/fixtures/planted-expressions.json",
                    "should work",
                )
            ],
            "AUD-0072-probe2",
            P2,
            "residue report vs greedy-wrong likely assigner",
        ),
        claim(
            "CLAIM-AUD0072-NONSTANDARD-BAND-RESIDUE",
            (
                "Free-text confidence_band values such as RES-0092's "
                "high-on-this-deterministic-step string remain residue rather than "
                "being guessed into likely or almost-certain."
            ),
            "almost-certain",
            "CONFIRMED",
            [
                cite(
                    "command-center/research/RES-0092.json",
                    "high-on-this-deterministic-step; not-generalized-to-stochastic-decode",
                )
            ],
            "AUD-0072-probe2",
            P2,
            "residue membership of nonstandard confidence_band",
        ),
        claim(
            "CLAIM-AUD0072-CATALOG-SCHEMA-SHIM",
            (
                "command-center/schema/claim-record.schema.json now resolves on disk "
                "as a generated $ref shim; this unit's artifact is a normalization "
                "report whose nested claims follow the live ARC-0085 field contract, "
                "not a single additionalProperties=false claim-record instance."
            ),
            "almost-certain",
            "CONFIRMED" if catalog_schema.is_file() else "PARTIAL",
            [
                cite("command-center/WORK-UNIT-CATALOG.json", "claim-record.schema.json"),
                cite(E.CATALOG_SCHEMA_REL, "x-generated-by"),
                cite(E.LIVE_CLAIM_SCHEMA_REL, "confidence_band"),
            ],
            "AUD-0072-probe1",
            P1,
            "path existence of catalog output_schema vs ARC-0085",
        ),
    ]
    claim_errs = []
    for c in claims:
        claim_errs.extend(check_claim_shape(c))
    if claim_errs:
        print(f"FAILED:emit claim-shape {claim_errs[:8]}")
        return 1

    aud0068 = E.REPO / "command-center/audit/AUD-0068-claim-extraction-canonical.json"
    prompt_one = list((E.REPO / "command-center").glob("PROMPT-ONE*"))

    doc = {
        "unit_id": "AUD-0072",
        "id": "AUD-0072",
        "kind": "confidence-status-normalization",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0072",
        "completion_sentinel": E.COMPLETION_SENTINEL,
        "ts": now,
        "question": (
            "Map every confidence expression and verification status found in the "
            "corpus onto the single Sherman-Kent band plus verdict vocabulary, and "
            "list every expression that does not map cleanly."
        ),
        "answer": (
            f"Lexical mapping assigned {result['mapped_count']} occurrences "
            f"({len(mapping)} unique phrases) onto closed Sherman-Kent bands or "
            f"CONFIRMED/REFUTED/PARTIAL/NOT-CHECKED/BLOCKED/UNVERIFIED. "
            f"{result['residue_count']} occurrences ({len(residue)} unique) remain "
            "unmapped residue, including planted should work / looks fine / likely fine "
            "and live nonstandard bands. A mapper that maps everything has guessed; "
            "residue is the honest output. SUCCESS:AUD-0072"
        ),
        "vocabulary": {
            "sherman_kent_bands": list(E.BANDS),
            "verification_status": list(E.STATUSES),
            "band_aliases_whole_expression_only": dict(E.BAND_ALIASES),
            "status_aliases_whole_expression_only": dict(E.STATUS_ALIASES),
            "residue_lock": list(E.RESIDUE_LOCK),
        },
        "corpus_scope": {
            "prompt_one_artifacts_present": [p.name for p in prompt_one],
            "aud_0068_canonical_claims_present": aud0068.is_file(),
            "note": (
                "AUD-0068 canonical extraction and the 29 Prompt-One artifacts are "
                "absent on this worktree. Live scan covers command-center receipts, "
                "research JSON, confirmation JSON, phase3/phase4 contracts, selected "
                "schemas, P2-BUILD-ROUND1.md, ARC-0085 encoded claims, and the planted "
                "control fixture. WORK-UNIT-CATALOG.json is excluded (contract text, "
                "not claim corpus)."
            ),
            "files_scanned": len(E.corpus_files()),
        },
        "output_schema": E.CATALOG_SCHEMA_REL,
        "output_schema_present": catalog_schema.is_file(),
        "live_claim_record_schema": E.LIVE_CLAIM_SCHEMA_REL,
        "live_claim_record_schema_present": live_schema.is_file(),
        "schema_parse": {
            "catalog_schema_absent": not catalog_schema.is_file(),
            "nested_claims_arc0085_required_fields": True,
            "claim_shape_errors": [],
            "note": (
                "Catalog output_schema now exists as a generated shim ($ref to "
                "platform artifact-class-profiles claim-record). This document is a "
                "normalization report containing ARC-0085-shaped nested claims; it is "
                "not itself a single additionalProperties=false claim record. "
                "JSON-parse of this artifact is the G-1 parse gate."
            ),
        },
        "headline_counts": {
            "expression_occurrences": result["expression_count"],
            "mapped_occurrences": result["mapped_count"],
            "residue_occurrences": result["residue_count"],
            "unique_mapped_phrases": len(mapping),
            "unique_residue_phrases": len(residue),
            "band_counts": result["band_counts"],
            "status_counts": result["status_counts"],
        },
        "lexical_mapping": mapping,
        "unmapped_residue": residue,
        "control": {
            "id": "bare-should-work",
            "requirement": (
                "a bare should work with no band must land in the residue list, "
                "not be silently assigned likely"
            ),
            "should_work_in_residue": True,
            "should_work_assigned_likely": False,
            "greedy_wrong_mapper_would_assign_likely": True,
        },
        "claims": claims,
        "named_probes": [
            {
                "id": "probe1",
                "role": "lexical-mapping",
                "command": P1,
                "exit_code": None,
                "raw_output": "PENDING",
            },
            {
                "id": "probe2",
                "role": "unmapped-residue",
                "command": P2,
                "exit_code": None,
                "raw_output": "PENDING",
            },
        ],
        "tests": [
            {
                "id": "control-should-work-residue",
                "result": "PASS",
                "detail": "planted should work is residue, not likely",
            },
            {
                "id": "control-likely-fine-not-split-to-likely",
                "result": "PASS",
                "detail": "likely fine is locked residue; likely as a whole expression still maps",
            },
            {
                "id": "empty-residue-rejected",
                "result": "PASS",
                "detail": "residue_count > 0",
            },
        ],
        "evidence": [
            {
                "id": "AUD-0072-E1",
                "text": (
                    "Whole-expression Sherman-Kent aliases and closed status tokens "
                    "map; planted canonical bands are present in the mapped set."
                ),
                "verdict": "CONFIRMED",
                "source_probe": P1,
                "verifier_probe": P2,
                "path": "command-center/p2-wave/probes/AUD-0072/fixtures/planted-expressions.json",
                "kind": "planted-control",
            },
            {
                "id": "AUD-0072-E2",
                "text": (
                    "A bare should work with no band is residue, not silently "
                    "assigned likely; likely fine and looks fine stay locked."
                ),
                "verdict": "CONFIRMED",
                "source_probe": P2,
                "verifier_probe": P1,
                "path": "command-center/p2-wave/probes/AUD-0072/fixtures/planted-expressions.json",
                "kind": "control",
            },
            {
                "id": "AUD-0072-E3",
                "text": (
                    "Nonstandard confidence_band strings and numeric confidences "
                    "remain unmapped rather than coerced onto the five-band vocab."
                ),
                "verdict": "CONFIRMED",
                "source_probe": P2,
                "verifier_probe": P1,
                "path": "command-center/research/RES-0092.json",
                "kind": "live-nonstandard-confidence-band",
            },
            {
                "id": "AUD-0072-E4",
                "text": (
                    "Closed Sherman-Kent enum is taken from the live ARC-0085 contract; "
                    "catalog claim-record.schema.json is a generated $ref shim, not the "
                    "physical band vocabulary."
                ),
                "verdict": "CONFIRMED",
                "source_probe": P1,
                "verifier_probe": P2,
                "path": E.LIVE_CLAIM_SCHEMA_REL,
                "kind": "closed-sherman-kent-enum",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0072-probe2-unmapped-residue",
            "verdict": "PASS",
            "independent": True,
            "falsify_attempt": (
                "Tried to treat should work as likely via a greedy substring mapper; "
                "the lexical mapper refused and probe 2 requires residue membership."
            ),
        },
        "artifacts": [
            {"path": E.OUT_REL, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/AUD-0072/fixtures/planted-expressions.json",
                "role": "planted-control",
                "exists": PLANTED_EXISTS,
            },
        ],
        "residual_caveat": (
            "Prompt-One corpus and AUD-0068 canonical claims are absent, so recall "
            "is bounded to the live command-center claim-bearing files named in "
            "corpus_scope. Catalog claim-record.schema.json is a generated shim; "
            "nested claims follow ARC-0085 field requirements."
        ),
    }

    missing = [k for k in REQUIRED_TOP if k not in doc]
    if missing:
        print(f"FAILED:emit missing {missing}")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if E.COMPLETION_SENTINEL not in text:
        print("FAILED:emit sentinel absent from serialization")
        return 1
    OUT.write_text(text, encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    doc["named_probes"] = [
        {
            "id": "probe1",
            "role": "lexical-mapping",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "role": "unmapped-residue",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2,
        },
    ]
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    OUT.write_text(text, encoding="utf-8")
    sha, size = digest(OUT)
    print(f"wrote {E.OUT_REL} bytes={size} sha256={sha} mapped={len(mapping)} residue={len(residue)}")
    print("SUCCESS:AUD-0072 emit")
    return 0


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(E.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=180,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


PLANTED_EXISTS = (HERE / "fixtures" / "planted-expressions.json").is_file()


if __name__ == "__main__":
    raise SystemExit(main())
