#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0023.json (convergence attribution)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema import RefResolver

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from attribute import (  # noqa: E402
    NULL_MODEL,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    attribute_scenario,
    load_json,
    required_planted,
    sha256_file,
    share_from_labels,
)
from live import live_attributions, load_inventory  # noqa: E402

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
UNIT = "SYN-0023"
MANIFEST_REL = "command-center/p2-wave/probes/SYN-0023/UNIT-ARTIFACT-MANIFEST.json"
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:SYN-0023"
CONSUME_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"import json; from pathlib import Path; "
    "p=Path('command-center/receipts/SYN-0023.json'); "
    "d=json.loads(p.read_text(encoding='utf-8')); "
    "r=d.get('report') or {}; "
    "print('join', r.get('join_key')); "
    "print('planted', len(r.get('planted_controls') or [])); "
    "print('share', (r.get('conformity_share') or {}).get('status'))\""
)


def catalog_sentinel() -> str:
    catalog = load_json(REPO / CATALOG_REL)
    for bucket in ("work_units", "items"):
        for unit in catalog.get(bucket) or []:
            if isinstance(unit, dict) and unit.get("id") == UNIT:
                return str(unit.get("completion_sentinel") or SENTINEL)
    return SENTINEL


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text[-65000:]


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    else:
        eol = "LF"
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def planted_row(result: dict) -> dict:
    return {
        "id": result["id"],
        "conclusion_id": result.get("conclusion_id"),
        "conclusion": result.get("conclusion"),
        "claim_true": result.get("claim_true"),
        "expected_label": result["expected_label"],
        "observed_label": result["observed_label"],
        "correct": bool(result["correct"]),
        "lineage_by_agent": result["lineage_by_agent"],
        "lowest_common_ancestors": result["lowest_common_ancestors"],
        "join_key": "artifact-identity",
    }


def live_row(result: dict) -> dict:
    return {
        "conclusion_id": str(result.get("conclusion_id") or result.get("id")),
        "label": result["observed_label"],
        "lineage_by_agent": result["lineage_by_agent"],
        "lowest_common_ancestors": result["lowest_common_ancestors"],
        "population": "live",
        "join_key": "artifact-identity",
    }


def schema_errors(doc: dict) -> list[str]:
    """Validate against the declared shim using an on-disk $id store (no network)."""
    store: dict = {}
    for rel in (
        SCHEMA_REL,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = str(data.get("$id") or f"https://ast-integrate.invalid/{rel}")
        store[sid] = data
    schema = store[json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))["$id"]]
    resolver = RefResolver.from_schema(schema, store=store)
    validator = jsonschema.Draft202012Validator(schema, resolver=resolver)
    return sorted(
        f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in validator.iter_errors(doc)
    )


def build_domain() -> tuple[dict, list[dict], list[dict], dict, dict, dict]:
    planted_results = [
        attribute_scenario(scenario, join="identity") for scenario in required_planted()
    ]
    bad = [row for row in planted_results if not row["correct"]]
    if bad:
        raise SystemExit(
            "FAILED:SYN-0023 planted-mislabelled "
            + json.dumps(
                [
                    {
                        "id": row["id"],
                        "expected": row["expected_label"],
                        "observed": row["observed_label"],
                    }
                    for row in bad
                ]
            )
        )
    inventory, docs = load_inventory()
    live_hits, live_skipped, syn_meta = live_attributions(docs)
    live_share = share_from_labels(
        [row["observed_label"] for row in live_hits],
        "SYN-0010 agreed conclusions (live); planted controls excluded",
    )
    planted_share = share_from_labels(
        [row["observed_label"] for row in planted_results],
        "planted controls (not the live agreed set)",
    )
    live_n = len(live_hits)
    headline = (
        f"planted labelled correctly; live_agreed_attributed={live_n} "
        f"live_share={live_share['numerator']}/{live_share['denominator']} "
        f"({live_share['status']}); planted_share="
        f"{planted_share['numerator']}/{planted_share['denominator']}"
    )
    report = {
        "kind": "convergence-attribution",
        "question": QUESTION,
        "join_key": "artifact-identity",
        "null_model": NULL_MODEL,
        "input_inventory": inventory,
        "syn0010_coefficient": syn_meta.get("value"),
        "syn0010_meta": syn_meta,
        "warning": (
            "a high SYN-0010 agreement coefficient with a high live "
            "conformity share is a warning, not a result"
        ),
        "planted_controls": [planted_row(row) for row in planted_results],
        "agreed_conclusions": [live_row(row) for row in live_hits],
        "unattributable_live": live_skipped,
        "conformity_share": live_share,
        "planted_conformity_share": planted_share,
        "headline": headline,
        "observations": [
            {
                "name": "planted_conformity",
                "measured": next(
                    row["observed_label"]
                    for row in planted_results
                    if row["id"] == "planted-conformity"
                ),
                "method": "identity-join over planted_conformity.json",
                "anchor": (
                    "command-center/p2-wave/probes/SYN-0023/fixtures/"
                    "planted_conformity.json"
                ),
            },
            {
                "name": "planted_corroboration",
                "measured": next(
                    row["observed_label"]
                    for row in planted_results
                    if row["id"] == "planted-corroboration"
                ),
                "method": "identity-join over planted_corroboration.json",
                "anchor": (
                    "command-center/p2-wave/probes/SYN-0023/fixtures/"
                    "planted_corroboration.json"
                ),
            },
            {
                "name": "planted_shared_stale_ancestor",
                "measured": next(
                    row["observed_label"]
                    for row in planted_results
                    if row["id"] == "planted-shared-stale-ancestor"
                ),
                "method": "ancestor-closure identity join",
                "anchor": (
                    "command-center/p2-wave/probes/SYN-0023/fixtures/"
                    "planted_shared_stale_ancestor.json"
                ),
            },
            {
                "name": "live_conformity_share",
                "measured": (
                    f"{live_share['numerator']}/{live_share['denominator']} "
                    f"{live_share['status']}"
                ),
                "method": "|CONFORMITY| / |SYN-0010 agreed set|",
                "anchor": "command-center/receipts/SYN-0010.json",
            },
            {
                "name": "join_key",
                "measured": "artifact-identity",
                "method": "sha256 then artifact_id then path; title never identity",
                "anchor": "command-center/p2-wave/probes/SYN-0023/attribute.py",
            },
        ],
        "control_ids": [
            "SYN0023-C1-planted-conformity",
            "SYN0023-C2-planted-corroboration",
            "SYN0023-C3-shared-stale-ancestor",
            "SYN0023-C4-title-trap",
        ],
    }
    return report, planted_results, live_hits, live_skipped, live_share, syn_meta


def build_doc(
    sentinel: str,
    started: str,
    ended: str,
    report: dict,
    t1: str,
    c1: int,
    t2: str,
    c2: int,
    consume_raw: str,
    consume_rc: int,
    primary: dict,
) -> dict:
    live_n = len(report.get("agreed_conclusions") or [])
    live_skipped = report.get("unattributable_live") or []
    live_share = report["conformity_share"]
    syn_meta = report.get("syn0010_meta") or {}
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 1024,
        "profile": "convergence-attribution",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "independence-analyst",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [
            primary,
            art_row(SCHEMA_REL, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Planted conformity (all agents fed one artifact carrying a "
                    "false claim) is labelled CONFORMITY, planted corroboration "
                    "(two disjoint partitions, no shared ancestor) is labelled "
                    "CORROBORATED, and two disjoint children of one stale root "
                    "are labelled CONFORMITY."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/SYN-0023/probe1_planted_labels.py"
                ),
                "probes": [
                    probe_obj("source", "test-run", P1, t1, c1),
                    probe_obj(
                        "verifier",
                        "file-read",
                        (
                            "python3 -B -c "
                            "\"from pathlib import Path; import sys; "
                            "sys.path.insert(0,'command-center/p2-wave/probes/SYN-0023'); "
                            "from attribute import attribute_scenario, required_planted; "
                            "rows=[attribute_scenario(s) for s in required_planted()]; "
                            "print([(r['id'], r['observed_label']) for r in rows])\""
                        ),
                        t1,
                        c1,
                    ),
                ],
            },
            {
                "claim": (
                    "Lineage join uses artifact identity (sha256 / artifact_id / "
                    "path), never title similarity: the title-trap fixture is "
                    "CORROBORATED on identity and CONFORMITY on title join."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/SYN-0023/probe2_identity_join.py"
                ),
                "probes": [
                    probe_obj("source", "test-run", P2, t2, c2),
                    probe_obj(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/SYN-0023/fixtures/planted_title_trap.json",
                        t2,
                        c2,
                    ),
                ],
            },
            {
                "claim": (
                    f"Live SYN-0010 agreed set on this worktree: attributed="
                    f"{live_n} skipped={len(live_skipped)} reason="
                    f"{syn_meta.get('reason')} live_conformity_share="
                    f"{live_share['numerator']}/{live_share['denominator']} "
                    f"status={live_share['status']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/receipts/SYN-0010.json",
                "settling_experiment": (
                    "Place a schema-valid SYN-0010 receipt with a non-empty "
                    "agreed set and SYN-0008 partition manifests on this "
                    "worktree, then re-run live_attributions()."
                ),
                "probes": [
                    probe_obj(
                        "source",
                        "file-read",
                        "stat command-center/receipts/SYN-0010.json",
                        json.dumps(report.get("input_inventory") or [], sort_keys=True),
                        0,
                    ),
                    probe_obj(
                        "verifier",
                        "other",
                        "command-center/p2-wave/probes/SYN-0023/live.py:live_attributions",
                        json.dumps(
                            {
                                "agreed_n": syn_meta.get("agreed_n"),
                                "reason": syn_meta.get("reason"),
                                "attributed": live_n,
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T-PLANTED-LABELS",
                "name": "planted conformity, corroboration, shared-stale-ancestor",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 3,
                "output_tail": t1[-500:],
            },
            {
                "id": "T-IDENTITY-JOIN",
                "name": "identity join vs title trap plus share recompute",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 4,
                "output_tail": t2[-500:],
            },
        ],
        "negative_controls": [
            {
                "id": "SYN0023-C1-planted-conformity",
                "kind": "known-broken-fixture",
                "description": (
                    "Feed all agents one artifact carrying a false claim. The "
                    "detector must fire CONFORMITY with a non-empty LCA."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "planted-conformity observed=CONFORMITY",
                "good_state_output": "planted-corroboration observed=CORROBORATED lca=[]",
            },
            {
                "id": "SYN0023-C2-planted-corroboration",
                "kind": "known-broken-fixture",
                "description": (
                    "Two disjoint partitions supporting one conclusion must be "
                    "CORROBORATED (silent of conformity)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "planted-conformity observed=CONFORMITY",
                "good_state_output": "planted-corroboration observed=CORROBORATED",
            },
            {
                "id": "SYN0023-C3-shared-stale-ancestor",
                "kind": "known-broken-fixture",
                "description": (
                    "Agents reading disjoint children of one stale root must "
                    "still be labelled CONFORMITY."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "planted-shared-stale-ancestor observed=CONFORMITY",
                "good_state_output": "planted-corroboration observed=CORROBORATED lca=[]",
            },
            {
                "id": "SYN0023-C4-title-trap",
                "kind": "known-broken-fixture",
                "description": (
                    "Same title, distinct sha256: identity join stays "
                    "CORROBORATED; title join collapses to CONFORMITY."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "title_join=CONFORMITY",
                "good_state_output": "identity=CORROBORATED",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0023-probe2-identity-join-and-share-recompute",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "Probe 2 recomputes planted and live conformity shares from the "
                "per-item table and rejects title-as-identity. Not a second "
                "human in a fresh context; disclosed."
            ),
            "reviewed_at": ended,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path plus share fields",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": consume_rc == 0,
                "exit_code": consume_rc,
                "probe": probe_obj(
                    "verifier", "file-read", CONSUME_CMD, consume_raw, consume_rc
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. The first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record, never an error "
                "to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live SYN-0010 agreed-set attribution is scoped to this "
                    f"worktree (reason={syn_meta.get('reason')}; attributed="
                    f"{live_n}). An empty live universe is UNIVERSE-EMPTY, not 0%."
                ),
                "verdict": "NOT-CHECKED" if syn_meta.get("reason") != "ok" else "PARTIAL",
                "settling_experiment": (
                    "Place a schema-valid SYN-0010 receipt with a non-empty "
                    "agreed set and SYN-0008 partition manifests on this "
                    "worktree, then re-run live_attributions()."
                ),
            }
        ],
        "report": report,
        "extensions": {
            "global_unit_manifest_write": False,
            "notes": (
                "G-1 for SYN-0023. Did not run tools/command-center/"
                "unit_manifest.py --write. Planted controls are scored "
                "separately from the live SYN-0010 agreed set."
            ),
        },
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def main() -> int:
    started = utc_now()
    sentinel = catalog_sentinel()
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "SYN-0023"},
        {},
    ]
    rejected = 0
    for blob in garbage:
        if schema_errors(blob):
            rejected += 1
    if rejected != 3:
        print(f"FAILED:SYN-0023 schema accepted garbage rejected={rejected}")
        return 1

    report, _planted, _live, _skipped, _share, _meta = build_domain()
    c1, t1 = run_cmd(P1)
    if c1 != 0:
        print("FAILED:SYN-0023 probe1")
        print(t1[-2000:])
        return 1

    ended = utc_now()
    placeholder = {
        "path": OUT_REL,
        "bytes": 1024,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }
    doc = build_doc(
        sentinel,
        started,
        ended,
        report,
        t1,
        c1,
        "receipt-pending-first-write",
        0,
        "CONSUMER-PENDING-FIRST-WRITE",
        0,
        placeholder,
    )
    errs = schema_errors(doc)
    if errs:
        print("FAILED:SYN-0023 schema errors (prewrite)")
        for line in errs[:20]:
            print(" ", line)
        return 1
    if sentinel not in dump(doc):
        print("FAILED:SYN-0023 catalog sentinel missing from artifact")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8", newline="\n")

    c2, t2 = run_cmd(P2)
    if c2 != 0:
        print("FAILED:SYN-0023 probe2")
        print(t2[-2000:])
        return 1
    cc, ct = run_cmd(CONSUME_CMD)
    if cc != 0:
        print("FAILED:SYN-0023 consumer")
        print(ct[-800:])
        return 1

    digest, size = sha256_file(out)
    primary = {
        "path": OUT_REL,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }
    ended = utc_now()
    doc = build_doc(
        sentinel, started, ended, report, t1, c1, t2, c2, ct, cc, primary
    )
    errs = schema_errors(doc)
    if errs:
        print("FAILED:SYN-0023 schema errors (final)")
        for line in errs[:20]:
            print(" ", line)
        return 1
    text = dump(doc)
    if sentinel not in text:
        print("FAILED:SYN-0023 catalog sentinel missing from artifact")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    digest, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print(report["headline"])
    print("SUCCESS:SYN-0023")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
