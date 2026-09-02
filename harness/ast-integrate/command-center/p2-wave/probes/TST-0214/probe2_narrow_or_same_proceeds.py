#!/usr/bin/env python3
"""Probe 2: identical or narrower permission sets install without a prompt.

Mechanically different from probe 1: this probe requires the update to
COMMIT and then reads the dest plugin.json permission set (not the
exception object). Reordering is not widening. An independent raw
set-containment check must agree.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{S.UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0214-p2-") as tmp:
        root = Path(tmp)
        dest = root / "dest"
        wide = S.write_payload(
            root,
            version="2.0.0",
            permissions=S.WIDE_PERMS,
            note="already-approved wide set",
        )
        reordered = S.write_payload(
            root,
            version="2.0.1",
            permissions=S.REORDERED_PERMS,
            note="same set, different order",
        )
        narrow = S.write_payload(
            root,
            version="2.0.2",
            permissions=S.NARROW_PERMS,
            note="narrower permission set",
        )
        S.install(wide, dest)
        if S.live_permissions(dest) != sorted(S.WIDE_PERMS):
            # dest stores the list as declared; compare as sets
            if set(S.live_permissions(dest)) != set(S.WIDE_PERMS):
                return fail(f"wide install perms {S.live_permissions(dest)}")

        same = S.install(reordered, dest)
        gate_same = same["result"]["permission_gate"]
        if gate_same.get("verdict") != "unchanged":
            return fail(f"reorder verdict {gate_same}")
        if gate_same.get("halt") is True:
            return fail("reorder halted")
        if S.live_version(dest) != "2.0.1":
            return fail(f"reorder did not commit version={S.live_version(dest)}")
        if set(S.live_permissions(dest)) != set(S.REORDERED_PERMS):
            return fail(f"reorder perms {S.live_permissions(dest)}")
        if S.independent_set_verdict(S.WIDE_PERMS, S.REORDERED_PERMS) != "unchanged":
            return fail("independent reorder verdict")

        narrowed = S.install(narrow, dest)
        gate_n = narrowed["result"]["permission_gate"]
        if gate_n.get("verdict") != "narrow":
            return fail(f"narrow verdict {gate_n}")
        if gate_n.get("halt") is True:
            return fail("narrow halted")
        if S.live_version(dest) != "2.0.2":
            return fail(f"narrow did not commit version={S.live_version(dest)}")
        if S.live_permissions(dest) != S.NARROW_PERMS:
            return fail(f"narrow perms {S.live_permissions(dest)}")
        if S.independent_set_verdict(S.WIDE_PERMS, S.NARROW_PERMS) != "narrow":
            return fail("independent narrow verdict")

        payload = {
            "probe": "probe2-narrow-or-same-proceeds",
            "unit_id": S.UNIT,
            "reorder": {
                "verdict": gate_same.get("verdict"),
                "halt": gate_same.get("halt"),
                "version": S.live_version(dest),
            },
            "narrow": {
                "verdict": gate_n.get("verdict"),
                "halt": gate_n.get("halt"),
                "effective_permissions": S.live_permissions(dest),
            },
            "pass": True,
        }
        # version after narrow is 2.0.2; record reorder version from gate path
        payload["reorder"]["version"] = "2.0.1"
        print(json.dumps(payload, sort_keys=True))

    if not S.ART.is_file():
        return fail("receipt missing")
    text = S.ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if S.SENTINEL not in text:
        return fail("sentinel absent")
    both = doc.get("both_states") or {}
    if both.get("identical_or_reordered_proceeds") is not True:
        return fail("receipt missing identical proceeds")
    if both.get("narrower_proceeds") is not True:
        return fail("receipt missing narrower proceeds")
    if both.get("widening_halts") is not True:
        return fail("receipt missing widening halt")

    print(
        "reorder_unchanged=True narrow_proceeds=True "
        f"effective_permissions={S.NARROW_PERMS}"
    )
    print(
        "SUCCESS:TST-0214-probe2 identical-or-narrower installs without a prompt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
