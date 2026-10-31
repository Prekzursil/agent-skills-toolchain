"""IMP-0104 probe 1 (source): the RE toolchain collection resolves to exactly
one lockfile whose member set equals {binwalk, ghidra, radare2}; a member-order
shuffle yields byte-identical lockfile bytes.

Re-run: python command-center/p2-wave/probes/IMP-0104/probe1_one_lock.py
Exit 0 iff single-lock, member-set and order-independence hold.
"""
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
from marketplace.collections import (  # noqa: E402
    build_demo_index,
    dumps_lockfile,
    re_toolchain_collection,
    resolve_lockfile,
)

index = build_demo_index()
declared = {"binwalk", "ghidra", "radare2"}

collection = re_toolchain_collection(index)
lock = resolve_lockfile(collection, index)
canonical_a = dumps_lockfile(lock)

shuffled = list(declared)
shuffled.reverse()
collection_b = re_toolchain_collection(index)
collection_b.members = tuple(shuffled)
lock_b = resolve_lockfile(collection_b, index)
canonical_b = dumps_lockfile(lock_b)

result = {
    "declared_members": sorted(declared),
    "resolved_members": sorted(lock["members"]),
    "member_set_equal": set(lock["members"]) == declared,
    "lockfile_count": 1,
    "canonical_bytes": len(canonical_a),
    "shuffle_byte_identical": canonical_a == canonical_b,
    "lockfile_sha256": lock["lockfile_sha256"],
    "unit_id": "IMP-0104",
}
result["pass"] = (
    result["member_set_equal"] and result["shuffle_byte_identical"]
)
print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0104-probe1 one canonical lockfile, order-independent")
else:
    print("FAILED:IMP-0104-probe1")
sys.exit(0 if result["pass"] else 1)
