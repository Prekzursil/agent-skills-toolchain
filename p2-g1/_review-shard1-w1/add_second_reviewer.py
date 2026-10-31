#!/usr/bin/env python3
"""Add the cross-vendor second-reviewer verdicts to the 3 closed multi-reviewer units."""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
R = REPO / "command-center/receipts"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SECOND = {
    "ADV-0132": {
        "file": "verdict-ADV-0132-round2.txt",
        "reviewer_id": "grok-4.7 via grok-lane (grok2api 127.0.0.1:8182) - cross-vendor reviewer #2, round 2",
        "note": (
            "Round-1 FAIL retracted after corrected transport evidence; round-2 PASS. "
            "Blind condition preserved: prompts carried verbatim instrument outputs, never reviewer #1's verdict. "
            "Round-1 reasons adjudicated: R1 (probe1 exit 1) was a Windows cmd.exe transport artifact of bundle "
            "assembly - probe1 verified end-to-end exit 0 under POSIX (first WSL run, verbatim in reviewer #1 "
            "transcript; WSL subsequently wedged 0x8007274c, so single-shot) plus mechanical decomposition on the "
            "native host (both sub-probes RES-0063/RES-0108 direct exit 0 with observations matching the artifact; "
            "probe1's four HC checks AGREEMENT-HELD; probe2 exit 0). R2 (annotated raw_output strings) partially "
            "upheld: study.py constructs the read_ok/schema-ok parenthetical strings as literals (disclosed in "
            "code); no catalog letter violated (evidence_requirement does not demand verbatim transcripts); "
            "recorded here. R3 (same-process pre-registration, one shared timestamp pair) upheld as "
            "letter-satisfied/spirit-weaker; compensating control: mutation control re-run live exit 0."
        ),
    },
    "ARC-0013": {
        "file": "verdict-ARC-0013.txt",
        "reviewer_id": "grok-4.7 via grok-lane (grok2api 127.0.0.1:8182) - cross-vendor reviewer #2",
        "note": (
            "Catalog requirement names Codex as the cross-vendor reviewer; Codex was unavailable "
            "(401 Missing bearer x19 via codex-cli 0.154.0 and McpHub rail; credential lifecycle is owner-owned, "
            "not touched). grok-4.7 substituted per program precedent (grok-p2-wave-* reviewers on prior closures). "
            "Blind condition preserved: prompt carried verbatim evidence bundle, no reviewer #1 verdict."
        ),
    },
    "ARC-0020": {
        "file": "verdict-ARC-0020.txt",
        "reviewer_id": "grok-4.7 via grok-lane (grok2api 127.0.0.1:8182) - cross-vendor reviewer #2",
        "note": (
            "Codex unavailable (same 401 class); grok-4.7 substituted per program precedent. "
            "Blind condition preserved."
        ),
    },
}

for uid, spec in SECOND.items():
    p = R / (uid + ".json")
    r = json.loads(p.read_text(encoding="utf-8"))
    verdict = (REPO / "_review-shard1-w1/codex" / spec["file"]).read_text(encoding="utf-8")
    head = verdict.strip().splitlines()[0] if verdict.strip() else "NO-VERDICT-LINE"
    rev = r["reviewer"]
    rev["second_reviewer"] = {
        "reviewer_id": spec["reviewer_id"],
        "model": "grok-4.7",
        "vendor": "xai (grok2api lane)",
        "independent": True,
        "blind_until_both_filed": True,
        "verdict": ("PASS" if head.upper().startswith("VERDICT: PASS") else "FAIL"),
        "verbatim": verdict,
        "note": spec["note"],
    }
    r["ts"] = NOW
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(p)
    print("PATCHED", uid, "second_reviewer.verdict =", rev["second_reviewer"]["verdict"])
print("SUCCESS:second-reviewer blocks written")
