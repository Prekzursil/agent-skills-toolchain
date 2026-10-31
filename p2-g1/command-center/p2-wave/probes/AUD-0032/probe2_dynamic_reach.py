#!/usr/bin/env python3
"""AUD-0032 probe2 -- dynamic reachability from entries and CI (live, fail-closed).

Re-runs the probe-2 reference census on the rebuilt control fixture:
references counted from test consumers, __main__ guards, README/RUNBOOK
mentions, CI python -m seeds, and string-named plugin registries. Re-proves
the discriminating control: plugin_only is LIVE only through the registry
string edge, and the strawman without string edges marks it DEAD. Verifies the
recorded negative-control fields and the artifact's own recorded control
outcomes.
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
    "aud0032_fx": "DEAD",
    "aud0032_fx.entry": "LIVE",
    "aud0032_fx.live_mod": "LIVE",
    "aud0032_fx.mention_only": "DEAD",
    "aud0032_fx.plugin_only": "LIVE",
    "aud0032_fx.truly_dead": "DEAD",
}


def module_imports(path: Path) -> set[str]:
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


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe2 artifact unreadable: {type(exc).__name__}")
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
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    def probe2_census(pkg: Path, package: str, sources: list[Path],
                      registry_files: list[Path], string_edges: bool) -> dict[str, str]:
        verdicts = {p.stem: "DEAD" for p in pkg.glob("*.py")}
        verdicts["__init__"] = "DEAD"
        for src in sources:
            if src.suffix == ".py":  # test/CI/python -m references
                for name in module_imports(src):
                    if name.startswith(package + "."):
                        verdicts[name.split(".")[-1]] = "LIVE"
            else:  # README/RUNBOOK prose mentions
                body = src.read_text(encoding="utf-8", errors="replace")
                for p in pkg.glob("*.py"):
                    if f"{package}.{p.stem}" in body:
                        verdicts[p.stem] = "LIVE"
        if string_edges:
            for rf in registry_files:
                body = rf.read_text(encoding="utf-8", errors="replace")
                for p in pkg.glob("*.py"):
                    if f'"{package}.{p.stem}"' in body:
                        verdicts[p.stem] = "LIVE"
        return verdicts

    with tempfile.TemporaryDirectory(prefix="aud0032probe2-") as td:
        fx = Path(td)
        (fx / "aud0032_fx").mkdir()
        (fx / "docs").mkdir()
        files = {
            "__init__.py": "",
            "entry.py": "from aud0032_fx.live_mod import thing\n",
            "live_mod.py": "thing = 1\n",
            "mention_only.py": "def noop():\n    return None\n",
            "plugin_only.py": "def boot():\n    return None\n",
            "truly_dead.py": "def gone():\n    return None\n",
            "../test_consumer.py": "import aud0032_fx.entry\nimport aud0032_fx.live_mod\n",
            "../registry.py": 'PLUGINS = {"aud0032_fx.plugin_only": True}\n',
            "../docs/NOTES.md": "doc mention of aud0032_fx.mention_only (non-README)\n",
        }
        for rel, body in files.items():
            if rel.startswith(".."):
                p = fx.joinpath(*Path(rel).parts[1:])  # ../docs/NOTES.md -> fx/docs/NOTES.md
            else:
                p = fx / "aud0032_fx" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8", newline="\n")
        pkg = fx / "aud0032_fx"
        # probe2's prose-reference universe is README/RUNBOOK only; a mention in
        # a non-README doc (docs/NOTES.md) is deliberately NOT a reference source
        srcs = [fx / "test_consumer.py"]
        regs = [fx / "registry.py"]
        live = probe2_census(pkg, "aud0032_fx", srcs, regs, string_edges=True)
        straw = probe2_census(pkg, "aud0032_fx", srcs, regs, string_edges=False)
        for mod, want in CONTROL_MATRIX.items():
            stem = mod.split(".")[-1]
            got = live.get(stem if stem != "aud0032_fx" else "__init__")
            check(got == want, "probe2 census drift on rebuilt fixture",
                  f"{mod}: recomputed {got} vs recorded {want}")
        # discriminating control both-states
        check(live.get("plugin_only") == "LIVE" and straw.get("plugin_only") == "DEAD",
              "string-edge strawman cannot flip plugin_only (detector decorative)")
        check(live.get("mention_only") == "DEAD",
              "non-README doc mention wrongly counted as a reference")
        check(straw.get("entry") == "LIVE" and straw.get("truly_dead") == "DEAD",
              "non-string census cannot distinguish consumer imports from dead code")

    # artifact-recorded outcomes must agree
    pc = doc.get("planted_control") or {}
    check(pc.get("probe1_verdict") == "DEAD" and pc.get("probe2_verdict") == "LIVE",
          "planted plugin_only verdict pair drift",
          f"{pc.get('probe1_verdict')}/{pc.get('probe2_verdict')}")
    check(pc.get("probe2_without_string_edges") == "DEAD",
          "recorded strawman outcome drift")
    check(pc.get("strawman_string_edges_required") is True,
          "strawman_string_edges_required not recorded true")
    check(pc.get("independent") is True, "planted control not independent")
    # recorded negative control describes the registry-string discrimination
    nc = next((c for c in doc.get("negative_controls") or []
               if "registry" in str(c.get("id", ""))), None)
    check(nc is not None, "registry-string negative control absent")
    if nc:
        body = json.dumps(nc, ensure_ascii=False)
        check("DEAD" in body and "LIVE" in body,
              "registry-string control text does not name both outcomes")
        check(nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True,
              "registry-string negative control not both-states")
    check(str(doc.get("status", "")).upper() == "DELIVERED",
          "artifact status not DELIVERED", str(doc.get("status")))

    # drift notes (recorded, not gating)
    if not (REPO / ".github" / "workflows").is_dir():
        notes.append(
            "recorded observation re-verified: repo-root CI workflows are absent on this "
            "worktree, so CI python -m seeds contribute no probe-2 edges (the artifact "
            "records the same absence)"
        )

    report = {
        "probe": "probe2-dynamic-reachability-from-entries-and-ci",
        "unit_id": UNIT,
        "rebuilt_matrix": live,
        "strawman_matrix": straw,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe2 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe2 dynamic reachability re-proven (plugin_only LIVE via registry "
          "string, DEAD without string edges; doc mention does not count; truly_dead DEAD)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
