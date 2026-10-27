"""IMP-0202 probe 2 (verifier): every cited artifact path is Test-Path-ed
BEFORE a digest is read or accepted. A ghost path rejects with digest_read
false; a digest with NO raw citations is a claim, not a receipt; the honest
raw-citing record passes.

Exit 0 iff all three states hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from confirmation_hook import confirm  # noqa: E402

RAW = HERE / "probe2-existence-before-digest.raw.txt"
claimed = json.loads((HERE / "claim.json").read_text(encoding="utf-8"))

missing_path = confirm({
    "author_id": "wf-author", "reviewer_id": "fresh-reviewer",
    "citations": {"raw": ["raw/per_case_rows.json", "raw/ghost-case-does-not-exist.json"]},
    "claimed_digest": claimed["claimed_digest"],
}, workspace=HERE)

digest_only = confirm({
    "author_id": "wf-author", "reviewer_id": "fresh-reviewer",
    "citations": {"digest": ["claim.json"]},
    "claimed_digest": claimed["claimed_digest"],
}, workspace=HERE)

honest = confirm({
    "author_id": "wf-author", "reviewer_id": "fresh-reviewer",
    "citations": {"raw": ["raw/per_case_rows.json"]},
    "claimed_digest": claimed["claimed_digest"],
}, workspace=HERE)

lines = [json.dumps({"probe": "probe2-existence-before-digest", "unit_id": "IMP-0202",
                     "missing_path": {"verdict": missing_path["verdict"],
                                      "reason": missing_path["reason"],
                                      "paths_missing": missing_path.get("paths_missing"),
                                      "digest_read": missing_path["digest_read"],
                                      "trace": missing_path["trace"]},
                     "digest_only": {"verdict": digest_only["verdict"],
                                     "reason": digest_only["reason"],
                                     "digest_accepted": digest_only["digest_accepted"]},
                     "honest": {"verdict": honest["verdict"],
                                "digest_accepted": honest["digest_accepted"],
                                "digest_read": honest["digest_read"]},
                     "absent_ok": missing_path["verdict"] == "REJECT",
                     "digest_ok": honest["verdict"] == "ACCEPT",
                     "pass": True})]
assert missing_path["verdict"] == "REJECT" and missing_path["reason"] == "PATH_ABSENT"
assert missing_path["digest_read"] is False, "digest read despite missing cited path"
assert missing_path.get("paths_missing") == ["raw/ghost-case-does-not-exist.json"]
assert any(t.startswith("test_path:") for t in missing_path["trace"]), "no test_path stage"
assert digest_only["verdict"] == "REJECT" and digest_only["reason"] == "DIGEST_IS_CLAIM"
assert honest["verdict"] == "ACCEPT" and honest["digest_read"] is True
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"absent_ok": True, "digest_ok": True,
                              "ghost_rejected_before_digest_read": True,
                              "digest_only_rejected": True}))
print("SUCCESS:IMP-0202-probe2 existence checked before any digest is read")
