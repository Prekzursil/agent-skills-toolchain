#!/usr/bin/env python3
"""Pack CC-0023 — owner adjudication packet as honest BLOCKED receipt.

Emits state=BLOCKED with blocked-on-owner-adjudication after green controls.
Catalog: owner_approval_required=true; owner is decision authority; one
independent reviewer checks that no reference was resolved without an owner
answer. Never invent SUCCESS. Never invent owner answers or timestamps.

Linux Cloud / no owner session: every unanswered ref is DEFERRED with impact.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0023"
OUT = "command-center/receipts/CC-0023.json"
SCHEMA = "command-center/schema/option-id-namespace.schema.json"
ALSO = ["command-center/schema/receipt.schema.json"]
PROBE_DIR = "command-center/p2-wave/probes/CC-0023"
TESTS = "tools/command-center/tests/test_owner_option_id_adjudication.py"
PROBE1 = f"{PROBE_DIR}/probe1_controls.py"
LIB = "command-center/lib/owner_option_id_adjudication.py"
CENSUS = "command-center/option-id/CC-0023-UNRESOLVED-REFS.json"
PACKET = "command-center/option-id/OWNER-ADJUDICATION-PACKET.md"
LEDGER = "command-center/option-id/OWNER-ADJUDICATION-LEDGER.json"
OWNER_DECISIONS = "command-center/OWNER-DECISIONS.md"
OWNER_Q = "command-center/OWNER-QUESTION-PACKET.md"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
TS0 = "2026-09-08T02:00:00Z"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=L.REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def load_review() -> dict | None:
    """Promote only when owner answers exist AND independent review confirms
    no ref was resolved without an owner answer. On Linux Cloud this stays None.
    """
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    if rev.get("no_resolution_without_owner_answer") is not True:
        return None
    # Must also have real owner answers — never SUCCESS on all-DEFERRED.
    led = json.loads((L.REPO / LEDGER).read_text(encoding="utf-8"))
    if led.get("counts", {}).get("owner_answered", 0) < 1:
        return None
    if led.get("counts", {}).get("deferred", 58) != 0:
        # Allow partial? Catalog wants all 58 ended answered OR deferred.
        # SUCCESS only when zero deferred remain AND review PASS.
        if led["counts"].get("deferred", 1) > 0:
            return None
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"CC-0023 pytest failed:\n{out}")

    p1_rc, p1_out = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    (L.REPO / PROBE_DIR / "probe1-controls.raw.txt").write_text(
        p1_out, encoding="utf-8"
    )
    if p1_rc != 0:
        raise SystemExit(f"CC-0023 probe1 failed:\n{p1_out}")

    controls = json.loads(
        (L.REPO / PROBE_DIR / "probe1-controls.json").read_text(encoding="utf-8")
    )
    led = json.loads((L.REPO / LEDGER).read_text(encoding="utf-8"))
    counts = led["counts"]

    rev = load_review()
    # SUCCESS only with full owner settlement + independent review.
    success = rev is not None and counts.get("deferred") == 0

    p_pytest = L.probe(
        "source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_probe1 = L.probe(
        "verifier", "command", f"python3 -B {PROBE1}", p1_out, p1_rc
    )

    ctrl_bits = ", ".join(
        f"{k}={'PASS' if v['pass'] else 'FAIL'}"
        for k, v in sorted(controls["controls"].items())
    )

    if success:
        state = "SUCCESS"
        sentinel = f"SUCCESS:{UNIT}"
        notes = rev.get("notes", "")
        if not isinstance(notes, str):
            notes = json.dumps(notes)
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-owner-answers-and-independent-review"
    else:
        state = "BLOCKED"
        # CC-0022-style withhold → FAILED blocked-on-owner-adjudication
        classification = "blocked-on-owner-adjudication"
        if (
            controls.get("ok")
            and counts.get("deferred") == 58
            and counts.get("owner_answered") == 0
        ):
            classification = "blocked-on-owner-adjudication"
        elif controls.get("ok") and counts.get("owner_answered", 0) > 0:
            # Packet green, some answers, but review unpaid / deferred remain
            classification = "blocked-on-independent-review"
        sentinel = (
            f"FAILED:{UNIT} {classification}; "
            f"refs=58 deferred={counts['deferred']} "
            f"owner_answered={counts['owner_answered']}; "
            f"questions={controls.get('n_questions')}; "
            f"controls[{ctrl_bits}]; "
            f"invented_owner_answers=false; "
            f"SUCCESS:{UNIT} withheld pending owner adjudication"
        )
        reviewer = {
            "reviewer_id": "awaiting-owner-adjudication",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only on Linux Cloud single-checkout. No owner "
                "session available — zero owner answers invented; all 58 refs "
                "recorded DEFERRED with impact statements. Catalog "
                "owner_approval_required=true unmet. Reviewer_requirement unmet: "
                "Owner is decision authority; one independent reviewer must later "
                "confirm no reference was resolved without an owner answer. "
                "Self-review banned; independent-review.json not invented; "
                "SUCCESS not invented. Scope: Prompt-One Windows trees and "
                "_optid_adjudicate.json intermediates unmounted; 58 refs "
                "enumerated as census bucket ordinals from OPTION-ID-RESOLUTION "
                "(requires_author_adjudication=58); per-token line IDs not "
                "fabricated. No silent M-NN rewrites applied to docs 16/18/19."
            ),
        }
        residual = [
            {
                "claim": (
                    "Owner has not answered the 12 foundation questions; all 58 "
                    "algorithmically unresolvable refs remain DEFERRED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Owner (or authors of docs 16/18/19) answers OQ-CC23-01..12 "
                    "one at a time with timestamped records in "
                    f"{LEDGER} / {OWNER_DECISIONS}; independent reviewer confirms "
                    "no ref disposition is OWNER_ANSWERED without provenance=owner; "
                    "then re-pack may emit SUCCESS only when deferred==0."
                ),
            }
        ]
        failure = {
            "classification": [classification, "owner-blocked"],
            "reason": (
                "Owner adjudication packet + four catalog controls are green "
                f"(pytest; probe1 ok={controls.get('ok')}; "
                f"deferred={counts['deferred']}/58; "
                f"owner_answered={counts['owner_answered']}; "
                f"controls[{ctrl_bits}]). Catalog owner_approval_required unmet "
                "and no timestamped owner answers exist — do not emit SUCCESS. "
                "LLM/inferred settlement banned (86% accurate / 100% of errors = "
                "data loss)."
            ),
            "blocked_on": "owner adjudication of 58 unresolvable option-id refs",
            "diagnostic_tail": (out + "\n" + p1_out)[-4000:],
            "two_signal_proof": [p_probe1, p_pytest],
        }
        anti = "BLOCKED-pending-owner-adjudication"

    downstream = [
        {
            "consumer": "owner_option_id_adjudication.run_all_controls",
            "artifact_path": f"{PROBE_DIR}/probe1-controls.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_probe1,
        },
        {
            "consumer": "owner_option_id_adjudication.materialize",
            "artifact_path": LEDGER,
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_probe1,
        },
    ]

    arts = [
        L.art(LIB, "primary"),
        L.art(CENSUS, "primary"),
        L.art(PACKET, "primary"),
        L.art(LEDGER, "primary"),
        L.art(OWNER_DECISIONS, "supporting"),
        L.art(OWNER_Q, "supporting"),
        L.art("command-center/OPTION-ID-RESOLUTION.json", "supporting"),
        L.art(f"{PROBE_DIR}/fixtures/doc18-blocks-before.md", "control"),
        L.art(f"{PROBE_DIR}/fixtures/doc18-blocks-silent-rewrite.md", "control"),
        L.art(f"{PROBE_DIR}/probe1-controls.json", "log"),
        L.art(f"{PROBE_DIR}/probe1-controls.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(TESTS, "supporting"),
    ]

    c = controls["controls"]
    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0023",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "owner-liaison",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Enumerated 58 algorithmically unresolvable refs from "
                    "OPTION-ID-RESOLUTION census buckets "
                    f"(doc17=10, doc16=16, doc18=11, doc19=5, diagrams=2, "
                    f"wave1=2, scratch=12; sum=58). Batched into "
                    f"{controls.get('n_questions')} foundation questions. "
                    f"Owner silent on Linux Cloud: deferred="
                    f"{counts['deferred']} owner_answered="
                    f"{counts['owner_answered']}; invented_owner_answers=false."
                ),
                "CONFIRMED",
                f"file:{CENSUS}",
                [p_probe1, p_pytest],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Four catalog controls: [{ctrl_bits}]. All 58 refs end "
                    "DEFERRED with impact (or would end OWNER_ANSWERED only with "
                    "provenance=owner+timestamp). Silent unattributed rewrite "
                    "fixture fires; unchanged excerpt silent. Grouping uses 7 "
                    "ref-bearing questions not 58. Durability round-trip of "
                    "OWNER-DECISIONS CC-0023 section recovers recorded owner "
                    f"answers (n={len(led.get('recorded_owner_answers') or [])})."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/probe1-controls.json",
                [p_probe1, p_pytest],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "No retry loop on the owner. Ask once per decision, record "
                "DEFERRED+impact if unanswered, continue independent work."
            ),
        },
        "tests": [
            {
                "id": "deferred-or-answered-coverage",
                "name": "All 58 refs end owner-answered or DEFERRED with impact.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_all_58_end_deferred_or_answered_with_impact -q"
                ),
                "result": "PASS" if c["deferred-or-answered-coverage"]["pass"] else "FAIL",
                "assertions": 4,
                "output_tail": out[-800:],
            },
            {
                "id": "zero-silent-rewrites",
                "name": "Unattributed M-NN rewrites fail; unchanged excerpt passes.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_zero_silent_rewrites_unattributed_change_fails -q"
                ),
                "result": "PASS"
                if c["zero-silent-rewrites"]["pass"]
                and c["silent-rewrite-bad-state-fires"]["pass"]
                else "FAIL",
                "assertions": 3,
                "output_tail": p1_out[-800:],
            },
            {
                "id": "grouping-batched",
                "name": "Shared decisions batched (12 questions, not 58).",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_grouping_batches_shared_decisions -q"
                ),
                "result": "PASS" if c["grouping-shared-decisions-batched"]["pass"] else "FAIL",
                "assertions": 3,
                "output_tail": out[-800:],
            },
            {
                "id": "durability-roundtrip",
                "name": "Re-read OWNER-DECISIONS returns every recorded owner answer.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_durability_roundtrip_empty_owner_answers -q"
                ),
                "result": "PASS"
                if c["durability-owner-decisions-roundtrip"]["pass"]
                else "FAIL",
                "assertions": 3,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "silent-rewrite-fires",
                "known-broken-fixture",
                "Unattributed M-16/M-18 → MECH rewrite must fail the silent-rewrite control.",
                True,
                True,
                bad=c["silent-rewrite-bad-state-fires"]["detail"],
                good="unchanged excerpt pass",
            ),
            L.control(
                "fake-answer-without-provenance-stays-deferred",
                "mutation",
                "Answers lacking provenance=owner must not settle refs.",
                True,
                True,
                bad="would count forged answers",
                good=f"owner_answered={counts['owner_answered']}",
            ),
            L.control(
                "census-arithmetic-58",
                "other",
                "Bucket sum and REF-001..058 must equal requires_author_adjudication=58.",
                True,
                True,
                bad="bucket_sum!=58",
                good=c["census-arithmetic-58"]["detail"],
            ),
        ],
        "reviewer": reviewer,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": downstream,
        "residual_unknowns": residual,
        "defects": [],
        "report": {
            "kind": "option-id-namespace",
            "observations": [
                {
                    "name": "requires_author_adjudication",
                    "measured": 58,
                    "method": "OPTION-ID-RESOLUTION.json totals + census bucket expansion",
                    "anchor": CENSUS,
                },
                {
                    "name": "deferred_count",
                    "measured": counts["deferred"],
                    "method": "apply_owner_silence with no provenance=owner answers",
                    "anchor": LEDGER,
                },
                {
                    "name": "owner_answered_count",
                    "measured": counts["owner_answered"],
                    "method": "ledger recorded_owner_answers",
                    "anchor": LEDGER,
                },
                {
                    "name": "foundation_questions",
                    "measured": controls.get("n_questions"),
                    "method": "QUESTIONS list in owner_option_id_adjudication.py",
                    "anchor": PACKET,
                },
            ],
            "control_ids": [
                "deferred-or-answered-coverage",
                "zero-silent-rewrites",
                "grouping-batched",
                "durability-roundtrip",
            ],
            "counts": counts,
            "controls": controls["controls"],
            "honesty": led.get("honesty"),
            "independent_review_present": REVIEW.is_file(),
            "scope": (
                "linux-cloud-single-checkout; owner session absent; "
                "58 refs as census bucket ordinals; no silent rewrites"
            ),
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "linux_cloud_scope": (
                "No owner session; Prompt-One Windows trees unmounted; "
                "per-token line IDs not invented"
            ),
            "depends_on": ["CC-0021", "CC-0022"],
        },
    }
    if failure is not None:
        receipt["failure"] = failure

    (L.REPO / MANIFEST).write_text(
        json.dumps(
            {
                "entry_id": UNIT,
                "unit_id": UNIT,
                "artifacts": [
                    OUT,
                    LIB,
                    CENSUS,
                    PACKET,
                    LEDGER,
                    OWNER_DECISIONS,
                    f"{PROBE_DIR}/probe1-controls.json",
                ],
                "state": state,
                "registered_at": ended,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rc_w = L.write_if_valid(receipt, OUT, SCHEMA, also=ALSO)
    if rc_w != 0:
        raise SystemExit(rc_w)
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA, also=ALSO)
    if rc2 != 0:
        raise SystemExit(rc2)

    v_rc, v_out = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(v_out, encoding="utf-8")
    if v_rc != 0 or "ACCEPT" not in v_out:
        raise SystemExit(f"receipt_validate rejected:\n{v_out}")

    print(f"PACKED {OUT} state={state} bytes={L.art(OUT)['bytes']}")
    print(
        f"deferred={counts['deferred']} answered={counts['owner_answered']} "
        f"invented={led['honesty']['invented_owner_answers']}"
    )
    print(f"independent_review={REVIEW.is_file()} (must stay false for this emit)")
    return receipt


if __name__ == "__main__":
    build()
