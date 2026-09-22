# CNF-0015 reviewer step 5: finalize evidence (append gate both-states section + independent-review.json).
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\agent-skills-toolchain")
EVID = REPO / "command-center" / "p2-wave" / "reviews" / "CNF-0015"
RAW = EVID / "detector-control-rerun.raw.txt"
gate_after = (EVID / "gate-after.txt").read_text(encoding="utf-8")

with RAW.open("a", encoding="utf-8", newline="\n") as f:
    f.write(
        "\n=== 4. rail_count_gate both-states (reviewer promotion delta) ===\n"
        "BEFORE (baseline, same tree, same basis):\n"
        "  FRESH DERIVATION: 89 blocked units, 9 rail-blocked, 80 satisfiable now, 75 of those reviewed\n"
        "  C5 CNF-0015 is satisfiable by a same-vendor independent reviewer but carries no independent\n"
        "  PASS (verdict='NOT-REVIEWED', independent=False) -- newly reachable work\n"
        "  FAILED:rail-count-gate 8 problem(s)\n"
        "AFTER (receipt promoted with reviewer PASS, notes 2187 chars):\n"
        + "".join("  " + ln + "\n" for ln in gate_after.strip().splitlines())
        + "\nCNF-0015 mentions in AFTER gate output: 0 (grep -c) -- no longer a C5 problem.\n"
        "Reviewed-satisfiable moved 75 -> 76; problem count 8 -> 7; remaining problems are other\n"
        "units' pending reviews (CC-0005, CC-0019, IMP-0022, IMP-0435) and pre-existing C1/C2 doc\n"
        "rot owned by other lanes -- out of this review's scope.\n"
    )

review = {
    "unit_id": "CNF-0015",
    "reviewer": {
        "vendor": "claude",
        "role": "fresh-context independent reviewer (detector-control re-run)",
        "fresh_context": True,
        "saw_implementer_transcript": False,
    },
    "verdict": "PASS",
    "verdict_basis": "Observed the detector fire on the known-broken fixture in my own run, "
    "and stay silent on the known-good fixture; corroborated by an independently written "
    "re-extraction that reproduces the same numbers.",
    "detector_control": {
        "detector": "command-center/p2-wave/probes/CNF-0015/option_id_collision.py (sha256 33c5abbe.., raw MATCH vs receipt)",
        "known_broken_fixture": "command-center/p2-wave/probes/CNF-0015/fixtures/pre-fix/ (doc-13 sha256 raw MATCH)",
        "known_good_fixture": "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix/ (doc-13 sha256 raw MATCH)",
        "runs": [
            {
                "cmd": "python -m pytest command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py -q",
                "output": "5 passed in 1.22s",
                "exit_code": 0,
                "note": "T1 (test_option_id_collision.py:22) asserts the detector FIRES on pre-fix: shared_id_count==31, collision_live is True",
            },
            {
                "cmd": "in-process: option_id_collision.measure_dir(fixtures/pre-fix)",
                "output": "{'family_m_count': 33, 'doc13_bare_m_count': 38, 'shared_id_count': 31, 'mech_token_count': 0, 'decision_present_tense_collision': True, 'collision_live': True}",
                "exit_code": 0,
                "note": "THE FIRING LINE on the known-broken fixture; extractor at option_id_collision.py:58-72, predicate at :71",
            },
            {
                "cmd": "in-process: option_id_collision.measure_dir(fixtures/post-fix)",
                "output": "{'family_m_count': 33, 'doc13_bare_m_count': 0, 'shared_id_count': 0, 'mech_token_count': 1, 'decision_present_tense_collision': False, 'collision_live': False}",
                "exit_code": 0,
                "note": "negative control: silent on the fixed state",
            },
            {
                "cmd": "gate form: SystemExit(1 if collision_is_live(dir) else 0)",
                "output": "PRE exit=1 (FIRED/RED); POST exit=0 (silent/green)",
                "exit_code": 1,
                "note": "firing exit code observed on the known-broken input",
            },
            {
                "cmd": "reviewer-written independent re-extraction (no probe import)",
                "output": "family=33, bare-M pre=38, |family AND bare| pre=31; post bare=0, intersection=0; MECH substr doc17 pre=0/post=1",
                "exit_code": 0,
                "note": "anti-rigging check: different implementation agrees -> the 31/0 is not an artifact of the probe's own code",
            },
        ],
    },
    "custody": {
        "raw_sha256_match": [
            "command-center/p2-wave/probes/CNF-0015/option_id_collision.py",
            "command-center/p2-wave/probes/CNF-0015/fixtures/pre-fix/13-ARCHITECTURE-CANDIDATES.md",
            "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix/13-ARCHITECTURE-CANDIDATES.md",
        ],
        "crlf_phantom_only": [
            "command-center/p2-wave/probes/CNF-0015/pytest.out (2 CRLF pairs; normalized sha MATCH)",
            "command-center/OPTION-ID-RESOLUTION.json (1197 CRLF pairs; normalized sha MATCH)",
        ],
        "real_drift_disclosed": "command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py: disk 1833B/5 tests vs receipt sha for 1855B (receipt tests list names 3). On-disk is a superset (adds detector_self_test both-states tests). Non-blocking for the control: the detector and both fixtures are byte-exact to the receipt, and I ran the on-disk suite AND the detector directly.",
        "corroboration": "command-center/OPTION-ID-RESOLUTION.json records detector_on_known_BROKEN_state_collisions=31 and detector_on_current_FIXED_state_collisions=0, plus an independent second signal (pre-fix backup 107 bare M-NN vs live 0 bare / 108 MECH-NN).",
        "residual_unknown_unchanged": "Live 07-OPTION-UNIVERSE.md / 13-ARCHITECTURE-CANDIDATES.md / 17-DECISION-LOG.md remain absent from this tree; harness-restore-20260806 contains only e2e/. The 31-vs-0 verdict therefore stands on sha256-verified fixtures + resolution-doc corroboration, per the receipt's own residual_unknowns entry. Settling experiment (mount live docs, re-run measure_dir at pinned rev) remains open and optional.",
    },
    "gate_confirmation": {
        "cmd": "python command-center/p2-next/rail_count_gate.py --basis worktree",
        "before": "8 problems; C5 flags CNF-0015 (verdict='NOT-REVIEWED'); reviewed_satisfiable=75",
        "after": "7 problems; CNF-0015 mentions: 0; reviewed_satisfiable=76",
        "conclusion": "CNF-0015 is no longer a C5 problem. Remaining problems belong to other units/lanes.",
    },
    "receipt_promotion": "command-center/confirmation/CNF-0015-blocker-repro.json reviewer block merged (PASS, independent=true, notes 2187 chars naming the both-states falsification control); all other fields preserved, state left BLOCKED for the orchestrator.",
    "raw_evidence": "command-center/p2-wave/reviews/CNF-0015/detector-control-rerun.raw.txt",
    "reviewed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
(EVID / "independent-review.json").write_text(
    json.dumps(review, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
    newline="\n",
)
print("written:", EVID / "independent-review.json")
print("raw evidence lines:", len(RAW.read_text(encoding="utf-8").splitlines()))
for p in sorted(EVID.iterdir()):
    print(f"  {p.name} {p.stat().st_size}B")
