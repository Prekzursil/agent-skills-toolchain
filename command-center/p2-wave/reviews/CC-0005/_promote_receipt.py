"""Promote CC-0005 receipt: merge independent reviewer block (PASS).

Preserves every other field; asserts notes floor (>=200 chars) and valid JSON out.
"""

import json
from pathlib import Path

RECEIPT = Path(
    "C:/Users/Prekzursil/source/agent-skills-toolchain/command-center/receipts/CC-0005.json"
)

notes = (
    "Independent Windows reproduction (Claude, fresh context, core.autocrlf=true checkout @ "
    "a49fdf8791; unit base 75da713 verified ancestor of HEAD). Recomputed 5 receipt-cited "
    "hashes from git blobs via cat-file with own commands (not the unit scripts): "
    "tools/command-center/validate.py@75da713=68f06a32e70c6f17807ef434b05c38a5f7b6e5b41c8d"
    "6889d590a739e906b4e0 MATCH; tools/measure-guard/blobread.py=a9f41cef63ded7ce58336bb585"
    "37e9e6bdfae76e0b7cce4a556b4e4d3671d49f MATCH (identical base/HEAD/worktree); "
    ".gitattributes@75da713=e30af5b07d68121f142008199282f2130ef8c2c62e80bbf1ee733d6deba2e561 "
    "MATCH; seed.py=fbca3417... and tests/test_reach6_blob_provenance.py=ccfb09f8... MATCH. "
    "Both-states control on the production REACH-6 input command-center/sources/REGISTER.md: "
    "blob f63cfeae2164 (69536B, 0 CRLF; equals the receipt probe sha12) vs worktree "
    "c09bf0e75ff8 (69912B, 376 CRLF), identical after LF-normalisation, byte delta 376 == "
    "line count 376 — worktree hashing would record the wrong digest, so the fix is "
    "load-bearing. Gate path re-read: tools/command-center/validate.py:83 "
    "_register_provenance_bytes -> tools/measure-guard/blobread.py:56 read_blob (git cat-file "
    "only; git archive appears solely in three_route_comparison as the indicted route). "
    "Windows: validate.py --require-complete EXIT=0 with the real CRLF REGISTER.md worktree "
    "present; pytest reach6-blob + provenance_blob_hash 9/9 green. Linux parity at the "
    "IDENTICAL commit (quality run 35441814807 @ a49fdf8, ubuntu-latest, job "
    "gate-tests-coverage (python packages)): pytest tools/command-center/tests 173 passed "
    "including all CC-0005 tests (local collect 179 == 173+6; the 6 errors are all "
    "test_mechanism_dedup_gate numpy ModuleNotFoundError — CC-0020, unrelated). CAVEAT: "
    "validate.py --require-complete was never reached in CI at this commit (bash -e aborted "
    "on the numpy errors first) and quality has never been green on this branch, so parity "
    "is suite-level, not a workflow-green validate.py run. Prior independent review "
    "(command-center/p2-wave/probes/CC-0005/independent-review.json, openai) blocked only on "
    "the Windows + CI halves supplied/scoped here. Raw evidence: "
    "command-center/p2-wave/reviews/CC-0005/independent-hash-repro.raw.txt"
)

data = json.loads(RECEIPT.read_text(encoding="utf-8"))
assert len(notes) >= 200, f"notes floor: {len(notes)}"

data["reviewer"] = {
    "verdict": "PASS",
    "independent": True,
    "fresh_context": True,
    "vendor": "claude",
    "reviewer_id": "c5-cc-0005-fresh-context-windows-checkout",
    "reviewed_at": "2026-09-19T13:04:59Z",
    "notes": notes,
}

out = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
RECEIPT.write_text(out, encoding="utf-8", newline="\n")

check = json.loads(RECEIPT.read_text(encoding="utf-8"))
assert (
    check["reviewer"]["verdict"] == "PASS" and check["reviewer"]["independent"] is True
)
assert check["unit_id"] == "CC-0005" and check["state"] == data["state"]
assert len(check["artifacts"]) == 13 and len(check["evidence"]) == 3
print(
    "SUCCESS:promote CC-0005 reviewer block PASS independent=true; JSON re-parsed OK;"
)
print(
    "notes_chars=%d artifacts=%d evidence=%d state=%s"
    % (
        len(check["reviewer"]["notes"]),
        len(check["artifacts"]),
        len(check["evidence"]),
        check["state"],
    )
)
