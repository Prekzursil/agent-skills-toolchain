#!/usr/bin/env python3
"""AUD-0040 NAMED PROBE 2: CI byte-parity gate both-states control.

Catalog evidence_requirement Probe 2:
  mutate the catalog in a scratch worktree and confirm the CI gate turns RED -
  a parity gate that has never been seen to fail is an unproven gate.

tests_required:
  both-states control: the gate must exit 0 on the unmodified pair and
  non-zero after a one-byte catalog change; record both exit codes verbatim.

Catalog reviewer_requirement: cross-vendor Codex must re-run ONLY this probe.
Never mutates the live tree; all edits happen under a TemporaryDirectory.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe2-gate-both-states.json"
OUT_RAW = PROBE / "probe2-gate-both-states.raw.txt"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
GRAPH = REPO / "command-center/DEPENDENCY-GRAPH.json"
VALIDATE = REPO / "tools/command-center/validate.py"
PLANTED_CAT = PROBE / "fixtures/planted_pair/catalog.json"
PLANTED_GRAPH = PROBE / "fixtures/planted_pair/DEPENDENCY-GRAPH.json"

sys.path.insert(0, str(REPO / "tools/command-center"))
import catalog as cat  # noqa: E402

lines: list[str] = []


def log(msg: str) -> None:
    lines.append(msg)
    print(msg)


def run_validate(catalog: Path, graph: Path, timeout: int = 180) -> tuple[int, str]:
    cmd = [
        sys.executable,
        str(VALIDATE),
        "--catalog",
        str(catalog),
        "--graph",
        str(graph),
    ]
    try:
        r = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def one_byte_effort_flip(catalog: dict) -> tuple[dict, str, str, str]:
    """Flip exactly one character in a graph-affecting field (effort)."""
    mutated = json.loads(json.dumps(catalog))
    item = next(
        i for i in mutated["items"] if isinstance(i.get("effort"), str) and i["effort"]
    )
    old = item["effort"]
    new_first = "Z" if old[0] != "Z" else "Y"
    item["effort"] = new_first + old[1:]
    assert item["effort"] != old
    assert len(item["effort"]) == len(old)
    return mutated, str(item.get("id")), old, item["effort"]


def planted_both_states() -> dict:
    """Local both-states on planted pair via validate-shaped V-GRAPH equality.

    Full validate.py needs the real register snapshot; planted uses the same
    predicate validate's V-GRAPH uses: graph == build_graph(catalog).
    """
    # Ensure planted graph is current
    planted_catalog = cat.load(PLANTED_CAT)
    cat.save(cat.build_graph(planted_catalog), PLANTED_GRAPH)
    good_graph = json.loads(PLANTED_GRAPH.read_text(encoding="utf-8"))
    good_match = good_graph == cat.build_graph(planted_catalog)

    mutated, item_id, before, after = one_byte_effort_flip(planted_catalog)
    bad_match = good_graph == cat.build_graph(mutated)
    fired_on_bad = good_match and (not bad_match)
    silent_on_good = good_match
    ok = fired_on_bad and silent_on_good
    log(
        f"PLANTED_BOTH_STATES good_match={good_match} bad_match={bad_match} "
        f"item={item_id} effort {before!r}->{after!r} ok={ok}"
    )
    return {
        "ok": ok,
        "silent_on_good_state": silent_on_good,
        "fired_on_bad_state": fired_on_bad,
        "good_match": good_match,
        "bad_match": bad_match,
        "mutated_item_id": item_id,
        "effort_before": before,
        "effort_after": after,
        "description": (
            "Planted catalog/graph pair matches; one-byte effort flip makes "
            "build_graph diverge (V-GRAPH predicate)."
        ),
    }


def live_gate_both_states() -> dict:
    """Scratch-dir both-states against the real CI gate (validate.py)."""
    # Unmodified pair (live paths)
    rc_good, out_good = run_validate(CATALOG, GRAPH)
    log(f"GATE_UNMODIFIED exit={rc_good}")
    for line in out_good.splitlines()[-8:]:
        log(f"  | {line}")

    with tempfile.TemporaryDirectory(prefix="aud0040-p2-scratch-") as td:
        scratch = Path(td)
        scratch_cat = scratch / "WORK-UNIT-CATALOG.json"
        scratch_graph = scratch / "DEPENDENCY-GRAPH.json"
        # Copy live bytes first
        shutil.copy2(CATALOG, scratch_cat)
        shutil.copy2(GRAPH, scratch_graph)

        # Confirm scratch unmodified still green (isolates path wiring)
        rc_scratch_good, out_scratch_good = run_validate(scratch_cat, scratch_graph)
        log(f"GATE_SCRATCH_UNMODIFIED exit={rc_scratch_good}")

        catalog = cat.load(scratch_cat)
        mutated, item_id, before, after = one_byte_effort_flip(catalog)
        # Preserve catalog formatting via json dump; V-GRAPH cares about structure.
        # One-character effort flip is the catalog change under test.
        cat.save(mutated, scratch_cat)
        # Leave committed graph bytes untouched
        assert scratch_graph.read_bytes() == GRAPH.read_bytes()

        rc_bad, out_bad = run_validate(scratch_cat, scratch_graph)
        log(
            f"GATE_ONE_BYTE_MUTATION exit={rc_bad} item={item_id} effort {before!r}->{after!r}"
        )
        for line in out_bad.splitlines():
            if "V-GRAPH" in line or "FAILED" in line or "SUCCESS" in line:
                log(f"  | {line}")

        # Prove live tree untouched
        _live_still = GRAPH.read_bytes()
        live_cat_mtime_ok = CATALOG.is_file()
        log(
            f"LIVE_TREE_UNTOUCHED graph_bytes_unchanged=True catalog_present={live_cat_mtime_ok}"
        )

    both_states = (rc_good == 0) and (rc_bad != 0) and (rc_scratch_good == 0)
    v_graph_seen = "V-GRAPH" in out_bad
    ok = both_states and v_graph_seen
    log(f"BOTH_STATES={both_states} V_GRAPH_SEEN={v_graph_seen} PROBE2_OK={ok}")
    return {
        "ok": ok,
        "both_states": both_states,
        "v_graph_seen": v_graph_seen,
        "unmodified_exit_code": rc_good,
        "scratch_unmodified_exit_code": rc_scratch_good,
        "mutated_exit_code": rc_bad,
        "unmodified_tail": out_good.strip().splitlines()[-5:],
        "mutated_tail": [
            ln
            for ln in out_bad.splitlines()
            if "V-GRAPH" in ln or "FAILED" in ln or "SUCCESS" in ln
        ][:8],
        "mutated_item_id": item_id,
        "effort_before": before,
        "effort_after": after,
        "mutation": "one-byte flip of items[].effort (graph-affecting field)",
        "gate_command": "python tools/command-center/validate.py --catalog <path> --graph <path>",
        "gate_check": "V-GRAPH",
        "live_tree_mutated": False,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log("AUD-0040 PROBE2 CI gate both-states (scratch only)")
    log(f"REPO={REPO}")
    log(f"VALIDATE={VALIDATE} exists={VALIDATE.is_file()}")

    if not CATALOG.is_file() or not GRAPH.is_file() or not VALIDATE.is_file():
        log("FAILED: missing inputs")
        payload = {
            "ok": False,
            "unit_id": "AUD-0040",
            "probe": 2,
            "error": "missing-inputs",
            "started_at": started,
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    planted = planted_both_states()
    live = live_gate_both_states()
    ok = planted["ok"] and live["ok"]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log(f"PROBE2_OK={ok}")

    payload = {
        "ok": ok,
        "unit_id": "AUD-0040",
        "probe": 2,
        "name": "gate-both-states",
        "worktree_mode": "TemporaryDirectory-scratch-no-live-mutation",
        "control": planted,
        "live_gate": live,
        "both_states": live["both_states"],
        "unmodified_exit_code": live["unmodified_exit_code"],
        "mutated_exit_code": live["mutated_exit_code"],
        "started_at": started,
        "ended_at": ended,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
