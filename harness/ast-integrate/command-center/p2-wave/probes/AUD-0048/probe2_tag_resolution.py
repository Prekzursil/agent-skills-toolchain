#!/usr/bin/env python3
"""Probe 2: resolve each tag to the SHA git ls-remote sees today.

Independent of probe 1: does not trust pin_class as proof of the blob the tag
points at. A later silent retag is detectable because today's SHA is recorded.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402
from resolve import resolve_use  # noqa: E402
from scan import scan_all  # noqa: E402

ART = REPO / E.OUT_REL
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0048-probe2 {msg}")
    return 1


def main() -> int:
    bundle = scan_all()
    tag_uses = []
    for wf in bundle["fixtures"]:
        for u in wf["uses"]:
            if u.get("pin_class") == "tag-pinned":
                tag_uses.append(u)
    if not tag_uses:
        return fail("no tag-pinned fixture uses to resolve")

    rows = []
    for u in tag_uses:
        got = resolve_use(u)
        rows.append(got)
        print(
            f"{got.get('action')}@{got.get('ref')} ok={got.get('ok')} "
            f"sha={got.get('sha')} attempted={got.get('attempted')}"
        )
        if not got.get("attempted"):
            return fail(f"did not attempt resolve for {u.get('raw')}")
        if not got.get("ok") or not SHA40.match(str(got.get("sha") or "")):
            return fail(f"tag did not resolve to 40-char SHA: {got}")
        if str(got.get("sha")) == str(u.get("ref")):
            return fail("resolved SHA equals the tag string; resolver is a no-op")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel absent from artifact")
    doc = json.loads(text)
    recorded = doc.get("probe2_resolutions") or []
    rec_shas = {str(r.get("sha")) for r in recorded if r.get("sha")}
    live_shas = {str(r.get("sha")) for r in rows}
    if not live_shas <= rec_shas:
        return fail(f"artifact resolutions missing live SHAs {live_shas - rec_shas}")

    print(
        json.dumps(
            {
                "resolved": [
                    {"action": r["action"], "ref": r["ref"], "sha": r["sha"]}
                    for r in rows
                ],
                "independent": "git-ls-remote",
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:AUD-0048-probe2 tag resolved to SHA via git ls-remote")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
