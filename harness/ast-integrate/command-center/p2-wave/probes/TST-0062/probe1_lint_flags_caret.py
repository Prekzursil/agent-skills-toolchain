#!/usr/bin/env python3
"""Probe 1: test_caret_ref_is_flagged_by_the_lint (both-states + use-vs-mention)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from caret_lint import lint_command, lint_path, naive_caret_present  # noqa: E402

UNIT = "TST-0062"
ART = REPO / "command-center/receipts/TST-0062.json"
FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    bad_peel = FIX / "bad_unquoted_peel.ps1"
    bad_parent = FIX / "bad_unquoted_parent.ps1"
    good_sq = FIX / "good_single_quoted.ps1"
    good_dq = FIX / "good_double_quoted.ps1"
    good_rl = FIX / "good_rev_list.ps1"
    mention = FIX / "mention_comment.ps1"

    f_bad_peel = lint_path(bad_peel)
    f_bad_parent = lint_path(bad_parent)
    f_sq = lint_path(good_sq)
    f_dq = lint_path(good_dq)
    f_rl = lint_path(good_rl)
    f_mention = lint_path(mention)

    if not f_bad_peel:
        return fail("unquoted peel was not flagged")
    if not f_bad_parent:
        return fail("unquoted HEAD^ was not flagged")
    if f_sq:
        return fail(f"single-quoted peel flagged: {f_sq}")
    if f_dq:
        return fail(f"double-quoted peel flagged: {f_dq}")
    if f_rl:
        return fail(f"rev-list form flagged: {f_rl}")
    if f_mention:
        return fail(f"comment mention flagged (use-vs-mention): {f_mention}")

    # Known-broken control: a caret substring check cannot tell use from mention.
    mention_text = mention.read_text(encoding="utf-8")
    if not naive_caret_present(mention_text):
        return fail("naive control did not see a caret in the mention fixture")
    if naive_caret_present(mention_text) and not f_mention:
        mention_control_ok = True
    else:
        mention_control_ok = False
    if not mention_control_ok:
        return fail("mention control did not discriminate naive vs shipped lint")

    good_sq_text = good_sq.read_text(encoding="utf-8")
    if not naive_caret_present(good_sq_text):
        return fail("naive control silent on quoted peel (control dead)")
    if f_sq:
        return fail("shipped lint flagged quoted peel")

    inline_bad = lint_command("git rev-parse v1.4.1^{commit}", shell="pwsh")
    inline_good = lint_command("git rev-parse 'v1.4.1^{commit}'", shell="pwsh")
    inline_rl = lint_command("git rev-list -n 1 v1.4.1", shell="pwsh")
    bash_unquoted = lint_command("git rev-parse v1.4.1^{commit}", shell="bash")
    if not inline_bad:
        return fail("inline unquoted peel not flagged")
    if inline_good or inline_rl:
        return fail("inline sanctioned forms flagged")
    if bash_unquoted:
        return fail("bash shell was linted as PowerShell")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt self-declared {doc.get('state')}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0062" not in text:
        return fail("sentinel absent")
    tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    if "test_caret_ref_is_flagged_by_the_lint" not in tests:
        return fail("catalog test id missing from receipt")
    if tests["test_caret_ref_is_flagged_by_the_lint"].get("result") != "PASS":
        return fail("receipt test result not PASS")

    payload = {
        "probe": "probe1-lint",
        "unit_id": UNIT,
        "pass": True,
        "unquoted_peel_findings": len(f_bad_peel),
        "unquoted_parent_findings": len(f_bad_parent),
        "quoted_silent": True,
        "rev_list_silent": True,
        "mention_silent": True,
        "naive_flags_mention": True,
        "bash_not_in_scope": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0062-probe1 caret ref flagged; quoted/rev-list/mention silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
