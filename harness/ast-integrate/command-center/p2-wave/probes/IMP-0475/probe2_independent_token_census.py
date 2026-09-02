#!/usr/bin/env python3
"""Named probe 2: independent token census vs AST scanner, plus receipt anchors.

Mechanically different from probe 1: tokenize NAME tokens in package source
(comments and strings are not NAME tokens) and reconstruct which declared
permissions have an API token. Concordance with the AST scanner is required.
Every exercised-permission anchor must be a real file:line containing the API.
"""
from __future__ import annotations

import io
import json
import sys
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.marketplace.permission_scan import (  # noqa: E402
    DEFAULT_MARKETPLACE,
    PERM_ENV,
    PERM_FS_READ,
    PERM_FS_WRITE,
    PERM_NET,
    PERM_SECRETS,
    PERM_SUBPROCESS,
    load_manifest,
    scan_marketplace,
)

ART = REPO / "command-center/receipts/IMP-0475.json"
SENTINEL = "SENTINEL:IMP-0475:PERMISSIONS-SCANNED"

TOKEN_TO_PERM = {
    "read_text": PERM_FS_READ,
    "read_bytes": PERM_FS_READ,
    "write_text": PERM_FS_WRITE,
    "write_bytes": PERM_FS_WRITE,
    "urlopen": PERM_NET,
    "urlretrieve": PERM_NET,
    "HTTPConnection": PERM_NET,
    "HTTPSConnection": PERM_NET,
    "subprocess": PERM_SUBPROCESS,
    "Popen": PERM_SUBPROCESS,
    "environ": PERM_ENV,
    "getenv": PERM_ENV,
}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0475-probe2 {msg}")
    return 1


def name_tokens(source: str) -> set[str]:
    names: set[str] = set()
    try:
        for tok in tokenize.tokenize(io.BytesIO(source.encode("utf-8")).readline):
            if tok.type == tokenize.NAME:
                names.add(tok.string)
    except tokenize.TokenError:
        return names
    return names


def independent_exercised(package_dir: Path) -> set[str]:
    found: set[str] = set()
    for py in sorted(package_dir.rglob("*.py")):
        if "__pycache__" in py.parts or py.name.startswith("test_"):
            continue
        source = py.read_text(encoding="utf-8")
        names = name_tokens(source)
        if "open" in names:
            found.add(PERM_FS_READ)
        for token, perm in TOKEN_TO_PERM.items():
            if token in names:
                found.add(perm)
        if any(marker in source for marker in ("API_KEY", "SECRET_TOKEN", "PASSWORD")):
            if "environ" in names or "getenv" in names:
                found.add(PERM_SECRETS)
    return found


def main() -> int:
    scan = scan_marketplace()
    rows = []
    for pkg in scan["packages"]:
        root = Path(pkg["package_dir"])
        declared = set(load_manifest(root).get("permissions") or [])
        token_exercised = independent_exercised(root)
        token_unexercised = sorted(declared - token_exercised)
        ast_unexercised = list(pkg["unexercised"])
        if token_unexercised != ast_unexercised:
            return fail(
                f"{pkg['package_id']} token unexercised {token_unexercised} "
                f"!= ast {ast_unexercised}"
            )
        if token_exercised != set(pkg["exercised"]):
            return fail(
                f"{pkg['package_id']} token exercised {sorted(token_exercised)} "
                f"!= ast {pkg['exercised']}"
            )
        for anchor in pkg["anchors"]:
            path = root / anchor["relpath"]
            lines = path.read_text(encoding="utf-8").splitlines()
            if not (1 <= anchor["line"] <= len(lines)):
                return fail(f"anchor line out of range {anchor}")
            line = lines[anchor["line"] - 1]
            token = anchor["qualified"].rsplit(".", 1)[-1]
            if token not in line:
                return fail(f"anchor token {token!r} missing from {line!r}")
        rows.append(
            {
                "package_id": pkg["package_id"],
                "declared": sorted(declared),
                "token_exercised": sorted(token_exercised),
                "token_unexercised": token_unexercised,
                "flagged": pkg["flagged"],
            }
        )

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    table = (
        doc.get("declared_versus_exercised")
        or report.get("declared_versus_exercised")
        or []
    )
    if len(table) < 2:
        return fail("receipt table too small")
    live_pairs = {
        (p["package_id"], row["permission"], row["finding"])
        for p in scan["packages"]
        for row in p["table"]
    }
    receipt_pairs = {
        (row["package_id"], row["permission"], row["finding"]) for row in table
    }
    if live_pairs != receipt_pairs:
        return fail("receipt table drifted from live scan")

    payload = {
        "probe": "probe2-independent-token-census",
        "unit_id": "IMP-0475",
        "pass": True,
        "instrument": "tokenize.NAME",
        "rows": rows,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("token_census_agrees_with_ast=True anchors_on_disk=True receipt_table_matches=True")
    print("SUCCESS:IMP-0475-probe2 independent token census agrees with AST scanner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
