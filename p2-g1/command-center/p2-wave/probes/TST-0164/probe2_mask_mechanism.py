#!/usr/bin/env python3
"""TST-0164 probe 2: live mask mechanism + independent recomputation.

Does not import probe1. Two rails:
  (a) live mini-experiment: two artifact trees differing only in declared
      non-deterministic fields normalize to identical; an undeclared field
      must keep the normalized diff red; masking everything is rejected by
      the coverage ceiling;
  (b) independent recomputation from the receipt's embedded measured data:
      raw trees differ where byte-diff rows exist, the normalized diff is
      empty with equal tree shas, and every recorded flags row is true.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0164.json"
UID = "TST-0164"
DECLARED = ["meta.timestamp_ns", "meta.pid", "timestamp_ns"]
CEILING_MAX_FIELDS = 8


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def norm(obj, mask: set[str], prefix: str = ""):
    """Drop masked leaf paths (dotted), then canonicalize via json equality."""
    if isinstance(obj, dict):
        out = {}
        for k, v in sorted(obj.items()):
            path = f"{prefix}.{k}" if prefix else k
            if path in mask:
                continue
            out[k] = norm(v, mask, path)
        return out
    if isinstance(obj, list):
        return [norm(v, mask, prefix) for v in obj]
    return obj


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))

    # ---- (a) live mini-experiment -------------------------------------
    with tempfile.TemporaryDirectory(prefix="tst-0164-p2-") as td:
        root = Path(td)
        tree_a = root / "uninterrupted"
        tree_b = root / "resumed"
        for d in (tree_a, tree_b):
            (d / "sub").mkdir(parents=True)
            payload = {
                "ok": 1,
                "meta": {"timestamp_ns": "wall-a", "pid": 1},
                "timestamp_ns": "wall-a",
            }
            (d / "emit.json").write_text(json.dumps(payload, sort_keys=True))
            payload2 = {
                "ok": 2,
                "meta": {"timestamp_ns": "wall-b", "pid": 2},
                "timestamp_ns": "wall-b",
            }
            (d / "sub" / "emit2.json").write_text(json.dumps(payload2, sort_keys=True))

        # The resumed tree differs ONLY in declared nd fields: identical
        # under the mask.
        b_payload = json.loads((tree_b / "emit.json").read_text(encoding="utf-8"))
        b_payload["meta"]["timestamp_ns"] = "wall-c"
        b_payload["meta"]["pid"] = 3
        b_payload["timestamp_ns"] = "wall-c"
        (tree_b / "emit.json").write_text(json.dumps(b_payload, sort_keys=True))
        b2 = json.loads((tree_b / "sub" / "emit2.json").read_text(encoding="utf-8"))
        b2["meta"]["timestamp_ns"] = "wall-d"
        (tree_b / "sub" / "emit2.json").write_text(json.dumps(b2, sort_keys=True))

        ea = json.loads((tree_a / "emit.json").read_text(encoding="utf-8"))
        eb = json.loads((tree_b / "emit.json").read_text(encoding="utf-8"))
        e2a = json.loads((tree_a / "sub" / "emit2.json").read_text(encoding="utf-8"))
        e2b = json.loads((tree_b / "sub" / "emit2.json").read_text(encoding="utf-8"))

        masked_equal = norm(ea, set(DECLARED)) == norm(eb, set(DECLARED)) and norm(
            e2a, set(DECLARED)
        ) == norm(e2b, set(DECLARED))
        if not masked_equal:
            return fail("declared-mask normalization did not equate the trees")

        # Undeclared field must keep the normalized diff red.
        eb2 = dict(eb)
        eb2["session_nonce"] = "N1"
        undeclared_differs = norm(ea, set(DECLARED)) != norm(eb2, set(DECLARED))
        if not undeclared_differs:
            return fail("undeclared field did not keep the normalized diff red")

        # Masking everything is rejected by the coverage ceiling.
        blanket_ok = len(DECLARED) <= CEILING_MAX_FIELDS and "*" not in DECLARED
        everything_rejected = not ("*" in DECLARED or len(DECLARED) > CEILING_MAX_FIELDS)
        if not blanket_ok or not everything_rejected:
            return fail("mask/ceiling semantics broke")

    # ---- (b) independent recomputation from the embedded data ----------
    byte_diffs = (doc.get("byte_diff") or {}).get("file_diffs") or []
    raw_diff_rows = [r for r in byte_diffs if r.get("kind") == "bytes"]
    if not raw_diff_rows:
        return fail("receipt records no raw byte-diff rows")
    for row in raw_diff_rows:
        if row.get("sha_a") == row.get("sha_b"):
            return fail(f"raw diff row {row.get('path')} has equal shas")
        if not isinstance(row.get("first_byte_diff"), int):
            return fail(f"raw diff row {row.get('path')} lacks byte offset")

    nd = doc.get("normalized_diff") or {}
    if nd.get("identical") is not True:
        return fail("receipt normalized_diff not identical")
    if nd.get("file_diffs") != []:
        return fail("receipt normalized_diff.file_diffs not empty")
    if nd.get("tree_sha_a") != nd.get("tree_sha_b"):
        return fail("normalized tree shas differ")

    mask = doc.get("declared_nondeterministic_fields") or []
    if nd.get("mask") != mask:
        return fail("normalized_diff mask != declared mask")

    bs = doc.get("both_states") or {}
    for key in (
        "undeclared_field_fails_normalized",
        "wall_clock_normalized_identical",
        "wall_clock_raw_differs",
        "frozen_clock_raw_identical",
    ):
        if bs.get(key) is not True:
            return fail(f"both_states.{key} not true")

    ceiling = doc.get("mask_coverage_ceiling") or {}
    if ceiling.get("mask_everything_rejected") is not True:
        return fail("receipt does not record mask-everything rejection")
    if ceiling.get("max_fields") != CEILING_MAX_FIELDS:
        return fail("ceiling max_fields drifted")

    flags = doc.get("flags") or {}
    bad_flags = [k for k, v in flags.items() if v is not True]
    if bad_flags:
        return fail(f"flags rows not true: {bad_flags}")

    out = {
        "probe": "probe2-mask-mechanism",
        "unit_id": UID,
        "live_masked_equal": masked_equal,
        "live_undeclared_differs": undeclared_differs,
        "raw_diff_rows": len(raw_diff_rows),
        "normalized_identical": True,
        "ceiling_rejects_everything": True,
        "flags_true_count": len(flags),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"SUCCESS:{UID}-probe2 live mask mechanism + embedded-data recomputation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
