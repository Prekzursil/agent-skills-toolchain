#!/usr/bin/env python3
"""Probe 1: rtv-pdr.js imports, validates, and fan-out width matches an independent count.

Two signals (catalog evidence_requirement):
  (1) import + validate_workflow is clean
  (2) FanOut.units length equals the syntactic parallel-array arity from
      count_fanout.py, which does not import the adapter
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "import-adapters"))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.spec import FanOut  # noqa: E402
from agentspec.validate import validate_workflow  # noqa: E402
from claude_saved_workflow import import_path, workflow_from_adapter_json  # noqa: E402
from count_fanout import parallel_array_widths  # noqa: E402

UNIT = "IMP-0160"
SRC = REPO / "workflows" / "rtv-pdr.js"
ART = REPO / "command-center" / "receipts" / "IMP-0160.json"
EXPECTED_WIDTH = 4


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')!r}")
    if "SUCCESS:IMP-0160" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    if not SRC.is_file():
        return fail("workflows/rtv-pdr.js missing")
    src = SRC.read_text(encoding="utf-8")
    result = import_path(SRC)
    wf = result.workflow
    viols = validate_workflow(wf)
    if viols:
        return fail("validate " + "; ".join(f"{v.id}:{v.message}" for v in viols))
    if result.violations:
        return fail("import violations " + "; ".join(result.violations))

    load_bearing = [e for e in result.ledger if e.load_bearing and not e.expressed]
    if load_bearing:
        return fail(
            "clean corpus leaked load-bearing losses "
            + json.dumps([e.to_json() for e in load_bearing])
        )

    fanouts = [n for n in wf.nodes if isinstance(n, FanOut)]
    if len(fanouts) != 1:
        return fail(f"fanout count {len(fanouts)} want=1")
    adapter_width = len(fanouts[0].unit_ids)
    adapter_widths = list(result.fanout_widths)
    independent_widths = parallel_array_widths(src)
    if adapter_width != EXPECTED_WIDTH:
        return fail(f"adapter width {adapter_width} want={EXPECTED_WIDTH}")
    if independent_widths != [EXPECTED_WIDTH]:
        return fail(f"independent widths {independent_widths} want=[{EXPECTED_WIDTH}]")
    if adapter_widths != independent_widths:
        return fail(
            f"width disagreement adapter={adapter_widths} independent={independent_widths}"
        )

    labels = {u.id for u in wf.units}
    for need in ("scope", "architect", "skeptic", "pragmatist", "critic", "synthesizer"):
        if need not in labels:
            return fail(f"missing unit {need}")

    cloned = workflow_from_adapter_json(wf.to_json())
    if validate_workflow(cloned):
        return fail("json round-trip validate")
    if cloned.to_json()["id"] != wf.id:
        return fail("json round-trip id")
    cloned_fan = [n for n in cloned.nodes if isinstance(n, FanOut)]
    if not cloned_fan or len(cloned_fan[0].unit_ids) != adapter_width:
        return fail("json round-trip lost fan-out")

    payload = {
        "probe": "probe1-roundtrip",
        "unit_id": UNIT,
        "pass": True,
        "imported": True,
        "validated": True,
        "adapter_fanout_width": adapter_width,
        "independent_fanout_width": independent_widths[0],
        "widths_agree": True,
        "units": sorted(labels),
        "name": getattr(result, "name", None) or wf.id,
        "ledger_load_bearing": 0,
        "source": "workflows/rtv-pdr.js",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"import_ok=True validate_ok=True fanout={adapter_width}/{independent_widths[0]}"
    )
    print(f"SUCCESS:{UNIT}-probe1 rtv-pdr.js import+validate fan-out width preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
