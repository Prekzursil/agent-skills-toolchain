import json

RECEIPT = r"C:\Users\Prekzursil\source\agent-skills-toolchain\command-center\receipts\CC-0019.json"

with open(RECEIPT, encoding="utf-8") as f:
    rec = json.load(f)

prior = rec.get("reviewer", {})

notes = (
    "Independent fresh-context review (claude, c5-cc-0019) 2026-09-19T12:57:50Z. "
    "Attempted the contracted different-20 record sample: author cited 0 records "
    "(report.sample_resolve=null, receipts/CC-0019.json:262), so disjointness is trivial, "
    "but ZERO normalized records exist to draw - resolve rate 0/0, sample 0 of 20 "
    "(shortfall -20). Falsification probes: (1) corpus mount absent on this machine too - "
    "C:/Users/Prekzursil/.claude/harness-restore-20260806 holds 0 files and re-running "
    "tools/command-center/corpus_normalize.py probe-presence measures all 5 expected "
    "basenames absent (n_expected_present=0); (2) repo sweep found no emitted record "
    "corpus (command-center/corpus/ absent; planted_synthetic appears only in receipt "
    "metadata); (3) fixture output cannot substitute by the tool's own design "
    "(corpus_normalize.py:166-170). Evidence requirement 're-open each cited file:line' "
    "is unsatisfiable. Verdict FAIL; unit stays blocked-on-missing-corpus-mount. The "
    "implementer's fail-closed stance (success_invented=false, corpus_fabricated=false) "
    "is correct and is NOT the defect - the missing corpus is. Raw evidence: "
    "command-center/p2-wave/reviews/CC-0019/sample-20-resolve.raw.txt + independent-review.json."
)

assert len(notes) >= 200, f"notes floor 200 chars, got {len(notes)}"

rec["reviewer"] = {
    "verdict": "FAIL",
    "independent": True,
    "fresh_context": True,
    "vendor": "claude",
    "reviewer_id": "c5-cc-0019-independent-reviewer",
    "reviewed_at": "2026-09-19T12:57:50Z",
    "resolve_rate": "0/0",
    "sample_size": 0,
    "sample_required": 20,
    "notes": notes,
    "prior_reviewer_state": {
        "verdict": prior.get("verdict", "NOT-REVIEWED"),
        "reviewer_id": prior.get("reviewer_id"),
        "note": "implementer-lane placeholder superseded by this independent review",
    },
    "evidence_files": [
        "command-center/p2-wave/reviews/CC-0019/sample-20-resolve.raw.txt",
        "command-center/p2-wave/reviews/CC-0019/independent-review.json",
    ],
}

# state/sentinel left untouched: a FAIL review must not flip a BLOCKED unit to SUCCESS.

with open(RECEIPT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(rec, f, indent=1, ensure_ascii=False)
    f.write("\n")

# verify round-trip
with open(RECEIPT, encoding="utf-8") as f:
    back = json.load(f)
rv = back["reviewer"]
print(
    "VERIFIED reviewer.verdict=%s independent=%s vendor=%s notes_len=%d state=%s sentinel_prefix=%s"
    % (
        rv["verdict"],
        rv["independent"],
        rv["vendor"],
        len(rv["notes"]),
        back.get("state"),
        back.get("sentinel", "")[:40],
    )
)
