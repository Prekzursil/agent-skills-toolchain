#!/usr/bin/env python3
"""Named probe 1: planted canary fires; clean extracted bundle is silent.

Both states in one run. Scan surface is an extracted payload directory,
not the repository. Values are never printed.
"""
from __future__ import annotations

import json
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.release.bundle_secret_scan import (  # noqa: E402
    CANARY_VARIABLE,
    SCANNER_VERSION,
    ensure_clean_bundle,
    pack_layer_tar,
    plant_canary,
    scan_extracted,
)

ART = REPO / "command-center/receipts/REL-0010.json"
CLEAN = HERE / "fixtures" / "clean-bundle"


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:REL-0010-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "REL-0010":
        return _fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:REL-0010" not in text:
        return _fail("sentinel-absent")

    ensure_clean_bundle(CLEAN)
    clean = scan_extracted(CLEAN)
    if not clean.completed:
        return _fail("clean scan tooling-error", clean.to_dict())
    if clean.findings:
        return _fail("clean bundle produced findings", [f.to_dict() for f in clean.findings])
    if clean.files_examined < 1:
        return _fail("clean examined-file count is zero")
    if clean.exit_code != 0:
        return _fail("clean scan exit was not 0", clean.to_dict())
    skip_suffixes = {s.suffix for s in clean.skipped}
    if ".png" not in skip_suffixes:
        return _fail("png skip not reported", [s.__dict__ for s in clean.skipped])

    canary_value = secrets.token_urlsafe(32)
    outside_value = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="rel0010-probe1-") as tmp:
        tmp_path = Path(tmp)
        planted = tmp_path / "extracted"
        shutil.copytree(CLEAN, planted)
        plant_canary(planted, canary_value)
        outside = tmp_path / "not-the-bundle" / "leak.env"
        outside.parent.mkdir(parents=True)
        outside.write_text(f"{CANARY_VARIABLE}={outside_value}\n", encoding="utf-8")
        canary = scan_extracted(planted)
        if not canary.completed:
            return _fail("canary scan tooling-error", canary.to_dict())
        hits = [f for f in canary.findings if f.variable_name == CANARY_VARIABLE]
        if not hits:
            return _fail("planted canary was not detected", canary.to_dict())
        hit = hits[0]
        if hit.byte_length != len(canary_value.encode("utf-8")):
            return _fail("canary byte_length mismatch", hit.to_dict())
        if hit.authenticates is not False:
            return _fail("synthetic canary must not authenticate", hit.to_dict())
        if "value" in hit.to_dict() or canary_value in json.dumps(hit.to_dict()):
            return _fail("finding leaked the canary value")
        if canary.exit_code != 2:
            return _fail("findings scan must exit 2", canary.to_dict())
        if outside_value in json.dumps(canary.to_dict()):
            return _fail("outside-repo canary value appeared in scan report")
        if any(outside_value in (f.containing_path + f.variable_name) for f in canary.findings):
            return _fail("scan walked outside extracted root")

        layer_src = tmp_path / "layer-src"
        shutil.copytree(planted, layer_src)
        layer_tar = tmp_path / "canary-layer.tar"
        pack_layer_tar(layer_src, layer_tar)
        layer = scan_extracted(CLEAN, layer_tars=[layer_tar])
        if not layer.completed:
            return _fail("layer scan tooling-error", layer.to_dict())
        layer_hits = [f for f in layer.findings if f.variable_name == CANARY_VARIABLE]
        if not layer_hits:
            return _fail("layer canary was not detected", layer.to_dict())
        if canary_value in json.dumps(layer.to_dict()) or outside_value in json.dumps(layer.to_dict()):
            return _fail("layer report leaked a canary value")

    stored_examined = (
        doc.get("evidence", {}).get("clean_bundle", {}).get("files_examined")
    )
    if stored_examined != clean.files_examined:
        return _fail(
            "receipt clean files_examined drifted from live scan",
            {"stored": stored_examined, "live": clean.files_examined},
        )
    stored_version = doc.get("scanner", {}).get("version")
    if stored_version != SCANNER_VERSION:
        return _fail("scanner version drifted", {"stored": stored_version, "live": SCANNER_VERSION})
    if canary_value in text or outside_value in text:
        return _fail("receipt contains a probe-generated canary body")

    payload = {
        "pass": True,
        "probe": "probe1-detector-and-clean",
        "unit_id": "REL-0010",
        "clean_files_examined": clean.files_examined,
        "clean_findings": 0,
        "skipped_suffixes": sorted(skip_suffixes),
        "canary_fired": True,
        "canary_variable_name": CANARY_VARIABLE,
        "canary_authenticates": False,
        "layer_canary_fired": True,
        "outside_root_ignored": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"clean_examined={clean.files_examined} clean_findings=0 "
        f"canary_fired=True layer_fired=True"
    )
    print("SUCCESS:REL-0010-probe1 detector control and clean bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
