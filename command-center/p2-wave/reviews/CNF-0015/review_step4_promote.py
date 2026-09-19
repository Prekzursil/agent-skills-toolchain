# CNF-0015 reviewer step 4: PROMOTE THE RECEIPT - merge reviewer block, preserve all else.
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\agent-skills-toolchain")
RECEIPT = REPO / "command-center" / "confirmation" / "CNF-0015-blocker-repro.json"
EVID = REPO / "command-center" / "p2-wave" / "reviews" / "CNF-0015"

NOTES = (
    "Fresh-context independent detector-control re-run (claude; implementer was openai/gpt-5-codex, "
    "transcript unseen). Falsification control run in BOTH STATES with the receipt-verified bytes: "
    "sha256 of command-center/p2-wave/probes/CNF-0015/option_id_collision.py and BOTH doc-13 fixtures "
    "match the receipt exactly, so I executed the shipped detector, not a re-implementation. "
    "(1) Shipped suite: `python -m pytest command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py -q` "
    "-> '5 passed in 1.22s', exit 0; T1 test_pre_fix_shared_id_count_is_31 "
    "(test_option_id_collision.py:22) asserts the detector FIRES on the known-broken fixture. "
    "(2) Detector directly on both states: PRE(known-broken) firing line "
    '\'{"family_m_count": 33, "doc13_bare_m_count": 38, "shared_id_count": 31, ..., "collision_live": true}\' '
    "(extractor at option_id_collision.py:58-72, gate predicate collision_live at :71, callable at :82-84); "
    "POST(known-good) shared_id_count=0, collision_live=false. "
    "(3) Gate form: SystemExit(1 if collision_is_live(dir)) -> exit code 1 (RED) on the known-broken "
    "fixture, exit 0 on the fixed one - I observed the firing exit myself. "
    "(4) Anti-rigging mutation-equivalent: reviewer-written independent re-extraction (different regex "
    "implementation, no probe import) reproduces 33 family ids / 38 bare-M / intersection 31 pre and "
    "0/0 post, MECH substr in doc17 0 pre / 1 post - agreeing with the detector, so the 31 is not an "
    "artifact of the probe's own code. OPTION-ID-RESOLUTION.json independently records "
    "detector_on_known_BROKEN_state_collisions=31 / FIXED=0, corroborating the fixture arithmetic. "
    "Custody caveats, disclosed: test_option_id_collision.py on disk (1833B, 5 tests) differs from the "
    "receipt sha (1855B, 3 tests listed) - a post-receipt superset, NOT content-identical; pytest.out "
    "and OPTION-ID-RESOLUTION.json differ only by CRLF (EOL-normalized sha matches). Live 07/13/17 docs "
    "remain absent from this tree (harness-restore-20260806 holds only e2e/), so the 31-vs-0 verdict "
    "stands on the sha256-verified fixtures plus the resolution-doc corroboration, per the receipt's "
    "own residual_unknowns entry. Verdict PASS: detector fired on the known-broken fixture in MY run."
)

reviewer = {
    "reviewer_id": "claude-fresh-context-detector-control-rerun",
    "verdict": "PASS",
    "independent": True,
    "fresh_context": True,
    "vendor": "claude",
    "reviewed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "detector_control": {
        "commands": [
            "python -m pytest command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py -q",
            "python (in-process) option_id_collision.measure_dir(fixtures/pre-fix) / (fixtures/post-fix)",
            "gate form: SystemExit(1 if collision_is_live(dir) else 0) on pre and post",
        ],
        "fired_on_broken": True,
        "silent_on_good": True,
        "firing_line": "PRE shared_id_count=31, collision_live=true; gate exit=1",
        "good_line": "POST shared_id_count=0, collision_live=false; gate exit=0",
        "independent_recomputation": "31 pre / 0 post (reviewer-written extractor, agrees)",
        "custody": {
            "option_id_collision.py": "raw sha256 MATCH",
            "fixtures/pre-fix/13-ARCHITECTURE-CANDIDATES.md": "raw sha256 MATCH",
            "fixtures/post-fix/13-ARCHITECTURE-CANDIDATES.md": "raw sha256 MATCH",
            "pytest.out": "CRLF phantom (normalized sha MATCH)",
            "OPTION-ID-RESOLUTION.json": "CRLF phantom (normalized sha MATCH)",
            "test_option_id_collision.py": "REAL DRIFT vs receipt sha (on-disk 5-test superset; disclosed, non-blocking)",
        },
        "raw_evidence": "command-center/p2-wave/reviews/CNF-0015/detector-control-rerun.raw.txt",
    },
    "notes": NOTES,
}

rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
rec["reviewer"] = reviewer
RECEIPT.write_text(
    json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
)

# verify the write parses and C5 inputs are present
back = json.loads(RECEIPT.read_text(encoding="utf-8"))
rv = back["reviewer"]
ok = (
    rv["verdict"] == "PASS"
    and rv["independent"] is True
    and len(rv["notes"]) >= 200
    and any(k in rv["notes"] for k in ("both", "falsif"))
    and back["unit_id"] == "CNF-0015"
    and back["state"] == "BLOCKED"  # untouched per reviewer scope
)
print(f"receipt promoted: {RECEIPT}")
print(f"notes chars: {len(rv['notes'])}  C5-verdict-shape ok: {ok}")
print(
    f"preserved fields intact: {len(back)} top-level keys; state={back['state']!r} (orchestrator-owned, untouched)"
)
