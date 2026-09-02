#!/usr/bin/env python3
"""Named probe 2: untransformable records are quarantined and reported.

Feed records the transform cannot handle. Assert each is quarantined with
original bytes and a reason, never silently dropped. Both-states: a valid
schema_version=1 object is TRANSFORMED, not quarantined.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from transform import (  # noqa: E402
    QUARANTINED,
    TRANSFORMED,
    apply_bytes,
    apply_obj,
    process_many,
    sha256_bytes,
)

ART = REPO / "command-center/phase4/contracts/ARC-0093.json"
SENTINEL = "SUCCESS:ARC-0093"

GOOD = {
    "schema_version": 1,
    "id": "arc-0093-probe2-good",
    "kind": "fixture",
}


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:ARC-0093-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:3000])
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("contract artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel-absent")
    policy = ((doc.get("x-arc-0093") or {}).get("executed_record") or {}).get(
        "untransformable_policy"
    ) or {}
    if policy.get("action") != "QUARANTINE" or policy.get("silent_drop") is not False:
        return fail("contract untransformable_policy drifted", policy)

    cases: list[tuple[str, bytes, str]] = [
        ("not-object.json", b"[1, 2, 3]\n", "not-an-object"),
        ("missing-version.json", b'{"id": "no-version"}\n', "schema_version-absent"),
        (
            "wrong-version.json",
            b'{"schema_version": 99, "id": "future"}\n',
            "schema_version-mismatch",
        ),
        ("unparseable.json", b"{this is not json", "unparseable:"),
        ("binary.bin", b"\xff\xfe\x00\x01not-utf8", "unparseable:"),
        (
            "add-collision.json",
            json.dumps(
                {"schema_version": 1, "format_family": "already-here"},
                sort_keys=True,
            ).encode("utf-8"),
            "transform-failed:add-exists:format_family",
        ),
    ]

    batch_inputs = [(name, raw) for name, raw, _prefix in cases]
    batch = process_many(batch_inputs, dry_run=True)
    if batch["would_drop"] != 0 or not batch["accounting_holds"]:
        return fail("silent drop or accounting break on untransformable batch", batch)
    if batch["would_transform"] != 0:
        return fail("untransformable batch produced TRANSFORMED rows", batch)
    if batch["would_quarantine"] != len(cases):
        return fail(
            f"quarantine count {batch['would_quarantine']} want={len(cases)}",
            batch,
        )

    for name, raw, prefix in cases:
        out = apply_bytes(raw, path=name)
        if out.status != QUARANTINED:
            return fail(f"{name} status={out.status} want=QUARANTINED", out.as_dict())
        if not (out.reason or "").startswith(prefix) and prefix not in (out.reason or ""):
            return fail(f"{name} reason {out.reason!r} want prefix {prefix!r}")
        if out.quarantine_raw is None:
            return fail(f"{name} quarantine_raw missing (would be a drop)")
        if out.quarantine_raw != raw:
            return fail(f"{name} quarantine bytes mutated")
        if out.report.get("silent_drop") is not False:
            return fail(f"{name} report silent_drop not false")
        if out.report.get("original_sha256") != sha256_bytes(raw):
            return fail(f"{name} report sha mismatch")
        if out.report.get("action") != "QUARANTINE":
            return fail(f"{name} report action")

    good = apply_obj(GOOD, path="good.json")
    if good.status != TRANSFORMED:
        return fail("both-states: good record was not TRANSFORMED", good.as_dict())
    if good.quarantine_raw is not None:
        return fail("both-states: good record was quarantined")

    mixed = process_many(
        [
            ("good.json", json.dumps(GOOD).encode("utf-8")),
            ("bad.json", b"not-json"),
        ],
        dry_run=True,
    )
    if mixed["records_in"] != 2:
        return fail("mixed records_in", mixed)
    if mixed["would_transform"] != 1 or mixed["would_quarantine"] != 1:
        return fail("mixed both-states counts", mixed)
    if mixed["would_drop"] != 0 or not mixed["accounting_holds"]:
        return fail("mixed accounting", mixed)

    result = {
        "probe": "probe2-quarantine",
        "unit_id": "ARC-0093",
        "untransformable": len(cases),
        "all_quarantined": True,
        "bytes_preserved": True,
        "silent_drop": False,
        "good_transformed": True,
        "accounting_holds": True,
        "pass": True,
    }
    print(json.dumps(result, sort_keys=True))
    print(
        f"quarantined={len(cases)} good_transformed=True "
        f"drop={batch['would_drop']} mixed_t={mixed['would_transform']}/"
        f"q={mixed['would_quarantine']}"
    )
    print("SUCCESS:ARC-0093-probe2 untransformable records quarantined not dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
