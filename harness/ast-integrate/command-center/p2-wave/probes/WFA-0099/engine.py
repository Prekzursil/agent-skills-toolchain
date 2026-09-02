"""Append-only collapse audit trail with restore-from-record-alone.

CollapseGate.collapse is the only public mutator. It appends a hash-chained
JSONL record (surviving id, absorbed ids, deciding signals, preserved union,
and full pre-collapse records) BEFORE mutating the store. A collapse with no
durable trail record is refused. Restore reconstructs pre-collapse records
from that trail record alone.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from tokens import score_pair
from fixtures import TS, clone_records, collapse_plans

GENESIS = "0" * 64
GATE_TOKEN = object()
SIGNALS = ("LEXICAL", "EMBEDDING", "STRUCTURAL")

LICENCE_RANK = {
    "CC0-1.0": 0,
    "MIT": 1,
    "BSD-2-Clause": 1,
    "BSD-3-Clause": 1,
    "Apache-2.0": 2,
    "LGPL-2.1-only": 3,
    "GPL-3.0-only": 4,
    "AGPL-3.0-only": 5,
}


class TrailRewriteError(RuntimeError):
    """In-place rewrite of the trail is a gate failure."""


class TrailAppendRequired(RuntimeError):
    """Collapse refused because a durable trail record was not written."""


class CollapseRefused(RuntimeError):
    """Policy or signal check refused the collapse."""


class RestoreError(RuntimeError):
    """Trail record cannot reconstruct pre-collapse records."""


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_text(canonical(obj))


def event_hash_of(event: Mapping[str, Any]) -> str:
    body = {k: event[k] for k in event if k != "event_hash"}
    return sha256_obj(body)


def licence_strictest(licences: list[str]) -> str:
    if not licences:
        raise CollapseRefused("no licence obligations to preserve")
    ranked = []
    for lic in licences:
        if lic not in LICENCE_RANK:
            ranked.append((100, lic))
        else:
            ranked.append((LICENCE_RANK[lic], lic))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return ranked[0][1]


def union_lists(*lists: list[str]) -> list[str]:
    seen: list[str] = []
    bag: set[str] = set()
    for lst in lists:
        for item in lst or []:
            if item not in bag:
                bag.add(item)
                seen.append(item)
    return seen


def preserved_union(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    mechanisms = union_lists(*[list(r.get("mechanisms") or []) for r in records])
    anchors = union_lists(*[list(r.get("provenance_anchors") or []) for r in records])
    licences = union_lists(*[list(r.get("licence_obligations") or []) for r in records])
    stops = union_lists(*[list(r.get("stop_rules") or []) for r in records])
    if not mechanisms:
        raise CollapseRefused("union of mechanisms is empty")
    strict = licence_strictest(licences)
    return {
        "mechanisms": mechanisms,
        "provenance_anchors": anchors,
        "licence_obligations": licences,
        "licence_governing": strict,
        "stop_rules": stops,
    }


def union_would_drop(pre: list[Mapping[str, Any]], merged_union: Mapping[str, Any]) -> list[str]:
    drops: list[str] = []
    want_m: set[str] = set()
    want_a: set[str] = set()
    want_l: set[str] = set()
    want_s: set[str] = set()
    for r in pre:
        want_m.update(r.get("mechanisms") or [])
        want_a.update(r.get("provenance_anchors") or [])
        want_l.update(r.get("licence_obligations") or [])
        want_s.update(r.get("stop_rules") or [])
    got_m = set(merged_union.get("mechanisms") or [])
    got_a = set(merged_union.get("provenance_anchors") or [])
    got_l = set(merged_union.get("licence_obligations") or [])
    got_s = set(merged_union.get("stop_rules") or [])
    if want_m - got_m:
        drops.append(f"mechanisms:{sorted(want_m - got_m)}")
    if want_a - got_a:
        drops.append(f"provenance_anchors:{sorted(want_a - got_a)}")
    if want_l - got_l:
        drops.append(f"licence_obligations:{sorted(want_l - got_l)}")
    if want_s - got_s:
        drops.append(f"stop_rules:{sorted(want_s - got_s)}")
    return drops


class RecordStore:
    """In-memory workflow record store. Public mutation is CollapseGate only."""

    def __init__(self, records: Mapping[str, dict] | None = None) -> None:
        self._records: dict[str, dict] = deepcopy(dict(records or {}))

    def get(self, rid: str) -> dict:
        if rid not in self._records:
            raise KeyError(rid)
        return deepcopy(self._records[rid])

    def ids(self) -> list[str]:
        return sorted(self._records)

    def snapshot(self) -> dict[str, dict]:
        return deepcopy(self._records)

    def fingerprint(self) -> str:
        return sha256_obj(self.snapshot())

    def _commit_collapse(
        self,
        surviving_id: str,
        absorbed_ids: list[str],
        merged: dict,
        *,
        _gate_token: object | None = None,
    ) -> None:
        if _gate_token is not GATE_TOKEN:
            raise TrailAppendRequired(
                "collapse with no trail record is impossible: use CollapseGate.collapse"
            )
        if surviving_id not in self._records:
            raise CollapseRefused(f"survivor {surviving_id} missing")
        self._records[surviving_id] = deepcopy(merged)
        for aid in absorbed_ids:
            self._records.pop(aid, None)


class CollapseTrail:
    """Append-only JSONL with a hash chain. Rewrite is a gate failure."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def events(self) -> list[dict]:
        text = self.path.read_text(encoding="utf-8")
        out: list[dict] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if not isinstance(rec, dict):
                raise TrailRewriteError(f"non-object trail line: {line[:80]}")
            out.append(rec)
        return out

    def verify(self) -> dict[str, Any]:
        expected_prev = GENESIS
        expected_seq = 1
        tip = GENESIS
        count = 0
        try:
            events = self.events()
        except (OSError, json.JSONDecodeError, TrailRewriteError) as exc:
            return {"ok": False, "events": 0, "tip": GENESIS, "error": str(exc)}
        for i, event in enumerate(events, 1):
            if event.get("seq") != expected_seq:
                return {
                    "ok": False,
                    "events": count,
                    "tip": tip,
                    "error": f"line {i}: seq {event.get('seq')!r} != {expected_seq}",
                }
            if event.get("prev_hash") != expected_prev:
                return {
                    "ok": False,
                    "events": count,
                    "tip": tip,
                    "error": f"line {i}: prev_hash mismatch",
                }
            recomputed = event_hash_of(event)
            if event.get("event_hash") != recomputed:
                return {
                    "ok": False,
                    "events": count,
                    "tip": tip,
                    "error": f"line {i}: event_hash mismatch",
                }
            expected_prev = event["event_hash"]
            expected_seq += 1
            tip = event["event_hash"]
            count += 1
        return {"ok": True, "events": count, "tip": tip, "error": None}

    def append(self, payload: Mapping[str, Any]) -> dict:
        report = self.verify()
        if not report["ok"]:
            raise TrailRewriteError(f"refusing append on broken chain: {report['error']}")
        events = self.events()
        prev = events[-1]["event_hash"] if events else GENESIS
        seq = len(events) + 1
        rec = dict(payload)
        rec["kind"] = "collapse"
        rec["seq"] = seq
        rec["prev_hash"] = prev
        rec["ts"] = rec.get("ts") or TS
        rec["event_hash"] = event_hash_of(rec)
        line = canonical(rec) + "\n"
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
        durable = self.events()
        if not durable or durable[-1].get("event_hash") != rec["event_hash"]:
            raise TrailAppendRequired("append did not persist a matching trail record")
        post = self.verify()
        if not post["ok"]:
            raise TrailRewriteError(f"chain broken after append: {post['error']}")
        return deepcopy(durable[-1])

    def rewrite_line(self, index: int, new_obj: Mapping[str, Any]) -> None:
        raise TrailRewriteError(
            "trail is append-only; in-place rewrite is a gate failure "
            f"(index={index})"
        )


class CollapseGate:
    """THE collapse entry point. Store mutation is impossible without a trail record."""

    def __init__(self, store: RecordStore, trail: CollapseTrail) -> None:
        self.store = store
        self.trail = trail

    def collapse(
        self,
        surviving_id: str,
        absorbed_ids: list[str],
        primary_signal: str,
    ) -> dict:
        if primary_signal not in SIGNALS:
            raise CollapseRefused(f"unknown signal {primary_signal}")
        absorbed_ids = list(absorbed_ids)
        if not absorbed_ids:
            raise CollapseRefused("absorbed_ids empty")
        if surviving_id in absorbed_ids:
            raise CollapseRefused("survivor cannot absorb itself")
        involved = [surviving_id, *absorbed_ids]
        pre: dict[str, dict] = {}
        for rid in involved:
            pre[rid] = self.store.get(rid)

        scores_by_absorbed = []
        fired_all: list[str] = []
        survivor = pre[surviving_id]
        for aid in absorbed_ids:
            scores = score_pair(survivor, pre[aid])
            scores_by_absorbed.append({"absorbed_id": aid, **scores})
            for sig in scores["fired"]:
                if sig not in fired_all:
                    fired_all.append(sig)
            hit_key = {
                "LEXICAL": "lexical_hit",
                "EMBEDDING": "embedding_hit",
                "STRUCTURAL": "structural_hit",
            }[primary_signal]
            if not scores[hit_key]:
                raise CollapseRefused(
                    f"required signal {primary_signal} did not fire for "
                    f"{surviving_id}/{aid} scores={scores}"
                )

        union = preserved_union(list(pre.values()))
        drops = union_would_drop(list(pre.values()), union)
        if drops:
            raise CollapseRefused(f"lossy collapse refused: {drops}")

        merged = deepcopy(survivor)
        merged["id"] = surviving_id
        merged["mechanisms"] = list(union["mechanisms"])
        merged["provenance_anchors"] = list(union["provenance_anchors"])
        merged["licence_obligations"] = list(union["licence_obligations"])
        merged["licence_governing"] = union["licence_governing"]
        merged["stop_rules"] = list(union["stop_rules"])
        merged["duplicate_of"] = union_lists(
            list(survivor.get("duplicate_of") or []), absorbed_ids
        )
        merged["absorbed_ids"] = list(absorbed_ids)
        edges = [
            {"from": aid, "to": surviving_id, "kind": "duplicate-of"}
            for aid in absorbed_ids
        ]

        payload = {
            "surviving_id": surviving_id,
            "absorbed_ids": list(absorbed_ids),
            "primary_signal": primary_signal,
            "deciding_signals": [primary_signal],
            "signals_fired": fired_all,
            "scores": scores_by_absorbed,
            "preserved_union": union,
            "pre_records": pre,
            "merged_record": merged,
            "duplicate_of_edges": edges,
            "ts": TS,
        }

        before_fp = self.store.fingerprint()
        durable = self.trail.append(payload)
        events = self.trail.events()
        if not events or events[-1].get("event_hash") != durable["event_hash"]:
            raise TrailAppendRequired("collapse refused: trail record not durable")
        if not durable.get("pre_records"):
            raise TrailAppendRequired("collapse refused: trail record lacks pre_records")
        self.store._commit_collapse(
            surviving_id, absorbed_ids, merged, _gate_token=GATE_TOKEN
        )
        if self.store.fingerprint() == before_fp:
            raise CollapseRefused("store did not mutate after durable trail write")
        return deepcopy(durable)


def restore_from_trail_record(record: Mapping[str, Any]) -> dict[str, dict]:
    """Reconstruct pre-collapse records from the trail record ALONE."""
    pre = record.get("pre_records")
    if not isinstance(pre, dict) or not pre:
        raise RestoreError("trail record lacks pre_records; not restorable")
    surviving = record.get("surviving_id")
    absorbed = list(record.get("absorbed_ids") or [])
    expected = {surviving, *absorbed}
    got = set(pre)
    if got != expected:
        raise RestoreError(f"pre_records ids {sorted(got)} != {sorted(expected)}")
    out = {rid: deepcopy(rec) for rid, rec in pre.items()}
    for rid, rec in out.items():
        if rec.get("id") != rid:
            raise RestoreError(f"pre_records[{rid}].id={rec.get('id')}")
    return out


def deep_diff(left: Any, right: Any, prefix: str = "") -> list[str]:
    if type(left) is not type(right) and not (
        isinstance(left, (int, float)) and isinstance(right, (int, float))
    ):
        return [f"{prefix}: type {type(left).__name__} != {type(right).__name__}"]
    if isinstance(left, dict):
        diffs: list[str] = []
        keys = set(left) | set(right)
        for k in sorted(keys, key=str):
            p = f"{prefix}.{k}" if prefix else str(k)
            if k not in left:
                diffs.append(f"{p}: missing on left")
            elif k not in right:
                diffs.append(f"{p}: missing on right")
            else:
                diffs.extend(deep_diff(left[k], right[k], p))
        return diffs
    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{prefix}: len {len(left)} != {len(right)}"]
        diffs = []
        for i, (a, b) in enumerate(zip(left, right)):
            diffs.extend(deep_diff(a, b, f"{prefix}[{i}]"))
        return diffs
    if left != right:
        return [f"{prefix}: {left!r} != {right!r}"]
    return []


def run_rehearsal(trail_path: Path) -> dict[str, Any]:
    """Execute three collapses across different signals and restore each."""
    store = RecordStore(clone_records())
    trail = CollapseTrail(trail_path)
    rehearsals: list[dict[str, Any]] = []
    for plan in collapse_plans():
        involved = [plan["surviving_id"], *plan["absorbed_ids"]]
        snap = {rid: store.get(rid) for rid in involved}
        snap_sha = {rid: sha256_obj(rec) for rid, rec in snap.items()}
        durable = CollapseGate(store, trail).collapse(
            plan["surviving_id"], plan["absorbed_ids"], plan["primary_signal"]
        )
        restored = restore_from_trail_record(durable)
        rest_sha = {rid: sha256_obj(rec) for rid, rec in restored.items()}
        diffs = deep_diff(snap, restored)
        after_ids = set(store.ids())
        rehearsals.append(
            {
                "primary_signal": plan["primary_signal"],
                "surviving_id": plan["surviving_id"],
                "absorbed_ids": list(plan["absorbed_ids"]),
                "event_hash": durable["event_hash"],
                "seq": durable["seq"],
                "signals_fired": durable["signals_fired"],
                "deciding_signals": durable["deciding_signals"],
                "scores": durable["scores"],
                "preserved_union": durable["preserved_union"],
                "duplicate_of_edges": durable["duplicate_of_edges"],
                "pre_sha256": snap_sha,
                "restored_sha256": rest_sha,
                "equal": diffs == [],
                "diffs": diffs[:20],
                "absorbed_absent_after": all(
                    aid not in after_ids for aid in plan["absorbed_ids"]
                ),
                "survivor_present_after": plan["surviving_id"] in after_ids,
            }
        )
    chain = trail.verify()
    signals = [r["primary_signal"] for r in rehearsals]
    return {
        "rehearsals": rehearsals,
        "trail_events": trail.events(),
        "chain": chain,
        "primary_signals": signals,
        "three_distinct_signals": set(signals) == {"LEXICAL", "EMBEDDING", "STRUCTURAL"},
        "all_restored": all(r["equal"] for r in rehearsals),
        "n_collapses": len(rehearsals),
        "final_store_ids": store.ids(),
        "final_store_fingerprint": store.fingerprint(),
    }


def load_trail_schema() -> dict:
    return json.loads(
        (Path(__file__).resolve().parent / "trail-record.schema.json").read_text(
            encoding="utf-8"
        )
    )


def load_report_schema() -> dict:
    return json.loads(
        (Path(__file__).resolve().parent / "audit-report.schema.json").read_text(
            encoding="utf-8"
        )
    )


def validate_instance(schema: dict, instance: Any) -> list[str]:
    import jsonschema

    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(instance)
    ]


def schema_rejects_garbage(schema: dict) -> bool:
    import jsonschema

    validator = jsonschema.Draft7Validator(schema)
    garbage = [
        {},
        {"unit_id": "WFA-0099", "state": "SUCCESS"},
        {"foo": "bar", "n": 999999},
        {"trail_records": []},
        "not-an-object",
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            return False
    return True



class RefusingTrail(CollapseTrail):
    """Append raises; used to prove the gate will not mutate the store."""

    def append(self, payload: Mapping[str, Any]) -> dict:
        raise TrailAppendRequired("append refused by control")


class SilentTrail(CollapseTrail):
    """Returns a fake record without writing; gate must refuse."""

    def append(self, payload: Mapping[str, Any]) -> dict:
        rec = dict(payload)
        rec["kind"] = "collapse"
        rec["seq"] = 1
        rec["prev_hash"] = GENESIS
        rec["ts"] = rec.get("ts") or TS
        rec["event_hash"] = event_hash_of(rec)
        return rec


def mutate_first_line(src: Path, dest: Path) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RuntimeError("empty trail")
    rec = json.loads(lines[0])
    rec["surviving_id"] = "mutated-survivor"
    lines[0] = canonical(rec)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_append_only_controls(good_trail: Path, scratch: Path) -> dict[str, Any]:
    """Both-states: intact chain verifies; rewritten line is a gate failure."""
    good = CollapseTrail(good_trail)
    intact = good.verify()
    api_raised = False
    api_err = ""
    try:
        good.rewrite_line(0, {"surviving_id": "nope"})
    except TrailRewriteError as exc:
        api_raised = True
        api_err = str(exc)
    mutated = scratch / "mutated.jsonl"
    mutate_first_line(good_trail, mutated)
    broken = CollapseTrail(mutated).verify()
    ok = (
        intact.get("ok") is True
        and intact.get("events", 0) >= 3
        and api_raised
        and broken.get("ok") is False
    )
    return {
        "intact_ok": intact.get("ok") is True,
        "intact_events": intact.get("events"),
        "rewrite_api_raised": api_raised,
        "rewrite_api_error": api_err,
        "mutated_ok": broken.get("ok") is True,
        "mutated_error": broken.get("error"),
        "pass": ok,
    }


def run_entry_point_controls(scratch: Path) -> dict[str, Any]:
    """Collapse with no durable trail record must be impossible."""
    plan = collapse_plans()[0]
    # 1. Direct store commit without token.
    store_a = RecordStore(clone_records())
    fp_a = store_a.fingerprint()
    direct_raised = False
    try:
        store_a._commit_collapse(
            plan["surviving_id"],
            list(plan["absorbed_ids"]),
            store_a.get(plan["surviving_id"]),
        )
    except TrailAppendRequired:
        direct_raised = True
    direct_unchanged = store_a.fingerprint() == fp_a

    # 2. Refusing trail.
    store_b = RecordStore(clone_records())
    fp_b = store_b.fingerprint()
    refuse_path = scratch / "refuse.jsonl"
    refuse_raised = False
    try:
        CollapseGate(store_b, RefusingTrail(refuse_path)).collapse(
            plan["surviving_id"], list(plan["absorbed_ids"]), plan["primary_signal"]
        )
    except TrailAppendRequired:
        refuse_raised = True
    refuse_unchanged = store_b.fingerprint() == fp_b
    refuse_empty = (
        not refuse_path.exists()
        or not refuse_path.read_text(encoding="utf-8").strip()
    )

    # 3. Silent (non-durable) trail.
    store_c = RecordStore(clone_records())
    fp_c = store_c.fingerprint()
    silent_path = scratch / "silent.jsonl"
    silent_raised = False
    try:
        CollapseGate(store_c, SilentTrail(silent_path)).collapse(
            plan["surviving_id"], list(plan["absorbed_ids"]), plan["primary_signal"]
        )
    except TrailAppendRequired:
        silent_raised = True
    silent_unchanged = store_c.fingerprint() == fp_c
    silent_empty = (
        not silent_path.exists()
        or not silent_path.read_text(encoding="utf-8").strip()
    )

    ok = (
        direct_raised
        and direct_unchanged
        and refuse_raised
        and refuse_unchanged
        and refuse_empty
        and silent_raised
        and silent_unchanged
        and silent_empty
    )
    return {
        "direct_commit_raised": direct_raised,
        "direct_store_unchanged": direct_unchanged,
        "refusing_trail_raised": refuse_raised,
        "refusing_store_unchanged": refuse_unchanged,
        "refusing_trail_empty": refuse_empty,
        "silent_trail_raised": silent_raised,
        "silent_store_unchanged": silent_unchanged,
        "silent_trail_empty": silent_empty,
        "pass": ok,
    }
