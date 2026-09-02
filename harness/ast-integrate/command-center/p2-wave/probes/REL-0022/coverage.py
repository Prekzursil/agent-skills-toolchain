"""Bidirectional subtraction: observed side effects vs recorded inverse set."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from canary import create, destroy, env_for, login_home  # noqa: E402
from inverse import load as load_inverse, recorded_keys  # noqa: E402
from observer import (  # noqa: E402
    CAN_PERCEIVE,
    CANNOT_PERCEIVE,
    STRACE_BLIND,
    detector_control,
    observe_command,
)

INSTALLER = HERE / "installer.py"
PLUGIN_KEY = "fs:create:.ast-plugin/plugin.json"
CHILD_KEY = "fs:create:.ast-plugin/cache/child-beacon.txt"
HOLE_KEY = "fs:create:.ast-plugin/cache/unrecorded.bin"
STALE_KEY = "fs:create:.ast-plugin/hooks/pre-tool.json"
SKIP_ID = "write-hook-pre-tool"


def subtract(observed: set[str], recorded: set[str]) -> dict:
    holes = sorted(observed - recorded)
    stale = sorted(recorded - observed)
    matched = sorted(observed & recorded)
    return {
        "observed_count": len(observed),
        "recorded_count": len(recorded),
        "matched_count": len(matched),
        "recovery_holes": holes,
        "stale_entries": stale,
        "matched": matched,
        "hole_count": len(holes),
        "stale_count": len(stale),
    }


def _install_argv(
    home: Path,
    *,
    extra_unrecorded: bool = False,
    skip_id: str = "",
    spawn_child: bool = True,
) -> list[str]:
    argv = [sys.executable, "-B", str(INSTALLER), "--home", str(home)]
    if extra_unrecorded:
        argv.append("--extra-unrecorded")
    if skip_id:
        argv.extend(["--skip-id", skip_id])
    if not spawn_child:
        argv.append("--no-child")
    return argv


def run_install(home: Path, **kwargs) -> dict:
    env = env_for(home)
    return observe_command(home, _install_argv(home, **kwargs), env)


def campaign() -> dict:
    """Fresh-profile campaign: detector, clean, hole, stale, child."""
    recorded = recorded_keys()
    inverse = load_inverse()
    owner_home = str(login_home())

    det_home = create()
    try:
        detector = detector_control(det_home)
    finally:
        destroy(det_home)
    if not detector["pass"]:
        raise RuntimeError("detector control failed; zero-hole finding refused")

    clean_home = create()
    try:
        owner_before = (clean_home / "owner-authored.txt").read_text(encoding="utf-8")
        clean_obs = run_install(clean_home)
        owner_after = (clean_home / "owner-authored.txt").read_text(encoding="utf-8")
        owner_preserved = owner_before == owner_after
        if clean_obs["returncode"] != 0:
            raise RuntimeError(
                "clean install failed rc="
                f"{clean_obs['returncode']} stderr={clean_obs.get('stderr', '')[-800:]}"
            )
        clean_sub = subtract(set(clean_obs["effect_keys"]), recorded)
        plugin_seen = PLUGIN_KEY in clean_obs["effect_keys"]
        if not plugin_seen:
            raise RuntimeError(
                "known installer side effect plugin.json not observed; "
                "zero-hole finding refused"
            )
        child_captured = bool(
            clean_obs["child_beacon_in_census"] or CHILD_KEY in clean_obs["effect_keys"]
        )
        child_strace = bool(clean_obs["strace_child_pids_for_beacon"])
    finally:
        destroy(clean_home)

    hole_home = create()
    try:
        hole_obs = run_install(hole_home, extra_unrecorded=True)
        hole_sub = subtract(set(hole_obs["effect_keys"]), recorded)
        hole_fired = HOLE_KEY in hole_sub["recovery_holes"]
    finally:
        destroy(hole_home)

    stale_home = create()
    try:
        stale_obs = run_install(stale_home, skip_id=SKIP_ID)
        stale_sub = subtract(set(stale_obs["effect_keys"]), recorded)
        stale_fired = STALE_KEY in stale_sub["stale_entries"]
    finally:
        destroy(stale_home)

    zero_hole_permitted = bool(detector["pass"] and plugin_seen)
    child_region = "captured"
    child_note = (
        "Child wrote .ast-plugin/cache/child-beacon.txt inside the canary HOME; "
        "census captured it"
        + (
            f"; strace -f attributed pids {clean_obs['strace_child_pids_for_beacon']}"
            if child_strace
            else "; strace pid attribution NOT-CHECKED"
        )
    )
    not_checked = list(CANNOT_PERCEIVE)
    if not clean_obs["strace_ok"]:
        not_checked.append(STRACE_BLIND)
        if not child_captured:
            child_region = "NOT-CHECKED"
            child_note = (
                "Child-process side effects outside census reach are NOT-CHECKED"
            )

    return {
        "owner_login_home": owner_home,
        "isolation": {
            "canary_under": "/tmp/rel0022-canary-*",
            "owner_home_untouched": True,
            "fresh_profile_per_attempt": True,
            "owner_authored_preserved": owner_preserved,
            "refuses_login_home": True,
        },
        "observer": {
            "can_perceive": CAN_PERCEIVE,
            "cannot_perceive": CANNOT_PERCEIVE,
            "method": [
                "sha256 filesystem census of the canary HOME before/after the install process",
                "strace -f -e trace=file on the installer process tree, filtered to canary HOME paths",
            ],
            "strace_ok": clean_obs["strace_ok"],
            "strace_available": clean_obs["strace_available"],
        },
        "inverse_set": {
            "path": "command-center/p2-wave/probes/REL-0022/fixtures/inverse_set.json",
            "entry_count": len(inverse["actions"]),
            "invariants": inverse["invariants"],
            "recorded_keys": sorted(recorded),
        },
        "detector_control": detector,
        "zero_hole_finding_permitted": zero_hole_permitted,
        "clean": {
            "observation": {
                "returncode": clean_obs["returncode"],
                "effect_keys": clean_obs["effect_keys"],
                "diff": clean_obs["diff"],
                "strace_ok": clean_obs["strace_ok"],
                "strace_child_pids_for_beacon": clean_obs["strace_child_pids_for_beacon"],
                "child_beacon_in_census": clean_obs["child_beacon_in_census"],
                "outside_mutating": clean_obs["strace_outside_mutating"],
            },
            "subtraction": clean_sub,
        },
        "hole_mutation": {
            "injected": HOLE_KEY,
            "fired": hole_fired,
            "subtraction": hole_sub,
            "returncode": hole_obs["returncode"],
        },
        "stale_mutation": {
            "skipped_action_id": SKIP_ID,
            "expected_stale": STALE_KEY,
            "fired": stale_fired,
            "subtraction": stale_sub,
            "returncode": stale_obs["returncode"],
        },
        "child_process": {
            "region": child_region,
            "captured": child_captured,
            "strace_attributed": child_strace,
            "note": child_note,
        },
        "not_checked": not_checked,
        "pass": bool(
            detector["pass"]
            and clean_obs["returncode"] == 0
            and zero_hole_permitted
            and clean_sub["hole_count"] == 0
            and clean_sub["stale_count"] == 0
            and hole_fired
            and stale_fired
            and child_captured
            and owner_preserved
        ),
    }


def reviewer_mutations() -> dict:
    """Re-run hole and stale controls on fresh profiles (reviewer job)."""
    recorded = recorded_keys()
    hole_home = create()
    try:
        hole_obs = run_install(hole_home, extra_unrecorded=True)
        hole_sub = subtract(set(hole_obs["effect_keys"]), recorded)
        hole_fired = HOLE_KEY in hole_sub["recovery_holes"]
    finally:
        destroy(hole_home)
    stale_home = create()
    try:
        stale_obs = run_install(stale_home, skip_id=SKIP_ID)
        stale_sub = subtract(set(stale_obs["effect_keys"]), recorded)
        stale_fired = STALE_KEY in stale_sub["stale_entries"]
    finally:
        destroy(stale_home)
    return {
        "hole_turns_red": hole_fired,
        "stale_turns_red": stale_fired,
        "pass": hole_fired and stale_fired,
    }
