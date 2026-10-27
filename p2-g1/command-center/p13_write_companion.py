"""P13: write the JSON companion to P13-BLINDSPOT-REVIEW.md, kept in step with it.

Wave 3's audit updated its JSON progressively and left its .md as an untouched
skeleton. This script exists so the two cannot drift: it regenerates the companion
from one in-file source of truth and asserts the .md is no longer a skeleton.
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"
MD = CC / "P13-BLINDSPOT-REVIEW.md"
OUT = CC / "P13-BLINDSPOT-REVIEW.json"

QUESTIONS = [
    (
        "Q01",
        "what files were never read",
        "NOT-CHECKED",
        "No transcript read-ledger was built (that is BLD-0001's method). Reported as NOT-CHECKED "
        "rather than approximated: a proxy would be indistinguishable from the real answer while "
        "being wrong. Structural facts only: the corpus holds 610 tracked files and the spec "
        "restricts reading to lines 10473-11437 of an ~11,400-line document, so ~90% of the "
        "governing prompt is out of declared scope by construction.",
    ),
    (
        "Q02",
        "what clients were never tested",
        "CONFIRMED",
        "Exactly one client is exercised: claude-code (12 token occurrences) plus a single "
        "antigravity reference. Codex/OpenAI is a first-class vendor throughout the program but is "
        "not a tested install target. min_client/max_client semver gating exists at "
        "platform/plugin/schemas.py:709-710 with no non-claude-code test. Cursor, Windsurf, Zed, "
        "Continue, Copilot: zero references.",
    ),
    (
        "Q03",
        "what platforms were never tested",
        "CONFIRMED",
        "platform/ has ZERO CI on any OS (0 hits across 7 workflow files; positive control "
        "command-center=5, monitorcore=22, mcpctl=28). All 13 CI jobs are ubuntu-latest, no "
        "matrix. macOS never exercised by any route despite being in the plugin platforms enum. "
        "Measured on Linux by this unit: 24 failed / 3875 passed / 37 skipped vs Windows 0 / 3847 "
        "/ 14; 22 of 24 failures in platform/routing, root-caused to the live ~/.claude coupling.",
    ),
    (
        "Q04",
        "what owner requirements disappeared",
        "CONFIRMED",
        "All three owner-input slots in the governing spec are still literal placeholders "
        "(_USER-PROMPTS.md:10516 option IDs, :10520 overrides, :10524 release mode) and all 27 "
        "owner questions are OPEN (OWNER-DECISIONS.md:5). OQ-3 (release mode) is open with 'Phase "
        "15 branches entirely on it', so the brief's 'PR-ONLY is binding' is an EXECUTOR "
        "assumption with no owner decision record. OQ-4 asks whether the scope substitution was "
        "ever approved: 'No approval record exists anywhere I searched.'",
    ),
    (
        "Q05",
        "what option IDs were silently dropped",
        "CONFIRMED",
        "None newly. OPTION-ID-RESOLUTION.json measured 283 options with MD/JSON symmetric "
        "difference 0, zero title mismatches, and 70 owner-decided in exact agreement across "
        "three encodings; the historic 31-way M-NN collision was re-prefixed to MECH-NN. The live "
        "gap is not dropped IDs but that OQ-1 was never answered, so no option ID was ever "
        "SELECTED.",
    ),
    (
        "Q06",
        "what failures were normalized away",
        "CONFIRMED",
        "488 suppression constructs over 355 in-scope deliverable files, 13 regex patterns each "
        "proven on a known-positive and a known-negative line first. Largest classes: 112 "
        "'# pragma: no cover', 33 pytest.skip() absence guards, 16 '|| true'. TWO OF MY OWN "
        "COUNTS WERE CORRECTED DOWNWARD: the except-clause pattern matched 290 lines but only 29 "
        "are true swallows (body pass/.../continue), and continue-on-error matched 3 of which 2 "
        "are inside YAML comments, leaving exactly 1 live (routing-benchmark.yml:96, self-labelled "
        "shadow).",
    ),
    (
        "Q07",
        "what unknowns remain",
        "CONFIRMED",
        "13 unknowns (U-1..U-13) on UNKNOWNS-REGISTER.md, none retired; each names its settling "
        "experiment. Load-bearing: U-4 (only 7 of 46 failure classes seeded), U-8 (everything "
        "marked [inherited] was never re-probed by its own author), U-13 (live vs repo harness "
        "never compared). Beyond the register: Phase 13's own contracted artifact did not exist - "
        "blindspot-register, contradiction-register and prior-art-register schemas all ship with "
        "ZERO instances repo-wide. This unit emits the first blindspot-register instance.",
    ),
    (
        "Q08",
        "what existing work was ignored",
        "CONFIRMED",
        "The repo already holds the disposition machinery the 2,007 units never used: "
        "tools/command-center/close.py + render.py, whose generated header at OWNER-DECISIONS.md:1 "
        "states dispositions are closed by running close.py and re-rendering. The 103-item "
        "register uses it; the 2,007-unit catalog does not, hence zero receipts and no disposition "
        "field. Also ignored: the declared target itself (target 2048, count 2007, shortfall 41, "
        "never closed) and hooks/semantic-router, the pre-existing router that CI still gates "
        "instead of platform/routing.",
    ),
    (
        "Q09",
        "what test could falsely pass",
        "CONFIRMED",
        "Latent, not live. The dominant shape is absence-is-not-failure: "
        "test_catalog_conformance.py:33-34 'if not CATALOG.is_file(): pytest.skip(...)' carrying "
        "'# pragma: no cover'. 33 such guards exist. Correctly scoped: NONE currently fire - a "
        "targeted run of the guarded modules gave 221 passed / 0 skipped. The risk compounds with "
        "Q03: the guard branch is invisible to coverage and platform/ has no CI, so a deletion "
        "flipping 100+ conformance tests from PASS to SKIP would be caught by nothing. My first "
        "proof attempt returned masks_found=0, which was a DETECTOR FAILURE (platform/ shadows the "
        "stdlib platform module), pivoted per AGENTS.md 4b rather than attempted a third time.",
    ),
    (
        "Q10",
        "what threat actor was not modeled",
        "CONFIRMED",
        "No STRIDE threat-model artifact exists: every STRIDE hit is a catalog declaration. All 14 "
        "spec-required phase-12 refuter lenses are unexecuted (phase 12: 129 catalogued / 0 "
        "produced; command-center/adversarial/ does not exist), including the 'cross-platform "
        "behavior' refuter that would have caught the Linux failures. The unmodeled actor with a "
        "live counterpart already found by a sibling lane is the malicious/compromised publisher "
        "plus stale mirror (two CONFIRMED revocation escapes). The actor I judge least modeled is "
        "the operator's own fan-out, which the catalog itself flags: 'a threat model that excludes "
        "the operator's own fan-out is incomplete by construction'.",
    ),
    (
        "Q11",
        "what would break at 10x scale",
        "PARTIAL",
        "Structural facts read, no load test run (NOT-CHECKED). (1) The catalog is a 5.36 MB "
        "single JSON blob json.loads'd whole by the conformance tests, schema resolver, "
        "authorization gate and renderer; at 10x that is ~54 MB per invocation with no index, no "
        "streaming, no pagination. (2) platform/ shadows the stdlib platform module - proven, not "
        "inferred, by 'No module named platform.lib; platform is not a package' - survivable only "
        "because no __init__.py exists. (3) Wall-clock is already binding: ~211s on Windows, and "
        "with zero CI nobody will run it by hand at 10x. (4) A hard-killed plugin install wedges "
        "the prefix for 1 hour (sibling finding), which dominates at 10x install concurrency.",
    ),
]

BLIND_SPOTS = [
    (
        "BS-01",
        "2,006 of 2,007 catalogued units produced nothing; no plan-to-delivery reconciliation exists",
        "P0",
        "WORK UNIT",
        None,
    ),
    (
        "BS-02",
        "Scope substitution (2,048 -> a few dozen units) never approved (OQ-4)",
        "P0",
        "OWNER DECISION",
        "Prekzursil",
    ),
    (
        "BS-03",
        "platform/ has zero CI on any OS; the 3,847-test green is hand-run and unreproducible",
        "P0",
        "WORK UNIT",
        None,
    ),
    (
        "BS-04",
        "CI is ubuntu-latest only (13/13 jobs); Windows and macOS ungated",
        "P1",
        "WORK UNIT",
        None,
    ),
    ("BS-05", "24 Linux full-suite failures (measured)", "P1", "WORK UNIT", None),
    (
        "BS-06",
        "macOS never exercised, yet declared in the plugin platforms enum",
        "P2",
        "ACCEPTED RISK",
        "Prekzursil",
    ),
    (
        "BS-07",
        "Release mode is an executor assumption; OQ-3 open",
        "P1",
        "OWNER DECISION",
        "Prekzursil",
    ),
    (
        "BS-08",
        "3 spec owner-input placeholders still literal; 27/27 owner questions open",
        "P1",
        "OWNER DECISION",
        "Prekzursil",
    ),
    (
        "BS-09",
        "0/103 register receipts exist; 26 DONE-VERIFIED items have inline evidence but no schema-valid receipt",
        "P1",
        "WORK UNIT",
        None,
    ),
    (
        "BS-10",
        "No STRIDE threat model; all 14 phase-12 refuter lenses unexecuted",
        "P1",
        "WORK UNIT",
        None,
    ),
    (
        "BS-11",
        "239/261 mcp__-bearing units unapproved",
        "P1",
        "OWNER DECISION",
        "Prekzursil",
    ),
    (
        "BS-12",
        "33 absence-is-skip guards + 112 '# pragma: no cover', invisible to coverage and to nonexistent CI",
        "P2",
        "WORK UNIT",
        None,
    ),
    (
        "BS-13",
        "Only 7 of 46 named failure classes seeded as regressions (U-4, not re-verified here)",
        "P2",
        "WORK UNIT",
        None,
    ),
    (
        "BS-14",
        "Codex/OpenAI is a first-class vendor but never a tested install client",
        "P2",
        "WORK UNIT",
        None,
    ),
    (
        "BS-15",
        "No transcript read-ledger, so Q01 is unanswerable today (BLD-0001)",
        "P2",
        "ACCEPTED RISK",
        "Prekzursil",
    ),
    (
        "BS-16",
        "5.36 MB monolithic catalog parsed whole on every consumer path",
        "P2",
        "ACCEPTED RISK",
        "Prekzursil",
    ),
    (
        "BS-17",
        "platform/ shadows stdlib platform; safe only because no __init__.py exists",
        "P2",
        "WORK UNIT",
        None,
    ),
    (
        "BS-18",
        "41-unit declared shortfall against the 2,048 target, never closed",
        "P3",
        "ACCEPTED RISK",
        "Prekzursil",
    ),
    (
        "BS-19",
        "contradiction-register and prior-art-register schemas ship with zero instances",
        "P3",
        "WORK UNIT",
        None,
    ),
    (
        "BS-20",
        "ARTIFACT-MANIFEST.json lists itself with bytes 0 / sha256 '(self)'; cannot verify itself",
        "P3",
        "ACCEPTED RISK",
        "Prekzursil",
    ),
    (
        "BS-21",
        "platform/routing measured against the live ~/.claude, so Phase 8 numbers are machine-specific and no CI runner can pass; an unused ROUTING_HOME seam exists",
        "P1",
        "WORK UNIT",
        None,
    ),
    (
        "BS-22",
        "routing-benchmark.yml gates hooks/semantic-router, not platform/routing, fail-open; two routers exist and T-13's evidence cites the older one",
        "P1",
        "WORK UNIT",
        None,
    ),
    (
        "BS-23",
        "The receipt predicate cannot express an audit unit that correctly found defects: SUCCESS is forbidden while any P0/P1 is open, so phase-12/13 units cannot emit SUCCESS when they succeed",
        "P2",
        "WORK UNIT",
        None,
    ),
]


def main() -> int:
    if not MD.is_file():
        print(f"FAILED:p13-companion {MD} does not exist")
        return 1
    md = MD.read_text(encoding="utf-8")
    if "UNKNOWN - not yet measured" in md:
        print(
            "FAILED:p13-companion the .md is still a skeleton; refusing to emit a companion "
            "that would claim more than the review does"
        )
        return 1

    report = {
        "artifact": "P13-BLINDSPOT-REVIEW",
        "unit": "depth/p13-blindspot",
        "status": "MEASURED",
        "date": "2026-08-10",
        "spec_anchor": "_USER-PROMPTS.md:11066-11082",
        "companion_md": "command-center/P13-BLINDSPOT-REVIEW.md",
        "receipt": "command-center/receipts/BLD-0023.json",
        "headline": (
            "1 of 2,007 catalogued work units produced the artifact it declared. The catalog is "
            "an orphaned plan: it carries no execution-state field and its 2,007 declared output "
            "paths intersect the program's own ARTIFACT-MANIFEST in 0 places, so plan and "
            "delivery cannot be reconciled by anything in the repo. Separately, the entire "
            "platform/ tree has zero CI on any OS, and the suite fails 24 tests on Linux."
        ),
        "questions": [
            {"id": q, "question": text, "verdict": v, "finding": f}
            for q, text, v, f in QUESTIONS
        ],
        "blind_spot_register": [
            {
                "id": i,
                "blind_spot": s,
                "severity": sev,
                "disposition": disp,
                "acceptor": acc,
            }
            for i, s, sev, disp, acc in BLIND_SPOTS
        ],
        "counts": {
            "questions_total": len(QUESTIONS),
            "questions_confirmed": sum(
                1
                for *_, v, _ in [(a, b, c, d) for a, b, c, d in QUESTIONS]
                if v == "CONFIRMED"
            ),
            "questions_partial": sum(1 for q in QUESTIONS if q[2] == "PARTIAL"),
            "questions_not_checked": sum(1 for q in QUESTIONS if q[2] == "NOT-CHECKED"),
            "blind_spots_total": len(BLIND_SPOTS),
            "blind_spots_p0": sum(1 for b in BLIND_SPOTS if b[2] == "P0"),
            "blind_spots_p1": sum(1 for b in BLIND_SPOTS if b[2] == "P1"),
            "work_units": sum(1 for b in BLIND_SPOTS if b[3] == "WORK UNIT"),
            "owner_decisions": sum(1 for b in BLIND_SPOTS if b[3] == "OWNER DECISION"),
            "accepted_risks": sum(1 for b in BLIND_SPOTS if b[3] == "ACCEPTED RISK"),
        },
        "owner_decisions_required": [
            {"id": b[0], "blind_spot": b[1], "acceptor": b[4]}
            for b in BLIND_SPOTS
            if b[3] in ("OWNER DECISION", "ACCEPTED RISK")
        ],
        "my_own_corrected_measurements": [
            "except-clause census: 290 -> 29 (the pattern matched correct handlers too)",
            "CI continue-on-error: 3 -> 1 live (2 occurrences sit inside YAML comments)",
            "skip-mask monkeypatch probe reported masks_found=0, which was a detector failure "
            "(platform/ shadows the stdlib platform module), not a finding",
        ],
        "detector_controls_run": [
            "output-existence: known-present file, known-present dir, known-absent path, "
            "known-present-but-empty file - all 4 correct before any count",
            "CI grep: positive control on three known-present strings (5/22/28 hits) before "
            "accepting the 0 for platform/",
            "suppression census: 13 patterns each fired on a known-positive and stayed silent "
            "on a known-negative line",
            "Linux report: refuses to emit unless the summary's failure count equals the number "
            "of parsed FAILED lines",
            "receipt: 5 seeded mutants (drop report.kind, empty observations, drop control_ids, "
            "single-probe evidence, drop failure object) all REJECTED while the real receipt "
            "validates with 0 errors",
        ],
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    c = report["counts"]
    print(
        f"questions: {c['questions_total']} "
        f"(CONFIRMED {c['questions_confirmed']}, PARTIAL {c['questions_partial']}, "
        f"NOT-CHECKED {c['questions_not_checked']})"
    )
    print(
        f"blind spots: {c['blind_spots_total']} "
        f"(P0 {c['blind_spots_p0']}, P1 {c['blind_spots_p1']})"
    )
    print(
        f"dispositions: {c['work_units']} work units, "
        f"{c['owner_decisions']} owner decisions, {c['accepted_risks']} accepted risks"
    )
    print(f"SUCCESS:p13-companion wrote {OUT} ({OUT.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
