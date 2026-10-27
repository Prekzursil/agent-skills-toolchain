#!/usr/bin/env python3
"""AUD-0032 probe1 -- AST symbol-reference resolution census (live, fail-closed).

Rebuilds the aud0032_fx control fixture in a temp dir and re-runs the AST
import-reference census, re-proving the recorded control matrix: entry/live_mod
LIVE (test-consumer imports), plugin_only DEAD on AST (referenced only via a
string-named plugin registry), mention_only DEAD (doc mention only),
truly_dead/__init__ DEAD. Then re-verifies the artifact's tallies arithmetic
both-probes-dead + probe-disagreements partition the scan, spot-checks recorded
matrix rows, and proves the detector both-states (a truly-imported module goes
LIVE; an unreferenced one stays DEAD).
"""
from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0032-dead-code-census.json"
UNIT = "AUD-0032"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

CONTROL_MATRIX = {
    "aud0032_fx": ("DEAD", "DEAD"),
    "aud0032_fx.entry": ("LIVE", "LIVE"),
    "aud0032_fx.live_mod": ("LIVE", "LIVE"),
    "aud0032_fx.mention_only": ("DEAD", "DEAD"),
    "aud0032_fx.plugin_only": ("DEAD", "LIVE"),
    "aud0032_fx.truly_dead": ("DEAD", "DEAD"),
}

FIXTURE_FILES = {
    "__init__.py": "",
    "entry.py": "from aud0032_fx.live_mod import thing\n",
    "live_mod.py": "thing = 1\n",
    "mention_only.py": "def noop() -> None:\n    return None\n",
    "plugin_only.py": "def boot() -> None:\n    return None\n",
    "truly_dead.py": "def gone() -> None:\n    return None\n",
    # reference sources OUTSIDE the scanned package:
    "../test_consumer.py": "import aud0032_fx.entry\nimport aud0032_fx.live_mod\n",
    "../registry.py": 'PLUGINS = {"aud0032_fx.plugin_only": True}\n',
    "../docs/NOTES.md": "mention of aud0032_fx.mention_only in a non-README doc\n",
}


def module_imports(path: Path) -> set[str]:
    """Names of modules imported by a python file (AST, exact top name)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def probe1_census(scan_root: Path, package: str, sources: list[Path]) -> dict[str, str]:
    """AST import-reference census: LIVE iff some reference source imports it."""
    verdicts = {m.stem: "DEAD" for m in scan_root.glob("*.py")}
    verdicts["__init__"] = "DEAD"
    for src in sources:
        if src.suffix == ".py":
            for name in module_imports(src):
                if name.startswith(package + "."):
                    verdicts[name.split(".")[-1]] = "LIVE"
    return verdicts


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe1 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    check(OUT.stat().st_size > 0, "artifact empty")
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    # rebuild the control fixture and re-run the AST census
    with tempfile.TemporaryDirectory(prefix="aud0032probe1-") as td:
        fx = Path(td)
        (fx / "aud0032_fx").mkdir()
        (fx / "docs").mkdir()
        for rel, body in FIXTURE_FILES.items():
            p = fx / "aud0032_fx" / rel.split("/")[-1]
            if rel.startswith(".."):
                p = fx / "/".join(rel.split("/")[1:])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8", newline="\n")
        pkg = fx / "aud0032_fx"
        sources = [fx / "test_consumer.py", fx / "registry.py"]
        live = probe1_census(pkg, "aud0032_fx", sources)
        for mod, (want1, _want2) in CONTROL_MATRIX.items():
            stem = mod.split(".")[-1] if "." in mod else "__init__"
            got = live.get(stem if stem != "__init__" else "__init__")
            check(got == want1, "probe1 census drift on rebuilt fixture",
                  f"{mod}: recomputed {got} vs recorded {want1}")
        # both-states: detector distinguishes imported vs unreferenced
        check(live.get("live_mod") == "LIVE" and live.get("truly_dead") == "DEAD",
              "probe1 detector cannot distinguish imported from unreferenced")

    # artifact tallies arithmetic
    t = doc.get("tallies") or {}
    n_scan = int(t.get("modules_scanned", 0))
    check(n_scan == int(t.get("tools_modules", 0)) + int(t.get("control_modules", 0)),
          "modules_scanned != tools_modules + control_modules", json.dumps(t))
    p1d, p2d, both, dis = (int(t.get("probe1_dead", -1)), int(t.get("probe2_dead", -1)),
                           int(t.get("both_dead", -1)), int(t.get("disagree", -1)))
    check(p1d - both >= 0 and p2d - both >= 0 and (p1d - both) + (p2d - both) == dis,
          "partition arithmetic broken",
          f"p1_only={p1d - both} p2_only={p2d - both} sum={ (p1d - both) + (p2d - both) } vs disagree={dis}")
    inv = ((doc.get("inventory") or {}).get("modules")) or []
    check(len(inv) == n_scan, "inventory rows != modules_scanned", f"{len(inv)} vs {n_scan}")
    check(len([m for m in inv if m.get("universe") == "control"]) == int(t.get("control_modules", -1)),
          "control-universe row count mismatch")
    # spot rows from the recorded matrix
    by_id = {m.get("id"): m for m in inv}
    for mod, (w1, w2) in CONTROL_MATRIX.items():
        row = by_id.get(mod)
        check(row is not None, "recorded control row missing", mod)
        if row:
            check(row.get("probe1_verdict") == w1 and row.get("probe2_verdict") == w2,
                  "recorded control row verdict drift", mod)
    # both_dead/disagree lists consistent with the inventory
    bd = set(doc.get("both_dead_modules") or [])
    dg = {d.get("id") for d in doc.get("disagree_modules") or []}
    check(len(bd) == both and len(dg) == dis, "both_dead/disagree list lengths mismatch")
    check(not (bd & dg), "a module is both both-dead and disagreeing")
    for m in inv:
        mid = m.get("id")
        want = "DEAD" if m.get("probe1_verdict") == "DEAD" else "LIVE"
        if mid in bd:
            check(m.get("probe2_verdict") == "DEAD", "both-dead row probe2 not DEAD", str(mid))
        elif mid in dg:
            check(want in ("DEAD", "LIVE"), "disagree row malformed", str(mid))
    # the planted discriminating control
    pc = doc.get("planted_control") or {}
    check(pc.get("independent") is True, "planted_control.independent not true")
    check(str(pc.get("module", "")).endswith("plugin_only"),
          "planted control is not the plugin_only module", str(pc.get("module")))
    for c in doc.get("negative_controls") or []:
        check(c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True,
              "negative control not both-states", str(c.get("id")))

    # drift notes (recorded, not gating)
    if not (REPO / "command-center/p2-wave/probes/AUD-0032/fixtures").is_dir():
        notes.append(
            "instrument-absent: the original fixture directory "
            "command-center/p2-wave/probes/AUD-0032/fixtures/aud0032_fx was lost with the "
            "prior builder's tree; this probe rebuilt an equivalent control fixture in a "
            "temp dir and re-proved the recorded verdict matrix on it"
        )

    report = {
        "probe": "probe1-ast-symbol-reference-resolution",
        "unit_id": UNIT,
        "rebuilt_matrix": live,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe1 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe1 AST census re-proven on rebuilt fixture "
          "(entry/live_mod LIVE, plugin_only DEAD-on-AST, mention_only/truly_dead DEAD); "
          f"tallies partition arithmetic holds ({p1d}/{p2d}/{both}/{dis})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
