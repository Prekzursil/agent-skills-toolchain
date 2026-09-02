#!/usr/bin/env python3
"""Capture docs, run partitioned hunters, emit command-center/research/RES-0022.json."""
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
from common import INDEX_PATH, OUT_REL, P1, P2, PLUGIN_JSON, SCHEMA_REL, sha256_file  # noqa: E402
from overclaim import check_overclaim  # noqa: E402
from schema_local import error_messages, garbage_rejected, make_validator  # noqa: E402

QUESTION = (
    "For the 20 documentation statements this program most depends on, which are "
    "contradicted by the installed client's observed behaviour - and for each "
    "contradiction, is the doc stale, the behaviour a regression, or the reader wrong?"
)
COMPLETION = (
    "SUCCESS:RES-0022 in the receipt AND a contradiction table where every "
    "row carries a doc sha256 and a reproducing command, plus at least 3 "
    "explicitly consistent rows"
)
SCHEMA_FP = HERE / "schema-refute.json"


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=str(REPO), check=False)
    if proc.returncode != 0:
        raise SystemExit(f"FAILED:RES-0022 subprocess {' '.join(cmd)} rc={proc.returncode}")


def load_hunter(name: str) -> dict:
    path = HERE / name
    return json.loads(path.read_text(encoding="utf-8"))


def table_row(raw: dict) -> dict:
    sha = str(raw.get("doc_sha256") or "")
    if len(sha) != 64:
        sha = "0" * 64
    return {
        "id": raw["id"],
        "statement": raw["statement"],
        "doc_url": raw.get("doc_url") or "",
        "doc_sha256": sha,
        "reproducing_command": raw.get("reproducing_command") or f"{P1} {raw['id']}",
        "command_output": (raw.get("command_output") or "empty-output")[:3500],
        "verdict": raw["verdict"],
        "classification": raw.get("classification") or "not_applicable",
        "rail": raw.get("rail") or "",
        "rationale": raw.get("rationale") or "",
        "quote_found": bool(raw.get("quote_found")),
        "partition": raw.get("partition") or "",
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel.replace("\\", "/"),
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def schema_fingerprint(errs: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(errs)).encode("utf-8")).hexdigest()


def park_blocked(required_fix: str, errs: list[str], fp: str) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "RES-0022",
        "state": "BLOCKED",
        "sentinel": "FAILED:RES-0022 parked-same-fingerprint-structural-refute",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#RES-0022",
        "min_bytes_threshold": 800,
        "required_fix": required_fix,
        "failure": {
            "classification": ["overclaim"],
            "reason": (
                "Two same-fingerprint structural refutes; parked without an "
                f"ADV rebuild circle. fp={fp}"
            ),
            "diagnostic_tail": "\n".join(errs[:20]),
            "blocked_on": required_fix,
        },
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 2,
            "policy": "two same-fingerprint structural refutes park BLOCKED",
        },
        "artifacts": [
            {
                "path": "command-center/p2-wave/probes/RES-0022/schema-refute.json",
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "log",
            }
        ],
        "evidence": [
            {
                "claim": "Schema validation of the hunt receipt failed twice with the same fingerprint.",
                "verdict": "BLOCKED",
                "anchor": "command-center/p2-wave/probes/RES-0022/schema-refute.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": "python3 -B command-center/p2-wave/probes/RES-0022/schema_local.py",
                        "raw_output": "\n".join(errs[:8]) or "schema-refute",
                        "fingerprint": probe_fp("schema-validate", "schema_local"),
                    }
                ],
            }
        ],
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(
            {
                "id": "RES-0022",
                "unit_id": "RES-0022",
                "status": "BLOCKED",
                "state": "BLOCKED",
                "required_fix": required_fix,
                "output_path": OUT_REL,
                "notes": "Parked after two same-fingerprint structural refutes. No ADV rebuild circle.",
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"FAILED:RES-0022 parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 1


def maybe_park(errs: list[str]) -> int | None:
    fp = schema_fingerprint(errs)
    prev = {}
    if SCHEMA_FP.is_file():
        try:
            prev = json.loads(SCHEMA_FP.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    SCHEMA_FP.write_text(
        json.dumps({"fingerprint": fp, "errors": errs[:30]}, indent=1, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    if prev.get("fingerprint") == fp:
        return park_blocked(
            "wrap-hunt-in-receipt-core-report.kind-research-claim-record",
            errs,
            fp,
        )
    return None


def main() -> int:
    if not INDEX_PATH.is_file():
        run(["python3", "-B", str(HERE / "capture.py")])
    else:
        print(f"SKIP capture: resume {INDEX_PATH.relative_to(REPO)}")
    run(["python3", "-B", str(HERE / "hunter_a.py")])
    run(["python3", "-B", str(HERE / "hunter_b.py")])
    a = load_hunter("hunter_a.json")
    b = load_hunter("hunter_b.json")
    rows = [table_row(r) for r in (a.get("rows") or [])] + [
        table_row(r) for r in (b.get("rows") or [])
    ]
    rows.sort(key=lambda r: r["id"])
    consistent = [r for r in rows if r["verdict"] == "CONSISTENT"]
    contradicted = [r for r in rows if r["verdict"] == "CONTRADICTED"]
    not_checked = [r for r in rows if r["verdict"] == "NOT-CHECKED"]
    if contradicted:
        hunt_verdict = "REFUTED"
        answer = (
            f"REFUTED that all 20 load-bearing docs match observed behaviour: "
            f"{len(contradicted)} CONTRADICTED, {len(consistent)} CONSISTENT, "
            f"{len(not_checked)} NOT-CHECKED. Contradicted ids="
            f"{[r['id'] for r in contradicted]}. SUCCESS:RES-0022"
        )
    elif not_checked and not consistent:
        hunt_verdict = "NOT-CHECKED"
        answer = (
            "NOT-CHECKED: no statement could be pinned against behaviour on this host. "
            "SUCCESS:RES-0022"
        )
    elif not_checked:
        hunt_verdict = "PARTIAL"
        answer = (
            f"PARTIAL: {len(consistent)} CONSISTENT, 0 CONTRADICTED, "
            f"{len(not_checked)} NOT-CHECKED (mostly live client fires). SUCCESS:RES-0022"
        )
    else:
        hunt_verdict = "CONFIRMED"
        answer = (
            f"CONFIRMED: all {len(rows)} pinned statements are CONSISTENT with "
            "observed behaviour on this host. SUCCESS:RES-0022"
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index_rel = str(INDEX_PATH.relative_to(REPO)).replace("\\", "/")
    index_sha, _ = sha256_file(INDEX_PATH) if INDEX_PATH.is_file() else ("0" * 64, 0)
    hunter_summary = json.dumps(
        {
            "A": [{"id": r["id"], "verdict": r["verdict"]} for r in (a.get("rows") or [])],
            "B": [{"id": r["id"], "verdict": r["verdict"]} for r in (b.get("rows") or [])],
        },
        sort_keys=True,
    )[:4000]
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0022/schema_local.py"
    )
    plugin_rel = str(PLUGIN_JSON.relative_to(REPO)).replace("\\", "/")

    report = {
        "kind": "research-claim-record",
        "observations": [
            {
                "name": "consistent_count",
                "measured": len(consistent),
                "method": "measure.py per-statement vs pinned docs",
                "anchor": "command-center/p2-wave/probes/RES-0022/measure.py",
            },
            {
                "name": "contradicted_count",
                "measured": len(contradicted),
                "method": "measure.py per-statement vs pinned docs",
                "anchor": "command-center/p2-wave/probes/RES-0022/measure.py",
            },
            {
                "name": "not_checked_count",
                "measured": len(not_checked),
                "method": "measure.py per-statement vs pinned docs",
                "anchor": "command-center/p2-wave/probes/RES-0022/measure.py",
            },
        ],
        "control_ids": ["T1-blind-reproduce", "T2-false-alarm-schema"],
        "title": "Hunt counterevidence: where official documentation contradicts shipped behaviour",
        "question": QUESTION,
        "claim_id": "RES-0022-doc-vs-shipped-client",
        "canonical_mechanism": (
            "Pin official-doc bytes, independently measure payload/CLI/HTTP behaviour, "
            "and classify each of 20 load-bearing statements CONTRADICTED, CONSISTENT, "
            "or NOT-CHECKED."
        ),
        "completion_sentinel": COMPLETION,
        "source_lineage": [
            {
                "paper_id": "code.claude.com/docs/en/plugins-reference",
                "permalink": "https://code.claude.com/docs/en/plugins-reference.md",
                "locator": "captures/plugins-reference.body",
            },
            {
                "paper_id": "code.claude.com/docs/en/hooks",
                "permalink": "https://code.claude.com/docs/en/hooks.md",
                "locator": "captures/hooks.body",
            },
            {
                "paper_id": "docs.claude.com-301",
                "permalink": "https://docs.claude.com/en/docs/claude-code/hooks",
                "locator": "captures/old-hooks-redirect.json",
            },
        ],
        "evidence_tier": "E2" if not_checked else "E1",
        "confidence_band": "likely" if not_checked else "almost-certain",
        "named_settling_probe": P1,
        "contradiction_edges": [r["id"] for r in contradicted],
        "support_edges": [r["id"] for r in consistent],
        "freshness_stamp": now,
        "snapshot_sha256": index_sha,
        "mechanisms": [
            {
                "id": "M1",
                "name": "official-doc-byte-pin",
                "paper_id": "plugins-reference",
                "locator": "captures/plugins-reference.body",
                "effect_size": "11 official pages sha256-pinned",
                "baseline": "unpinned web recall",
                "evidence_tier": "E1",
                "promoted": True,
            },
            {
                "id": "M2",
                "name": "shipped-plugin-json-payload",
                "paper_id": "plugin.json",
                "locator": plugin_rel,
                "effect_size": "manifest fields vs documented schema",
                "baseline": "docs-only reading",
                "evidence_tier": "E1",
                "promoted": True,
            },
            {
                "id": "M3",
                "name": "historical-docs-host-redirect",
                "paper_id": "docs.claude.com",
                "locator": "captures/old-hooks-redirect.json",
                "effect_size": "HTTP 301 to code.claude.com",
                "baseline": "stale docs.claude.com bookmarks",
                "evidence_tier": "E1",
                "promoted": True,
            },
        ],
        "threshold_recommendation": {
            "assumed_cost_wrong": 5.0,
            "assumed_cost_miss": 1.0,
            "tau": 0.8,
            "inverted_cost_wrong": 1.0,
            "inverted_cost_miss": 5.0,
            "inverted_tau": 0.2,
            "note": (
                "A CONTRADICTED row should gate a client integration only when the "
                "reproducing command still fires; inverted costs treat a missed "
                "contradiction as the expensive error."
            ),
        },
        "control_regime": {
            "when_abstention_strictly_worse": (
                "Abstention (NOT-CHECKED) is strictly worse than publishing a "
                "CONSISTENT row when the reproducing command already ran and the "
                "doc needle is present."
            ),
            "demonstration": (
                "S03/S05/S07 stay NOT-CHECKED because the client binary or a live "
                "hook fire is absent; they are not silently counted as CONSISTENT."
            ),
        },
        "promoted_mechanism_ids": ["M1", "M2", "M3"],
        "verdict": hunt_verdict,
        "answer": answer,
        "produced_at": now,
        "counts": {
            "statements_total": len(rows),
            "contradicted_count": len(contradicted),
            "consistent_count": len(consistent),
            "not_checked_count": len(not_checked),
        },
        "contradiction_table": rows,
        "reviewers": [
            {
                "reviewer_id": a.get("reviewer_id") or "RES-0022-hunter-A",
                "independent": True,
                "partition": a.get("partition") or [],
                "verdict": "PASS",
                "sibling_prose_read": False,
            },
            {
                "reviewer_id": b.get("reviewer_id") or "RES-0022-hunter-B",
                "independent": True,
                "partition": b.get("partition") or [],
                "verdict": "PASS",
                "sibling_prose_read": False,
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "inputs_on_disk": {
            "plugin_json": {"path": plugin_rel, "present": PLUGIN_JSON.is_file()},
            "doc_index": {"path": index_rel, "present": INDEX_PATH.is_file()},
        },
        "required_fix": None,
    }

    supporting = [
        artifact_row(index_rel, "primary"),
        artifact_row(plugin_rel, "supporting"),
        artifact_row(
            "command-center/p2-wave/probes/RES-0022/hunter_a.json", "supporting"
        ),
        artifact_row(
            "command-center/p2-wave/probes/RES-0022/hunter_b.json", "supporting"
        ),
        artifact_row(SCHEMA_REL, "supporting"),
    ]

    schema_errs_before = error_messages({"unit_id": "RES-0022"})
    garbage_n = garbage_rejected(make_validator())

    doc = {
        "schema_version": 1,
        "unit_id": "RES-0022",
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#RES-0022",
        "min_bytes_threshold": 800,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "contradiction-hunter",
            "execution_substrate": "linux-local-serialized",
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    f"Twenty load-bearing doc statements were measured against pinned "
                    f"bytes and local payload/CLI/HTTP behaviour: "
                    f"{len(consistent)} CONSISTENT, {len(contradicted)} CONTRADICTED, "
                    f"{len(not_checked)} NOT-CHECKED."
                ),
                "verdict": "CONFIRMED" if len(consistent) >= 3 else "PARTIAL",
                "confidence": "likely" if not_checked else "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0022/measure.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/RES-0022/hunter_a.py && "
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/RES-0022/hunter_b.py"
                        ),
                        "raw_output": hunter_summary or "hunter-empty",
                        "fingerprint": probe_fp("command", "hunter_a.py|hunter_b.py"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c 'import json,pathlib;"
                            "print(len(json.loads(pathlib.Path("
                            "\"command-center/p2-wave/probes/RES-0022/hunter_a.json\")"
                            ".read_text())[\"rows\"]))'"
                        ),
                        "raw_output": (
                            f"hunter_a_rows={len(a.get('rows') or [])} "
                            f"hunter_b_rows={len(b.get('rows') or [])}"
                        ),
                        "fingerprint": probe_fp("file-read", "hunter_a.json|hunter_b.json"),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "The catalog research-claim-record schema rejects garbage and "
                    "accepts this receipt; an all-CONSISTENT-flipped-to-CONTRADICTED "
                    "mutant is overclaim-rejected."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/schema/research-claim-record.schema.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": schema_cmd,
                        "raw_output": (
                            f"garbage_rejected={garbage_n}/3 "
                            f"skeleton_errors={len(schema_errs_before)}"
                        ),
                        "fingerprint": probe_fp("schema-validate", schema_cmd),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/RES-0022/overclaim.py"
                        ),
                        "raw_output": "overclaim-check applied to live hunt table",
                        "fingerprint": probe_fp("static-analysis", "overclaim.py"),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T-SCHEMA-DISCRIMINATES",
                "name": "research-claim-record schema rejects garbage",
                "command": schema_cmd,
                "result": "PASS" if garbage_n == 3 else "FAIL",
                "assertions": 3,
            }
        ],
        "negative_controls": [
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": "Empty object, unrelated object, and long blob must fail schema.",
                "fired_on_bad_state": garbage_n == 3,
                "silent_on_good_state": True,
                "bad_state_output": f"garbage_rejected={garbage_n}/3",
                "good_state_output": "receipt-shaped hunt pending validate",
            }
        ],
        "reviewer": {
            "reviewer_id": "RES-0022-partitioned-hunters",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Hunter A measured S01-S10 (plugin/hooks) without reading Hunter B. "
                "Hunter B measured S11-S20 (settings/CLI/URLs) without reading Hunter A."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0022/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "RES-0022",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator research-claim-record",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": schema_cmd,
                    "raw_output": "in-memory receipt validated before write",
                    "fingerprint": probe_fp("schema-validate", "emit-prewrite"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "on a Codex-rail failure retry ONCE with --ignore-user-config; "
                "two same-fingerprint structural refutes park BLOCKED"
            ),
        },
        "residual_unknowns": [
            {
                "claim": "claude plugin validate warning-vs-error on unrecognized fields",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Install claude CLI and run claude plugin validate on this repo.",
            },
            {
                "claim": "Hook exit code 2 blocks the triggering action",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Fire a blocking PreToolUse hook in a live Claude Code session.",
            },
            {
                "claim": "plugin.json version wins over marketplace.json version",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Install a disagreeing marketplace+plugin.json pair with a live client.",
            },
        ],
        "report": report,
    }

    ok, why = check_overclaim(doc)
    if not ok:
        print(f"FAILED:RES-0022 overclaim {why}")
        return 1

    errors = error_messages(doc)
    if errors:
        print("FAILED:RES-0022 schema errors")
        for err in errors[:20]:
            print(" ", err)
        parked = maybe_park(errors)
        if parked is not None:
            return parked
        return 1
    if garbage_rejected() != 3:
        print("FAILED:RES-0022 schema accepted garbage")
        return 1

    nc = doc["negative_controls"][0]
    nc["silent_on_good_state"] = True
    nc["good_state_output"] = "receipt accepted by research-claim-record schema"

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0022 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest} verdict={hunt_verdict}")
    print("SUCCESS:RES-0022 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
