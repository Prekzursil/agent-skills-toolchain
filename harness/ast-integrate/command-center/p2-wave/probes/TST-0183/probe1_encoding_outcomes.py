#!/usr/bin/env python3
"""Probe 1 (signal a): loader outcome per encoding.

Mechanically independent of probe 2: this probe records accept/reject +
detected encoding + logical document equality. It does not hash field UTF-8
bytes and does not run the pre-parse repair mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from plugin.manifest_loader import (  # noqa: E402
    CANONICAL_DESCRIPTION,
    encode_manifest,
    load_manifest_bytes,
    sample_manifest,
)

ART = REPO / "command-center/receipts/TST-0183.json"
ENCODINGS = ("utf-8", "utf-8-sig", "utf-16-le")


def fail(msg: str) -> int:
    print(f"FAILED:TST-0183-probe1 {msg}")
    return 1


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0183" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def naive_utf8_outcome(raw: bytes) -> dict:
    try:
        parsed = json.loads(raw.decode("utf-8"))
        return {"status": "accepted", "name": parsed.get("name")}
    except UnicodeDecodeError as exc:
        return {"status": "rejected", "error": f"UnicodeDecodeError:{exc.reason}"}
    except json.JSONDecodeError as exc:
        return {"status": "rejected", "error": f"JSONDecodeError:{exc.msg}"}


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        return fail(art_err)

    doc = sample_manifest()
    utf8_raw = encode_manifest(doc, "utf-8")
    baseline = load_manifest_bytes(utf8_raw)
    if baseline.document != doc:
        return fail("plain UTF-8 did not round-trip the fixture document")
    if baseline.document["description"] != CANONICAL_DESCRIPTION:
        return fail("plain UTF-8 description drifted")
    if baseline.encoding != "utf-8" or baseline.policy != "accept-and-normalize":
        return fail(f"plain UTF-8 encoding/policy {baseline.encoding}/{baseline.policy}")

    outcomes = []
    for enc in ENCODINGS:
        raw = encode_manifest(doc, enc)
        result = load_manifest_bytes(raw)
        if result.policy != "accept-and-normalize":
            return fail(f"{enc} policy {result.policy}")
        if result.document != baseline.document:
            return fail(f"{enc} document != utf-8 baseline")
        if result.document["description"] != CANONICAL_DESCRIPTION:
            return fail(f"{enc} description mojibake")
        naive = naive_utf8_outcome(raw)
        outcomes.append(
            {
                "encoding": enc,
                "detected": result.encoding,
                "policy": result.policy,
                "accepted": True,
                "bom": result.bom,
                "source_bytes": result.source_bytes,
                "naive_utf8": naive,
            }
        )

    # Both-states: naive stdlib utf-8 path must NOT accept BOM / UTF-16LE,
    # proving the declared policy is load-bearing (not "json.loads always works").
    if outcomes[0]["naive_utf8"]["status"] != "accepted":
        return fail("naive utf-8 rejected plain UTF-8 (control is broken)")
    if outcomes[1]["naive_utf8"]["status"] != "rejected":
        return fail("naive utf-8 accepted UTF-8-with-BOM; contrast is not red")
    if outcomes[2]["naive_utf8"]["status"] != "rejected":
        return fail("naive utf-8 accepted UTF-16LE; contrast is not red")

    payload = {
        "baseline_encoding": "utf-8",
        "declared_policy": "accept-and-normalize",
        "identical_to_utf8": True,
        "outcomes": outcomes,
        "pass": True,
        "probe": "probe1-encoding-outcomes",
        "unit_id": "TST-0183",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "utf8=accept bom=accept utf16le=accept "
        f"naive_contrast_red=True policy={baseline.policy}"
    )
    print("SUCCESS:TST-0183-probe1 loader outcomes identical across encodings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
