#!/usr/bin/env python3
"""Probe 1: timed edit-then-query. Editing a description changes the next answer.

Also asserts mtime-only invalidation (touch without byte change) forces a rebuild,
and that an unedited sibling capability keeps its answer (negative control).
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    GLOSS_STABLE,
    PAINT_AFTER,
    PAINT_BEFORE,
    QUERY_BLUE,
    QUERY_GLOSS,
    QUERY_RED,
    build_capability_tree,
    edit_paint_description,
)
from tools.router.index_cache import fingerprint_tree, load_or_rebuild  # noqa: E402
from tools.router.query import route_next  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0402.json"
SENTINEL = "SENTINEL:IMP-0402:INDEX-INVALIDATION-SAFE"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0402-probe1 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "receipt sentinel absent"
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable:{exc}"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"receipt self-declared:{st}"
    return None


def main() -> int:
    receipt_err = check_receipt()
    if receipt_err:
        return fail(receipt_err)

    trace: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="imp0402-p1-") as tmp:
        root = Path(tmp) / "caps"
        cache = Path(tmp) / "router-cache" / "capability-index.json"
        files = build_capability_tree(root)
        roots = [root]

        t0 = time.time_ns()
        a0 = route_next(QUERY_RED, cache_path=cache, roots=roots)
        t0_done = time.time_ns()
        trace.append(
            {
                "step": "initial-red",
                "t_unix_ns": t0,
                "elapsed_ns": t0_done - t0,
                "query": QUERY_RED,
                "verdict": a0["verdict"],
                "capability_id": a0["capability_id"],
                "answer": a0["answer"],
                "cache_action": a0["cache_action"],
                "content_hash": a0["content_hash"],
            }
        )
        if a0["verdict"] != "SELECTED" or a0["capability_id"] != "paint":
            return fail(f"initial red did not select paint: {a0}")
        if PAINT_BEFORE not in (a0["answer"] or ""):
            return fail("initial answer missing RED-PIGMENT description")
        if a0["cache_action"] != "rebuilt":
            return fail(f"first call should rebuild missing cache, got {a0['cache_action']}")

        t_ctrl = time.time_ns()
        gloss0 = route_next(QUERY_GLOSS, cache_path=cache, roots=roots)
        trace.append(
            {
                "step": "control-gloss-before-edit",
                "t_unix_ns": t_ctrl,
                "query": QUERY_GLOSS,
                "verdict": gloss0["verdict"],
                "answer": gloss0["answer"],
                "cache_action": gloss0["cache_action"],
            }
        )
        if gloss0["verdict"] != "SELECTED" or gloss0["capability_id"] != "gloss":
            return fail(f"gloss control failed before edit: {gloss0}")
        if gloss0["cache_action"] != "cache-hit":
            return fail(f"unchanged tree should cache-hit, got {gloss0['cache_action']}")
        if GLOSS_STABLE not in (gloss0["answer"] or ""):
            return fail("gloss answer missing GLOSS-COAT")

        fp_before = fingerprint_tree(roots)
        t_edit = time.time_ns()
        edit_paint_description(files["paint"], PAINT_AFTER)
        fp_after = fingerprint_tree(roots)
        if fp_after.content_hash == fp_before.content_hash:
            return fail("content hash did not change after description edit")
        if fp_after.mtime_token == fp_before.mtime_token:
            return fail("mtime token did not change after description edit")

        t1 = time.time_ns()
        a1_red = route_next(QUERY_RED, cache_path=cache, roots=roots)
        t1_done = time.time_ns()
        trace.append(
            {
                "step": "post-edit-red",
                "t_unix_ns": t1,
                "elapsed_ns": t1_done - t1,
                "edit_unix_ns": t_edit,
                "query": QUERY_RED,
                "verdict": a1_red["verdict"],
                "capability_id": a1_red["capability_id"],
                "answer": a1_red["answer"],
                "cache_action": a1_red["cache_action"],
                "cache_reason": a1_red["cache_reason"],
                "content_hash": a1_red["content_hash"],
            }
        )
        if a1_red["answer"] == a0["answer"]:
            return fail("post-edit red query returned the stale answer")
        if PAINT_BEFORE in (a1_red["answer"] or ""):
            return fail("stale RED-PIGMENT description survived the next call")
        if a1_red["cache_action"] != "rebuilt":
            return fail(
                f"edit must invalidate cache on the next call, got {a1_red['cache_action']}"
            )
        if a1_red["cache_reason"] != "stale-hash":
            return fail(f"expected stale-hash, got {a1_red['cache_reason']}")

        t2 = time.time_ns()
        a2_blue = route_next(QUERY_BLUE, cache_path=cache, roots=roots)
        t2_done = time.time_ns()
        trace.append(
            {
                "step": "post-edit-blue",
                "t_unix_ns": t2,
                "elapsed_ns": t2_done - t2,
                "query": QUERY_BLUE,
                "verdict": a2_blue["verdict"],
                "capability_id": a2_blue["capability_id"],
                "answer": a2_blue["answer"],
                "cache_action": a2_blue["cache_action"],
            }
        )
        if a2_blue["verdict"] != "SELECTED" or a2_blue["capability_id"] != "paint":
            return fail(f"BLUE-PIGMENT did not select paint after edit: {a2_blue}")
        if PAINT_AFTER not in (a2_blue["answer"] or ""):
            return fail("post-edit answer missing BLUE-PIGMENT description")
        if a2_blue["cache_action"] != "cache-hit":
            return fail("second post-edit call should cache-hit")

        gloss1 = route_next(QUERY_GLOSS, cache_path=cache, roots=roots)
        if gloss1["answer"] != gloss0["answer"]:
            return fail("unedited gloss answer changed (negative control failed)")
        if GLOSS_STABLE not in (gloss1["answer"] or ""):
            return fail("gloss control lost GLOSS-COAT")

        hit = load_or_rebuild(cache, roots)
        if hit.action != "cache-hit":
            return fail(f"pre-touch expected cache-hit, got {hit.action}")
        paint = files["paint"]
        st = paint.stat()
        paint.touch()
        if paint.stat().st_mtime_ns == st.st_mtime_ns:
            # Some filesystems have 1s mtime granularity; nudge ns via utime.
            os_utime = __import__("os").utime
            os_utime(paint, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        touched = load_or_rebuild(cache, roots)
        trace.append(
            {
                "step": "mtime-only-touch",
                "t_unix_ns": time.time_ns(),
                "cache_action": touched.action,
                "cache_reason": touched.reason,
                "content_hash_unchanged": touched.fingerprint.content_hash
                == hit.fingerprint.content_hash,
            }
        )
        if touched.action != "rebuilt":
            return fail(f"mtime-only change must rebuild, got {touched.action}")
        if touched.reason != "stale-mtime":
            return fail(f"expected stale-mtime, got {touched.reason}")
        if touched.fingerprint.content_hash != hit.fingerprint.content_hash:
            return fail("touch changed content hash (bytes should be identical)")

    summary = {
        "probe": "probe1-edit-then-query",
        "unit_id": "IMP-0402",
        "pass": True,
        "answer_changed_on_next_call": True,
        "stale_description_absent": True,
        "mtime_only_rebuild": True,
        "unedited_sibling_stable": True,
        "trace": trace,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0402-probe1 edit-then-query answer changed on next call")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
