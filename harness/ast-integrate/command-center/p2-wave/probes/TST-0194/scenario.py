#!/usr/bin/env python3
"""Live measurement for TST-0194: case-only duplicates fail at BUILD.

Signal (a): subprocess exit status and stderr of tools/plugin/pack.py
Signal (b): independent NFC+casefold set-size over the manifest `files` list
            (does not import pack.collision_groups).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PACK = REPO / "tools" / "plugin" / "pack.py"
MUTANT = HERE / "install_time_packer.py"
WORK = HERE / "_work"
ART = REPO / "command-center" / "receipts" / "TST-0194.json"

PACK_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0194/probe1_packer_exit_and_setsize.py"
)
PROBE2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0194/probe2_both_states_and_install_deferral.py"
)


def posix_rel(path: str) -> str:
    text = str(path).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def independent_nfc_casefold(path: str) -> str:
    """Probe-local fold. Must not call tools.plugin.pack."""
    return unicodedata.normalize("NFC", posix_rel(path)).casefold()


def independent_set_size(paths: list[str]) -> dict:
    raw = [posix_rel(p) for p in paths if posix_rel(p)]
    folded = {independent_nfc_casefold(p) for p in raw}
    lowered = {posix_rel(p).lower() for p in raw}
    return {
        "paths": raw,
        "raw_count": len(raw),
        "folded_count": len(folded),
        "lower_count": len(lowered),
        "collision": len(folded) < len(raw),
        "lower_misses_casefold": len(folded) < len(lowered),
    }


def load_manifest_files(fixture: str) -> list[str]:
    data = json.loads(
        (HERE / "fixtures" / fixture / "manifest.json").read_text(encoding="utf-8")
    )
    return [posix_rel(str(x)) for x in (data.get("files") or [])]


def run_proc(args: list[str]) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(
        args,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {
        "rc": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "text": text,
        "argv": [str(a) for a in args],
    }


def pack_fixture(fixture: str) -> dict:
    staging = HERE / "fixtures" / fixture
    manifest = staging / "manifest.json"
    output = WORK / f"{fixture}.zip"
    WORK.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    result = run_proc(
        [
            sys.executable,
            "-B",
            str(PACK),
            "--staging",
            str(staging),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ]
    )
    result["fixture"] = fixture
    result["output"] = str(output.relative_to(REPO).as_posix()) if output.exists() else None
    result["output_exists"] = output.is_file()
    return result


def mutant_pack_fixture(fixture: str) -> dict:
    staging = HERE / "fixtures" / fixture
    manifest = staging / "manifest.json"
    output = WORK / f"{fixture}.mutant.zip"
    WORK.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    result = run_proc(
        [
            sys.executable,
            "-B",
            str(MUTANT),
            "--staging",
            str(staging),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ]
    )
    result["fixture"] = fixture
    result["output_exists"] = output.is_file()
    result["zip_names"] = []
    if output.is_file():
        with zipfile.ZipFile(output) as zf:
            result["zip_names"] = zf.namelist()
    return result


def names_both(text: str, a: str, b: str) -> bool:
    return a in text and b in text


def evaluate() -> dict:
    colliding_paths = load_manifest_files("colliding")
    declared_paths = load_manifest_files("declared-only")
    clean_paths = load_manifest_files("clean")
    eszett_paths = load_manifest_files("casefold-not-lower")

    sig_b_colliding = independent_set_size(colliding_paths)
    sig_b_declared = independent_set_size(declared_paths)
    sig_b_clean = independent_set_size(clean_paths)
    sig_b_eszett = independent_set_size(eszett_paths)

    pack_colliding = pack_fixture("colliding")
    pack_declared = pack_fixture("declared-only")
    pack_clean = pack_fixture("clean")
    pack_eszett = pack_fixture("casefold-not-lower")
    mutant = mutant_pack_fixture("colliding")

    colliding_text = pack_colliding["text"]
    declared_text = pack_declared["text"]
    eszett_text = pack_eszett["text"]

    both_named_colliding = names_both(colliding_text, "README.md", "readme.md")
    both_named_declared = names_both(declared_text, "README.md", "readme.md")
    both_named_eszett = names_both(eszett_text, "Straße.md", "STRASSE.md")

    # PASS criterion: build fails with both paths named.
    colliding_build_rejected = pack_colliding["rc"] == 2 and both_named_colliding
    declared_build_rejected = pack_declared["rc"] == 2 and both_named_declared
    eszett_build_rejected = pack_eszett["rc"] == 2 and both_named_eszett
    clean_builds = pack_clean["rc"] == 0 and pack_clean["output_exists"] is True

    # Negative control: install-time packer emits an archive (exit 0) for the
    # colliding manifest. Applying TST-0194's PASS rule to that mutant is FAIL.
    mutant_built = mutant["rc"] == 0 and mutant["output_exists"] is True
    mutant_named_collision_at_build = "CASEFOLD-COLLISION" in mutant["text"]
    test_applied_to_mutant = (
        "FAIL"
        if mutant_built and not mutant_named_collision_at_build
        else "UNEXPECTED-PASS"
    )
    negative_control_fired = test_applied_to_mutant == "FAIL"

    signals_agree = (
        colliding_build_rejected
        and sig_b_colliding["collision"] is True
        and declared_build_rejected
        and sig_b_declared["collision"] is True
        and eszett_build_rejected
        and sig_b_eszett["collision"] is True
        and sig_b_eszett["lower_misses_casefold"] is True
        and sig_b_clean["collision"] is False
        and clean_builds
    )

    pack_src = PACK.read_text(encoding="utf-8") if PACK.is_file() else ""
    fold_is_casefold = "def nfc_casefold" in pack_src and ".casefold(" in pack_src
    fold_uses_nfc = 'normalize("NFC"' in pack_src
    passed = (
        signals_agree
        and negative_control_fired
        and PACK.is_file()
        and fold_is_casefold
        and fold_uses_nfc
    )

    return {
        "pass": passed,
        "pack_script": "tools/plugin/pack.py",
        "pack_exists": PACK.is_file(),
        "signal_a": {
            "colliding": {
                "rc": pack_colliding["rc"],
                "both_paths_named": both_named_colliding,
                "text_tail": colliding_text[-800:],
                "output_exists": pack_colliding["output_exists"],
            },
            "declared_only": {
                "rc": pack_declared["rc"],
                "both_paths_named": both_named_declared,
                "text_tail": declared_text[-800:],
                "output_exists": pack_declared["output_exists"],
            },
            "eszett": {
                "rc": pack_eszett["rc"],
                "both_paths_named": both_named_eszett,
                "text_tail": eszett_text[-800:],
                "output_exists": pack_eszett["output_exists"],
            },
            "clean": {
                "rc": pack_clean["rc"],
                "output_exists": pack_clean["output_exists"],
                "text_tail": pack_clean["text"][-400:],
            },
        },
        "signal_b": {
            "colliding": sig_b_colliding,
            "declared_only": sig_b_declared,
            "eszett": sig_b_eszett,
            "clean": sig_b_clean,
        },
        "both_states": {
            "clean_manifest_builds": clean_builds,
            "clean_paths": clean_paths,
        },
        "negative_control": {
            "id": "TST-0194-NC-INSTALL-TIME-DEFERRAL",
            "mutant": "command-center/p2-wave/probes/TST-0194/install_time_packer.py",
            "mutant_build_rc": mutant["rc"],
            "mutant_built_archive": mutant_built,
            "mutant_named_collision_at_build": mutant_named_collision_at_build,
            "test_applied_to_mutant": test_applied_to_mutant,
            "fired_on_bad_state": negative_control_fired,
            "silent_on_good_state": colliding_build_rejected,
            "zip_names": mutant.get("zip_names") or [],
        },
        "gates": {
            "colliding_build_rejected": colliding_build_rejected,
            "declared_build_rejected": declared_build_rejected,
            "eszett_build_rejected": eszett_build_rejected,
            "eszett_proves_casefold_not_lower": sig_b_eszett["lower_misses_casefold"],
            "clean_builds": clean_builds,
            "signals_agree": signals_agree,
            "negative_control_fired": negative_control_fired,
        },
    }


def artifact_ok(doc: dict) -> list[str]:
    errors: list[str] = []
    if doc.get("unit_id") != "TST-0194":
        errors.append(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if "SUCCESS:TST-0194" not in text:
        errors.append("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errors.append(f"self-declared:{st}")
    if str(doc.get("report_kind") or "") != "portability_report":
        errors.append("report_kind")
    if str(doc.get("overall_verdict") or "") != "PASS":
        errors.append("overall_verdict")
    return errors
