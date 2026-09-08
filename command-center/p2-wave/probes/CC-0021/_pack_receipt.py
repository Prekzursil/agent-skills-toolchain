#!/usr/bin/env python3
"""Pack CC-0021 — option-id namespace registry + ambiguous-bare-token gate.

Emits state=BLOCKED with blocked-on-independent-review after green controls.
Catalog reviewer_requirement: one independent reviewer who re-runs the
extractor with a different regex construction and confirms the counts agree.
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

UNIT = "CC-0021"
OUT = "command-center/receipts/CC-0021.json"
SCHEMA = "command-center/schema/option-id-namespace.schema.json"
ALSO = ["command-center/schema/receipt.schema.json"]
PROBE_DIR = "command-center/p2-wave/probes/CC-0021"
GATE = "tools/command-center/option_id_namespace.py"
TESTS = "tools/command-center/tests/test_option_id_namespace.py"
PROBE1 = f"{PROBE_DIR}/probe1_controls.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
TS0 = "2026-09-08T01:30:00Z"


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
    """Promote only when an independent reviewer re-runs a distinct regex."""
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
    if not rev.get("alternate_regex") and not rev.get("counts_agree"):
        return None
    if rev.get("counts_agree") is not True:
        return None
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"CC-0021 pytest failed:\n{out}")

    p1_rc, p1_out = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    if p1_rc != 0:
        raise SystemExit(f"CC-0021 probe1 failed:\n{p1_out}")

    controls = json.loads(
        (L.REPO / PROBE_DIR / "probe1-controls.json").read_text(encoding="utf-8")
    )
    raw1 = (L.REPO / PROBE_DIR / "probe1-controls.raw.txt").read_text(encoding="utf-8")
    measure = controls["measure"]
    arith = measure["arithmetic"]
    regex = measure["regexes"]["BARE_M_RE"]

    m_rc, m_out = _run(
        [sys.executable, "-B", str(L.REPO / GATE), "measure"]
    )
    (L.REPO / PROBE_DIR / "measure.out").write_text(m_out, encoding="utf-8")

    rev = load_review()
    success = rev is not None

    p_pytest = L.probe(
        "source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_probe1 = L.probe(
        "verifier", "command", f"python3 -B {PROBE1}", raw1, p1_rc
    )
    p_measure = L.probe(
        "source", "command", f"python3 -B {GATE} measure", m_out, m_rc
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
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-independent-alternate-regex"
        downstream = [
            {
                "consumer": "option_id_namespace.run_controls",
                "artifact_path": GATE,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_probe1,
            }
        ]
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-independent-review; "
            f"remeasured arithmetic={arith}; "
            f"BARE_M_RE={regex!r}; "
            f"deep_research_m16={measure['deep_research_m16_refs']}/"
            f"{measure['deep_research_m16_files']}; "
            f"live_shared_bare={measure['live_shared_bare_count']}; "
            f"controls[{ctrl_bits}]; "
            f"SUCCESS:{UNIT} withheld pending independent alternate-regex confirm"
        )
        reviewer = {
            "reviewer_id": "awaiting-independent-alternate-regex",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only on Linux Cloud single-checkout. Catalog "
                "reviewer_requirement unmet: one independent reviewer must re-run "
                "the extractor with a different regex construction and confirm "
                "counts agree (33/38/31/7/2 family/mech/collide/doc13only/univonly "
                "and 20/16 deep-research M-16 refs/files). Self-review banned; "
                "independent-review.json not invented. Scope: Prompt-One Windows "
                "trees unmounted; doc 07/13 re-measured from CNF-0015 fixtures; "
                "deep-research from in-repo .agents/skills + skills duplicates."
            ),
        }
        residual = [
            {
                "claim": (
                    "Independent reviewer has not re-run the extractor with a "
                    "different regex construction nor confirmed count agreement."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer authors an alternate bare-M regex "
                    "(mechanically different construction from "
                    f"{regex!r}), re-runs measure+controls against the same "
                    "corpus, returns PASS with independent=true, "
                    "fresh_context=true, alternate_regex=<pattern>, "
                    "counts_agree=true, and matching arithmetic + deep-research "
                    "20/16."
                ),
            }
        ]
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Namespace registry + gate + four catalog controls are green "
                f"(pytest; probe1 ok={controls.get('ok')}; arithmetic={arith}; "
                f"controls[{ctrl_bits}]). Catalog reviewer_requirement unmet — "
                "do not emit SUCCESS without an independent alternate-regex "
                "confirmation. Live doc07↔doc13 bare collision is 0 "
                f"(live_shared_bare={measure['live_shared_bare_count']}); prior "
                "live-blocker prose is stale; arithmetic reconfirmed by executed "
                "extractor."
            ),
            "blocked_on": (
                "independent reviewer alternate-regex + count agreement"
            ),
            "diagnostic_tail": (out + "\n" + raw1 + "\n" + m_out)[-4000:],
            "two_signal_proof": [p_probe1, p_measure],
        }
        anti = "BLOCKED-pending-independent-alternate-regex"
        # SUCCESS-ready shape: non-empty executed downstream_consumers.
        downstream = [
            {
                "consumer": "option_id_namespace.run_controls",
                "artifact_path": f"{PROBE_DIR}/probe1-controls.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_probe1,
            },
            {
                "consumer": "option_id_namespace.measure",
                "artifact_path": f"{PROBE_DIR}/measure.out",
                "executed": True,
                "read_ok": True,
                "exit_code": m_rc,
                "probe": p_measure,
            },
        ]

    arts = [
        L.art(GATE, "primary"),
        L.art(TESTS, "supporting"),
        L.art(f"{PROBE_DIR}/fixtures/planted-bare-m16.md", "control"),
        L.art(f"{PROBE_DIR}/fixtures/mention-collision-quote.md", "control"),
        L.art(f"{PROBE_DIR}/probe1-controls.json", "log"),
        L.art(f"{PROBE_DIR}/probe1-controls.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/measure.out", "log"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(
            "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix/07-OPTION-UNIVERSE.md",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix/13-ARCHITECTURE-CANDIDATES.md",
            "supporting",
        ),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0021",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "detector-engineer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Executed extractor printed regexes and re-measured "
                    f"arithmetic={arith} (family_m/doc13_mech/collide/"
                    f"doc13_only/universe_only). BARE_M_RE={regex!r}. "
                    f"live_shared_bare={measure['live_shared_bare_count']} "
                    "(prior live-blocker conclusion stale). deep-research "
                    f"M-16 refs={measure['deep_research_m16_refs']} files="
                    f"{measure['deep_research_m16_files']} across duplicated "
                    "trees .agents/skills/deep-research + skills/deep-research."
                ),
                "CONFIRMED",
                f"file:{GATE}",
                [p_measure, p_probe1],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Four catalog controls: [{ctrl_bits}]. Known-present 20/16; "
                    "MECH-NN not reported as bare; planted bare M-16 fires gate; "
                    "use-vs-mention quote not flagged unresolved."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/probe1-controls.json",
                [p_pytest, p_probe1],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot from prefix heuristics to an explicit "
                "per-file namespace declaration; never guess a token's namespace "
                "from surrounding prose."
            ),
        },
        "tests": [
            {
                "id": "known-present-deep-research-m16",
                "name": "All 20 deep-research M-16 refs found across both trees.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_known_present_all_20_deep_research_m16 -q"
                ),
                "result": "PASS" if controls["controls"]["known_present"]["pass"] else "FAIL",
                "assertions": 3,
                "output_tail": out[-800:],
            },
            {
                "id": "false-positive-mech-not-bare",
                "name": "MECH-NN must NOT be reported as bare ambiguous M-NN.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_false_positive_mech_not_reported_as_bare -q"
                ),
                "result": "PASS" if controls["controls"]["false_positive"]["pass"] else "FAIL",
                "assertions": 4,
                "output_tail": out[-800:],
            },
            {
                "id": "known-broken-planted-bare-m16",
                "name": "Planted bare M-16 in scratch must make the gate fire.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_known_broken_planted_bare_m16_fires_gate -q"
                ),
                "result": "PASS" if controls["controls"]["known_broken"]["pass"] else "FAIL",
                "assertions": 3,
                "output_tail": out[-800:],
            },
            {
                "id": "use-vs-mention",
                "name": "Document quoting the collision must not be flagged unresolved.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_use_vs_mention_quote_not_flagged_unresolved -q"
                ),
                "result": "PASS" if controls["controls"]["use_vs_mention"]["pass"] else "FAIL",
                "assertions": 2,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "planted-bare-m16-fires",
                "known-broken-fixture",
                "Scratch file with bare M-16 outside namespace homes must fire the gate.",
                True,
                True,
                bad=f"planted unresolved={controls['controls']['known_broken']['unresolved_count']}",
                good="mention doc unresolved=0",
            ),
            L.control(
                "mech-not-bare-false-positive",
                "absent-input",
                "MECH-NN tokens must not appear as bare M-NN after strip-first extract.",
                True,
                True,
                bad="would report MECH-16 as M-16",
                good="sample+doc13 bare sets empty",
            ),
            L.control(
                "use-vs-mention-silent",
                "mutation",
                "A document quoting the collision to describe it must not be unresolved.",
                True,
                True,
                bad="would flag mention doc unresolved",
                good=f"mentions={controls['controls']['use_vs_mention']['mention_count']}",
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
                    "name": "remeasured_arithmetic",
                    "measured": arith,
                    "method": f"extractor BARE_M_RE={regex!r} + FAMILY_M_CARD_RE + MECH_NN_RE on CNF-0015 fixtures",
                    "anchor": measure["corpus_post"],
                },
                {
                    "name": "live_shared_bare_count",
                    "measured": measure["live_shared_bare_count"],
                    "method": "family_m ∩ bare_m(post-fix doc13) after strip MECH",
                    "anchor": measure["corpus_post"] + "/13-ARCHITECTURE-CANDIDATES.md",
                },
                {
                    "name": "deep_research_m16_refs",
                    "measured": measure["deep_research_m16_refs"],
                    "method": "path-scoped BARE_M_RE for token M-16; tests/ excluded",
                    "anchor": ".agents/skills/deep-research + skills/deep-research",
                },
                {
                    "name": "deep_research_m16_files",
                    "measured": measure["deep_research_m16_files"],
                    "method": "distinct files carrying Research Harness M-16",
                    "anchor": ".agents/skills/deep-research + skills/deep-research",
                },
            ],
            "control_ids": [
                "known-present-deep-research-m16",
                "false-positive-mech-not-bare",
                "known-broken-planted-bare-m16",
                "use-vs-mention",
            ],
            "regexes": measure["regexes"],
            "namespaces": controls.get("namespaces", measure.get("namespaces")),
            "controls": controls["controls"],
            "independent_review_present": REVIEW.is_file(),
            "scope": measure["scope"],
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "linux_cloud_scope": measure["scope"],
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
                    GATE,
                    TESTS,
                    f"{PROBE_DIR}/fixtures/planted-bare-m16.md",
                    f"{PROBE_DIR}/fixtures/mention-collision-quote.md",
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
    print(f"arithmetic={arith} deep_research={measure['deep_research_m16_refs']}/{measure['deep_research_m16_files']}")
    print(f"independent_review={REVIEW.is_file()} (must stay false for this emit)")
    return receipt


if __name__ == "__main__":
    build()
