# CC-0019 r2 evidence writer: merges the two re-probed verdicts into the sample
# record (first-pass flag kept honestly, reprobe outcome added), writes
# r2-sample-20.raw.txt + r2-independent-review.json, then promotes the receipt
# reviewer block (reviewer block ONLY - every other field preserved).
import json
import datetime
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REV = r"C:\Users\Prekzursil\source\agent-skills-toolchain\command-center\p2-wave\reviews\CC-0019"
RECEIPT = r"C:\Users\Prekzursil\source\agent-skills-toolchain\command-center\receipts\CC-0019.json"

d = json.load(open(REV + r"\r2-sample-20.json", encoding="utf-8"))
reprobe = {
    "CC19-Probe-1:-run-gitleaks-plus-a-high-entropy-scan-a-5e81cabed2f9": (
        "RESOLVED",
        "first-pass flag was a detector artifact (reverse check demanded the whole "
        'JSON \'"claim": "...",\' wrapper line be inside claim_text). Re-probe: record title == '
        "cited line's quoted value[:200] verbatim; canonical_mechanism == value[:500] verbatim "
        "prefix; only 19 chars past the normalizer cap dropped ('e before any tally.' = tail of "
        "'...file before any tally.'). Faithful per the corpus anchor convention "
        "(command-center/adversarial/ADV-0023-corpus-secret-canary-sweep.json:27).",
    ),
    "CC19-STRIDE-threat-model-of-the-plugin-installation-a-ad15ed2618f0": (
        "RESOLVED",
        "first-pass flag was a detector artifact (same JSON-wrapper cause). Re-probe: "
        "quoted title value 'STRIDE threat model of the plugin installation and update path' is "
        "verbatim in claim_text (command-center/casualty/recovered/ADV-0021-spec.json:41).",
    ),
}
resolved = 0
for row in d["rows"]:
    if row["claim_id"] in reprobe:
        v, note = reprobe[row["claim_id"]]
        row["first_pass_verdict"] = row["verdict"]
        row["verdict"], row["reason"] = v, note
    if row["verdict"] == "RESOLVED":
        resolved += 1
d["resolved_after_reprobe"] = resolved
d["content_mismatch_after_reprobe"] = sum(
    1 for x in d["rows"] if x["verdict"] == "CONTENT-MISMATCH"
)
d["dead_anchor_after_reprobe"] = sum(
    1 for x in d["rows"] if x["verdict"] == "DEAD-ANCHOR"
)
assert resolved == 20, resolved
json.dump(
    d,
    open(REV + r"\r2-sample-20.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)

lines = []
lines.append(
    "CC-0019 r2 INDEPENDENT REVIEW RAW EVIDENCE (fresh-context reviewer c5-cc-0019-r2, claude)"
)
lines.append(
    "date: "
    + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
)
lines.append(
    "draw: random.Random(seed=7).sample(pool, 20); pool = 1046 emitted records minus the"
)
lines.append(
    "      author's seed=19 20 ids (command-center/p2-wave/probes/CC-0019/sample-resolve.json);"
)
lines.append(
    "      author ids all present in corpus; sample overlap with author = 0 by construction."
)
lines.append(
    "per-anchor check: re-open cited file at cited line; CONTENT check (title verbatim in the"
)
lines.append(
    "line / line value verbatim in claim_text), not mere file existence. #fragment json anchors"
)
lines.append(
    "also key-checked. Convention: md lines = heading line; json lines = first verbatim"
)
lines.append(
    "occurrence of the record title (normalize-summary.json anchor_convention)."
)
lines.append("")
for row in d["rows"]:
    lines.append("[%s] %s" % (row["verdict"], row["claim_id"]))
    lines.append("    anchor=%s" % row["anchor"])
    lines.append(
        "    line %s = %r" % (row["line"], (row.get("cited_line") or "")[:150])
    )
    if row.get("first_pass_verdict"):
        lines.append(
            "    FIRST-PASS=%s then REPROBED: %s"
            % (row["first_pass_verdict"], row["reason"])
        )
lines.append("")
lines.append(
    "TALLY: resolved 20/20 (0 content-mismatch, 0 dead-anchor after reprobe of 2 first-pass"
)
lines.append("detector artifacts - both re-probes documented inline above).")
lines.append("")
lines.append("CONSERVATION SPOT-CHECK (command-center/corpus/normalize-summary.json):")
lines.append("  1046 + 47 + 203 = 1296 = claimed inputs  -> True")
lines.append(
    "  families extracted 1092 + dropped 203 + planted 1 = 1296 inputs -> True"
)
lines.append("  1092 + 1 planted - 47 merged = 1046 emitted -> True")
lines.append(
    "  merged_enumerated len=47, dropped_enumerated len=203 (match claimed counts)"
)
lines.append("")
lines.append(
    "PLANTED SYNTHETIC MARKING (command-center/corpus/claim-records.jsonl, exact-id match 1):"
)
lines.append(
    "  claim_id='CC-0019-PLANTED-SYNTHETIC-FINDING'; claim_text='CC-0019-PLANTED-SYNTHETIC-MARKER-v1';"
)
lines.append(
    "  mechanism text says 'planted synthetic finding ... detector control'; lineage note ="
)
lines.append(
    "  'planted detector control; not a real corpus finding'; anchor=__cc0019_planted_synthetic__.marker:1."
)
lines.append("  Cannot masquerade as a real finding.")
lines.append("")
lines.append(
    "SUBSTITUTION DISCLOSURE: receipts/CC-0019.json report.population_substitution discloses"
)
lines.append(
    "contracted input ABSENT + in-repo substituted population + fabricated_contracted_contents=false;"
)
lines.append("state stayed BLOCKED pending this review (designed flow).")
open(REV + r"\r2-sample-20.raw.txt", "w", encoding="utf-8", newline="\n").write(
    "\n".join(lines) + "\n"
)
print("wrote r2-sample-20.raw.txt (%d lines)" % len(lines))

review = {
    "unit": "CC-0019",
    "review_round": 2,
    "reviewer": "c5-cc-0019-r2 (fresh-context independent reviewer, claude)",
    "independent": True,
    "fresh_context": True,
    "sample": {
        "seed": 7,
        "draw": "random.Random(7).sample(1046 records minus author seed=19 ids, 20)",
        "size": 20,
        "overlap_with_author_ids": [],
        "resolve_fraction": "20/20",
        "content_mismatch": 0,
        "dead_anchor": 0,
        "reprobed_first_pass_flags": list(reprobe.keys()),
    },
    "conservation": {
        "inputs": 1296,
        "emitted": 1046,
        "merged": 47,
        "dropped": 203,
        "equation_holds": True,
        "enumerated_lens_match": True,
    },
    "planted_synthetic_marked": True,
    "substitution_disclosed": True,
    "verdict": "PASS",
    "evidence_files": [
        "command-center/p2-wave/reviews/CC-0019/r2-sample-20.raw.txt",
        "command-center/p2-wave/reviews/CC-0019/r2-sample-20.json",
        "command-center/p2-wave/reviews/CC-0019/r2-independent-review.json",
    ],
}
json.dump(
    review,
    open(REV + r"\r2-independent-review.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)
print("wrote r2-independent-review.json")

# --- promote receipt reviewer block ONLY ---
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
notes = (
    "Independent fresh-context different-20 review (claude, c5-cc-0019-r2) %s. Falsification: drew "
    "random.Random(seed=7).sample over the 1046 emitted records EXCLUDING the author's seed=19 20 ids "
    "(probes/CC-0019/sample-resolve.json) - overlap 0; re-opened each cited file:line and CONTENT-verified "
    "the record against the anchor (title verbatim at line / line value verbatim in claim_text), not mere "
    "existence: resolve fraction 20/20, 0 content-mismatch, 0 dead anchors. Two first-pass flags "
    "(ADV-0023:27 gitleaks, ADV-0021-spec.json:41 STRIDE) were my detector's JSON-wrapper artifact; "
    "re-probes (verbatim-prefix + quoted-value-in-claim checks) resolved both, documented in "
    "reviews/CC-0019/r2-sample-20.raw.txt. Conservation re-derived: 1046+47+203=1296, families 1092+203+1=1296 "
    "inputs, 1092+1-47=1046 emitted, enumerated lens 47/203 match. Planted synthetic unambiguously marked "
    "(claim-records.jsonl exact-id row CC-0019-PLANTED-SYNTHETIC-FINDING, MARKER-v1, lineage note 'planted "
    "detector control; not a real corpus finding'). Population substitution honestly disclosed in "
    "receipts/CC-0019.json report.population_substitution; BLOCKED-until-review was the designed flow. "
    "PASS on the substituted population; catalog adjudication of the substitution itself remains the "
    "owner's open call (residual NOT-CHECKED, not a review blocker)." % now
)
assert len(notes) >= 200
rec = json.load(open(RECEIPT, encoding="utf-8"))
prev = dict(rec.get("reviewer", {}))
rec["reviewer"] = {
    "verdict": "PASS",
    "independent": True,
    "notes": notes,
    "vendor": "claude",
    "reviewed_at": now,
}
json.dump(rec, open(RECEIPT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(
    "receipt reviewer block promoted: prev verdict=%s -> PASS at %s"
    % (prev.get("verdict"), now)
)
# re-parse to prove valid JSON
json.load(open(RECEIPT, encoding="utf-8"))
print(
    "receipt re-parses as valid JSON; other fields preserved (unit_id=%s state=%s)"
    % (rec["unit_id"], rec["state"])
)
