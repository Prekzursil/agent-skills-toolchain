"""Read-only live render: pane displays live data and cannot mutate state (IMP-0450)."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
from monitorcore.monitorcore.program_pane import PROGRAM_PANE_ID, ProgramPane, ReadOnlyPaneError




def tree_state(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(
                p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return out


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "command-center" / "events").mkdir(parents=True)
        (root / "command-center" / "receipts").mkdir(parents=True)
        events = root / "command-center" / "events" / "EVENTS.jsonl"
        events.write_text(
            json.dumps({"id": "evt-live-IMP-0450", "kind": "RESUME"}) + "\n" +
            json.dumps({"id": "evt-prior", "kind": "SUCCESS"}) + "\n",
            encoding="utf-8")
        (root / "command-center" / "receipts" / "IMP-0434.json").write_text(
            json.dumps({"id": "IMP-0434", "state": "SUCCESS",
                        "sentinel": "SENTINEL:FIXTURE-0450:LIVE"}), encoding="utf-8")

        pane = ProgramPane(root)
        before = tree_state(root)
        rendered = pane.render()
        assert "evt-live-IMP-0450" in rendered, "live event id missing from render"
        assert "IMP-0434" in rendered, "receipt missing from render"
        assert "events count=2" in rendered and "receipts count=1" in rendered

        mutations = 0
        for call in ("mutate_append_event", "mutate_write_receipt", "dispatch_unit"):
            try:
                getattr(pane, call)()
            except ReadOnlyPaneError:
                mutations += 1
        assert mutations == 3, "all three mutation surfaces must refuse"

        after = tree_state(root)
        assert before == after, "pane mutated program state"
        capture = (
            "=== cockpit pane: program (read-only) ===\n"
            "mutates_program_state=False\n"
            "control_plane=False\n"
            "pane_id=%s\n\n%s" % (PROGRAM_PANE_ID, rendered))

    out_path = HERE / "pane-capture.txt"
    out_path.write_text(capture, encoding="utf-8", newline="\n")

    print(json.dumps({
        "probe": "probe1-readonly",
        "unit_id": "IMP-0450",
        "pane_id": PROGRAM_PANE_ID,
        "live_event_rendered": True,
        "receipt_rendered": True,
        "mutations_refused": mutations,
        "filesystem_unchanged": True,
        "capture": "command-center/p2-wave/probes/IMP-0450/pane-capture.txt",
        "sentinel": "SENTINEL:IMP-0450:COCKPIT-SINGLE-PLANE",
    }, indent=2))
    print("SUCCESS:IMP-0450-probe1 pane renders live data read-only; all mutations refuse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
