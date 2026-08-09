"""Open, close, defer, supersede, drop, or annotate a backlog item -- one command each.

SYMMETRY IS THE WHOLE POINT. A register where opening an item costs one command
and closing it costs a manual markdown edit rots, because the cheap operation
runs and the expensive one does not. Every verb here is one line:

    python tools/command-center/close.py --open "title" --program MONITOR --action "first step"
    python tools/command-center/close.py R-M01 --evidence "monitors.toml:12 [cockpit] stanza; monitorcore.unified --help exit 0"
    python tools/command-center/close.py R-M01 --defer "waiting on owner Q14" --days 14
    python tools/command-center/close.py R-M01 --superseded-by R-M02 --evidence "R-M02 subsumes the stanza"
    python tools/command-center/close.py R-M01 --dropped "owner decision <anchor>"
    python tools/command-center/close.py R-M01 --note "half landed in PR #NNN"
    python tools/command-center/close.py --list --program MONITOR

`--evidence` is REQUIRED for a close and rejected when blank: this register's own
vocabulary says DONE-VERIFIED means shipped AND you cite the executable evidence,
and DONE-CLAIMED is a synonym for NOT-CHECKED. `--defer` never deletes anything;
the item stays OPEN and simply stops being surfaced until `defer_until`.

Every mutation rewrites the derived graph and appends to the append-only event
log, so the graph can never drift from the catalog and no state change is
untraceable.

REFUSAL POLICY. The command re-validates the mutated catalog and refuses only
violations THIS change introduced. A pre-existing violation elsewhere must not
block an unrelated close -- an advisory whose only satisfying action is somebody
else's work is a deadlock, which is the failure mode this whole lane exists to
avoid.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog as cat
import validate as val

PROGRAM_PREFIX = {
    "A-toolchain": "A",
    "HARNESS": "H",
    "MONITOR": "M",
    "B-workflow_design": "B",
}
DEFAULT_DEFER_DAYS = 7


def _now(explicit: str | None = None) -> datetime:
    if explicit:
        return datetime.fromisoformat(explicit)
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def next_id(catalog: dict[str, Any], program: str) -> str:
    prefix = PROGRAM_PREFIX.get(program)
    if prefix is None:
        raise ValueError(
            f"unknown program {program!r}; expected one of {sorted(PROGRAM_PREFIX)}"
        )
    highest = 0
    for item in cat.items(catalog):
        item_id = str(item.get("id", ""))
        if item_id.startswith(f"R-{prefix}") and item_id[3:].isdigit():
            highest = max(highest, int(item_id[3:]))
    return f"R-{prefix}{highest + 1:02d}"


def _record(item: dict[str, Any], action: str, moment: datetime, detail: str) -> None:
    item.setdefault("history", []).append(
        {"ts": _stamp(moment), "action": action, "detail": detail}
    )


def append_event(payload: dict[str, Any], path: Path | None = None) -> None:
    """Append-only event log -- the 14th command-center artifact Prompt Two names
    alongside the 13 files (`_USER-PROMPTS.md:10603`)."""
    target = path or cat.events_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def apply_change(
    catalog: dict[str, Any],
    args: argparse.Namespace,
    moment: datetime,
) -> tuple[str, dict[str, Any]]:
    """Mutate `catalog` in place. Returns (verb, event payload)."""
    index = cat.by_id(catalog)

    if args.open:
        item_id = next_id(catalog, args.program)
        item = {
            "id": item_id,
            "title": args.open,
            "phase": {
                "A-toolchain": "prompt-two",
                "HARNESS": "unified-contract",
                "MONITOR": "monitor-cockpit",
                "B-workflow_design": "program-b",
            }.get(args.program, "cross-program"),
            "target": args.open,
            "inputs": [],
            "dependencies": list(args.depends_on or []),
            "output_path": f"command-center/receipts/{item_id}.json",
            "completion_sentinel": f"SUCCESS:{item_id}",
            "program": args.program,
            "section": "OUTSTANDING",
            "status": "OPEN",
            "disposition": None,
            "disposition_evidence": "",
            "effort": args.effort or "UNKNOWN",
            "evidence": args.evidence or "",
            "sources": [],
            "owner_gate": list(args.owner_gate or []),
            "security_class": args.security_class,
            "next_smallest_action": args.action or cat.UNKNOWN,
            "defer": None,
            "history": [],
        }
        _record(item, "open", moment, args.open)
        catalog["items"].append(item)
        return "open", {"id": item_id, "program": args.program, "title": args.open}

    item = index.get(args.item_id or "")
    if item is None:
        raise KeyError(f"no such item: {args.item_id!r}")

    if args.note:
        _record(item, "note", moment, args.note)
        if args.action:
            item["next_smallest_action"] = args.action
        return "note", {"id": item["id"], "note": args.note}

    if args.defer:
        until = moment + timedelta(days=args.days)
        item["defer"] = {"until": _stamp(until), "reason": args.defer}
        _record(item, "defer", moment, f"{args.defer} (until {_stamp(until)})")
        return "defer", {"id": item["id"], "until": _stamp(until), "reason": args.defer}

    if args.superseded_by:
        if args.superseded_by not in index:
            raise KeyError(
                f"--superseded-by names an unknown item: {args.superseded_by!r}"
            )
        item["disposition"] = "SUPERSEDED"
        item["status"] = "SUPERSEDED"
        item["section"] = "SUPERSEDED"
        item["disposition_evidence"] = (
            f"superseded by {args.superseded_by}: {args.evidence or ''}".strip()
        )
        item["defer"] = None
        _record(item, "supersede", moment, args.superseded_by)
        return "supersede", {"id": item["id"], "by": args.superseded_by}

    if args.dropped:
        item["disposition"] = "DROPPED-BY-OWNER"
        item["status"] = "DROPPED-BY-OWNER"
        item["section"] = "DELIBERATELY-SKIPPED"
        item["disposition_evidence"] = args.dropped
        item["defer"] = None
        _record(item, "drop", moment, args.dropped)
        return "drop", {"id": item["id"], "decision": args.dropped}

    # Default verb: close.
    evidence = (args.evidence or "").strip()
    if not evidence:
        raise ValueError(
            "a close needs --evidence (a file:line or a reproducible command). "
            "DONE without cited evidence is DONE-CLAIMED, which this register treats as NOT-CHECKED."
        )
    item["disposition"] = "DONE-VERIFIED"
    item["status"] = "DONE-VERIFIED"
    item["section"] = "SETTLED"
    item["disposition_evidence"] = evidence
    item["defer"] = None
    _record(item, "close", moment, evidence)
    return "close", {"id": item["id"], "evidence": evidence}


def _violation_keys(violations) -> set[tuple[str, str, str]]:
    return {(entry["check"], entry["id"], entry["detail"]) for entry in violations}


def list_items(
    catalog: dict[str, Any], program: str | None, only_open: bool
) -> list[str]:
    lines: list[str] = []
    for item in cat.items(catalog):
        if program and item.get("program") != program:
            continue
        if only_open and not cat.is_open(item):
            continue
        state = item.get("disposition") or item.get("status") or "OPEN"
        deferred = " [deferred]" if item.get("defer") else ""
        lines.append(
            f"{item['id']:<7} {state:<16} {str(item.get('title', ''))[:88]}{deferred}"
        )
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Move one backlog item to a new state."
    )
    parser.add_argument(
        "item_id", nargs="?", help="the item to act on (omit for --open / --list)"
    )
    parser.add_argument("--evidence", help="file:line or command proving the close")
    parser.add_argument(
        "--defer", help="park the item; it stays OPEN and returns after --days"
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DEFER_DAYS)
    parser.add_argument("--superseded-by", help="the item that replaces this one")
    parser.add_argument("--dropped", help="the recorded owner decision that drops it")
    parser.add_argument("--note", help="progress note; does not change disposition")
    parser.add_argument("--open", help="open a NEW item with this title")
    # No default: a new item silently filed under the wrong program is a dropped
    # item wearing someone else's badge, and --list must be able to mean "all".
    parser.add_argument("--program", default=None, choices=sorted(PROGRAM_PREFIX))
    parser.add_argument(
        "--action", help="next smallest action (set on --open or with --note)"
    )
    parser.add_argument("--effort", help="S/M/L/XL descriptive range")
    parser.add_argument(
        "--depends-on", nargs="*", help="ids this new item is blocked by"
    )
    parser.add_argument(
        "--owner-gate", nargs="*", help="owner question ids blocking it"
    )
    parser.add_argument("--security-class", default="none")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--only-open", action="store_true")
    parser.add_argument("--catalog", default=None)
    parser.add_argument("--graph", default=None)
    parser.add_argument("--events", default=None)
    parser.add_argument("--now", default=None, help="ISO timestamp override (tests)")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog_file = Path(args.catalog) if args.catalog else cat.catalog_path()
    graph_file = Path(args.graph) if args.graph else cat.graph_path()
    events_file = Path(args.events) if args.events else cat.events_path()

    try:
        catalog = cat.load(catalog_file)
    except Exception as exc:
        print(f"FAILED:cc-close cannot read {catalog_file}: {exc}")
        return 1

    if args.list:
        for line in list_items(catalog, args.program, args.only_open):
            print(line)
        print(
            f"SUCCESS:cc-close listed open={len(cat.open_items(catalog))} total={len(cat.items(catalog))}"
        )
        return 0

    if not args.open and not args.item_id:
        print("FAILED:cc-close nothing to do: pass an item id, --open, or --list")
        return 1

    if args.open and not args.program:
        print(
            f"FAILED:cc-close --open needs --program (one of {sorted(PROGRAM_PREFIX)})"
        )
        return 1

    before, _ = val.validate(catalog)
    try:
        verb, payload = apply_change(catalog, args, _now(args.now))
    except (KeyError, ValueError) as exc:
        print(f"FAILED:cc-close {exc}")
        return 1

    after, stats = val.validate(catalog)
    introduced = _violation_keys(after) - _violation_keys(before)
    if introduced:
        for check, item_id, detail in sorted(introduced):
            print(f"  {check} {item_id}: {detail}")
        print(
            f"FAILED:cc-close this change would introduce {len(introduced)} violation(s); nothing written"
        )
        return 1

    if args.dry_run:
        print(f"SUCCESS:cc-close dry-run {verb} {payload.get('id')} (nothing written)")
        return 0

    cat.save(catalog, catalog_file)
    cat.save(cat.build_graph(catalog), graph_file)
    append_event({"ts": _stamp(_now(args.now)), "verb": verb, **payload}, events_file)
    print(
        f"SUCCESS:cc-close {verb} {payload.get('id')} open={stats['open']} total={stats['items']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
