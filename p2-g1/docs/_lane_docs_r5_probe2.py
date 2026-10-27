"""LANE DOCS round 5 -- probe 2. Independent signals on "is hooks/hooks.json a live entry point".

Probe 1's P4 (fixture-store natural experiment) came back 0 on BOTH arms. A control that
returns the same answer under both hypotheses is INERT -- it measured fixture shape, not the
ecosystem. It is discarded here rather than cited. This file replaces it with signals that
are mechanically independent of each other AND of probe 1.

  S1  Are the routing fixtures stub-only? If they carry no hooks dir for ANY of 83 plugins,
      P4's zero is explained by fixture shape and carries no information either way.
  S2  The file's own self-description -- does it claim to BE this plugin's hooks, and does it
      record a loader behaviour that could only be observed if something loads it?
  S3  LIVE, READ-ONLY: is the everything-claude-code plugin installed, and does IT ship the
      scripts/hooks tree this file points at? That settles ORIGIN.
  S4  LIVE, READ-ONLY: is agent-skills-toolchain installed as a plugin, and would its own
      plugin root resolve the 3 targets?

No credential file is read. No file is written outside docs/. Nothing is modified.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.path.expanduser("~"))
TARGETS = [
    "scripts/hooks/run-with-flags.js",
    "scripts/hooks/run-with-flags-shell.sh",
    "scripts/hooks/auto-tmux-dev.js",
]


def main() -> int:
    rep: dict[str, object] = {}

    # --- S1: explain P4's zero ---------------------------------------------------------
    store = (
        REPO
        / "platform"
        / "routing"
        / "fixtures"
        / "home"
        / ".claude"
        / "plugins"
        / "store"
    )
    roots = [pj.parents[1] for pj in store.glob("*/*/.claude-plugin/plugin.json")]
    rep["S1_fixture_plugin_roots"] = len(roots)
    with_any_hooks_dir = sum(1 for r in roots if (r / "hooks").is_dir())
    # What DO the fixture plugin dirs contain? If only .claude-plugin, they are stubs.
    entries: dict[str, int] = {}
    for r in roots:
        for child in r.iterdir():
            entries[child.name] = entries.get(child.name, 0) + 1
    rep["S1_fixture_roots_with_hooks_dir"] = with_any_hooks_dir
    rep["S1_fixture_child_entry_histogram"] = dict(
        sorted(entries.items(), key=lambda kv: -kv[1])[:8]
    )
    rep["S1_verdict"] = (
        "STUB-ONLY -> P4 zero is a fixture artifact, carries NO information"
        if with_any_hooks_dir == 0
        else "fixtures carry real hook dirs -> P4 zero would have been informative"
    )

    # --- S2: the file's own testimony ---------------------------------------------------
    hj = REPO / "hooks" / "hooks.json"
    data = json.loads(hj.read_text(encoding="utf-8"))
    desc = data.get("description", "")
    rep["S2_description"] = desc
    rep["S2_claims_to_be_this_plugins_hooks"] = "agent-skills-toolchain hooks" in desc
    rep["S2_records_a_loader_behaviour"] = bool(
        re.search(r"loads ZERO hooks from this plugin", desc)
    )
    rep["S2_has_schema_key"] = "$schema" in data

    # --- S3: ORIGIN. Is ECC installed live, and does it ship the tree? -------------------
    plug = HOME / ".claude" / "plugins"
    ecc_candidates = []
    if plug.is_dir():
        for base in [plug, plug / "marketplace", plug / "store"]:
            if not base.is_dir():
                continue
            for child in base.iterdir():
                if "everything-claude-code" in child.name:
                    ecc_candidates.append(child)
            # marketplace/store are two-level: <market>/<plugin>
            for child in base.glob("*/*"):
                if "everything-claude-code" in child.name:
                    ecc_candidates.append(child)
    rep["S3_ecc_roots_found"] = [str(c) for c in ecc_candidates]
    ecc_hits = []
    for c in ecc_candidates:
        present = [t for t in TARGETS if (c / t).exists()]
        if present:
            ecc_hits.append({"root": str(c), "targets_present": present})
    rep["S3_ecc_roots_shipping_the_targets"] = ecc_hits
    rep["S3_origin_settled"] = bool(ecc_hits)

    # --- S4: is THIS plugin installed live, and do its targets resolve? ------------------
    ast_candidates = []
    if plug.is_dir():
        for base in [plug, plug / "marketplace", plug / "store"]:
            if not base.is_dir():
                continue
            for child in list(base.iterdir()) + list(base.glob("*/*")):
                if child.is_dir() and "agent-skills-toolchain" in child.name:
                    ast_candidates.append(child)
    rep["S4_ast_plugin_roots_found"] = [str(c) for c in ast_candidates]
    ast_state = []
    for c in ast_candidates:
        ast_state.append(
            {
                "root": str(c),
                "has_hooks_json": (c / "hooks" / "hooks.json").is_file(),
                "targets_present": [t for t in TARGETS if (c / t).exists()],
                "targets_absent": [t for t in TARGETS if not (c / t).exists()],
            }
        )
    rep["S4_ast_installed_state"] = ast_state
    rep["S4_installed_as_plugin"] = bool(ast_candidates)

    print(json.dumps(rep, indent=2))
    print(
        "SUCCESS:docs-r5-probe2 "
        f"fixtures_stub_only={with_any_hooks_dir == 0} "
        f"origin_settled={rep['S3_origin_settled']} "
        f"ast_installed_as_plugin={rep['S4_installed_as_plugin']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
