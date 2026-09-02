"""Executable turn schedules and pre-lift identity-leak detection for CNL-0041."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROTOCOLS_PATH = HERE / "fixtures" / "protocols.json"

SEAT_IDS = ["A", "B", "C", "D", "E", "F"]

DEFAULT_SEATS = [
    {
        "seat_id": sid,
        "token": f"tok-{sid}",
        "style_marker": f"sty{sid}-qx7",
        "tool_run_id": f"tool-{sid}-1",
        "delay_ms": 10 + i,
    }
    for i, sid in enumerate(SEAT_IDS)
]


def load_protocols(path: Path | None = None) -> list[dict]:
    doc = json.loads((path or PROTOCOLS_PATH).read_text(encoding="utf-8"))
    return list(doc.get("protocols") or [])


def protocol_by_id(pid: str, protocols: list[dict] | None = None) -> dict:
    for p in protocols or load_protocols():
        if p.get("id") == pid:
            return p
    raise KeyError(pid)


def _token_map(seats: list[dict]) -> dict[str, dict]:
    return {s["token"]: s for s in seats}


def _style_map(seats: list[dict]) -> dict[str, str]:
    return {s["style_marker"]: s["seat_id"] for s in seats}


def _tool_map(seats: list[dict]) -> dict[str, str]:
    return {s["tool_run_id"]: s["seat_id"] for s in seats}


def _values_for(pid: str, round_idx: int, n: int) -> list[float]:
    base = {
        "P20": [10.0, 12.0, 11.0, 10.0, 13.0, 12.0],
        "P21": [20.0, 22.0, 21.0, 19.0, 23.0, 21.0],
    }
    row = list(base.get(pid, [float(i + 1) for i in range(n)]))
    if round_idx > 0:
        row = [v + 0.2 * round_idx for v in row]
    return row[:n]


def _event(etype: str, public: dict, private: dict | None = None, round_idx: int = 0) -> dict:
    return {
        "type": etype,
        "round": round_idx,
        "public": public,
        "private": private or {},
    }


def _median_iqr(values: list[float]) -> tuple[float, float]:
    med = float(statistics.median(values))
    if len(values) < 2:
        return med, 0.0
    qs = statistics.quantiles(values, n=4, method="inclusive")
    return med, float(qs[2] - qs[0])


def _surprisingly_popular(ballots: list[dict]) -> dict:
    votes = [b["vote"] for b in ballots]
    n = len(votes) or 1
    actual_a = votes.count("A") / n
    actual_b = 1.0 - actual_a
    mean_pred_a = sum(b["pred_a"] for b in ballots) / n
    mean_pred_b = 1.0 - mean_pred_a
    score_a = actual_a - mean_pred_a
    score_b = actual_b - mean_pred_b
    winner = "A" if score_a >= score_b else "B"
    return {
        "actual_a": actual_a,
        "actual_b": actual_b,
        "mean_pred_a": mean_pred_a,
        "score_a": score_a,
        "score_b": score_b,
        "winner": winner,
    }


def run_protocol(protocol: dict, seats: list[dict] | None = None, knobs: dict | None = None) -> dict:
    """Execute the named schedule. knobs plant leaks without changing the schedule shape."""
    seats = seats or DEFAULT_SEATS
    knobs = knobs or {}
    pid = protocol["id"]
    n = len(seats)
    events: list[dict] = []
    round_idx = 0
    estimates: list[float] = []
    stopping = {"satisfied": False, "reason": ""}

    publish_timing = bool(knobs.get("publish_timing"))
    attach_tools = bool(knobs.get("attach_tool_traces"))
    forward_style = bool(knobs.get("forward_style"))
    attribute_estimates_in_discuss = bool(knobs.get("attribute_estimates_in_discuss"))
    plant_style_in = set(knobs.get("plant_style_in") or [])
    plant_tool_in = set(knobs.get("plant_tool_in") or [])

    def leak_fields(seat: dict, kind: str) -> dict:
        pub: dict[str, Any] = {"token": seat["token"], "object_class": kind}
        if publish_timing:
            pub["submit_delay_ms"] = seat["delay_ms"]
        if attach_tools or kind in plant_tool_in:
            pub["tool_run_id"] = seat["tool_run_id"]
        if forward_style or kind in plant_style_in:
            pub["text"] = f"comment {seat['style_marker']}"
        return pub

    for step in protocol.get("schedule") or []:
        if step == "ROUND_OPEN":
            round_idx += 1
            events.append(_event("ROUND_OPEN", {"round": round_idx}, round_idx=round_idx))
        elif step == "SUBMIT_SEALED":
            estimates = _values_for(pid, max(round_idx - 1, 0), n)
            for seat, val in zip(seats, estimates):
                pub = leak_fields(seat, "estimate")
                pub["value_present"] = True
                priv = {
                    "seat_id": seat["seat_id"],
                    "value": val,
                    "style_marker": seat["style_marker"],
                    "tool_run_id": seat["tool_run_id"],
                    "delay_ms": seat["delay_ms"],
                }
                events.append(_event("SUBMIT_SEALED", pub, priv, round_idx=round_idx))
        elif step == "AGGREGATE":
            med, iqr = _median_iqr(estimates or [0.0])
            rng = (max(estimates) - min(estimates)) if estimates else 0.0
            events.append(
                _event(
                    "AGGREGATE",
                    {"median": med, "iqr": iqr, "range": rng, "n": n},
                    round_idx=round_idx,
                )
            )
            clauses = (protocol.get("stopping") or {}).get("clauses") or []
            for c in clauses:
                if c.get("kind") == "iqr_below" and iqr <= float(c.get("value") or 0):
                    stopping = {"satisfied": True, "reason": "iqr_below"}
                if c.get("kind") == "range_below" and rng <= float(c.get("value") or 0):
                    stopping = {"satisfied": True, "reason": "range_below"}
                if c.get("kind") == "max_rounds" and round_idx >= int(c.get("value") or 0):
                    stopping = {"satisfied": True, "reason": "max_rounds"}
        elif step == "FEEDBACK_ANON":
            med, iqr = _median_iqr(estimates or [0.0])
            pub: dict[str, Any] = {"median": med, "iqr": iqr, "object_class": "rationale"}
            if forward_style or "rationale" in plant_style_in:
                # Forwards one seat's rationale into the shared feedback channel.
                pub["text"] = f"peer comment {seats[0]['style_marker']}"
            events.append(_event("FEEDBACK_ANON", pub, round_idx=round_idx))
        elif step == "DISCUSSION_OPEN":
            events.append(_event("DISCUSSION_OPEN", {"conversational_identity": True}, round_idx=round_idx))
        elif step == "DISCUSS":
            for seat in seats:
                pub = {
                    "seat_id": seat["seat_id"],
                    "object_class": "speech",
                    "text": f"discuss-{seat['seat_id']}",
                }
                if attribute_estimates_in_discuss:
                    pub["estimate_by_seat"] = seat["seat_id"]
                    pub["object_class"] = "estimate"
                events.append(_event("DISCUSS", pub, round_idx=round_idx))
        elif step == "CYCLE":
            round_idx += 1
            for seat in seats:
                pub = leak_fields(seat, "idea")
                pub["sheet_token"] = f"sheet-{seat['token']}-c{round_idx}"
                priv = {"seat_id": seat["seat_id"], "style_marker": seat["style_marker"]}
                events.append(_event("CYCLE", pub, priv, round_idx=round_idx))
            stopping = {"satisfied": True, "reason": "pass_cycles"} if round_idx >= 6 else stopping
        elif step == "POOL_REVEAL":
            bodies = []
            for seat in seats:
                body = {"token": seat["token"], "object_class": "note_author"}
                if forward_style or "note_author" in plant_style_in or "idea" in plant_style_in:
                    body["text"] = f"pooled {seat['style_marker']}"
                else:
                    body["text"] = f"pooled-idea-{seat['token']}"
                if attach_tools or "note_author" in plant_tool_in:
                    body["tool_run_id"] = seat["tool_run_id"]
                if publish_timing:
                    body["submit_delay_ms"] = seat["delay_ms"]
                bodies.append(body)
            events.append(_event("POOL_REVEAL", {"items": bodies}, round_idx=round_idx))
        elif step == "SILENT_WINDOW_OPEN":
            events.append(_event("SILENT_WINDOW_OPEN", {"public_view": False}, round_idx=round_idx))
        elif step == "SILENT_WINDOW_CLOSE":
            events.append(_event("SILENT_WINDOW_CLOSE", {"closed": True}, round_idx=round_idx))
            stopping = {"satisfied": True, "reason": "silent_window_closed"}
        elif step == "BALLOT_SEALED":
            ballots = []
            for i, seat in enumerate(seats):
                vote = "A" if i % 2 == 0 else "B"
                pred_a = 0.4 + 0.05 * i
                pub = leak_fields(seat, "ballot")
                pub.pop("value_present", None)
                priv = {
                    "seat_id": seat["seat_id"],
                    "vote": vote,
                    "pred_a": pred_a,
                    "style_marker": seat["style_marker"],
                }
                ballots.append({"vote": vote, "pred_a": pred_a})
                events.append(_event("BALLOT_SEALED", pub, priv, round_idx=round_idx))
            protocol["_ballots"] = ballots
        elif step == "SCORE_SURPRISINGLY_POPULAR":
            scored = _surprisingly_popular(protocol.get("_ballots") or [])
            events.append(_event("SCORE_SURPRISINGLY_POPULAR", scored, round_idx=round_idx))
        elif step == "SCORE_FREEZE":
            events.append(_event("SCORE_FREEZE", {"frozen": True}, round_idx=round_idx))
            stopping = {"satisfied": True, "reason": "score_frozen"}
        elif step == "INGEST_SEALED":
            author = seats[0]
            pub = leak_fields(author, "author")
            pub["artifact"] = "work-product"
            if "author" not in plant_style_in and not forward_style:
                pub.pop("text", None)
            events.append(
                _event(
                    "INGEST_SEALED",
                    pub,
                    {"seat_id": author["seat_id"], "style_marker": author["style_marker"]},
                    round_idx=round_idx,
                )
            )
        elif step == "SCORE_SEALED":
            for seat in seats[1:]:
                pub = leak_fields(seat, "reviewer")
                pub["score"] = 1
                priv = {"seat_id": seat["seat_id"]}
                events.append(_event("SCORE_SEALED", pub, priv, round_idx=round_idx))
        elif step == "SCORE_LOCK":
            events.append(_event("SCORE_LOCK", {"locked": True}, round_idx=round_idx))
            stopping = {"satisfied": True, "reason": "score_locked"}
        elif step == "RESULT_FREEZE":
            events.append(_event("RESULT_FREEZE", {"frozen": True}, round_idx=round_idx))
            if not stopping["satisfied"]:
                stopping = {"satisfied": True, "reason": "result_freeze"}
        elif step == "UNSEAL":
            binding = {s["token"]: s["seat_id"] for s in seats}
            events.append(_event("UNSEAL", {"token_to_seat": binding}, round_idx=round_idx))
        else:
            raise ValueError(f"unknown schedule step {step} on {pid}")

    lift_idx = next((i for i, e in enumerate(events) if e["type"] == "UNSEAL"), None)
    if lift_idx is None:
        return {
            "id": pid,
            "verdict": "NOT-EXECUTABLE",
            "missing_element": "UNSEAL event (anonymity lift never occurs; schedule cannot finish)",
            "events": events,
            "stopping": stopping,
        }
    missing = protocol.get("missing_element")
    verdict = "NOT-EXECUTABLE" if missing else "EXECUTABLE"
    return {
        "id": pid,
        "slug": protocol.get("slug"),
        "verdict": verdict,
        "missing_element": missing,
        "anonymity_lift_event": protocol.get("anonymity_lift_event"),
        "lift_index": lift_idx,
        "events": events,
        "stopping": stopping,
        "conversational_identity_allowed_from": protocol.get("conversational_identity_allowed_from"),
        "protected_until_unseal": list(protocol.get("protected_until_unseal") or []),
    }


def _walk_public(obj: Any) -> list[dict]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_public(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_public(v)


def detect_pre_lift_identity_leaks(run: dict, seats: list[dict] | None = None) -> dict:
    """FIRE if a public object before UNSEAL binds a protected class to a seat.

    DISCUSS speech after DISCUSSION_OPEN may carry seat_id (P21 conversational
    clock). Estimate attribution during DISCUSS still FIREs.
    """
    seats = seats or DEFAULT_SEATS
    styles = _style_map(seats)
    tools = _tool_map(seats)
    delays = [s["delay_ms"] for s in seats]
    unique_delays = {d for d in delays if delays.count(d) == 1}
    delay_to_seat = {s["delay_ms"]: s["seat_id"] for s in seats}
    conv_from = run.get("conversational_identity_allowed_from")
    conv_open = False
    lift_idx = run["lift_index"]
    leaks: list[dict] = []

    for i, ev in enumerate(run["events"]):
        if ev["type"] == "DISCUSSION_OPEN":
            conv_open = True
        if i >= lift_idx:
            break
        if ev["type"] == "UNSEAL":
            break
        for node in _walk_public(ev.get("public") or {}):
            if not isinstance(node, dict):
                continue
            obj_class = str(node.get("object_class") or ev.get("type") or "")
            speech_ok = (
                conv_from
                and conv_open
                and ev["type"] == "DISCUSS"
                and obj_class == "speech"
            )
            sid = node.get("seat_id") or node.get("author") or node.get("reviewer_id")
            if sid and not speech_ok:
                leaks.append(
                    {
                        "channel": "identity_field",
                        "event": ev["type"],
                        "index": i,
                        "seat_id": sid,
                        "object_class": obj_class,
                    }
                )
            text = str(node.get("text") or "")
            for marker, seat in styles.items():
                if marker and marker in text:
                    leaks.append(
                        {
                            "channel": "writing_style",
                            "event": ev["type"],
                            "index": i,
                            "seat_id": seat,
                            "object_class": obj_class,
                            "marker": marker,
                        }
                    )
            tid = node.get("tool_run_id")
            if tid and tid in tools:
                leaks.append(
                    {
                        "channel": "tool_traces",
                        "event": ev["type"],
                        "index": i,
                        "seat_id": tools[tid],
                        "object_class": obj_class,
                        "tool_run_id": tid,
                    }
                )
            delay = node.get("submit_delay_ms")
            if delay in unique_delays:
                leaks.append(
                    {
                        "channel": "timing",
                        "event": ev["type"],
                        "index": i,
                        "seat_id": delay_to_seat[delay],
                        "object_class": obj_class,
                        "submit_delay_ms": delay,
                    }
                )

    # Dedup identical channel/event/seat triples
    seen: set[tuple] = set()
    uniq: list[dict] = []
    for leak in leaks:
        key = (leak.get("channel"), leak.get("event"), leak.get("seat_id"), leak.get("index"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(leak)

    fired = len(uniq) > 0
    return {
        "fired": fired,
        "silent": not fired,
        "protocol_id": run.get("id"),
        "leak_count": len(uniq),
        "leaks": uniq,
    }


def run_all(knobs: dict | None = None, protocols: list[dict] | None = None) -> list[dict]:
    out = []
    for proto in protocols or load_protocols():
        run = run_protocol(proto, knobs=knobs)
        det = detect_pre_lift_identity_leaks(run)
        out.append({"run": run, "detector": det})
    return out
