#!/usr/bin/env python3
"""Pack CC-0018 receipt.

BLOCKED until the catalog's independent adversarial reviewer lands with PASS.
Never invents independent-review.json or SUCCESS. success_invented=false.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0018"
OUT = "command-center/receipts/CC-0018.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0018"
GATE = "tools/command-center/claim_rank.py"
TESTS = "tools/command-center/tests/test_claim_rank.py"
PROBE1 = f"{PROBE_DIR}/probe1_adversarial.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
TS0 = "2026-09-08T03:20:00Z"

BLOCKED_ON = (
    "independent adversarial reviewer owed whose explicit brief is to construct "
    "an input that games the ranking upward through repetition; "
    "independent-review.json absent; SUCCESS:CC-0018 withheld "
    "(success_invented=false)"
)


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
    """Promote only when an independent adversarial reviewer PASSes."""
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
    # Must show they attempted a gaming input (anti-repetition brief).
    if not (rev.get("gaming_input") or rev.get("adversarial_input") or rev.get("notes")):
        return None
    if rev.get("rank_rose_under_repetition") is True:
        return None
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    dep = json.loads((L.REPO / "command-center/receipts/CC-0017.json").read_text(encoding="utf-8"))
    if dep.get("state") != "SUCCESS":
        raise SystemExit(f"CC-0018 refuses pack: CC-0017 state={dep.get('state')!r}")

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest-claim-rank.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"CC-0018 pytest failed:\n{out}")

    p1_rc, p1_out = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    if p1_rc != 0:
        raise SystemExit(f"CC-0018 probe1 failed:\n{p1_out}")

    adv = json.loads(
        (L.REPO / PROBE_DIR / "adversarial-before-after-ranks.json").read_text(encoding="utf-8")
    )
    raw1 = (L.REPO / PROBE_DIR / "adversarial-before-after-ranks.raw.txt").read_text(
        encoding="utf-8"
    )
    if not adv.get("ok") or adv.get("score_rose"):
        raise SystemExit(f"CC-0018 adversarial property failed: {adv}")

    rev = load_review()
    success = rev is not None

    before = adv["before_ranks"]
    after = adv["after_ranks"]

    p_pytest = L.probe(
        "source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_adv = L.probe(
        "verifier", "command", f"python3 -B {PROBE1}", raw1, p1_rc
    )

    if success:
        state = "SUCCESS"
        notes = rev.get("notes", "")
        if not isinstance(notes, str):
            notes = json.dumps(notes)
        sentinel = (
            f"SUCCESS:{UNIT} anti-repetition demonstrated "
            f"before_rank={before['rank']} after_rank={after['rank']} "
            f"before_score={before['score']} after_score={after['score']}; "
            f"reviewer={rev.get('reviewer_id')}"
        )
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-independent-adversarial-review-PASS"
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-independent-adversarial-reviewer; "
            f"anti-repetition executed before_rank={before['rank']} "
            f"after_rank={after['rank']} score_flat={before['score']==after['score']}; "
            f"CC-0017 SUCCESS verified; SUCCESS:{UNIT} withheld "
            f"(success_invented=false)"
        )
        reviewer = {
            "reviewer_id": "awaiting-independent-adversarial-reviewer",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer lane only. Catalog reviewer_requirement: one independent "
                "adversarial reviewer whose explicit brief is to construct an input that "
                "games the ranking upward through repetition. Self-review banned; "
                "independent-review.json not invented. Planted controls + executed "
                f"adversarial before/after ranks are green "
                f"(before rank={before['rank']} score={before['score']}; "
                f"after n={after['n_agents']} rank={after['rank']} "
                f"score={after['score']})."
            ),
        }
        residual = [
            {
                "claim": (
                    "Whether the ranking function remains ungameable under an "
                    "adversarial reviewer's constructed repetition input is unchecked "
                    "in this lane."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context independent reviewer authors a gaming corpus that "
                    "attempts to raise rank via repetition/echoes, runs "
                    f"`python3 -B {GATE} rank <gaming.json>` and the planted pytest "
                    "suite, and returns PASS with independent=true, fresh_context=true, "
                    "gaming_input=<path>, rank_rose_under_repetition=false."
                ),
            }
        ]
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "claim_rank anti-repetition controls + executed adversarial "
                "before/after ranks are green, but catalog reviewer_requirement "
                "is unmet. SUCCESS not invented."
            ),
            "blocked_on": BLOCKED_ON,
            "diagnostic_tail": (out + "\n" + raw1)[-4000:],
            "two_signal_proof": [p_pytest, p_adv],
        }
        anti = "BLOCKED-pending-independent-adversarial-reviewer"

    downstream = [
        {
            "consumer": "claim_rank.rank_claims",
            "artifact_path": f"{PROBE_DIR}/adversarial-before-after-ranks.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_adv,
        },
        {
            "consumer": "pytest:test_claim_rank",
            "artifact_path": TESTS,
            "executed": True,
            "read_ok": True,
            "exit_code": rc,
            "probe": p_pytest,
        },
    ]

    arts = [
        L.art(GATE, "primary"),
        L.art(TESTS, "supporting"),
        L.art(f"{PROBE_DIR}/adversarial-before-after-ranks.json", "log"),
        L.art(f"{PROBE_DIR}/adversarial-before-after-ranks.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/adversarial-run.json", "log"),
        L.art(f"{PROBE_DIR}/pytest-claim-rank.out", "log"),
        L.art(f"{PROBE_DIR}/probe1_adversarial.py", "control"),
        L.art("command-center/receipts/CC-0017.json", "supporting"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0018",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent-worktree",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Anti-repetition demonstrated by executed adversarial run: "
                    f"before n={before['n_agents']} rank={before['rank']} "
                    f"score={before['score']}; after n={after['n_agents']} "
                    f"rank={after['rank']} score={after['score']}; "
                    f"score_rose={adv['score_rose']} rank_improved={adv['rank_improved']}. "
                    "Printed before/after ranks, not argued from formula shape."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/adversarial-before-after-ranks.json",
                [p_adv, p_pytest],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Four planted controls green: (1) N shared-source echoes cannot "
                    "raise rank; (2) one strong independent probe outranks ten weaker "
                    "echoes; (3) lineage collapse to one source document; "
                    "(4) monotonicity when a genuinely independent corroborating probe "
                    "is added. Dependency CC-0017 SUCCESS verified on disk."
                ),
                "CONFIRMED",
                f"file:{TESTS}",
                [
                    L.probe(
                        "source",
                        "file-read",
                        "read command-center/receipts/CC-0017.json state",
                        json.dumps({"unit_id": "CC-0017", "state": dep.get("state")}),
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "test-run",
                        f"python3 -m pytest {TESTS} -q --tb=line",
                        out,
                        rc,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; if weighting cannot defeat the gaming input "
                "twice, switch to source-set cardinality rather than tuning weights "
                "a third time."
            ),
        },
        "tests": [
            {
                "id": "adversarial-control",
                "name": "N shared-source agent echoes must not raise rank.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_adversarial_control_rank_does_not_rise_with_n_shared_source_echoes -q"
                ),
                "result": "PASS",
                "assertions": 6,
                "output_tail": out[-800:],
            },
            {
                "id": "strong-outranks-echoes",
                "name": "Strong independent probe outranks ten weaker echoes.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_strong_independent_probe_outranks_ten_weaker_echoes -q"
                ),
                "result": "PASS",
                "assertions": 5,
                "output_tail": out[-800:],
            },
            {
                "id": "lineage-collapse",
                "name": "Same source document collapses to one independent signal.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_lineage_collapse_same_source_document_is_one_signal -q"
                ),
                "result": "PASS",
                "assertions": 4,
                "output_tail": out[-800:],
            },
            {
                "id": "monotonicity",
                "name": "Independent corroborating probe raises score/rank.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_monotonicity_independent_corroborating_probe_raises_rank -q"
                ),
                "result": "PASS",
                "assertions": 4,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "shared-source-echoes",
                "mutation",
                "Duplicate claim across N agents on one source -> rank/score flat.",
                True,
                True,
                bad=f"n={after['n_agents']} would raise rank if broken",
                good=adv.get("printed_summary", ""),
            ),
            L.control(
                "lineage-collapse",
                "mutation",
                "Path/URL aliases of one document must count as one signal.",
                True,
                True,
                bad="docs/spec.md#section counted separately",
                good="normalize_source_document collapses aliases",
            ),
            L.control(
                "monotonicity",
                "mutation",
                "Add independent source -> score rises (function not inert).",
                True,
                True,
                bad="score unchanged after new independent source",
                good="score increases with independent_source_count",
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
            "kind": "claim-rank",
            "dependency_cc0017_state": dep.get("state"),
            "adversarial_before": before,
            "adversarial_after": after,
            "score_rose": adv.get("score_rose"),
            "rank_improved": adv.get("rank_improved"),
            "success_invented": False,
            "independent_review_invented": False,
            "independent_review_present": rev is not None,
        },
        "extensions": {
            "anti_false_green": anti,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "success_invented": False,
            "independent_review_invented": False,
        },
    }
    if failure is not None:
        receipt["failure"] = failure
    return receipt


def main() -> int:
    receipt = build()
    state = receipt["state"]
    manifest = {
        "schema_version": 1,
        "unit_id": UNIT,
        "entry_id": UNIT,
        "state": state,
        "artifacts": [a["path"] for a in receipt["artifacts"]],
        "receipt_path": OUT,
        "success_invented": False,
        "independent_review_invented": False,
    }
    if state == "BLOCKED":
        manifest["blocked_on"] = receipt["failure"]["blocked_on"]
    man_path = L.REPO / MANIFEST
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rc = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc != 0:
        return rc
    # Re-measure including receipt + manifest now on disk.
    receipt["artifacts"] = [
        L.art(OUT, "primary"),
        L.art(GATE, "primary"),
        L.art(TESTS, "supporting"),
        L.art(f"{PROBE_DIR}/adversarial-before-after-ranks.json", "log"),
        L.art(f"{PROBE_DIR}/adversarial-before-after-ranks.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/adversarial-run.json", "log"),
        L.art(f"{PROBE_DIR}/pytest-claim-rank.out", "log"),
        L.art(f"{PROBE_DIR}/probe1_adversarial.py", "control"),
        L.art("command-center/receipts/CC-0017.json", "supporting"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(MANIFEST, "supporting"),
    ]
    if state == "SUCCESS":
        receipt["artifacts"].append(
            L.art(f"{PROBE_DIR}/independent-review.json", "supporting")
        )
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA)
    print(
        f"state={state} success_invented=false "
        f"review={'present' if load_review() else 'absent'} rc={rc2}"
    )
    return rc2


if __name__ == "__main__":
    raise SystemExit(main())
