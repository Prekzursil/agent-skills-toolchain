"""Write the independent-review receipts for the 3 remaining satisfiable units.

Same discipline as _b13: reviewer.verdict=PASS on the REVIEW clause only, state stays BLOCKED, and
failure.blocked_on is rewritten to name what actually remains. Schema-validated before and after;
a write that would invalidate the receipt is refused and reported.
"""

import copy
import datetime as dt
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
NOW = (
    dt.datetime.now(dt.timezone.utc)
    .replace(microsecond=0)
    .isoformat()
    .replace("+00:00", "Z")
)
REVIEWER_ID = "p2next-build-lane-fresh-context-claude-opus-5-reviewer"

spec = importlib.util.spec_from_file_location(
    "receipt_validate", ROOT / "command-center/receipt_validate.py"
)
rv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rv)
gate = rv._load_gate()
ids = rv.catalog_ids()

MANIFEST_CLAUSE = (
    "ALSO completion condition 11: manifest_registration.registered is false and the schema "
    "hard-rejects state=SUCCESS while it is. ARTIFACT-MANIFEST.json is derived by "
    "tools/command-center/render.py from the 13 charter docs only, so no unit artifact can be "
    "registered by it; 0 of 74 real unit receipts carry registered=true. Owner/orchestrator action."
)

UNITS = {
    "IMP-0440": {
        "path": "command-center/receipts/IMP-0440.json",
        "keep_classes": ["scope-exceeded"],
        "new_classes": [
            "scope-exceeded",
            "cross-tree-edit-authority-absent",
            "manifest-registration-absent",
        ],
        "blocked_on": (
            "cross-tree edit authority for the single-helper consolidation (T5 still FAILS). NOT a "
            "review blocker any more: the reviewer_requirement -- 'independent-claude-reviewer "
            "re-measures the three-route comparison on a DIFFERENT file' -- is SATISFIED (see "
            "reviewer.notes). " + MANIFEST_CLAUSE
        ),
        "notes": (
            "INDEPENDENT REVIEW, fresh context, did not author this unit. The requirement is to "
            "re-measure the three-route comparison on a DIFFERENT file; the unit used "
            "command-center/ready_units.py and tools/measure-guard/blobread.py, so this reviewer "
            "measured FOUR others: .agents/skills/acceptance-review/scripts/acceptance_review.py, "
            ".agents/skills/claude-science-local/cs_monitor.py, command-center/receipt_validate.py "
            "and hooks/todo-surfacer/test_marker_discrimination.py. On every one: `git cat-file -p` "
            "and `git show <rev>:<path>` are BYTE-IDENTICAL with 0 CRLF, `git archive` carries CRLF, "
            "and all three share one sha256 after LF normalisation. The row's claim reproduces. "
            "STRONGER CONTROL THAN THE ROW'S OWN: the byte delta equals the archive CRLF count "
            "EXACTLY on all four files (621/621, 220/220, 205/205, 100/100), which is what makes "
            "this a pure line-ending expansion rather than a content difference -- one \\n becoming "
            "\\r\\n adds exactly one byte. Negative half: a staged newline-free file shows 0 CRLF "
            "and no delta. REFUTED REVIEWER HYPOTHESIS, recorded rather than hidden: this reviewer "
            "first predicted archive would diverge ONLY where the WORKTREE has CRLF, and measured "
            "that WRONG -- cs_monitor.py is LF in both blob and worktree and archive still returned "
            "220 CRLF. git archive applies export-time EOL conversion from gitattributes/autocrlf, "
            "independent of worktree bytes. The unit's claim never rested on my hypothesis; only my "
            "control did, and the control was replaced with the exact-delta test above. "
            "SECOND BLOCKER RE-MEASURED AND STILL OPEN: T5. Scoped honestly -- `git grep -l "
            "cat-file` now matches 62 .py files outside blobread.py, but that is a MENTION count by "
            "the same use-vs-mention method the row itself used for its 37, and this reviewer did "
            "NOT re-derive it by AST. UNVERIFIED [likely, 55-80%] that the true consolidation debt "
            "is near 62; settling experiment: run the AST import check over those 62 the way this "
            "lane did for blobread's consumers. Either way T5 is not closed, so the row remains "
            "correctly BLOCKED on edit authority. VERDICT PASS on the review clause."
        ),
    },
    "TST-0334": {
        "path": "command-center/receipts/TST-0334.json",
        "new_classes": ["manifest-registration-absent"],
        "blocked_on": (
            "NOT a review blocker any more: the reviewer_requirement -- re-run the probe under a "
            "SECOND Windows shell and report divergence as a finding -- is SATISFIED with ZERO "
            "divergence (see reviewer.notes). The row's other stated blocker, 'a committed consumer "
            "of blobread', is now STALE: 5 committed non-test files import it, including the "
            "CI-wired tools/measure-guard/unitgate.py and vendordrift.py. "
            + MANIFEST_CLAUSE
        ),
        "notes": (
            "INDEPENDENT REVIEW, fresh context, did not author this unit. Requirement: re-run the "
            "probe under a SECOND Windows shell (pwsh7 and Git Bash) and report any divergence as a "
            "FINDING rather than a retry. Executed: "
            "`blobread.py hooks/todo-surfacer/test_marker_discrimination.py --compare` run once via "
            "PowerShell/python and once via C:/Program Files/Git/bin/bash.exe. RESULT: 20 payload "
            "fields compared, ZERO differing; all 12 route-measurement fields identical; the "
            "SUCCESS: terminal marker identical; both rc=0. So there is NO cross-shell divergence "
            "to report -- git_cat_file 3737B/0CRLF, git_show 3737B/0CRLF, working_tree 3837B/100, "
            "git_archive 3837B/100, one LF-normalised digest across all four routes, under BOTH "
            "shells. Both-states half: the probe on a path absent from the revision exits rc=1 "
            "rather than returning empty bytes, so a downstream content check cannot trivially "
            "pass. REVIEWER-INSTRUMENT NOTE, recorded because it nearly became a false finding: the "
            "first version of the comparison ran json.loads over the WHOLE stdout, which raises "
            "'Extra data' because blobread prints a JSON object THEN a SUCCESS: marker line. Both "
            "parses returned None, the equality guard evaluated False, and this reviewer was one "
            "step from filing a MEDIUM cross-shell-divergence finding that does not exist. Fixed by "
            "parsing the JSON prefix; the zero-divergence verdict above is from the corrected "
            "instrument. FINDING (LOW, stale blocker): failure.blocked_on names 'a committed "
            "consumer of blobread' as outstanding, and that is no longer true. An AST import check "
            "over the 15 files git grep matched finds 6 real importers, 5 of them non-test: "
            "command-center/eol_probe.py, command-center/p2-wave/_i2_redproof.py, "
            "command-center/p2-wave/_i4_percontract.py, tools/measure-guard/unitgate.py and "
            "tools/measure-guard/vendordrift.py. The grep-vs-AST gap is 15 candidates to 6 real "
            "importers, i.e. 9 mention-only -- the use-vs-mention correction this repo's own "
            "blocker_census.py already documents, applied here to the reviewer's own first probe. "
            "VERDICT PASS on the review clause."
        ),
    },
    "TST-0350": {
        "path": "command-center/receipts/TST-0350.json",
        "new_classes": ["ci-execution-pending", "manifest-registration-absent"],
        "blocked_on": (
            "first CI execution of the wired step -- an external event this reviewer cannot cause. "
            "NOT a review blocker any more: the reviewer_requirement -- an independent adversarial "
            "reviewer in a fresh context who did not author the harness and who must reproduce the "
            "both-states control -- is SATISFIED (see reviewer.notes). "
            + MANIFEST_CLAUSE
        ),
        "notes": (
            "INDEPENDENT REVIEW, fresh context, did not author the harness under test. The "
            "requirement is to REPRODUCE the both-states control before signing off, so the row's "
            "declared NC2 was re-run rather than read: 'point the collector at an empty directory: "
            "pytest exits 0 over nothing, so the floor must reject it. This is the primary defect "
            "being guarded.' Reproduced in-process against suitefloor's own API. BAD STATE: "
            "collect_count() over an empty directory returns 0 with tail 'no tests collected', and "
            "require_nonempty(0, ...) RAISES ValueError -- 'an empty or short input set is an ERROR, "
            "never a pass'. GOOD STATE, the half that proves the guard is not a blanket reject: "
            "collect_count('platform') returns 3948 against floor 3900, check_suite returns "
            "ok=True, and require_nonempty(3948) stays silent. So the control discriminates in both "
            "directions. Corroborating: the CLI the CI step calls exits 0 on --all across three "
            "registered suites (platform 3948>=3900, command-center 61>=55, casualty 32>=28), it "
            "fails CLOSED with rc=1 and 'FAILED:suite-floor unknown suite' on an unregistered name, "
            "and the harness's own test file passes 16/16. REVIEWER-INSTRUMENT NOTE, recorded: a "
            "first NC2 attempt used a temp directory OUTSIDE the repo and died with "
            "FileNotFoundError WinError 2 on Windows rootdir resolution -- it measured nothing, and "
            "reporting its silence as a pass would have been the inert-control failure this program "
            "keeps hitting. Re-run with a scratch dir inside the repo and the real signatures "
            "(collect_count returns a (count, tail) tuple; require_nonempty takes (count, label)), "
            "which the first attempt got wrong and crashed on. SECOND BLOCKER unchanged: the wired "
            "CI step has still not executed once; that is not something a reviewer can supply. "
            "VERDICT PASS on the review clause."
        ),
    },
}

results = {}
for uid, cfg in UNITS.items():
    p = ROOT / cfg["path"]
    raw = p.read_bytes()
    eol = (
        "\r\n" if raw.count(b"\r\n") > (raw.count(b"\n") - raw.count(b"\r\n")) else "\n"
    )
    doc = json.loads(raw.decode("utf-8"))
    before = gate.validate_receipt(doc)
    new = copy.deepcopy(doc)
    new["reviewer"] = {
        "reviewer_id": REVIEWER_ID,
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": "anthropic",
        "reviewed_at": NOW,
        "notes": cfg["notes"][:8192],
    }
    f = dict(new.get("failure") or {})
    f["classification"] = cfg["new_classes"][:16]
    f["blocked_on"] = cfg["blocked_on"][:2048]
    f["reason"] = (
        "The reviewer gate is CLEARED: an independent, fresh-context reviewer that did not author "
        "this unit executed the row's own reviewer_requirement and returned PASS (reviewer.notes "
        "records the method, the both-states control, and any finding). State remains BLOCKED "
        "rather than SUCCESS because other conditions are genuinely unmet -- see "
        "failure.blocked_on. Flipping to SUCCESS here would be the false green this program exists "
        "to prevent."
    )[:8192]
    new["failure"] = f
    after = gate.validate_receipt(new)
    if after:
        results[uid] = {"status": "REFUSED", "schema_errors": after[:3]}
        print(f"{uid}: REFUSED -- would become schema-invalid: {after[:2]}")
        continue
    with open(p, "w", encoding="utf-8", newline=eol) as fh:
        fh.write(json.dumps(new, indent=1, sort_keys=True) + "\n")
    admitted, _, reason = rv.admit(p, ids, gate)
    results[uid] = {
        "status": "WRITTEN",
        "path": cfg["path"],
        "state": new["state"],
        "eol": "CRLF" if eol == "\r\n" else "LF",
        "schema_errors_before": before[:2],
        "schema_errors_after": [],
        "admitted_after_write": admitted,
        "admit_reason": reason,
    }
    print(
        f"{uid}: WRITTEN eol={results[uid]['eol']} admitted={admitted} state={new['state']}"
    )

(ROOT / "command-center/p2-next/REVIEW-RECEIPTS-WRITTEN-3.json").write_text(
    json.dumps(
        {"reviewed_at": NOW, "reviewer_id": REVIEWER_ID, "units": results}, indent=2
    ),
    encoding="utf-8",
)
bad = [u for u, r in results.items() if r["status"] != "WRITTEN"]
print(
    f"\nwritten={sum(1 for r in results.values() if r['status'] == 'WRITTEN')} problems={bad}"
)
print("SUCCESS:write-three" if not bad else f"FAILED:write-three {bad}")
sys.exit(0 if not bad else 1)
