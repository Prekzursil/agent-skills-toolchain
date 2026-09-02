#!/usr/bin/env python3
"""CNF-0167 temporal integrity auditor.

Join receipt timestamps, artifact mtimes, git commit times, and an append-only
event log. Flag causal inversions. Distinguish clock-artifact from fabrication.
Never compare naive local civil times as if they were instants.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
EVENTS_REL = "command-center/events/EVENTS.jsonl"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
RECEIPTS_REL = "command-center/receipts"
UNIT_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
OFFSET_NOCOLON = re.compile(r"([+-])(\d{2})(\d{2})$")
CLOCK_SKEW_SECONDS = 2.0
SKEW = timedelta(seconds=CLOCK_SKEW_SECONDS)
TS_KEYS = ("ts", "generated_at", "written_at", "completed_at", "emitted_at", "completion_ts")
TZ_A = "2026-08-24T18:00:00Z"
TZ_B = "2026-08-24T14:00:00-04:00"


class Instant:
    __slots__ = ("raw", "kind", "utc", "naive")

    def __init__(self, raw: str, kind: str, utc: datetime | None, naive: datetime | None):
        self.raw = raw
        self.kind = kind
        self.utc = utc
        self.naive = naive

    @property
    def aware(self) -> bool:
        return self.utc is not None

    def iso_utc(self) -> str | None:
        if self.utc is None:
            return None
        return self.utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_instant(value: Any) -> Instant:
    if value is None or value == "":
        return Instant("", "missing", None, None)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value > 10**12:
            value = value / 1000.0
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        return Instant(str(value), "epoch", dt, None)
    s = str(value).strip()
    if not s:
        return Instant("", "missing", None, None)
    kind = "naive"
    work = s.replace(" ", "T")
    if work.endswith("Z") or work.endswith("z"):
        kind = "zulu"
        work = work[:-1] + "+00:00"
    else:
        m = OFFSET_NOCOLON.search(work)
        if m and ":" not in work[m.start() :]:
            work = work[: m.start()] + f"{m.group(1)}{m.group(2)}:{m.group(3)}"
            kind = "offset"
        elif re.search(r"[+-]\d{2}:\d{2}$", work):
            kind = "offset"
    try:
        dt = datetime.fromisoformat(work)
    except ValueError:
        return Instant(s, "unparseable", None, None)
    if dt.tzinfo is None:
        return Instant(s, "naive", None, dt)
    return Instant(s, kind, dt.astimezone(timezone.utc), None)


def same_instant(a: Instant, b: Instant) -> bool | None:
    if a.utc is None or b.utc is None:
        return None
    return a.utc == b.utc


def is_before(a: Instant, b: Instant) -> bool | None:
    """True iff aware instant a is strictly before b by more than CLOCK_SKEW."""
    if a.utc is None or b.utc is None:
        return None
    return (b.utc - a.utc) > SKEW


def naive_civil_compare(a_raw: str, b_raw: str) -> str:
    """Forbidden comparator: strip tz and compare civil clocks.

    Used only as a detector-control: it must flag the timezone pair that UTC
    treats as the same instant.
    """
    def strip(s: str) -> datetime:
        t = s.strip().replace(" ", "T")
        if t.endswith("Z") or t.endswith("z"):
            t = t[:-1]
        t = re.sub(r"[+-]\d{2}:?\d{2}$", "", t)
        return datetime.fromisoformat(t)

    na, nb = strip(a_raw), strip(b_raw)
    if na < nb:
        return "a_before_b"
    if nb < na:
        return "b_before_a"
    return "equal"


def load_world(name: str) -> dict:
    path = FIX / f"world_{name.replace('-', '_')}.json"
    if not path.is_file():
        # dep-order lives as world_dep_order.json
        alt = {
            "healthy": "world_healthy.json",
            "backdated": "world_backdated.json",
            "timezone": "world_timezone.json",
            "dep-order": "world_dep_order.json",
            "dep_order": "world_dep_order.json",
        }
        path = FIX / alt[name]
    return json.loads(path.read_text(encoding="utf-8"))


def _iso(value: Any) -> str | None:
    inst = parse_instant(value)
    if inst.utc is not None:
        return inst.iso_utc()
    return inst.raw or None


def _inv(
    *,
    kind: str,
    subject: str,
    classification: str,
    proposed_cause: str,
    receipt_ts: Any,
    artifact_mtime: Any,
    git_commit_ts: Any,
    event_ts: Any = None,
    third_timestamp_source: str,
    extra: dict | None = None,
) -> dict:
    row = {
        "kind": kind,
        "subject": subject,
        "classification": classification,
        "proposed_cause": proposed_cause,
        "receipt_ts": _iso(receipt_ts),
        "artifact_mtime": _iso(artifact_mtime),
        "git_commit_ts": _iso(git_commit_ts) if git_commit_ts not in (None, "") else None,
        "event_ts": _iso(event_ts) if event_ts not in (None, "") else None,
        "third_timestamp_source": third_timestamp_source,
    }
    if extra:
        row.update(extra)
    return row


def _index_by_path(rows: list[dict], key: str = "path") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        p = str(row.get(key) or "")
        if p:
            out[p] = row
    return out


def _index_receipts(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        uid = str(row.get("unit_id") or "")
        if uid:
            out[uid] = row
    return out


def audit_event_log(events: list[dict]) -> dict:
    """Reviewer path: ordering from the event log alone. No mtimes, no git."""
    inversions: list[dict] = []
    equivalences: list[dict] = []
    unorderable: list[dict] = []
    ordered = sorted(events, key=lambda e: int(e.get("seq") or 0))
    instants = [parse_instant(e.get("ts")) for e in ordered]

    for i, ev in enumerate(ordered):
        if instants[i].kind in {"naive", "unparseable", "missing"}:
            unorderable.append(
                {
                    "seq": ev.get("seq"),
                    "unit_id": ev.get("unit_id"),
                    "kind": ev.get("kind"),
                    "ts": ev.get("ts"),
                    "parse_kind": instants[i].kind,
                    "reason": "naive-or-unparseable timestamps are not ordered as local civil time",
                }
            )

    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            a, b = instants[i], instants[j]
            eq = same_instant(a, b)
            if eq is True:
                equivalences.append(
                    {
                        "seq_a": ordered[i].get("seq"),
                        "seq_b": ordered[j].get("seq"),
                        "ts_a": ordered[i].get("ts"),
                        "ts_b": ordered[j].get("ts"),
                        "utc": a.iso_utc(),
                    }
                )
                continue
            before = is_before(b, a)
            if before is True:
                inversions.append(
                    _inv(
                        kind="event-log-order-inversion",
                        subject=str(ordered[j].get("unit_id") or ordered[j].get("path") or f"seq-{ordered[j].get('seq')}"),
                        classification="fabrication",
                        proposed_cause=(
                            "later append-only seq has an earlier UTC instant than an "
                            "earlier seq; log order and clocks disagree"
                        ),
                        receipt_ts=ordered[j].get("ts"),
                        artifact_mtime=None,
                        git_commit_ts=None,
                        event_ts=ordered[i].get("ts"),
                        third_timestamp_source="event-log",
                        extra={
                            "seq_later": ordered[j].get("seq"),
                            "seq_earlier": ordered[i].get("seq"),
                            "later_kind": ordered[j].get("kind"),
                            "earlier_kind": ordered[i].get("kind"),
                        },
                    )
                )

    completions: dict[str, Instant] = {}
    for ev, inst in zip(ordered, instants):
        if ev.get("kind") == "unit-completed" and inst.aware:
            completions[str(ev.get("unit_id") or "")] = inst
    for ev, inst in zip(ordered, instants):
        if ev.get("kind") != "unit-completed" or not inst.aware:
            continue
        for dep in ev.get("depends_on") or []:
            parent = completions.get(str(dep))
            if parent is None:
                # parent completed later in the list, or missing
                continue
            if is_before(inst, parent) is True:
                inversions.append(
                    _inv(
                        kind="receipt-before-dependency",
                        subject=str(ev.get("unit_id")),
                        classification="fabrication",
                        proposed_cause=(
                            f"event-log unit-completed for {ev.get('unit_id')} is before "
                            f"declared dependency {dep} completed"
                        ),
                        receipt_ts=ev.get("ts"),
                        artifact_mtime=None,
                        git_commit_ts=None,
                        event_ts=parent.raw,
                        third_timestamp_source="event-log",
                        extra={"dependency": str(dep), "dependency_completed_ts": parent.iso_utc()},
                    )
                )

    created: dict[str, Instant] = {}
    for ev, inst in zip(ordered, instants):
        if ev.get("kind") == "artifact-created" and inst.aware:
            p = str(ev.get("path") or "")
            if p:
                created[p] = inst
    for ev, inst in zip(ordered, instants):
        if ev.get("kind") != "receipt-written" or not inst.aware:
            continue
        for path in ev.get("cites") or []:
            art = created.get(str(path))
            if art is None:
                continue
            if is_before(inst, art) is True:
                inversions.append(
                    _inv(
                        kind="receipt-before-cited-artifact",
                        subject=str(ev.get("unit_id") or ev.get("path")),
                        classification="fabrication",
                        proposed_cause=(
                            "event-log receipt-written is before artifact-created for a cited path"
                        ),
                        receipt_ts=ev.get("ts"),
                        artifact_mtime=art.iso_utc(),
                        git_commit_ts=None,
                        event_ts=ev.get("ts"),
                        third_timestamp_source="event-log",
                        extra={"cited_path": str(path), "artifact_created_ts": art.iso_utc()},
                    )
                )

    return {
        "inversions": inversions,
        "equivalences": equivalences,
        "unorderable": unorderable,
        "event_count": len(ordered),
        "signals": ["event-log"],
    }


def audit_world(world: dict) -> dict:
    """Full join: events + receipt bodies + artifact mtimes + git commit times + catalog edges."""
    events = list(world.get("events") or [])
    receipts = list(world.get("receipts") or [])
    artifacts = list(world.get("artifacts") or [])
    edges = dict(world.get("catalog_edges") or {})
    by_path = _index_by_path(artifacts)
    by_unit = _index_receipts(receipts)
    log = audit_event_log(events)
    inversions = list(log["inversions"])
    seen = {
        (i.get("kind"), i.get("subject"), i.get("receipt_ts"), i.get("artifact_mtime"))
        for i in inversions
    }

    def add(row: dict) -> None:
        key = (row.get("kind"), row.get("subject"), row.get("receipt_ts"), row.get("artifact_mtime"))
        if key in seen:
            return
        seen.add(key)
        inversions.append(row)

    for rec in receipts:
        rec_ts = parse_instant(rec.get("ts"))
        for cited in rec.get("cites") or []:
            art = by_path.get(str(cited)) or {}
            mtime = parse_instant(art.get("mtime") or art.get("created_ts"))
            created = parse_instant(art.get("created_ts") or art.get("mtime"))
            git_ts = parse_instant(art.get("git_commit_ts"))
            if rec_ts.aware and created.aware and is_before(rec_ts, created) is True:
                cls = "fabrication"
                cause = (
                    "receipt declared ts is before the cited artifact's created_ts "
                    "after UTC conversion and clock-skew window"
                )
                add(
                    _inv(
                        kind="receipt-before-cited-artifact",
                        subject=str(rec.get("unit_id")),
                        classification=cls,
                        proposed_cause=cause,
                        receipt_ts=rec.get("ts"),
                        artifact_mtime=art.get("mtime") or art.get("created_ts"),
                        git_commit_ts=art.get("git_commit_ts"),
                        event_ts=rec.get("ts"),
                        third_timestamp_source="git-commit" if git_ts.aware else "event-log",
                        extra={"cited_path": str(cited)},
                    )
                )
            if rec_ts.aware and git_ts.aware and is_before(rec_ts, git_ts) is True:
                add(
                    _inv(
                        kind="receipt-before-git-commit",
                        subject=str(rec.get("unit_id")),
                        classification="fabrication",
                        proposed_cause=(
                            "receipt declared ts is before the git commit timestamp of the cited artifact"
                        ),
                        receipt_ts=rec.get("ts"),
                        artifact_mtime=art.get("mtime"),
                        git_commit_ts=art.get("git_commit_ts"),
                        event_ts=rec.get("ts"),
                        third_timestamp_source="git-commit",
                        extra={"cited_path": str(cited)},
                    )
                )
            if rec_ts.kind == "naive" or created.kind == "naive":
                # Do not manufacture an inversion by attaching local tz.
                pass

        deps = list(rec.get("depends_on") or []) + list(edges.get(str(rec.get("unit_id") or ""), []) or [])
        for dep in dict.fromkeys(str(d) for d in deps):
            parent = by_unit.get(dep)
            if not parent:
                continue
            p_ts = parse_instant(parent.get("ts"))
            if is_before(rec_ts, p_ts) is True:
                add(
                    _inv(
                        kind="receipt-before-dependency",
                        subject=str(rec.get("unit_id")),
                        classification="fabrication",
                        proposed_cause=(
                            f"receipt for {rec.get('unit_id')} completes before declared "
                            f"dependency {dep}"
                        ),
                        receipt_ts=rec.get("ts"),
                        artifact_mtime=(by_path.get((rec.get("cites") or [None])[0], {}) or {}).get("mtime"),
                        git_commit_ts=(by_path.get((rec.get("cites") or [None])[0], {}) or {}).get("git_commit_ts"),
                        event_ts=parent.get("ts"),
                        third_timestamp_source="event-log",
                        extra={"dependency": dep, "dependency_ts": _iso(parent.get("ts"))},
                    )
                )

    naive_trap = naive_civil_compare(TZ_A, TZ_B)
    tz_a, tz_b = parse_instant(TZ_A), parse_instant(TZ_B)
    return {
        "world_id": world.get("id"),
        "inversions": inversions,
        "inversion_count": len(inversions),
        "equivalences": log["equivalences"],
        "unorderable": log["unorderable"],
        "event_count": log["event_count"],
        "naive_civil_timezone_pair": naive_trap,
        "utc_timezone_pair_same_instant": same_instant(tz_a, tz_b) is True,
        "signals": ["event-log", "receipt-ts", "artifact-mtime", "git-commit", "catalog-edges"],
    }


def timezone_control() -> dict:
    a, b = parse_instant(TZ_A), parse_instant(TZ_B)
    naive = naive_civil_compare(TZ_A, TZ_B)
    return {
        "ts_a": TZ_A,
        "ts_b": TZ_B,
        "utc_a": a.iso_utc(),
        "utc_b": b.iso_utc(),
        "same_instant": same_instant(a, b) is True,
        "utc_flags_inversion": is_before(a, b) is True or is_before(b, a) is True,
        "naive_civil_result": naive,
        "naive_would_flag": naive != "equal",
        "pass": same_instant(a, b) is True and naive != "equal",
        "policy": (
            "Parse every timestamp to an aware UTC instant. Equal instants with "
            "different offset spellings are not inversions. Naive local-time "
            "comparison (strip tz, compare civil clocks) is forbidden because it "
            "manufactures inversions on this estate. DST is irrelevant once the "
            "comparison is on instants, not civil times."
        ),
    }


def run_required_controls() -> dict:
    healthy = audit_world(load_world("healthy"))
    backdated = audit_world(load_world("backdated"))
    timezone = audit_world(load_world("timezone"))
    dep = audit_world(load_world("dep-order"))
    tz = timezone_control()
    log_healthy = audit_event_log(load_world("healthy")["events"])
    log_back = audit_event_log(load_world("backdated")["events"])
    log_tz = audit_event_log(load_world("timezone")["events"])
    log_dep = audit_event_log(load_world("dep-order")["events"])

    back_kinds = {i["kind"] for i in backdated["inversions"]}
    dep_kinds = {i["kind"] for i in dep["inversions"]}
    tz_fab = [
        i
        for i in timezone["inversions"]
        if i.get("classification") == "fabrication"
        and i.get("kind") in {"event-log-order-inversion", "receipt-before-cited-artifact", "receipt-before-dependency"}
    ]
    # Timezone world may list unorderable naive note; fabrication causal inversions must be empty.
    tz_causal = [
        i
        for i in timezone["inversions"]
        if i.get("kind") == "event-log-order-inversion"
    ]

    planted_caught = "receipt-before-cited-artifact" in back_kinds
    dep_caught = "receipt-before-dependency" in dep_kinds
    healthy_zero = healthy["inversion_count"] == 0
    tz_silent = len(tz_causal) == 0 and tz["same_instant"] and not tz["utc_flags_inversion"]
    naive_fires = tz["naive_would_flag"]
    log_back_caught = any(i["kind"] == "receipt-before-cited-artifact" for i in log_back["inversions"])
    log_dep_caught = any(i["kind"] == "receipt-before-dependency" for i in log_dep["inversions"])
    log_healthy_zero = len(log_healthy["inversions"]) == 0
    log_tz_order = [
        i for i in log_tz["inversions"] if i.get("kind") == "event-log-order-inversion"
    ]
    log_tz_silent = len(log_tz_order) == 0
    tz_has_equivalence = any(
        e.get("utc") == "2026-08-24T18:00:00Z" for e in timezone["equivalences"]
    )

    tests = {
        "planted_backdated_caught": planted_caught,
        "timezone_same_instant_not_flagged": tz_silent and tz_has_equivalence,
        "naive_civil_would_flag_timezone_pair": naive_fires,
        "dependency_before_parent_caught": dep_caught,
        "healthy_zero_inversions": healthy_zero,
        "eventlog_only_backdated_caught": log_back_caught,
        "eventlog_only_dep_caught": log_dep_caught,
        "eventlog_only_healthy_zero": log_healthy_zero,
        "eventlog_only_timezone_silent": log_tz_silent,
    }
    tests["all_pass"] = all(tests.values())
    return {
        "tests": tests,
        "timezone_control": tz,
        "worlds": {
            "healthy": healthy,
            "backdated": backdated,
            "timezone": timezone,
            "dep-order": dep,
        },
        "eventlog_only": {
            "healthy": log_healthy,
            "backdated": log_back,
            "timezone": log_tz,
            "dep-order": log_dep,
        },
        "clock_skew_seconds": CLOCK_SKEW_SECONDS,
        "tz_fabrication_rows_should_be_empty": tz_fab,
    }


def git_available(repo: Path) -> bool:
    git_dir = repo / ".git"
    if git_dir.exists():
        return True
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0 and (p.stdout or "").strip() == "true"


def git_commit_ts(repo: Path, rel: str) -> str | None:
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%cI", "--", rel],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    s = (p.stdout or "").strip()
    return s or None


def file_mtime_utc(path: Path) -> Instant:
    try:
        st = path.stat()
    except OSError:
        return Instant("", "missing", None, None)
    dt = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    return Instant(dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "mtime", dt, None)


def extract_declared_ts(doc: dict) -> Instant:
    for key in TS_KEYS:
        if key in doc and doc[key] not in (None, ""):
            inst = parse_instant(doc[key])
            inst.raw = f"{key}:{doc[key]}"
            return inst
    return Instant("", "missing", None, None)


def load_catalog_edges(repo: Path) -> dict[str, list[str]]:
    path = repo / CATALOG_REL
    edges: dict[str, list[str]] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return edges
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if not UNIT_RE.match(uid):
            continue
        deps = [
            str(d)
            for d in (unit.get("dependencies") or [])
            if isinstance(d, str) and UNIT_RE.match(d)
        ]
        if deps:
            edges[uid] = deps
    return edges


def live_scan(repo: Path) -> dict:
    events_path = repo / EVENTS_REL
    event_present = events_path.is_file() and events_path.stat().st_size > 0
    live_events: list[dict] = []
    if event_present:
        for i, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                rec = {"seq": i, "kind": "unparseable", "ts": None, "raw": line[:120]}
            if "seq" not in rec:
                rec["seq"] = i
            live_events.append(rec)

    git_ok = git_available(repo)
    receipts_dir = repo / RECEIPTS_REL
    receipt_rows: list[dict] = []
    by_unit: dict[str, dict] = {}
    for path in sorted(receipts_dir.glob("*.json")):
        uid = path.stem
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            receipt_rows.append(
                {
                    "unit_id": uid,
                    "path": f"{RECEIPTS_REL}/{path.name}",
                    "parse_error": type(exc).__name__,
                }
            )
            continue
        declared = extract_declared_ts(doc if isinstance(doc, dict) else {})
        mtime = file_mtime_utc(path)
        git_ts = git_commit_ts(repo, f"{RECEIPTS_REL}/{path.name}") if git_ok else None
        cites: list[str] = []
        if isinstance(doc, dict):
            for art in doc.get("artifacts") or []:
                if isinstance(art, dict) and art.get("path"):
                    cites.append(str(art["path"]).replace("\\", "/"))
        row = {
            "unit_id": uid,
            "path": f"{RECEIPTS_REL}/{path.name}",
            "declared_raw": declared.raw,
            "declared_kind": declared.kind,
            "declared_utc": declared.iso_utc(),
            "mtime_utc": mtime.iso_utc(),
            "git_commit_ts": git_ts,
            "cites": cites,
        }
        receipt_rows.append(row)
        by_unit[uid] = {**row, "_declared": declared, "_mtime": mtime}

    edges = load_catalog_edges(repo)
    clock_artifacts: list[dict] = []
    causal: list[dict] = []
    unorderable: list[dict] = []
    missing_declared: list[str] = []

    for row in receipt_rows:
        if "parse_error" in row:
            continue
        declared = by_unit[row["unit_id"]]["_declared"]
        mtime = by_unit[row["unit_id"]]["_mtime"]
        git_inst = parse_instant(row["git_commit_ts"]) if row.get("git_commit_ts") else Instant("", "missing", None, None)
        if declared.kind == "missing":
            missing_declared.append(row["unit_id"])
        if declared.kind in {"naive", "unparseable"}:
            unorderable.append(
                {
                    "unit_id": row["unit_id"],
                    "declared_raw": declared.raw,
                    "parse_kind": declared.kind,
                    "reason": "declared timestamp is naive or unparseable; not compared as local civil time",
                }
            )
        # declared vs mtime: on a non-git copy, mtime is copy time → clock-artifact, not fabrication
        if declared.aware and mtime.aware and abs((mtime.utc - declared.utc).total_seconds()) > CLOCK_SKEW_SECONDS:
            cls = "clock-artifact"
            if not git_ok and not event_present:
                cause = (
                    "declared receipt ts and filesystem mtime disagree beyond clock-skew; "
                    "git commit timestamp NOT-CHECKED (no .git) and EVENTS.jsonl is absent, "
                    "so this is classified clock-artifact (copy/rewrite/skew), not fabrication"
                )
            elif git_inst.aware and is_before(declared, git_inst) is True:
                cls = "fabrication"
                cause = "declared ts precedes git commit time of the receipt blob"
            else:
                cause = (
                    "declared ts and mtime disagree beyond skew; event-log join "
                    f"{'ran' if event_present else 'NOT-CHECKED'}; classified {cls}"
                )
            target = causal if cls == "fabrication" else clock_artifacts
            target.append(
                _inv(
                    kind="receipt-vs-mtime",
                    subject=row["unit_id"],
                    classification=cls,
                    proposed_cause=cause,
                    receipt_ts=declared.iso_utc(),
                    artifact_mtime=mtime.iso_utc(),
                    git_commit_ts=row.get("git_commit_ts"),
                    event_ts=None,
                    third_timestamp_source="git-commit" if git_inst.aware else "unavailable",
                )
            )
        for cited in row.get("cites") or []:
            if cited == row["path"]:
                continue
            cited_path = repo / cited
            if not cited_path.is_file():
                continue
            cited_mtime = file_mtime_utc(cited_path)
            cited_git = git_commit_ts(repo, cited) if git_ok else None
            if declared.aware and cited_mtime.aware and is_before(mtime, cited_mtime) is True:
                # receipt file older than cited artifact file
                cls = "clock-artifact" if not event_present else "fabrication"
                (causal if cls == "fabrication" else clock_artifacts).append(
                    _inv(
                        kind="receipt-before-cited-artifact",
                        subject=row["unit_id"],
                        classification=cls,
                        proposed_cause=(
                            "receipt file mtime is before cited artifact mtime; "
                            "without an event log this is treated as clock-artifact on a copied tree"
                            if cls == "clock-artifact"
                            else "receipt mtime precedes cited artifact mtime and event log is present"
                        ),
                        receipt_ts=declared.iso_utc(),
                        artifact_mtime=cited_mtime.iso_utc(),
                        git_commit_ts=cited_git,
                        event_ts=None,
                        third_timestamp_source="git-commit" if cited_git else "unavailable",
                        extra={"cited_path": cited},
                    )
                )

    for uid, row in by_unit.items():
        declared = row["_declared"]
        for dep in edges.get(uid, []):
            parent = by_unit.get(dep)
            if not parent:
                continue
            p_ts = parent["_declared"]
            if is_before(declared, p_ts) is True:
                causal.append(
                    _inv(
                        kind="receipt-before-dependency",
                        subject=uid,
                        classification="fabrication",
                        proposed_cause=(
                            f"live receipt ts for {uid} is before live receipt ts for "
                            f"catalog dependency {dep} after UTC conversion"
                        ),
                        receipt_ts=declared.iso_utc(),
                        artifact_mtime=row["_mtime"].iso_utc(),
                        git_commit_ts=row.get("git_commit_ts"),
                        event_ts=p_ts.iso_utc(),
                        third_timestamp_source="git-commit" if row.get("git_commit_ts") else "event-log",
                        extra={"dependency": dep, "dependency_ts": p_ts.iso_utc()},
                    )
                )

    event_join = None
    if event_present:
        event_join = audit_event_log(live_events)
        causal.extend(event_join.get("inversions") or [])

    return {
        "event_log_path": EVENTS_REL,
        "event_log_present": event_present,
        "event_log_bytes": events_path.stat().st_size if event_present else 0,
        "git_available": git_ok,
        "receipts_scanned": len(receipt_rows),
        "clock_artifact_count": len(clock_artifacts),
        "causal_inversion_count": len(causal),
        "unorderable_count": len(unorderable),
        "missing_declared_ts_count": len(missing_declared),
        "missing_declared_ts_ids": missing_declared,
        "clock_artifacts": clock_artifacts,
        "causal_inversions": causal,
        "unorderable": unorderable,
        "event_join": event_join,
        "catalog_unit_edges_loaded": len(edges),
        "timezone_and_skew": {
            "clock_skew_seconds": CLOCK_SKEW_SECONDS,
            "naive_local_comparison": "forbidden",
            "dst": "instants, not civil times",
        },
    }


def controls_pass(ctrl: dict | None = None) -> bool:
    ctrl = ctrl or run_required_controls()
    return bool(ctrl["tests"]["all_pass"])


if __name__ == "__main__":
    ctrl = run_required_controls()
    print(json.dumps({"tests": ctrl["tests"], "timezone": ctrl["timezone_control"]}, indent=2, sort_keys=True))
    raise SystemExit(0 if ctrl["tests"]["all_pass"] else 1)
