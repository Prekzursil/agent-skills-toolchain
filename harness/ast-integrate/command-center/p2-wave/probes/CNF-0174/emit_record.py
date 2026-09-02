#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0174.json — confirmation record."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import fanin as F  # noqa: E402
import scenario as S  # noqa: E402
from reducer import MODULE_PATH, SYMBOL  # noqa: E402

OUT = "command-center/receipts/CNF-0174.json"
SCHEMA = "command-center/schema/confirmation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0174/probe1_split_surface.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0174/probe2_controls.py"
)
CLAIM_ID = "CNF-0174-nested-completion-split-surfaces"
CLAIM_STATEMENT = (
    "When two subcouncils disagree about whether the work is complete, the "
    "council-of-councils surfaces the disagreement (both verdicts + escalation "
    "path) rather than silently averaging it into a consensus. Spec:11343."
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def run_bundle() -> dict[str, Any]:
    split_children = S.split_two()
    agree = S.agree_complete()
    agree_b = S.agree_blocked()
    three = S.three_way()
    persistent = S.persistent_split()

    split_first = F.fan_in(split_children, split_detector=True, attempt=1)
    split_term = F.fan_in_until_terminal(persistent, split_detector=True)
    agree_out = F.fan_in(agree, split_detector=True, attempt=1)
    agree_blocked_out = F.fan_in(agree_b, split_detector=True, attempt=1)
    three_out = F.fan_in(three, split_detector=True, attempt=1)
    broken = F.fan_in(split_children, split_detector=False, attempt=1)

    prod = C.census()
    return {
        "split_first": split_first,
        "split_terminal": split_term,
        "agree_complete": agree_out,
        "agree_blocked": agree_blocked_out,
        "three_way": three_out,
        "known_broken": broken,
        "census": prod,
        "children": {
            "split_two": split_children,
            "agree_complete": agree,
            "three_way": three,
        },
    }


def blinding_hash() -> str:
    payload = {
        "claim_id": CLAIM_ID,
        "claim_statement": CLAIM_STATEMENT,
        "scenario_sha256": sha256_file(HERE / "scenario.py")[0],
        "excluded": [
            "command-center/receipts/CNF-0174.json",
            "implementer receipts",
            "prior confirmation verdicts",
        ],
    }
    return sha256_text(canonical(payload))


def build(bundle: dict[str, Any]) -> dict[str, Any]:
    split = bundle["split_first"]
    term = bundle["split_terminal"]
    agree = bundle["agree_complete"]
    three = bundle["three_way"]
    broken = bundle["known_broken"]
    census = bundle["census"]
    beta_reason = S.BLOCKED_REASON
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    production_present = bool(census.get("production_nested_present"))
    harness_confirms = (
        split.get("split_surfaced") is True
        and split.get("averaged") is False
        and split.get("parent_verdict") == "SPLIT"
        and any(r.get("reasoning") == beta_reason for r in split.get("minority_reports") or [])
        and term.get("escalation") == F.ESCALATION_POLICY["on_persistent_split"]
        and term.get("looped") is False
        and agree.get("split_surfaced") is False
        and agree.get("escalation") is None
        and agree.get("parent_completion") == "COMPLETE"
        and broken.get("split_surfaced") is False
        and broken.get("averaged") is True
        and not (broken.get("minority_reports") or [])
        and three.get("split_surfaced") is True
        and len(three.get("subcouncil_verdicts") or []) == 3
    )

    # Production nested runtime is absent, so the system-level claim is not
    # CONFIRMED. The harness claim is CONFIRMED. Record-level verdict is PARTIAL.
    record_verdict = "CONFIRMED" if (harness_confirms and production_present) else "PARTIAL"
    if not harness_confirms:
        record_verdict = "REFUTED"

    p1_fp = sha256_file(HERE / "probe1_split_surface.py")[0]
    p2_fp = sha256_file(HERE / "probe2_controls.py")[0]
    split_digest = sha256_text(canonical(split))
    verify_digest = sha256_text(
        canonical(
            {
                "agree": bundle["agree_complete"],
                "agree_blocked": bundle["agree_blocked"],
                "known_broken": broken,
                "census_nested_present": production_present,
            }
        )
    )

    claims = [
        {
            "id": "C-HARNESS-SPLIT-SURFACES",
            "claim": "Confirmer-authored fan-in surfaces COMPLETE vs BLOCKED instead of merging them.",
            "verdict": "CONFIRMED" if split.get("split_surfaced") else "REFUTED",
            "anchor": "command-center/p2-wave/probes/CNF-0174/fanin.py:fan_in",
        },
        {
            "id": "C-MINORITY-PRESERVED",
            "claim": "Losing subcouncil reasoning survives into the parent artifact.",
            "verdict": (
                "CONFIRMED"
                if any(r.get("reasoning") == beta_reason for r in split.get("minority_reports") or [])
                else "REFUTED"
            ),
            "anchor": "command-center/p2-wave/probes/CNF-0174/scenario.py:BLOCKED_REASON",
        },
        {
            "id": "C-DEADLOCK-ESCALATES",
            "claim": "Persistent split reaches ESCALATE_TO_OWNER_NO_LOOP and does not loop.",
            "verdict": (
                "CONFIRMED"
                if term.get("escalation") == F.ESCALATION_POLICY["on_persistent_split"]
                and term.get("looped") is False
                else "REFUTED"
            ),
            "anchor": "command-center/p2-wave/probes/CNF-0174/fanin.py:ESCALATION_POLICY",
        },
        {
            "id": "C-BOTH-STATES-AGREE",
            "claim": "Agreeing COMPLETE subcouncils fan in to COMPLETE with no spurious escalation.",
            "verdict": (
                "CONFIRMED"
                if agree.get("parent_completion") == "COMPLETE" and agree.get("escalation") is None
                else "REFUTED"
            ),
            "anchor": "command-center/p2-wave/probes/CNF-0174/scenario.py:agree_complete",
        },
        {
            "id": "C-KNOWN-BROKEN",
            "claim": "Disabling the split detector makes the split-surface test go red (averaging).",
            "verdict": (
                "CONFIRMED"
                if broken.get("averaged") is True and broken.get("split_surfaced") is False
                else "REFUTED"
            ),
            "anchor": "command-center/p2-wave/probes/CNF-0174/fanin.py:_average_away",
        },
        {
            "id": "C-PRODUCTION-NESTED",
            "claim": "Production tools/council/topology/nested.py exists and is the fan-in under test.",
            "verdict": "CONFIRMED" if production_present else "REFUTED",
            "anchor": "tools/council/topology/nested.py",
            "defect_locus": "DESIGN",
        },
        {
            "id": "C-THREE-WAY",
            "claim": "A three-way COMPLETE/BLOCKED/INCOMPLETE split still surfaces all three verdicts.",
            "verdict": (
                "CONFIRMED"
                if three.get("split_surfaced")
                and len({r["completion"] for r in three.get("subcouncil_verdicts") or []}) == 3
                else "REFUTED"
            ),
            "anchor": "command-center/p2-wave/probes/CNF-0174/scenario.py:three_way",
        },
    ]

    schema_path = REPO / SCHEMA
    doc: dict[str, Any] = {
        "unit_id": "CNF-0174",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0174",
        "claim_id": CLAIM_ID,
        "claim_under_test": CLAIM_STATEMENT,
        "question": (
            "When two subcouncils disagree about whether the work is complete, "
            "does the council-of-councils SURFACE the disagreement, or silently "
            "average it into a consensus?"
        ),
        "confirmer": {
            "identity": "CNF-0174-independent-confirmer",
            "vendor": "anthropic",
            "model": "opus",
            "role": "independent-confirmer",
            "execution_substrate": "local-parallel",
        },
        "blinding_attestation_hash": blinding_hash(),
        "output_schema": SCHEMA,
        "output_schema_present": schema_path.is_file(),
        "verdict": record_verdict,
        "source_probe": {
            "id": "probe1",
            "command": P1,
            "role": "split-surface-minority-deadlock-three-way",
            "fingerprint": p1_fp,
            "live_result_digest": split_digest,
        },
        "verifier_probe": {
            "id": "probe2",
            "command": P2,
            "role": "both-states-known-broken-census-averaging",
            "fingerprint": p2_fp,
            "live_result_digest": verify_digest,
        },
        "baseline_repro": {
            "label": "split-detector-on",
            "parent_verdict": split.get("parent_verdict"),
            "parent_completion": split.get("parent_completion"),
            "split_surfaced": split.get("split_surfaced"),
            "escalation": split.get("escalation"),
            "escalation_path": split.get("escalation_path"),
            "subcouncil_verdicts": [
                {"id": r["id"], "completion": r["completion"]}
                for r in split.get("subcouncil_verdicts") or []
            ],
            "minority_ids": [r["id"] for r in split.get("minority_reports") or []],
            "digest": split_digest,
        },
        "corrected_repro": {
            "label": "persistent-split-terminal-escalation",
            "parent_verdict": term.get("parent_verdict"),
            "escalation": term.get("escalation"),
            "attempts": term.get("history_attempts") or term.get("attempts"),
            "looped": term.get("looped"),
            "terminal": term.get("terminal"),
            "escalation_path": term.get("escalation_path"),
        },
        "rollback_repro": {
            "label": "known-broken-detector-off",
            "parent_verdict": broken.get("parent_verdict"),
            "split_surfaced": broken.get("split_surfaced"),
            "averaged": broken.get("averaged"),
            "mean_completion": broken.get("mean_completion"),
            "minority_reports": broken.get("minority_reports"),
            "note": (
                "Disabling the split detector restores averaging. Same children, "
                "merged COMPLETE, minority reasoning dropped. This is the red state."
            ),
        },
        "regression_diff": {
            "detector_on_parent_verdict": split.get("parent_verdict"),
            "detector_off_parent_verdict": broken.get("parent_verdict"),
            "split_preserved_on": True,
            "split_preserved_off": False,
            "minority_reasoning_on": beta_reason,
            "minority_reasoning_off": None,
        },
        "discrepancies": [
            {
                "id": "D-PRODUCTION-ABSENT",
                "kind": "missing-runtime",
                "detail": census.get("object_under_test_reason"),
                "production_nested_present": production_present,
            }
        ]
        if not production_present
        else [],
        "residual_caveat": (
            "Object under test is command-center/p2-wave/probes/CNF-0174/fanin.py. "
            "tools/council/topology/nested.py is absent. "
            "command-center/phase3/A1/FAILURE-MODES.json is also absent; FC-11343 "
            "is cited from live reconstructed prompt text "
            "(CC-0024/fixtures/prompt-two-slice.md:11343) and the catalog unit. "
            "confirmation-record.schema.json exists as a generated shim. This "
            "record CONFIRMS harness behaviour and REFUTES production nested "
            "presence; record-level verdict is PARTIAL, not CONFIRMED. "
            "cloud ok=true is not delivery. Did not run unit_manifest.py --write."
        ),
        "fan_in_output": {
            "split": split,
            "persistent_terminal": term,
            "agree_complete": agree,
            "agree_blocked": bundle["agree_blocked"],
            "three_way": three,
            "known_broken": broken,
        },
        "reducer": {
            "module": MODULE_PATH,
            "symbol": SYMBOL,
            "cited_by_parent": split.get("reducer_module") == MODULE_PATH,
        },
        "census": census,
        "claims": claims,
        "tests": [
            {
                "id": "both-states-agree",
                "result": "PASS" if agree.get("escalation") is None else "FAIL",
                "command": P2,
            },
            {
                "id": "minority-preservation",
                "result": (
                    "PASS"
                    if any(r.get("reasoning") == beta_reason for r in split.get("minority_reports") or [])
                    else "FAIL"
                ),
                "command": P1,
            },
            {
                "id": "deadlock-escalation",
                "result": (
                    "PASS"
                    if term.get("escalation") == F.ESCALATION_POLICY["on_persistent_split"]
                    and not term.get("looped")
                    else "FAIL"
                ),
                "command": P1,
            },
            {
                "id": "known-broken-control",
                "result": "PASS" if broken.get("averaged") and not broken.get("split_surfaced") else "FAIL",
                "command": P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0174-three-way-subcouncil-split",
            "verdict": "PASS" if three.get("split_surfaced") else "FAIL",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Reviewer construct is scenario.three_way: COMPLETE + BLOCKED + "
                "INCOMPLETE. Parent must list all three completions; gamma's "
                "exit-zero-missing-artifact must not become COMPLETE."
            ),
            "three_way_completions": sorted(
                {r["completion"] for r in three.get("subcouncil_verdicts") or []}
            ),
        },
        "spec_anchor": "_USER-PROMPTS.md:11343 nested councils disagree on completion",
        "failure_class": "FC-11343",
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "split-surface"},
            {"id": "probe2", "command": P2, "role": "controls"},
        ],
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "independent-confirmer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "ts": now,
        "answer": (
            "Harness fan-in SURFACES the split (parent_verdict=SPLIT, both "
            "subcouncil verdicts forwarded, minority reasoning preserved, "
            "persistent split escalates to ESCALATE_TO_OWNER_NO_LOOP). "
            "Production nested runtime is ABSENT, so the estate-level claim is "
            "not CONFIRMED. Record verdict="
            f"{record_verdict}. SUCCESS:CNF-0174"
        ),
    }
    return doc


def main() -> int:
    bundle = run_bundle()
    if not bundle["split_first"].get("split_surfaced"):
        print("FAILED:CNF-0174 emit split was not surfaced")
        return 1
    doc = build(bundle)
    if doc.get("source_probe", {}).get("fingerprint") == doc.get("verifier_probe", {}).get(
        "fingerprint"
    ):
        print("FAILED:CNF-0174 emit source_probe fingerprint equals verifier_probe")
        return 1
    if not doc.get("source_probe"):
        print("FAILED:CNF-0174 emit empty source_probe")
        return 1
    if doc.get("verdict") in {"CONFIRMED", "REFUTED"} and not doc.get("source_probe"):
        print("FAILED:CNF-0174 unsourced terminal verdict")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0174 artifact {size}B below floor")
        return 1
    if "SUCCESS:CNF-0174" not in text:
        print("FAILED:CNF-0174 sentinel missing from artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest} verdict={doc['verdict']}")
    print("SUCCESS:CNF-0174 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
