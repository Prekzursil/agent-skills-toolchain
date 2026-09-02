#!/usr/bin/env python3
"""Probe 1: six-registry three-column matrix + live capture facts.

Different field than probe 2: this probe reads cell booleans and capture
bytes (packument signatures, keys, data-provenance, cksum). Probe 2 recounts
shared_primitive_id groups and scans THIS program's marketplace files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from signals import COLUMNS, REGISTRIES  # noqa: E402

ART = REPO / "command-center/research/RES-0047.json"
CAP = HERE / "captures"
SENTINEL = (
    "SUCCESS:RES-0047 in the receipt AND a six-registry three-column matrix "
    "with a stated count of collapsed shared-primitive signals"
)
NEED_REG = set(REGISTRIES)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0047-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    matrix = doc.get("matrix") or {}
    regs = list(matrix.get("registries") or [])
    if set(regs) != NEED_REG or len(regs) != 6:
        return fail(f"registries={regs}")
    cols = list(matrix.get("columns") or [])
    if cols != COLUMNS:
        return fail(f"columns={cols}")
    signals = list(matrix.get("signals") or [])
    if len(signals) < 6:
        return fail(f"signals={len(signals)}")
    seen_reg = {s.get("registry") for s in signals}
    if seen_reg != NEED_REG:
        return fail(f"signal registries {seen_reg}")
    cells = list(matrix.get("cells") or [])
    want_cells = len(signals) * 3
    if len(cells) != want_cells:
        return fail(f"cells={len(cells)} want={want_cells}")
    for cell in cells:
        if cell.get("column_id") not in COLUMNS:
            return fail(f"bad column {cell}")
        if not isinstance(cell.get("value"), bool):
            return fail(f"non-bool cell {cell}")
    collapsed = (doc.get("collapse") or {}).get("collapsed_shared_primitive_signals")
    if not isinstance(collapsed, int) or collapsed < 1:
        return fail(f"collapse count {collapsed}")
    if doc.get("program_missing_column") != "enforced_at_publish":
        return fail(f"missing-column={doc.get('program_missing_column')}")

    keys = json.loads((CAP / "npm-keys.body").read_text(encoding="utf-8"))
    schemes = {k.get("scheme") for k in keys.get("keys") or []}
    if "ecdsa-sha2-nistp256" not in schemes or len(keys.get("keys") or []) < 1:
        return fail(f"npm keys {schemes}")
    left = json.loads((CAP / "npm-leftpad.body").read_text(encoding="utf-8"))
    sigs = (left.get("dist") or {}).get("signatures") or []
    if not sigs or "keyid" not in sigs[0]:
        return fail("left-pad missing signatures")
    sigstore = json.loads((CAP / "npm-sigstore-packument.body").read_text(encoding="utf-8"))
    att = (sigstore.get("dist") or {}).get("attestations") or {}
    if "provenance" not in att:
        return fail("sigstore packument missing dist.attestations.provenance")
    simple = (CAP / "pypi-simple-requests.body").read_text(encoding="utf-8")
    if "data-provenance=" not in simple or "#sha256=" not in simple:
        return fail("pypi simple missing data-provenance or sha256")
    prov = json.loads((CAP / "pypi-provenance.body").read_text(encoding="utf-8"))
    bundles = prov.get("attestation_bundles") or []
    if not bundles or not (bundles[0].get("attestations") or []):
        return fail("pypi provenance missing attestation_bundles")
    pub = bundles[0].get("publisher") or {}
    if pub.get("kind") != "GitHub" or pub.get("repository") != "psf/requests":
        return fail(f"pypi publisher {pub}")
    idx_text = (CAP / "crates-index-serde.body").read_text(encoding="utf-8")
    last = [ln for ln in idx_text.splitlines() if ln.strip()][-1]
    crate = json.loads(last)
    if crate.get("name") != "serde" or not crate.get("cksum"):
        return fail(f"crates index last {crate.get('name')}")
    tp_docs = CAP / "crates-tp-docs.body"
    if tp_docs.stat().st_size != 0:
        return fail("crates trusted-publishing docs expected 404 empty body")

    print(
        json.dumps(
            {
                "probe": "probe1-matrix",
                "unit_id": "RES-0047",
                "registries": 6,
                "columns": 3,
                "signals": len(signals),
                "cells": len(cells),
                "collapsed_shared_primitive_signals": collapsed,
                "npm_ecdsa_keys": len(keys["keys"]),
                "left_pad_signed": True,
                "sigstore_packument_attestations": True,
                "pypi_simple_data_provenance": True,
                "pypi_integrity_github_publisher": pub.get("repository"),
                "crates_serde_cksum_prefix": str(crate["cksum"])[:16],
                "crates_tp_docs_404_empty": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:RES-0047-probe1 six-registry three-column matrix "
        f"collapsed={collapsed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
