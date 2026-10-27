"""Per-unit negative-control extraction from THIS reviewer's live probe captures.

Each row is emitted ONLY when both its fired-pattern and silent-pattern are found in
the live capture files written by verify.py (never from recorded/builder outputs).
Quoted lines are verbatim from the live run.
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE = HERE / "live"

# unit -> list of (control_id, kind, description, fired_regex, silent_regex, probe_file_hint)
CONTROL_MAP = {
    "AUD-0033": [
        ("AUD-0033-C1-fence-vs-prose", "known-broken-fixture",
         "extractor finds the fenced path and rejects the prose slash in the same fixture",
         r'"fence_present_extracted":\s*true', r'"prose_false_path_extracted":\s*false',
         "probe1"),
    ],
    "AUD-0043": [
        ("AUD-0043-include-omit-console", "mutation",
         "include-omit mutant: installed console entry point goes RED on the mutant and stays GREEN on the good wheel",
         r"mutant_console=RED", r"good_console=GREEN", "probe2"),
        ("AUD-0043-source-lane-good", "mutation",
         "source-tree invocation stays green on the good package (baseline for the miss the unit measures)",
         r'"good_ok":\s*true', r'"pass":\s*true', "probe1"),
    ],
    "AUD-0047": [
        ("AUD-0047-fixture-control-narrow", "known-broken-fixture",
         "planted narrow-workflow fixture exercises the paths-ignore evaluator on a known state",
         r'fixture-control-narrow', r'"pass":\s*true', "probe1"),
    ],
    "AUD-0053": [
        ("AUD-0053-egress-blocked-then-not", "known-broken-fixture",
         "egress control: connect attempt under blocked egress fails, then a control host is probed",
         r"control=EgressBlocked-then-not", r"control_host=", "probe1"),
    ],
    "AUD-0057": [
        ("AUD-0057-mutation-both-states", "mutation",
         "mutation control: exercised assertion goes red, unexercised stays green, independent of the census AST",
         r"exercised_goes_red=True", r"unexercised_still_green=True", "probe2"),
    ],
    "AUD-0066": [
        ("AUD-0066-wrong-port-control", "absent-input",
         "wrong-port control: endpoint health probe reports a deliberate wrong-port endpoint as down",
         r"wrong-port control", r"up=False", "probe2"),
    ],
    "AUD-0069": [
        ("AUD-0069-planted-mutant-calibration", "known-broken-fixture",
         "planted near-duplicate mutants score above thresholds (rename=1.0) while paraphrase/fork score below, calibrating the detector",
         r"rename_jaccard=1\.0", r"paraphrase_jaccard=0\.\d+", "probe1"),
    ],
    "AUD-0072": [
        ("AUD-0072-band-mapping-bounds", "known-broken-fixture",
         "every confidence band maps (should_work_unmapped=True) and out-of-vocabulary phrases stay unmapped",
         r"should_work_unmapped=True", r"bands=\{", "probe1"),
    ],
    "AUD-0080": [
        ("AUD-0080-use-vs-mention", "known-broken-fixture",
         "rm-gate CAUGHT on real use while naive fingerprints vanish on mention-only lines (verb_fp=0)",
         r"rm_gate=CAUGHT", r"verb_fp=0", "probe2"),
        ("AUD-0080-wrong-field-bypass", "adversarial-payload",
         "adversarial wrong-field payload BYPASSES the naive matcher (the defect class the unit audits)",
         r"wrong_field=BYPASS", r"naive_fp=\d+", "probe2"),
    ],
    "AUD-0082": [
        ("AUD-0082-fixture-vs-live", "known-broken-fixture",
         "reserved/long/case hazards reproduced on the fixture while the live tree is clean (fixture=True, live hazards 0)",
         r"fixture=True", r"hazards=\{'reserved-name':\s*0", "probe1"),
    ],
    "AUD-0084": [
        ("AUD-0084-ast-use-vs-mention", "known-broken-fixture",
         "AST adjudication separates string-literal path mentions from operational path uses",
         r"SUCCESS:AUD-0084-probe2", r"adjudicat", "probe2"),
    ],
    "AUD-0096": [
        ("AUD-0096-sandbox-cleanliness", "known-broken-fixture",
         "clean-profile sandbox measured only after cleanliness gate (sandbox_clean_before_measure=true)",
         r"sandbox_clean_before_measure.\s*true", r"clean_user=0", "probe1"),
        ("AUD-0096-leak-identification", "known-broken-fixture",
         "leaked-profile identification control: leaked ids are found in the current profile (leak_ok=True)",
         r"leak_ok=True", r"shared_count=\d+", "probe2"),
    ],
}


def _lines(text: str, pat: str):
    rx = re.compile(pat)
    return [ln.strip() for ln in text.splitlines() if rx.search(ln)]


def extract(uid: str) -> tuple[list[dict], list[str]]:
    controls, gaps = [], []
    for cid, kind, desc, fired_rx, silent_rx, hint in CONTROL_MAP.get(uid, []):
        cap = LIVE / f"{uid}_{hint}.out"
        if not cap.exists():
            gaps.append(f"{cid}: no live capture {cap.name}")
            continue
        txt = cap.read_text(encoding="utf-8", errors="replace")
        fired = _lines(txt, fired_rx)
        silent = _lines(txt, silent_rx)
        if fired and silent:
            controls.append({
                "id": cid[:256],
                "kind": kind,
                "description": desc[:2000],
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "\n".join(fired)[:4096],
                "good_state_output": "\n".join(silent)[:4096],
            })
        else:
            gaps.append(f"{cid}: fired={'yes' if fired else 'NO'} silent={'yes' if silent else 'NO'} (live)")
    return controls, gaps
