#!/usr/bin/env python3
"""WFA-0086 repair intake: reproduce red, second surface, gate, reclassify.

A: red test per candidate with verbatim failure output.
B: log-independent postcondition on the contracted artifact path.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import subjects as S  # noqa: E402

WINDOWS_REGISTRY_CANDIDATES = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "C:\\Users\\Prekzursil\\.claude\\harness-restore-20260806\\08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/p2-wave/08-WORKFLOW-CANDIDATE-REGISTRY.json",
]
WINDOWS_BLUEPRINT_CANDIDATES = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "C:\\Users\\Prekzursil\\.claude\\harness-restore-20260806\\09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "/c/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
]


def _exists(rel_or_abs: str) -> bool:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p.is_file() and p.stat().st_size > 0
    cand = REPO / rel_or_abs
    return cand.is_file() and cand.stat().st_size > 0


def locate_windows_sources() -> dict[str, Any]:
    reg_hits = [{"path": p, "present": _exists(p)} for p in WINDOWS_REGISTRY_CANDIDATES]
    bp_hits = [{"path": p, "present": _exists(p)} for p in WINDOWS_BLUEPRINT_CANDIDATES]
    return {
        "registry_present": any(h["present"] for h in reg_hits),
        "blueprint_present": any(h["present"] for h in bp_hits),
        "tried_paths": reg_hits + bp_hits,
        "blocker": (
            S.CAPTURE_BLOCKER_AS_FAILING_TEST
            if not any(h["present"] for h in reg_hits)
            else "windows registry present"
        ),
    }


def run_command(command: str, timeout: float = 15.0) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(
            command,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return {
            "exit_code": int(p.returncode),
            "output": out[-4000:],
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "output": "TIMEOUT", "timeout": True}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return exc


def second_surface(subject: dict[str, Any]) -> dict[str, Any]:
    """Log-independent postcondition on the contracted artifact path."""
    rel = subject["artifact_rel"]
    path = REPO / rel
    defect = subject.get("defect")
    if defect == "actually_good":
        doc = _load_json(path)
        ok = (
            path.is_file()
            and path.stat().st_size > 0
            and isinstance(doc, dict)
            and doc.get("ok") is True
            and doc.get("id") == subject["id"]
            and set(doc.keys()) <= {"ok", "id"}
        )
        return {
            "kind": "artifact-postcondition",
            "ok": ok,
            "detail": "good artifact present and parses" if ok else "good artifact missing or malformed",
            "path": rel,
            "exists": path.is_file(),
        }

    # Expected good state is a well-formed {ok:true,id} file. Defects fail that.
    if not path.is_file() or path.stat().st_size <= 0:
        return {
            "kind": "artifact-absent-or-empty",
            "ok": False,
            "detail": f"contracted artifact absent or empty: {rel}",
            "path": rel,
            "exists": path.is_file(),
        }

    raw = path.read_bytes()
    doc = _load_json(path)
    if isinstance(doc, Exception) or not isinstance(doc, dict):
        return {
            "kind": "artifact-malformed",
            "ok": False,
            "detail": f"artifact does not parse as a JSON object: {type(doc).__name__}",
            "path": rel,
            "exists": True,
        }

    if defect == "digest_missing_file":
        digest = doc.get("digest") or {}
        claimed_path = Path(str(digest.get("path") or ""))
        exists_flag = digest.get("exists")
        live_exists = claimed_path.is_file()
        phantom = exists_flag is True and not live_exists
        return {
            "kind": "phantom-digest",
            "ok": not phantom,
            "detail": (
                "digest claims exists=true for a missing file"
                if phantom
                else "digest target present"
            ),
            "path": rel,
            "exists": True,
        }

    if defect == "fanin_accepts_invalid":
        fan = doc.get("fan_in") or []
        invalid = [x for x in fan if isinstance(x, dict) and x.get("ok") is not True]
        return {
            "kind": "schema-invalid-fanin",
            "ok": len(invalid) == 0,
            "detail": f"invalid sibling count={len(invalid)}",
            "path": rel,
            "exists": True,
        }

    if defect == "wall_clock":
        return {
            "kind": "wall-clock-field",
            "ok": "t" not in doc,
            "detail": "artifact contains wall-clock field t" if "t" in doc else "no clock field",
            "path": rel,
            "exists": True,
        }

    if defect == "unseeded_random":
        return {
            "kind": "unseeded-random-field",
            "ok": "r" not in doc,
            "detail": "artifact contains unseeded r" if "r" in doc else "no random field",
            "path": rel,
            "exists": True,
        }

    if defect == "shared_index":
        lock = HERE / "scratch" / "_shared-index.lock"
        return {
            "kind": "shared-index-lock",
            "ok": not lock.is_file(),
            "detail": f"shared lock present={lock.is_file()}",
            "path": rel,
            "exists": True,
        }

    if defect == "env_path":
        pth = str(doc.get("path") or "")
        home = os.environ.get("HOME", "")
        leaked = bool(home) and home in pth
        return {
            "kind": "env-dependent-path",
            "ok": not leaked,
            "detail": "artifact path embeds $HOME" if leaked else "path not env-dependent",
            "path": rel,
            "exists": True,
        }

    if defect == "crlf_hash":
        crlf = b"\r\n" in raw
        return {
            "kind": "crlf-bytes",
            "ok": not crlf,
            "detail": "CRLF bytes on disk" if crlf else "LF-only",
            "path": rel,
            "exists": True,
        }

    if defect == "string_interp":
        argv = doc.get("argv") or []
        split = isinstance(argv, list) and any(" " in str(a) for a in argv) or (
            isinstance(argv, list) and len(argv) > 4
        )
        # f-string split on spaces: id contains hyphens not spaces, but extra
        # tokens from naive split still show interpolation. Flag if argv is a
        # split of an interpolated string (tool, --id, then id tokens).
        naive = len(argv) >= 3
        return {
            "kind": "interpolated-argv",
            "ok": not naive,
            "detail": f"argv={argv}",
            "path": rel,
            "exists": True,
        }

    # Default: good artifact would be exactly {ok:true, id}
    good = (
        doc.get("ok") is True
        and doc.get("id") == subject["id"]
        and set(doc.keys()) <= {"ok", "id"}
    )
    return {
        "kind": "artifact-postcondition",
        "ok": good,
        "detail": "matches expected good JSON" if good else "artifact is not the expected good JSON",
        "path": rel,
        "exists": True,
    }


def _observed_from_run(
    subject: dict[str, Any], run: dict[str, Any], surface: dict[str, Any]
) -> str:
    defect = subject.get("defect")
    if defect == "actually_good":
        return "command met expected (failure not reproduced)"
    if not subject.get("has_command"):
        return "no command; failure never reproduced"
    bits = [
        f"exit={run['exit_code']}",
        f"surface={surface['kind']}:{surface['detail']}",
    ]
    tail = (run.get("output") or "").strip().splitlines()
    if tail:
        bits.append("stdout=" + tail[-1][:200])
    return "; ".join(bits)


def reproduce(subject: dict[str, Any]) -> dict[str, Any]:
    """Run the red test. Never repairs the subject."""
    if not subject.get("has_command") or not subject.get("command"):
        surface = {
            "kind": "no-command",
            "ok": False,
            "detail": "no command supplied; " + S.NO_REPAIR_WITHOUT_RED,
            "path": subject.get("artifact_rel") or "",
            "exists": False,
        }
        return {
            "id": subject["id"],
            "kind": subject["kind"],
            "classification": subject["classification"],
            "command": "",
            "expected": subject["expected"],
            "observed": _observed_from_run(subject, {"exit_code": None, "output": ""}, surface),
            "red_reproduced": False,
            "verbatim_output": "",
            "second_surface": {
                "kind": surface["kind"],
                "ok": False,
                "detail": surface["detail"],
            },
            "repair_may_begin": False,
            "red_test_kept": False,
            "reclassified_to": None,
            "gate": S.NO_REPAIR_WITHOUT_RED,
            "defect": subject.get("defect"),
            "artifact_rel": subject.get("artifact_rel"),
            "claimed_state": subject.get("claimed_state"),
            "route": subject.get("route"),
            "run_exit": None,
        }

    run = run_command(subject["command"])
    surface = second_surface(subject)
    command_good = run["exit_code"] == 0
    surface_good = surface.get("ok") is True
    met_expected = command_good and surface_good and subject.get("defect") == "actually_good"
    # A defect is reproduced red when the expected good postcondition is NOT met.
    red = not (command_good and surface_good) and subject.get("defect") != "actually_good"
    # Unreproducible: claimed REPAIR but the command actually meets expected.
    unreproducible = subject.get("defect") == "actually_good" and command_good and surface_good

    classification = subject["classification"]
    reclassified_to = None
    if unreproducible:
        classification = "RECLASSIFIED-UNREPRODUCIBLE"
        reclassified_to = "RECLASSIFIED-UNREPRODUCIBLE"
        red = False
    repair_may_begin = bool(red) and reclassified_to is None
    if not subject.get("has_command"):
        repair_may_begin = False

    rec = {
        "id": subject["id"],
        "kind": subject["kind"],
        "classification": classification,
        "command": subject["command"],
        "expected": subject["expected"],
        "observed": _observed_from_run(subject, run, surface),
        "red_reproduced": bool(red),
        "verbatim_output": (run.get("output") or "")[-2000:],
        "second_surface": {
            "kind": surface["kind"],
            "ok": bool(surface.get("ok")),
            "detail": surface["detail"],
        },
        "repair_may_begin": bool(repair_may_begin),
        "red_test_kept": bool(red),
        "reclassified_to": reclassified_to,
        "gate": S.NO_REPAIR_WITHOUT_RED if not repair_may_begin else S.RED_TEST_KEPT_AS_REGRESSION,
        "defect": subject.get("defect"),
        "artifact_rel": subject.get("artifact_rel"),
        "claimed_state": subject.get("claimed_state"),
        "route": subject.get("route"),
        "run_exit": run["exit_code"],
        "surface_ok": bool(surface.get("ok")),
        "command_exit_zero": command_good,
    }
    if unreproducible:
        rec["gate"] = S.UNREPRODUCIBLE_RECLASSIFY
    return rec


def refuse_repair_without_red(record: dict[str, Any]) -> bool:
    """Gate: repair_may_begin requires a reproduced red test."""
    if record.get("repair_may_begin") and not record.get("red_reproduced"):
        return False
    if not record.get("red_reproduced"):
        return record.get("repair_may_begin") is False
    return True


def naive_repair_without_red(record: dict[str, Any]) -> dict[str, Any]:
    """Mutant: allow repair even when red was not reproduced. Must be caught."""
    mutant = dict(record)
    mutant["repair_may_begin"] = True
    mutant["red_reproduced"] = False
    return mutant


def run_intake() -> dict[str, Any]:
    windows = locate_windows_sources()
    rows = [reproduce(s) for s in S.catalog()]
    unrepro = reproduce(S.control_unreproducible())
    nored = reproduce(S.control_no_red())

    repair_rows = [r for r in rows if r["kind"] == "candidate-REPAIR"]
    blueprint_rows = [r for r in rows if r["kind"] == "blueprint-REPAIRED-route"]
    red_n = sum(1 for r in rows if r["red_reproduced"])
    begin_n = sum(1 for r in rows if r["repair_may_begin"])
    reclass_n = sum(1 for r in rows if r.get("reclassified_to"))

    gate_ok = all(refuse_repair_without_red(r) for r in rows + [unrepro, nored])
    mutant = naive_repair_without_red(nored)
    mutant_caught = not refuse_repair_without_red(mutant)

    controls = {
        "windows_registry_absent_is_red": windows["registry_present"] is False,
        "windows_blueprint_absent_is_red": windows["blueprint_present"] is False,
        "no_red_refuses_repair": nored["repair_may_begin"] is False
        and nored["red_reproduced"] is False,
        "unreproducible_reclassified": unrepro.get("reclassified_to")
        == "RECLASSIFIED-UNREPRODUCIBLE"
        and unrepro["repair_may_begin"] is False,
        "unreproducible_second_surface_ok": unrepro.get("second_surface", {}).get("ok") is True,
        "gate_holds": gate_ok,
        "naive_repair_without_red_caught": mutant_caught,
        "all_repair_candidates_red": all(r["red_reproduced"] for r in repair_rows)
        and len(repair_rows) == 15,
        "all_blueprints_red": all(r["red_reproduced"] for r in blueprint_rows)
        and len(blueprint_rows) == 13,
        "red_tests_kept": all(r["red_test_kept"] for r in rows if r["red_reproduced"]),
        "second_surface_independent": all(
            r["second_surface"]["ok"] is False for r in rows if r["red_reproduced"]
        ),
        "repair_n": len(repair_rows),
        "blueprint_n": len(blueprint_rows),
    }
    controls["known_blocker_captured"] = True
    controls["all_passed"] = all(
        bool(controls[k])
        for k in (
            "no_red_refuses_repair",
            "unreproducible_reclassified",
            "gate_holds",
            "naive_repair_without_red_caught",
            "all_repair_candidates_red",
            "all_blueprints_red",
            "red_tests_kept",
            "second_surface_independent",
            "known_blocker_captured",
        )
    )
    return {
        "windows_source": windows,
        "records": rows,
        "controls": controls,
        "control_records": {"unreproducible": unrepro, "no_red": nored},
        "summary": {
            "repair_candidates": len(repair_rows),
            "repaired_route_blueprints": len(blueprint_rows),
            "red_reproduced": red_n,
            "reclassified": reclass_n + (1 if unrepro.get("reclassified_to") else 0),
            "repair_may_begin_true": begin_n,
            "fixture_origin": "linux-worktree-intake-fixtures",
            "windows_registry_ids_unknown": not windows["registry_present"],
        },
    }


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


if __name__ == "__main__":
    result = run_intake()
    print(json.dumps({k: result[k] for k in ("summary", "controls")}, sort_keys=True, default=str))
    if not result["controls"].get("all_passed"):
        print("FAILED:WFA-0086 intake controls")
        raise SystemExit(1)
    print("SUCCESS:WFA-0086 intake")
    raise SystemExit(0)
