#!/usr/bin/env python3
"""Probe 1: widening update HALTS, names each added permission, dest unchanged.

Evidence signal (a): installer halt status + rendered diff.
Evidence signal (b): installed effective permission set afterward is unchanged.
Regression seed: marketplace package with malicious/excessive permissions.
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
    print(f"FAILED:{S.UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0214-p1-") as tmp:
        root = Path(tmp)
        dest = root / "dest"
        v1 = S.write_payload(
            root, version="1.0.0", permissions=S.BASE_PERMS, note="installed baseline"
        )
        v2 = S.write_payload(
            root,
            version="1.1.0",
            permissions=S.WIDE_PERMS,
            note="malicious or excessive permissions",
        )
        first = S.install(v1, dest)
        if first["result"]["permission_gate"]["verdict"] != "first-install":
            return fail("first install was gated")
        before_census = S.census_tree(dest)
        before_perms = S.live_permissions(dest)
        if before_perms != S.BASE_PERMS:
            return fail(f"baseline perms {before_perms}")

        try:
            S.install(v2, dest)
            return fail("widening update installed instead of halting")
        except S.PermissionWideningBlocked as exc:
            halt = exc
        if halt.status != "blocked" or halt.halt is not True or halt.warn:
            return fail(f"not a halt: status={halt.status} warn={halt.warn}")
        for name in ("net:connect", "spawn:python"):
            if name not in halt.added:
                return fail(f"diff omitted added {name}: {halt.added}")
            if name not in halt.rendered_diff:
                return fail(f"rendered diff omitted {name}")
            if name not in str(halt):
                return fail(f"exception text omitted {name}")
        after_census = S.census_tree(dest)
        after_perms = S.live_permissions(dest)
        if after_census != before_census:
            return fail("dest census changed after halted widening")
        if after_perms != before_perms:
            return fail(f"effective permissions changed: {after_perms}")
        independent = S.independent_set_verdict(before_perms, S.WIDE_PERMS)
        if independent != "widen":
            return fail(f"independent set check {independent}")
        lattice = S.decide(before_perms, S.WIDE_PERMS)
        if lattice.verdict != "widen" or not lattice.methods_agree:
            return fail("lattice/raw disagreement on explicit widening")

        payload = {
            "probe": "probe1-widen-halts",
            "unit_id": S.UNIT,
            "halt": True,
            "warn": False,
            "status": halt.status,
            "added": list(halt.added),
            "rendered_diff": halt.rendered_diff,
            "effective_permissions_after": after_perms,
            "census_unchanged": True,
            "independent_verdict": independent,
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True))

    if not S.ART.is_file():
        return fail("receipt missing")
    text = S.ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if S.SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    halt_ev = (doc.get("evidence") or [{}])[0]
    if halt_ev.get("halt") is not True:
        return fail("receipt did not record halt")
    named = halt_ev.get("named_added_permissions") or []
    if "net:connect" not in named or "spawn:python" not in named:
        return fail(f"receipt diff names {named}")

    print(
        "halt=True warn=False added=net:connect,spawn:python "
        "effective_permissions_unchanged=True"
    )
    print(
        "SUCCESS:TST-0214-probe1 widening update HALTED with named diff; "
        "installed permissions unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
