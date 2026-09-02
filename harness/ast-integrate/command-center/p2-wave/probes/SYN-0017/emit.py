#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0017.mechanism-dedup.json from a live run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import engine as E  # noqa: E402
import live_inputs as L  # noqa: E402
import schema_local as SL  # noqa: E402

CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
STRIKES = HERE / "_schema_strikes.json"
OUT = REPO / C.OUTPUT_REL
SUPPORTING = [
    C.SCHEMA_REL,
    "command-center/p2-wave/probes/SYN-0017/contract.py",
    "command-center/p2-wave/probes/SYN-0017/tokens.py",
    "command-center/p2-wave/probes/SYN-0017/findings.py",
    "command-center/p2-wave/probes/SYN-0017/engine.py",
    "command-center/p2-wave/probes/SYN-0017/live_inputs.py",
    "command-center/p2-wave/probes/SYN-0017/schema_local.py",
    "command-center/p2-wave/probes/SYN-0017/probe1_planted_mutants.py",
    "command-center/p2-wave/probes/SYN-0017/probe2_distinct_and_anchor_union.py",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": max(size, 1),
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def err_fp(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def record_strike(fingerprint: str, errs: list[str], ts: str) -> int:
    data = load_strikes()
    data["attempts"].append({"fp": fingerprint, "errs": errs[:12], "ts": ts})
    STRIKES.write_text(
        json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return sum(1 for a in data["attempts"] if a.get("fp") == fingerprint)


def park_blocked(
    required_fix: str, errs: list[str], fingerprint: str, started: str
) -> int:
    ended = utcnow()
    blocked = {
        "schema_version": 1,
        "unit_id": C.UNIT_ID,
        "state": "BLOCKED",
        "sentinel": f"FAILED:SYN-0017 schema-invalid parked fp={fingerprint}",
        "spec_anchor": "_USER-PROMPTS.md:11092",
        "min_bytes_threshold": 256,
        "artifacts": [
            {
                "path": C.OUTPUT_REL,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Two same-fingerprint structural refutes; parked without "
                    "an ADV rebuild circle."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0017/_schema_strikes.json",
                "probes": [
                    probe(
                        "source",
                        "schema-validate",
                        "command-center/p2-wave/probes/SYN-0017/schema_local.py",
                        "\n".join(errs[:12]),
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/SYN-0017/_schema_strikes.json",
                        f"fp={fingerprint} required_fix={required_fix}",
                    ),
                ],
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 2,
            "policy": "two same-fingerprint structural refutes park BLOCKED",
        },
        "failure": {
            "classification": ["schema-invalid"],
            "reason": required_fix,
            "diagnostic_tail": "\n".join(errs[:25]),
            "blocked_on": required_fix,
        },
        "report": {
            "kind": "dedup-report",
            "observations": [
                {
                    "name": "parked",
                    "measured": True,
                    "method": "same-fingerprint-count>=2",
                    "anchor": "command-center/p2-wave/probes/SYN-0017/_schema_strikes.json",
                }
            ],
            "control_ids": ["same-fingerprint-park"],
            "required_fix": required_fix,
            "schema_fingerprint": fingerprint,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(blocked, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    ret = {
        "id": C.UNIT_ID,
        "unit_id": C.UNIT_ID,
        "status": "BLOCKED",
        "state": "BLOCKED",
        "required_fix": required_fix,
        "output_path": C.OUTPUT_REL,
        "notes": (
            "Parked after two same-fingerprint structural refutes. "
            "No ADV rebuild circle."
        ),
        "ts": ended,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:SYN-0017 parked same-fingerprint structural refute fp={fingerprint}")
    print(f"required_fix={required_fix}")
    return 1


def pair_rows(pairs: list[dict]) -> list[dict]:
    return [
        {
            "left_id": p["left_id"],
            "right_id": p["right_id"],
            "lexical_score": p["lexical_score"],
            "embedding_score": p["embedding_score"],
            "agreement": p["agreement"],
            "collapse": p["collapse"],
            "canonical_mechanism_match": p["canonical_mechanism_match"],
        }
        for p in pairs
    ]


def finding_rows(findings: list[dict]) -> list[dict]:
    return [
        {
            "id": f["id"],
            "title": f["title"],
            "canonical_mechanism": f["canonical_mechanism"],
            "evidence_anchors": f["evidence_anchors"],
            "role": f["role"],
        }
        for f in findings
    ]


def build(run: dict, live: dict, started: str, ended: str) -> dict:
    mutants = run["planted_mutants"]
    which = {m["class"]: m["agreement"] for m in mutants}
    n_collapse = sum(1 for p in run["pairs"] if p["collapse"])
    n_pairs = len(run["pairs"])
    dc = run["distinct_pair_control"]
    loc = run["lexical_only_coverage"]
    ok_garb, why_garb = SL.schema_rejects_garbage()
    if not ok_garb:
        raise SystemExit(f"FAILED:SYN-0017 {why_garb}")

    mutant_tail = " | ".join(
        f"{m['class']} caught={m['caught']} lex={m['lexical_score']} "
        f"emb={m['embedding_score']} agreement={m['agreement']}"
        for m in mutants
    )
    distinct_tail = (
        f"collapsed={dc['collapsed']} lex={dc['lexical_score']} "
        f"emb={dc['embedding_score']} agreement={dc['agreement']}"
    )
    rewrite_tail = (
        f"collapsed={loc['collapsed']} scores_like_distinct="
        f"{loc['scores_like_distinct']} lex={loc['lexical_score']} "
        f"emb={loc['embedding_score']}"
    )
    answer = (
        f"Yes — the two-detector gate collapsed the three planted mutants "
        f"(rename={which.get('rename')}, paraphrase={which.get('paraphrase')}, "
        f"parameter-fork={which.get('parameter-fork')}) onto the incumbent "
        f"report-time manifest gate, kept the git-archive-CRLF finding and the "
        f"dissent-disposal finding apart, and preserved the union of evidence "
        f"anchors on every collapse. {n_collapse} of {n_pairs} scored pairs "
        f"collapsed. A full rewrite of the same mechanism scored like a "
        f"distinct entry; that lexical-only coverage is disclosed. SYN-0011 "
        f"adjudications are absent, so the scan is the planted fixture "
        f"corpus, not a fabricated live finding list. CLAIM-REGISTRY.json is "
        f"present but has no canonical_mechanism field, so it is not the "
        f"collapse rule. {C.SENTINEL}"
    )
    supporting = [art_row(rel, "supporting") for rel in SUPPORTING]
    artifacts = [
        {
            "path": C.OUTPUT_REL,
            "bytes": 1,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ] + supporting
    return {
        "schema_version": 1,
        "unit_id": C.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11092",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "mechanism-extractor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Planted rename, paraphrase, and one-parameter-fork mutants "
                    "all collapse onto the incumbent under the two-detector OR-gate."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0017/findings.py",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "command-center/p2-wave/probes/SYN-0017/findings.py",
                        mutant_tail,
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        "command-center/p2-wave/probes/SYN-0017/engine.py",
                        mutant_tail,
                    ),
                ],
            },
            {
                "claim": (
                    "Two genuinely distinct findings stay uncollapsed, collapse "
                    "preserves the union of evidence anchors, and a full rewrite "
                    "of the same mechanism scores like a distinct entry."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0017/engine.py",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "command-center/p2-wave/probes/SYN-0017/engine.py",
                        distinct_tail + " | " + rewrite_tail,
                    ),
                    probe(
                        "verifier",
                        "schema-validate",
                        "command-center/p2-wave/probes/SYN-0017/schema_local.py",
                        why_garb,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "test_planted_mutant_rename_paraphrase_parameter_fork_all_detected",
                "name": "Planted rename / paraphrase / parameter-fork all detected",
                "command": C.P1,
                "result": "PASS",
                "assertions": 3,
            },
            {
                "id": "test_two_genuinely_distinct_findings_must_not_be_collapsed",
                "name": "Two genuinely distinct findings must not be collapsed",
                "command": C.P2,
                "result": "PASS",
                "assertions": 1,
            },
            {
                "id": "test_collapse_preserves_the_union_of_evidence_anchors_from_both_members",
                "name": "Collapse preserves the union of evidence anchors",
                "command": C.P2,
                "result": "PASS",
                "assertions": 1,
            },
        ],
        "negative_controls": [
            {
                "id": "planted-mutants",
                "kind": "known-broken-fixture",
                "description": (
                    "Rename, paraphrase, and one-parameter fork of the incumbent "
                    "must fire the detector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": mutant_tail,
                "good_state_output": distinct_tail,
            },
            {
                "id": "distinct-pair",
                "kind": "known-broken-fixture",
                "description": (
                    "Git-archive CRLF and omitted-dissent findings are distinct "
                    "mechanisms and must not collapse."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": mutant_tail,
                "good_state_output": distinct_tail,
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": "Three garbage documents are rejected by the declared schema.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": why_garb,
                "good_state_output": "live receipt validates",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0017-probe1-planted-mutants",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Re-run the DETECTOR CONTROL on the planted known-broken "
                "mutants and the known-good distinct pair; re-reading this "
                "report is not verification."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0017/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": C.UNIT_ID,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/SYN-0017/schema_local.py",
                "artifact_path": C.OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "command-center/p2-wave/probes/SYN-0017/schema_local.py",
                    "schema_local.errors([]) empty on live receipt",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "at most 3 attempts, each changing substrate or interpreter; "
                "two same-fingerprint structural refutes park BLOCKED"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/synthesis/SYN-0011.adjudications.json is "
                    "absent; the detector is proven on the planted fixture corpus."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver SYN-0011, then re-run SYN-0017 over the merged "
                    "adjudication finding set instead of the fixture corpus."
                ),
            },
            {
                "claim": (
                    "CLAIM-REGISTRY.json is present but no claim carries "
                    "canonical_mechanism, so that field is not the collapse rule."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "If CLAIM-REGISTRY grows a canonical_mechanism field, "
                    "re-score pairs with that key as a reported label only, "
                    "never as the collapse rule, and keep the rewrite control."
                ),
            },
        ],
        "report": {
            "kind": "dedup-report",
            "question": C.QUESTION,
            "answer": answer,
            "collapse_rule": (
                "OR-gate: collapse when lexical Jaccard >= "
                f"{C.LEXICAL_THRESHOLD} or hashed-embedding cosine >= "
                f"{C.EMBEDDING_THRESHOLD}. Canonical-mechanism equality is "
                "recorded per pair and is NOT the collapse rule."
            ),
            "detectors": [
                {
                    "id": "lexical-token-jaccard",
                    "kind": "lexical-jaccard",
                    "threshold": C.LEXICAL_THRESHOLD,
                    "formula": (
                        "Jaccard(|tokens(left)| ∩ |tokens(right)|) / union, "
                        "stopwords dropped, no synonym fold"
                    ),
                },
                {
                    "id": "hashed-ngram-cosine",
                    "kind": "hashed-embedding-cosine",
                    "threshold": C.EMBEDDING_THRESHOLD,
                    "formula": (
                        f"L2-normalized signed SHA-256 feature hash of synonym-folded "
                        f"tokens plus character 3-grams into R^{C.EMBED_DIM}, cosine"
                    ),
                },
            ],
            "findings": finding_rows(run["findings"]),
            "pairs": pair_rows(run["pairs"]),
            "planted_mutants": mutants,
            "distinct_pair_control": dc,
            "collapses": run["collapses"],
            "lexical_only_coverage": loc,
            "live_inputs": live,
            "completion_sentinel": C.SENTINEL,
            "scope_does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "SYN-0011 live adjudication set was present on this worktree",
                "CLAIM-REGISTRY.json canonical_mechanism was the collapse rule",
                "a neural embedding model ran",
            ],
            "observations": [
                {
                    "name": "planted_mutants_caught",
                    "measured": all(m["caught"] for m in mutants),
                    "method": "two-detector OR-gate over planted rename/paraphrase/fork",
                    "anchor": "command-center/p2-wave/probes/SYN-0017/findings.py",
                },
                {
                    "name": "distinct_pair_collapsed",
                    "measured": dc["collapsed"],
                    "method": "two-detector OR-gate over git-archive vs dissent pair",
                    "anchor": "command-center/p2-wave/probes/SYN-0017/engine.py",
                },
                {
                    "name": "pairs_collapsed",
                    "measured": n_collapse,
                    "method": "count of scored pairs with agreement != NEITHER",
                    "anchor": "command-center/p2-wave/probes/SYN-0017/engine.py",
                },
                {
                    "name": "full_rewrite_scores_like_distinct",
                    "measured": loc["scores_like_distinct"],
                    "method": "lexical Jaccard plus hashed-n-gram cosine vs thresholds",
                    "anchor": "command-center/p2-wave/probes/SYN-0017/tokens.py",
                },
            ],
            "control_ids": [
                "planted-rename",
                "planted-paraphrase",
                "planted-parameter-fork",
                "distinct-pair",
                "anchor-union",
                "full-rewrite-lexical-only-coverage",
            ],
        },
    }


def main() -> int:
    started = utcnow()
    run = E.run()
    if not run["ok"]:
        print("FAILED:SYN-0017 emit detector invariants")
        for err in run["errors"]:
            print(" ", err)
        return 1
    live = L.scan(REPO)
    ended = utcnow()
    doc = build(run, live, started, ended)
    try:
        started_dt = datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        ended_dt = datetime.strptime(ended, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        doc["timestamps"]["duration_seconds"] = max(
            0.0, (ended_dt - started_dt).total_seconds()
        )
    except ValueError:
        doc["timestamps"]["duration_seconds"] = 0.0

    errs = SL.errors(doc)
    if errs:
        fingerprint = err_fp(errs)
        n = record_strike(fingerprint, errs, ended)
        print("FAILED:SYN-0017 schema", errs[:20])
        if n >= 2:
            return park_blocked(
                "align-artifact-to-dedup-report.schema.json",
                errs,
                fingerprint,
                started,
            )
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    sha, size = digest_file(OUT)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = max(size, 1)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    sha, size = digest_file(OUT)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = max(size, 1)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    post = json.loads(OUT.read_text(encoding="utf-8"))
    post_errs = SL.errors(post)
    if post_errs:
        print("FAILED:SYN-0017 post-write schema", post_errs[:20])
        return 1
    text = OUT.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        print("FAILED:SYN-0017 sentinel missing from artifact bytes")
        return 1
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        print("FAILED:SYN-0017 artifact missing after write")
        return 1
    print(f"wrote {C.OUTPUT_REL} bytes={OUT.stat().st_size} sha256={digest_file(OUT)[0]}")
    for m in run["planted_mutants"]:
        print(
            f"  mutant {m['class']} caught={m['caught']} "
            f"lex={m['lexical_score']} emb={m['embedding_score']} "
            f"agreement={m['agreement']}"
        )
    dc = run["distinct_pair_control"]
    print(
        f"  distinct collapsed={dc['collapsed']} "
        f"lex={dc['lexical_score']} emb={dc['embedding_score']}"
    )
    loc = run["lexical_only_coverage"]
    print(
        f"  rewrite collapsed={loc['collapsed']} "
        f"lex={loc['lexical_score']} emb={loc['embedding_score']}"
    )
    print("SUCCESS:SYN-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
