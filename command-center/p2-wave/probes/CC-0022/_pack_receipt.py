#!/usr/bin/env python3
"""Pack CC-0022 — decision-log reconcile + staleness sentinel.

Emits state=BLOCKED with blocked-on-independent-review after green probes.
Catalog reviewer_requirement: one independent reviewer who confirms no
decision content was altered, only its id namespace and its stale tense.
Never invent SUCCESS. Never invent independent-review.json.

Linux Cloud / single-checkout scope disclosed in reviewer.notes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0022"
OUT = "command-center/receipts/CC-0022.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0022"
TESTS = "tools/command-center/tests/test_decision_log_sentinel.py"
PROBE1 = f"{PROBE_DIR}/probe1_both_states.py"
PROBE2 = f"{PROBE_DIR}/probe2_planted_and_true.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
LIVE_LOG = "17-DECISION-LOG.md"
SENTINEL_MOD = "command-center/lib/decision_log_sentinel.py"
RECONCILE_MOD = "command-center/lib/decision_log_reconcile.py"
COLLISION_MOD = "command-center/lib/option_id_collision_probe.py"
FB02 = "command-center/lib/fb02_apply.py"
TS0 = "2026-09-08T01:50:00Z"


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
    """Promote only when an independent reviewer confirms namespace/tense-only edits."""
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
    if rev.get("content_unchanged") is not True:
        return None
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"CC-0022 pytest failed:\n{out}")

    p1_rc, p1_out = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    (L.REPO / PROBE_DIR / "probe1-both-states.raw.txt").write_text(
        p1_out, encoding="utf-8"
    )
    if p1_rc != 0:
        raise SystemExit(f"CC-0022 probe1 failed:\n{p1_out}")

    p2_rc, p2_out = _run([sys.executable, "-B", str(L.REPO / PROBE2)])
    (L.REPO / PROBE_DIR / "probe2-planted-and-true.raw.txt").write_text(
        p2_out, encoding="utf-8"
    )
    if p2_rc != 0:
        raise SystemExit(f"CC-0022 probe2 failed:\n{p2_out}")

    p1 = json.loads(
        (L.REPO / PROBE_DIR / "probe1-both-states.json").read_text(encoding="utf-8")
    )
    p2 = json.loads(
        (L.REPO / PROBE_DIR / "probe2-planted-and-true.json").read_text(
            encoding="utf-8"
        )
    )
    meta = json.loads(
        (L.REPO / PROBE_DIR / "fixtures" / "build-meta.json").read_text(
            encoding="utf-8"
        )
    )
    fb02_rec = json.loads(
        (L.REPO / "command-center/option-id/FB02-SUBSTITUTION-RECORD.json").read_text(
            encoding="utf-8"
        )
    )

    rev = load_review()
    success = rev is not None

    p_pytest = L.probe(
        "source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_probe1 = L.probe("verifier", "command", f"python3 -B {PROBE1}", p1_out, p1_rc)
    p_probe2 = L.probe("verifier", "command", f"python3 -B {PROBE2}", p2_out, p2_rc)

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
        anti = "SUCCESS-after-independent-namespace-tense-review"
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-independent-review; "
            f"pre_collision={p1['pre_collision']} post_collision={p1['post_collision']}; "
            f"before_fired={p1['before_fired']} after_fired={p1['after_fired']}; "
            f"planted_fired={p2['planted_fired']} true_silent={not p2['true_copy_fired']}; "
            f"fb02_subs={fb02_rec.get('substitutions')}; "
            f"SUCCESS:{UNIT} withheld pending independent content-vs-namespace/tense confirm"
        )
        reviewer = {
            "reviewer_id": "awaiting-independent-namespace-tense-review",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only on Linux Cloud single-checkout. Catalog "
                "reviewer_requirement unmet: one independent reviewer must confirm "
                "no decision content was altered — only id namespace (architecture "
                "M-NN→MECH-NN) and stale tense/status (DL-0042 CURRENT→SUPERSEDED "
                "with superseded_by; DL-0042b CURRENT with valid_as_of). Self-review "
                "banned; independent-review.json not invented. Scope: Prompt-One "
                "Windows 44 KB 17-DECISION-LOG.md unmounted; before-log reconstructed "
                "from catalog pin (line 175 present-tense collision, Queued as P2-09, "
                "zero MECH, ~44 KB); live collision probe uses family-M + architecture "
                "slices + FB02 record (107 substitutions at 2026-08-07T18:41:00Z). "
                "Measured both-states: FIRE on before line 175, SILENT after; "
                "planted DL-PLANT-STALE fires; currently-true silent; meaning review ok."
            ),
        }
        residual = [
            {
                "claim": (
                    "Independent reviewer has not confirmed that the reconcile "
                    "changed only namespace and tense, leaving decision meaning intact."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer diffs "
                    f"{PROBE_DIR}/fixtures/decision-log-before.md against "
                    f"{LIVE_LOG}, verifies ORIGINAL_SENTENCE retained under "
                    "DL-0042 SUPERSEDED+superseded_by, MECH-NN CURRENT entry "
                    "carries valid_as_of, and no other decision bodies changed; "
                    "returns PASS with independent=true, fresh_context=true, "
                    "content_unchanged=true."
                ),
            }
        ]
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Decision-log reconcile + staleness sentinel are green "
                f"(pytest; probe1 both-states FIRE→SILENT; probe2 planted-stale "
                f"fires and currently-true silent; fb02 substitutions="
                f"{fb02_rec.get('substitutions')}; live collision_count=0). "
                "Catalog reviewer_requirement unmet — do not emit SUCCESS without "
                "an independent confirmation that only namespace and tense changed."
            ),
            "blocked_on": (
                "independent reviewer content-vs-namespace/tense confirmation"
            ),
            "diagnostic_tail": (out + "\n" + p1_out + "\n" + p2_out)[-4000:],
            "two_signal_proof": [p_probe1, p_probe2],
        }
        anti = "BLOCKED-pending-independent-namespace-tense-review"

    # SUCCESS-ready shape: non-empty executed downstream_consumers.
    downstream = [
        {
            "consumer": "decision_log_sentinel.scan",
            "artifact_path": f"{PROBE_DIR}/probe1-both-states.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_probe1,
        },
        {
            "consumer": "decision_log_reconcile.unchanged_except_collision",
            "artifact_path": f"{PROBE_DIR}/probe2-planted-and-true.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_probe2,
        },
    ]

    arts = [
        L.art(LIVE_LOG, "primary"),
        L.art(SENTINEL_MOD, "primary"),
        L.art(RECONCILE_MOD, "supporting"),
        L.art(COLLISION_MOD, "supporting"),
        L.art(FB02, "supporting"),
        L.art("command-center/option-id/FB02-SUBSTITUTION-RECORD.json", "supporting"),
        L.art(
            "command-center/option-id/07-OPTION-UNIVERSE.family-M-slice.md",
            "supporting",
        ),
        L.art(
            "command-center/option-id/13-ARCHITECTURE-CANDIDATES.post-fix-slice.md",
            "supporting",
        ),
        L.art(f"{PROBE_DIR}/fixtures/decision-log-before.md", "control"),
        L.art(f"{PROBE_DIR}/fixtures/decision-log-after.md", "control"),
        L.art(f"{PROBE_DIR}/fixtures/build-meta.json", "fixture"),
        L.art(f"{PROBE_DIR}/probe1-both-states.json", "log"),
        L.art(f"{PROBE_DIR}/probe2-planted-and-true.json", "log"),
        L.art(f"{PROBE_DIR}/probe1-both-states.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/probe2-planted-and-true.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(TESTS, "supporting"),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0022",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "corpus-normalizer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Both-states staleness sentinel: FIRE on reconstructed before-log "
                    f"line 175 ({p1['before_line_175']!r}; bytes={p1['before_bytes']}; "
                    f"MECH={p1['before_mech']}); SILENT after reconcile "
                    f"(MECH={p1['after_mech']}; skipped_superseded="
                    f"{p1['after_skipped_superseded']}). Live collision probe "
                    f"pre={p1['pre_collision']} post={p1['post_collision']} "
                    f"(matches CC-0021 live_shared_bare=0)."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/probe1-both-states.json",
                [p_probe1, p_pytest],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Planted DL-PLANT-STALE fires (not hardcoded to line 175); "
                    "currently-true DL-0001 / DL-PLANT-TRUE silent; meaning-preserving "
                    f"diff ok={p2['meaning_review'].get('ok')}; original wording "
                    f"preserved={p2['original_sentence_preserved']}; "
                    f"fb02 substitutions={fb02_rec.get('substitutions')} at "
                    f"{fb02_rec.get('applied_at')}."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/probe2-planted-and-true.json",
                [p_probe2, p_pytest],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; if automated tense detection misfires "
                "twice, restrict the sentinel to entries carrying an explicit "
                "machine-checkable assertion."
            ),
        },
        "tests": [
            {
                "id": "both-states-line-175",
                "name": "Sentinel FIRE on before line 175; SILENT after reconcile.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_both_states_line_175_fires_then_silent -q"
                ),
                "result": "PASS"
                if p1.get("before_fired") and not p1.get("after_fired")
                else "FAIL",
                "assertions": 6,
                "output_tail": p1_out[-800:],
            },
            {
                "id": "planted-stale-not-hardcoded",
                "name": "Second planted stale entry also fires (not line-175-only).",
                "command": (
                    f"python3 -m pytest {TESTS}::test_planted_stale_also_fires -q"
                ),
                "result": "PASS" if p2.get("planted_fired") else "FAIL",
                "assertions": 2,
                "output_tail": p2_out[-800:],
            },
            {
                "id": "currently-true-silent",
                "name": "Currently-true census / planted-true entries do not fire.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_currently_true_entry_does_not_fire -q"
                ),
                "result": "PASS" if not p2.get("true_copy_fired") else "FAIL",
                "assertions": 2,
                "output_tail": p2_out[-800:],
            },
            {
                "id": "meaning-preserving-diff",
                "name": "Reconcile changes only namespace and tense; wording retained.",
                "command": (
                    f"python3 -m pytest {TESTS}::test_reconcile_preserves_meaning -q"
                ),
                "result": "PASS" if p2.get("meaning_review", {}).get("ok") else "FAIL",
                "assertions": 3,
                "output_tail": p2_out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "line-175-before-fires",
                "known-broken-fixture",
                "Frozen before-log line 175 present-tense collision must FIRE the sentinel.",
                True,
                True,
                bad=f"before fire_ids={p1.get('before_fire_ids')}",
                good="after_fired=False skipped_superseded>=1",
            ),
            L.control(
                "planted-stale-fires",
                "mutation",
                "Planted CURRENT stale collision claim must FIRE (not hardcoded to line 175).",
                True,
                True,
                bad=f"planted fire_ids={p2.get('planted_fire_ids')}",
                good="reconciled live log silent",
            ),
            L.control(
                "detector-not-constant-31-to-0",
                "known-broken-fixture",
                "Collision probe must read 31 on pre-fix arch and 0 on post-fix MECH arch.",
                True,
                True,
                bad=f"pre_collision={p1['pre_collision']}",
                good=f"post_collision={p1['post_collision']}",
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
            "kind": "decision-log-staleness",
            "observations": [
                {
                    "name": "before_line_175",
                    "measured": p1["before_line_175"],
                    "method": "reconstructed catalog-pin before-log splitlines()[174]",
                    "anchor": f"{PROBE_DIR}/fixtures/decision-log-before.md",
                },
                {
                    "name": "before_bytes",
                    "measured": p1["before_bytes"],
                    "method": "utf-8 byte length of before-log",
                    "anchor": f"{PROBE_DIR}/fixtures/decision-log-before.md",
                },
                {
                    "name": "live_collision_count",
                    "measured": p1["live_snapshot"]["collision_count"],
                    "method": "bare M-NN intersection option-slice ∩ post-fix arch-slice",
                    "anchor": "command-center/option-id/",
                },
                {
                    "name": "fb02_substitutions",
                    "measured": fb02_rec.get("substitutions"),
                    "method": "command-center/lib/fb02_apply.py M-NN→MECH-NN",
                    "anchor": "command-center/option-id/FB02-SUBSTITUTION-RECORD.json",
                },
            ],
            "control_ids": [
                "line-175-before-fires",
                "planted-stale-fires",
                "detector-not-constant-31-to-0",
            ],
            "build_meta": meta,
            "fb02": fb02_rec,
            "probe1": p1,
            "probe2": p2,
            "independent_review_present": REVIEW.is_file(),
            "scope": (
                "linux-cloud-single-checkout; 17-DECISION-LOG reconstructed from "
                "catalog pin; option/arch slices + FB02 substitution record"
            ),
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "linux_cloud_scope": (
                "Prompt-One Windows trees unmounted; decision log reconstructed "
                "from catalog pin on this single checkout"
            ),
            "depends_on": ["CC-0021"],
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
                    LIVE_LOG,
                    SENTINEL_MOD,
                    RECONCILE_MOD,
                    COLLISION_MOD,
                    FB02,
                    f"{PROBE_DIR}/fixtures/decision-log-before.md",
                    f"{PROBE_DIR}/fixtures/decision-log-after.md",
                    f"{PROBE_DIR}/probe1-both-states.json",
                    f"{PROBE_DIR}/probe2-planted-and-true.json",
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

    rc_w = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc_w != 0:
        raise SystemExit(rc_w)
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA)
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
        f"both-states FIRE→SILENT planted={p2['planted_fired']} "
        f"true_silent={not p2['true_copy_fired']}"
    )
    print(f"independent_review={REVIEW.is_file()} (must stay false for this emit)")
    print(f"sentinel={sentinel[:160]}...")
    return receipt


if __name__ == "__main__":
    build()
