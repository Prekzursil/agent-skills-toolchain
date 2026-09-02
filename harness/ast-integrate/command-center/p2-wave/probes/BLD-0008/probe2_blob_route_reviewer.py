#!/usr/bin/env python3
"""Probe 2: independent reviewer repeats two parser cells on blob-route bytes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from byte_forms import encode_form  # noqa: E402
from fixtures import PAYLOADS  # noqa: E402
from matrix import git_archive_file, git_cat_file, route_control  # noqa: E402
from parsers import parse_json_catalog, parse_register_md  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0008.json"
SENTINEL = "SUCCESS:BLD-0008"
ROUTE_REL = "tools/command-center/validate.py"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0008-probe2 {msg}")
    return 1


def cell_map(doc: dict) -> dict:
    return {c["id"]: c for c in doc.get("cells") or [] if isinstance(c, dict)}


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    raw = ART.read_text(encoding="utf-8")
    if SENTINEL not in raw:
        return fail("sentinel absent")
    doc = json.loads(raw)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    route = route_control()
    print(
        "route",
        json.dumps(
            {
                "cat_ok": route["cat_file"]["ok"],
                "archive_ok": route["archive"]["ok"],
                "windows_claim": route["windows_box_claim_reproduced"],
                "cat_crlf": route["cat_file"]["crlf_count"],
                "archive_crlf": route["archive"]["crlf_count"],
            },
            sort_keys=True,
        ),
    )
    if not route["pass"]:
        return fail("git route control did not record a measurement")
    if route["windows_box_claim_reproduced"] is True:
        print("note archive returned CRLF while cat-file returned LF (Windows-box claim live here)")
    else:
        print("note archive vs cat-file CRLF split NOT reproduced on this Linux tree; blob claims still use cat-file")

    blob = git_cat_file(ROUTE_REL)
    archive = git_archive_file(ROUTE_REL)
    if blob.get("bytes") is None:
        print("note git cat-file unavailable on this tree; reviewer uses synthetic LF as blob-equivalent and does not claim CI blob bytes")
    else:
        if archive.get("ok") and archive.get("bytes") == blob.get("bytes"):
            print("archive_bytes_equal_cat_file=True (expected on LF Linux checkout)")
        elif archive.get("ok"):
            print(
                "archive_bytes_equal_cat_file=False "
                f"archive_n={len(archive['bytes'])} cat_n={len(blob['bytes'])}"
            )

    cells = cell_map(doc)
    json_lf = encode_form(PAYLOADS["json-catalog"], "lf")
    reg_lf = encode_form(PAYLOADS["register-md"], "lf")
    got_json = parse_json_catalog(json_lf)
    got_reg = parse_register_md(reg_lf)
    rec_json = cells.get("json-catalog/lf")
    rec_reg = cells.get("register-md/lf")
    if rec_json is None or rec_reg is None:
        return fail("receipt missing json-catalog/lf or register-md/lf")
    print("reviewer_json", got_json.outcome, "receipt", rec_json.get("outcome"))
    print("reviewer_register", got_reg.outcome, "receipt", rec_reg.get("outcome"))
    if got_json.outcome != rec_json.get("outcome") or got_json.canonical != rec_json.get("canonical"):
        return fail("json-catalog/lf reviewer mismatch")
    if got_reg.outcome != rec_reg.get("outcome") or got_reg.canonical != rec_reg.get("canonical"):
        return fail("register-md/lf reviewer mismatch")

    json_crlf = encode_form(PAYLOADS["json-catalog"], "crlf")
    got_crlf = parse_json_catalog(json_crlf)
    rec_crlf = cells.get("json-catalog/crlf")
    if rec_crlf is None:
        return fail("receipt missing json-catalog/crlf")
    if got_crlf.canonical != rec_crlf.get("canonical"):
        return fail("json-catalog/crlf reviewer mismatch")
    if got_json.canonical != got_crlf.canonical:
        return fail("reviewer json LF vs CRLF canonical mismatch")

    print("SUCCESS:BLD-0008-probe2 blob-route reviewer json+register")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
