#!/usr/bin/env python3
"""Named probe 1: program pane is read-only and renders live events/receipts.

Both-states: ProgramPane leaves the ledger bytes unchanged and refuses mutate
APIs; a planted writer that appends to EVENTS.jsonl changes the digest and
fails the same assertion.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))

from monitorcore.cockpit import EXISTING_PANE_IDS, PROGRAM_PANE_ID, Cockpit  # noqa: E402
from monitorcore.program_pane import ProgramPane, ReadOnlyPaneError  # noqa: E402
from monitorcore.readonly import ReadOnlyFS  # noqa: E402

LIVE_EVENT_ID = "evt-live-IMP-0450"
LIVE_RECEIPT_SENTINEL = "SENTINEL:FIXTURE-0450:LIVE"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_digests(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = _digest(path)
    return out


def _build_fixture(root: Path) -> None:
    events = root / "command-center" / "events" / "EVENTS.jsonl"
    receipts = root / "command-center" / "receipts"
    events.parent.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)
    events.write_text(
        json.dumps(
            {
                "id": LIVE_EVENT_ID,
                "unit_id": "IMP-0443",
                "state": "RESUME",
                "action": "ledger-append",
            },
            sort_keys=True,
        )
        + "\n"
        + json.dumps(
            {
                "id": "evt-prior",
                "unit_id": "IMP-0434",
                "state": "SUCCESS",
                "action": "receipt-write",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (receipts / "IMP-0434.json").write_text(
        json.dumps(
            {
                "unit_id": "IMP-0434",
                "state": "SUCCESS",
                "sentinel": LIVE_RECEIPT_SENTINEL,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _planted_writer(root: Path) -> None:
    events = root / "command-center" / "events" / "EVENTS.jsonl"
    with events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"id": "planted-write", "state": "MUTATED"}) + "\n")


def main() -> int:
    cockpit_ids = Cockpit(REPO).pane_ids()
    if PROGRAM_PANE_ID not in cockpit_ids:
        print("FAILED:IMP-0450-probe1 program pane not registered")
        return 1
    missing = [p for p in EXISTING_PANE_IDS if p not in cockpit_ids]
    if missing:
        print(f"FAILED:IMP-0450-probe1 inherited panes missing {missing}")
        return 1
    if Cockpit(REPO).is_control_plane(PROGRAM_PANE_ID):
        print("FAILED:IMP-0450-probe1 program pane claimed as control plane")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0450-p1-") as tmp:
        root = Path(tmp)
        _build_fixture(root)
        before = _tree_digests(root)
        pane = ProgramPane(root)
        rendered = pane.render()
        capture = HERE / "pane-capture.txt"
        capture.write_text(rendered, encoding="utf-8", newline="\n")

        refused = []
        for call, kwargs in (
            ("mutate_append_event", {"payload": {"id": "should-not-land"}}),
            ("mutate_write_receipt", {"unit_id": "IMP-0450", "body": {"state": "X"}}),
            ("dispatch_unit", {"unit_id": "IMP-0450"}),
        ):
            try:
                getattr(pane, call)(**kwargs)
                print(f"FAILED:IMP-0450-probe1 {call} did not refuse")
                return 1
            except ReadOnlyPaneError as exc:
                refused.append(str(exc))

        try:
            pane.fs.open(pane.events_path, "a")
            print("FAILED:IMP-0450-probe1 ReadOnlyFS allowed append")
            return 1
        except ReadOnlyPaneError:
            refused.append("open-append")

        after_good = _tree_digests(root)
        if after_good != before:
            print("FAILED:IMP-0450-probe1 ledger mutated by ProgramPane")
            print(json.dumps({"before": before, "after": after_good}, indent=2)[:2000])
            return 1

        live_ok = LIVE_EVENT_ID in rendered and LIVE_RECEIPT_SENTINEL in rendered
        if not live_ok:
            print("FAILED:IMP-0450-probe1 pane did not display live fixture data")
            print(rendered[:2000])
            return 1
        if "count=2" not in rendered or "count=1" not in rendered:
            print("FAILED:IMP-0450-probe1 live counts missing from pane")
            print(rendered[:2000])
            return 1

        _planted_writer(root)
        after_bad = _tree_digests(root)
        fired_on_bad = after_bad != before
        if not fired_on_bad:
            print("FAILED:IMP-0450-probe1 planted writer did not change digest")
            return 1

    result = {
        "probe": "probe1-readonly",
        "unit_id": "IMP-0450",
        "pass": True,
        "inherited_panes": list(EXISTING_PANE_IDS),
        "program_pane_registered": True,
        "program_pane_is_control_plane": False,
        "refused_mutations": len(refused),
        "ledger_unchanged_on_good_pane": True,
        "planted_writer_changed_digest": True,
        "live_event_id_in_render": True,
        "live_receipt_sentinel_in_render": True,
        "capture": "command-center/p2-wave/probes/IMP-0450/pane-capture.txt",
        "fs_class": ReadOnlyFS.__name__,
    }
    print(json.dumps(result, sort_keys=True))
    print("ledger_unchanged=True planted_writer_detected=True live_render=True")
    print("SUCCESS:IMP-0450-probe1 read-only program pane with live data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
