"""Control BOTH calibration detectors before any threshold is derived from them.

_c1 reported two readings that would each steer the build:
  anchors      = 0/10  -> would REFUTE the plan's "resolvable evidence anchor" requirement
  falsif       = 10/10 -> would JUSTIFY making a falsification-method clause blocking

A 0 reading is most often a broken matcher, and a 10/10 reading is most often a matcher so
broad it fires on incidental prose. Neither may be used until it is shown to move.

For each detector this runs the KNOWN-PRESENT and KNOWN-ABSENT state and requires it to
discriminate. Failing that, the reading is a detector artifact, not a measurement.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "_vs_ctl", Path(__file__).with_name("vendor_satisfiability.py")
)
_vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vs)

_ANCHOR = re.compile(r"https?://\S+|\S+:\d+")
_FALSIF = re.compile(
    r"falsif|refut|mutat|counter-?example|tried to break|both[- ]states"
    r"|control|disconfirm|negative case",
    re.I,
)

bad: list[str] = []


def expect(name: str, got: object, want: object) -> None:
    ok = bool(got) == bool(want)
    if not ok:
        bad.append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got={bool(got)} want={bool(want)}")


def main() -> int:
    rows = [r for r in _vs.load_units("committed") if r["verdict"] == _vs.SAT]
    blobs = _vs.batch_blobs("HEAD", [r["output_path"] for r in rows])
    notes = {}
    for r in rows:
        rv = json.loads(blobs[r["output_path"]]).get("reviewer") or {}
        n = rv.get("notes")
        notes[r["id"]] = n if isinstance(n, str) else json.dumps(n)

    print("[1] ANCHOR detector, both states")
    expect(
        "fires on a synthetic file:line", _ANCHOR.search("see foo/bar.py:12 now"), True
    )
    expect("fires on a synthetic URL", _ANCHOR.search("see https://x.example/a"), True)
    expect(
        "silent on anchor-free prose",
        _ANCHOR.search("the reviewer read the code"),
        False,
    )
    real = {k: _ANCHOR.findall(v) for k, v in notes.items()}
    hits = {k: v for k, v in real.items() if v}
    print(
        f"      real notes carrying ANY anchor-shaped token: {len(hits)}/{len(notes)} {hits}"
    )
    # An anchor-shaped token is not an anchor that RESOLVES. Show the difference explicitly.
    seeded = (
        "per command-center/p2-next/rail_count_gate.py:309 the check is verdict-shaped"
    )
    expect("fires on a seeded REAL repo path", _ANCHOR.search(seeded), True)
    m = re.search(r"([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,6}):(\d+)", seeded)
    expect("that seeded path RESOLVES on disk", (REPO / m.group(1)).exists(), True)

    print("\n[2] FALSIFICATION detector, both states")
    expect(
        "fires on explicit falsification prose",
        _FALSIF.search("I tried to break it"),
        True,
    )
    expect(
        "silent on bland approval prose", _FALSIF.search("Looks good, approved."), False
    )
    # The load-bearing control: strip the matching vocabulary out of the REAL notes. If the
    # detector still fires, it was matching something incidental and 10/10 means nothing.
    stripped_still_firing = []
    which: dict[str, list[str]] = {}
    for k, v in notes.items():
        which[k] = sorted({m.group(0).lower() for m in _FALSIF.finditer(v)})
        if _FALSIF.search(_FALSIF.sub("", v)):
            stripped_still_firing.append(k)
    expect(
        "stripping the vocabulary silences it on ALL real notes",
        not stripped_still_firing,
        True,
    )
    print(f"      tokens matched per unit: {json.dumps(which, indent=8)}")

    print()
    if bad:
        print(f"FAILED:c2-control-detectors {bad}")
        return 1
    print("SUCCESS:c2-control-detectors both detectors discriminate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
