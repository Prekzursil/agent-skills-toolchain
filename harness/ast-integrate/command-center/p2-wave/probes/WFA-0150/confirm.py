"""Confirm or downgrade each declared conflict_map row by co-execution."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from session import co_execute_both_orders, static_intersect  # noqa: E402

MAP_PATH = HERE / "fixtures" / "conflict_map.json"
BP_PATH = HERE / "fixtures" / "blueprints.json"


def load_map() -> dict[str, Any]:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def load_blueprints() -> dict[str, dict[str, Any]]:
    doc = json.loads(BP_PATH.read_text(encoding="utf-8"))
    return {w["id"]: w for w in doc["workflows"]}


def declared_kind_observed(row: dict[str, Any], live: dict[str, Any], static: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """A row is confirmed only when the DECLARED kind is observed live.

    Static intersection is the independent second signal; it must agree.
    """
    kind = row["declared_kind"]
    target = row["declared_target"]
    obs: dict[str, Any] = {"kind": kind, "target": target}
    if kind == "SHARED_FILE":
        live_hit = target in live["shared_files"]
        static_hit = target in static["shared_files"]
        obs["live_shared_files"] = live["shared_files"]
        obs["static_shared_files"] = static["shared_files"]
        obs["live_hit"] = live_hit
        obs["static_hit"] = static_hit
        return live_hit and static_hit, obs
    if kind == "SHARED_PLANE":
        live_hit = target in live["shared_planes"]
        static_hit = target in static["shared_planes"]
        obs["live_shared_planes"] = live["shared_planes"]
        obs["static_shared_planes"] = static["shared_planes"]
        obs["live_hit"] = live_hit
        obs["static_hit"] = static_hit
        return live_hit and static_hit, obs
    if kind == "INCOMPATIBLE_STOP":
        live_hit = bool(live["stop_disagree"])
        static_hit = bool(static["stop_disagree"])
        declared_ids = set(target.split("|"))
        actual_ids = {live["stop_left"]["id"], live["stop_right"]["id"]}
        # Declared pair must be the rules that actually ran.
        pair_match = declared_ids == actual_ids
        obs["live_stop"] = [live["stop_left"], live["stop_right"]]
        obs["static_stop"] = [static["stop_left"], static["stop_right"]]
        obs["pair_match"] = pair_match
        obs["live_hit"] = live_hit
        obs["static_hit"] = static_hit
        return live_hit and static_hit and pair_match, obs
    raise KeyError(kind)


def confirm_row(row: dict[str, Any], bps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    left = bps[row["left"]]
    right = bps[row["right"]]
    live = co_execute_both_orders(left, right)
    static = static_intersect(left, right)
    matched, obs = declared_kind_observed(row, live, static)
    if matched:
        verdict = "CONFIRMED"
        reason = (
            f"co-execution observed {row['declared_kind']} at {row['declared_target']}"
        )
    else:
        verdict = "SUSPECTED"
        reason = (
            f"declared {row['declared_kind']} at {row['declared_target']} did not "
            "reproduce under co-execution; row downgraded, not deleted"
        )
    return {
        "id": row["id"],
        "left": row["left"],
        "right": row["right"],
        "declared_kind": row["declared_kind"],
        "declared_target": row["declared_target"],
        "verdict": verdict,
        "reason": reason,
        "downgraded_not_deleted": verdict == "SUSPECTED",
        "observed": obs,
        "live": {
            "shared_files": live["shared_files"],
            "shared_planes": live["shared_planes"],
            "stop_disagree": live["stop_disagree"],
            "ab_writers": live["ab"]["writers"],
            "ba_writers": live["ba"]["writers"],
        },
        "static": static,
        "signals_agree": obs.get("live_hit") == obs.get("static_hit"),
    }


def negative_control(cmap: dict[str, Any], bps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nc = cmap["negative_control"]
    live = co_execute_both_orders(bps[nc["left"]], bps[nc["right"]])
    static = static_intersect(bps[nc["left"]], bps[nc["right"]])
    clean = (
        not live["shared_files"]
        and not live["shared_planes"]
        and not live["stop_disagree"]
        and not static["shared_files"]
        and not static["shared_planes"]
        and not static["stop_disagree"]
    )
    return {
        "id": nc["id"],
        "left": nc["left"],
        "right": nc["right"],
        "verdict": "CLEAN" if clean else "COLLIDED",
        "live": {
            "shared_files": live["shared_files"],
            "shared_planes": live["shared_planes"],
            "stop_disagree": live["stop_disagree"],
        },
        "static": static,
    }


def run_all() -> dict[str, Any]:
    cmap = load_map()
    bps = load_blueprints()
    rows_in = cmap["rows"]
    results = [confirm_row(r, bps) for r in rows_in]
    ids = [r["id"] for r in results]
    confirmed = [r for r in results if r["verdict"] == "CONFIRMED"]
    suspected = [r for r in results if r["verdict"] == "SUSPECTED"]
    deleted = [rid for rid in (x["id"] for x in rows_in) if rid not in ids]
    nc = negative_control(cmap, bps)
    pos = next(r for r in results if r["id"] == "CF-01")
    return {
        "declared_count": len(rows_in),
        "result_count": len(results),
        "confirmed_count": len(confirmed),
        "suspected_count": len(suspected),
        "deleted_count": len(deleted),
        "deleted_ids": deleted,
        "rows": results,
        "negative_control": nc,
        "positive_control": {
            "id": pos["id"],
            "verdict": pos["verdict"],
            "kind": pos["declared_kind"],
            "target": pos["declared_target"],
        },
        "source": {
            "conflict_map": str(MAP_PATH.relative_to(HERE.parents[3])),
            "blueprints": str(BP_PATH.relative_to(HERE.parents[3])),
            "declaring_file_on_this_worktree": cmap["declaring_file_on_this_worktree"],
            "reconstruction": cmap["source"],
        },
    }


def predicates(bundle: dict[str, Any]) -> list[str]:
    bad: list[str] = []
    if bundle["declared_count"] != 20:
        bad.append(f"declared_count={bundle['declared_count']}")
    if bundle["result_count"] != 20:
        bad.append(f"result_count={bundle['result_count']}")
    if bundle["deleted_count"] != 0:
        bad.append(f"deleted={bundle['deleted_ids']}")
    if bundle["confirmed_count"] < 1:
        bad.append("no CONFIRMED row")
    if bundle["suspected_count"] < 1:
        bad.append("no SUSPECTED row")
    if bundle["negative_control"]["verdict"] != "CLEAN":
        bad.append("negative control collided")
    if bundle["positive_control"]["verdict"] != "CONFIRMED":
        bad.append("positive control CF-01 not CONFIRMED")
    for row in bundle["rows"]:
        if not row.get("signals_agree"):
            bad.append(f"{row['id']} live/static disagree")
        if row["verdict"] not in {"CONFIRMED", "SUSPECTED"}:
            bad.append(f"{row['id']} verdict={row['verdict']}")
    return bad


if __name__ == "__main__":
    doc = run_all()
    bad = predicates(doc)
    print(
        f"declared={doc['declared_count']} confirmed={doc['confirmed_count']} "
        f"suspected={doc['suspected_count']} deleted={doc['deleted_count']} "
        f"neg={doc['negative_control']['verdict']} pos={doc['positive_control']['verdict']}"
    )
    if bad:
        print("FAILED:WFA-0150-confirm " + "; ".join(bad))
        raise SystemExit(1)
    print("SUCCESS:WFA-0150-confirm")
