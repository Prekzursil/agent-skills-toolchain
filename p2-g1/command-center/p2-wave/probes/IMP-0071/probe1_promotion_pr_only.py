"""IMP-0071 probe 1 (source): a promotion produces a PR diff artifact and
performs ZERO direct index writes; the caller index sha256 is unchanged
before and after. Direct-write entry points raise DirectWritePromotionRefused.

Re-run: python command-center/p2-wave/probes/IMP-0071/probe1_promotion_pr_only.py
Exit 0 iff the PR-ONLY constraint is enforced in code.
"""
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
sys.path.insert(0, str(W / "tools" / "marketplace"))
from index_model import fixture_index, index_sha256  # noqa: E402
from promotion import (  # noqa: E402
    DirectWritePromotionRefused,
    apply_promotion_to_index_file,
    promote_direct_write,
    promote_via_pr,
)

index = fixture_index()
before = index_sha256(index)
promo = promote_via_pr(
    index,
    package="echo",
    version="1.1.0-beta.1",
    from_channel="beta",
    to_channel="stable",
)
after = index_sha256(index)

direct_write_guard = ""
try:
    promote_direct_write(package="echo", version="1.1.0-beta.1")
except DirectWritePromotionRefused as exc:
    direct_write_guard = str(exc)

index_file_guard = ""
sink = W / "command-center" / "receipts" / "IMP-0071-must-not-exist.json"
try:
    apply_promotion_to_index_file(sink, promo)
except DirectWritePromotionRefused as exc:
    index_file_guard = str(exc)

result = {
    "index_sha256_before": before,
    "index_sha256_after": after,
    "index_hash_unchanged": before == after,
    "direct_index_writes": promo.direct_index_writes,
    "pr_diff_sha256": __import__("hashlib").sha256(promo.pr_diff.encode("utf-8")).hexdigest(),
    "pr_diff_bytes": len(promo.pr_diff.encode("utf-8")),
    "release_mode": promo.release_mode,
    "direct_write_guard": direct_write_guard,
    "index_file_write_guard": index_file_guard,
    "sink_created": sink.is_file(),
    "unit_id": "IMP-0071",
}
result["pass"] = (
    result["index_hash_unchanged"]
    and result["direct_index_writes"] == 0
    and result["pr_diff_bytes"] > 0
    and bool(direct_write_guard)
    and bool(index_file_guard)
    and not result["sink_created"]
)
print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0071-probe1 promotion is a PR diff; direct writes refused in code")
else:
    print("FAILED:IMP-0071-probe1")
sys.exit(0 if result["pass"] else 1)
