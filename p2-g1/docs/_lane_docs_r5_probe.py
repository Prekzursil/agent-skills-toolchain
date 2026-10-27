"""LANE DOCS round 5 -- settle R4 §4's UNVERIFIED claim about hooks/hooks.json.

R4 §4 left this inline, tagged UNVERIFIED [likely 55-80%]:

    that `hooks/hooks.json` is live-wired as *this* plugin's hook entry point (which would
    make a fresh plugin install run 24 hooks pointing at nothing) rather than a vendored
    snapshot of the user's merged live config.

    Settling experiment: check whether `agent-self/harness/install.py` deploys
    `hooks/hooks.json` as an entry point, and whether `${CLAUDE_PLUGIN_ROOT}` resolves to
    the repo root for it.

TWO HYPOTHESES, stated before the probe so the controls can be checked for inertness:

  H1  hooks/hooks.json sits at THIS plugin's conventional entry-point path, so installing
      agent-skills-toolchain loads it and wires N hooks at ${CLAUDE_PLUGIN_ROOT}/scripts/hooks/*
      -- a directory this repo does not ship. Fresh install => N dead hooks.
  H2  it is an inert vendored snapshot that no loader reaches.

The discriminator must give DIFFERENT answers under H1 and H2. A probe that merely proves the
file parses is inert (this repo measured that exact failure four times on manifest["events"][ev]).

Run:  python docs/_lane_docs_r5_probe.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.path.expanduser("~"))

PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"


def sh(*args: str) -> str:
    """Run a git command in REPO and return stdout (empty string on failure)."""
    try:
        out = subprocess.run(
            args, cwd=REPO, capture_output=True, text=True, timeout=120, check=False
        )
        return out.stdout
    except Exception:  # noqa: BLE001 - a failed probe must not crash the report
        return ""


def commands_of(path: Path) -> list[str]:
    """Every hook 'command' string in a hooks.json, at any nesting depth."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                if key == "command" and isinstance(val, str):
                    found.append(val)
                else:
                    walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return found


def plugin_root_targets(command: str) -> list[str]:
    """Paths a command resolves RELATIVE TO THE PLUGIN ROOT.

    Only counts the ${CLAUDE_PLUGIN_ROOT}/<path> form. A bare 'scripts/hooks/foo.js' argument
    is a run-with-flags *label*, not a path the loader resolves, so counting it would inflate
    the number -- the 3x-overclaim shape R4 §5 already recorded once.
    """
    return re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)", command)


def tracked(rel: str) -> bool:
    return bool(sh("git", "ls-files", "--error-unmatch", rel).strip())


def main() -> int:
    report: dict[str, object] = {}

    # --- P1: is this repo a plugin at all, and where is its root? --------------------
    manifest = REPO / ".claude-plugin" / "plugin.json"
    report["P1_plugin_manifest_at_repo_root"] = manifest.is_file()
    report["P1_plugin_name"] = (
        json.loads(manifest.read_text(encoding="utf-8")).get("name")
        if manifest.is_file()
        else None
    )
    # The manifest declares NO component paths -> components are found BY CONVENTION.
    if manifest.is_file():
        keys = sorted(json.loads(manifest.read_text(encoding="utf-8")).keys())
        report["P1_manifest_keys"] = keys
        report["P1_manifest_declares_hooks_path"] = "hooks" in keys

    # --- P2: the entry-point file and what it points at ------------------------------
    hooks_json = REPO / "hooks" / "hooks.json"
    report["P2_hooks_json_at_conventional_path"] = hooks_json.is_file()
    cmds = commands_of(hooks_json)
    report["P2_total_command_entries"] = len(cmds)

    targets: list[str] = []
    for cmd in cmds:
        targets.extend(plugin_root_targets(cmd))
    uniq = sorted(set(targets))
    report["P2_distinct_plugin_root_targets"] = len(uniq)
    present = [t for t in uniq if (REPO / t).exists()]
    absent = [t for t in uniq if not (REPO / t).exists()]
    report["P2_targets_present_in_repo"] = present
    report["P2_targets_absent_from_repo"] = absent
    report["P2_n_absent"] = len(absent)

    # --- P3: the ownership tell -------------------------------------------------------
    # If the file were authored FOR this plugin, nothing in it would name a different
    # plugin. Search its own bytes for a foreign plugin root.
    raw = hooks_json.read_text(encoding="utf-8") if hooks_json.is_file() else ""
    foreign = sorted(set(re.findall(r"\.claude/plugins/([A-Za-z0-9._@-]+)", raw)))
    report["P3_foreign_plugin_roots_named_inside"] = foreign
    report["P3_self_name_appears"] = "agent-skills-toolchain" in raw

    # --- P4: CONTROL. Does convention-based discovery actually hold in this ecosystem? -
    # Natural experiment: the repo vendors ~85 REAL installed plugins as routing fixtures.
    # Under H1 (convention discovery is real) many carry hooks/hooks.json at their root while
    # their plugin.json declares no hooks path. Under H2 (explicit declaration required)
    # plugins carrying hooks would declare them. These give DIFFERENT counts -> not inert.
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
    conv_yes = 0  # has hooks/hooks.json, manifest does NOT declare a hooks path
    conv_declared = 0  # has hooks/hooks.json AND manifest declares a hooks path
    examined = 0
    exemplars: list[str] = []
    if store.is_dir():
        for pj in store.glob("*/*/.claude-plugin/plugin.json"):
            proot = pj.parents[1]
            examined += 1
            hj = proot / "hooks" / "hooks.json"
            if not hj.is_file():
                continue
            try:
                pdata = json.loads(pj.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if "hooks" in pdata:
                conv_declared += 1
            else:
                conv_yes += 1
                if len(exemplars) < 5:
                    exemplars.append(proot.name)
    report["P4_fixture_plugins_examined"] = examined
    report["P4_hooks_by_convention_undeclared"] = conv_yes
    report["P4_hooks_explicitly_declared"] = conv_declared
    report["P4_exemplars"] = exemplars

    # --- P5: POSITIVE CONTROL. A known-good plugin entry point in this very repo. -------
    # metaswarm is a vendored plugin whose hooks.json references ${CLAUDE_PLUGIN_ROOT}/... and
    # whose targets EXIST. If the resolver reports 0-absent for metaswarm and N-absent for the
    # root plugin, the resolver discriminates; if it reported "all absent" for both it would be
    # a broken matcher, not a finding.
    ms = REPO / "tools" / "editor" / "metaswarm" / "hooks" / "hooks.json"
    ms_cmds = commands_of(ms)
    ms_targets = sorted({t for c in ms_cmds for t in plugin_root_targets(c)})
    ms_root = REPO / "tools" / "editor" / "metaswarm"
    ms_absent = [t for t in ms_targets if not (ms_root / t).exists()]
    report["P5_control_metaswarm_targets"] = len(ms_targets)
    report["P5_control_metaswarm_absent"] = ms_absent
    report["P5_control_discriminates"] = (len(ms_targets) > 0) and (len(ms_absent) == 0)

    # --- P6: is the referenced tree in VCS at all? -------------------------------------
    report["P6_scripts_hooks_tracked_files"] = len(
        [ln for ln in sh("git", "ls-files", "scripts/hooks").splitlines() if ln.strip()]
    )
    report["P6_scripts_dir_exists_in_worktree"] = (REPO / "scripts" / "hooks").exists()

    # --- P7: the mirror ---------------------------------------------------------------
    mirror = REPO / "agent-self" / "config" / "hooks" / "hooks.json"
    report["P7_mirror_exists"] = mirror.is_file()
    if mirror.is_file() and hooks_json.is_file():
        report["P7_mirror_byte_identical"] = (
            mirror.read_bytes() == hooks_json.read_bytes()
        )

    # --- P8: does install.py deploy it as an entry point? ------------------------------
    inst = REPO / "agent-self" / "harness" / "install.py"
    if inst.is_file():
        text = inst.read_text(encoding="utf-8", errors="replace")
        report["P8_install_py_mentions_repo_hooks_json"] = bool(
            re.search(r"hooks/hooks\.json|hooks\\\\hooks\.json", text)
        )
        report["P8_install_py_codex_hooks_target"] = bool(
            re.search(r'\.codex["\']?\s*/\s*["\']hooks\.json', text)
        )

    print(json.dumps(report, indent=2))

    # Terminal state (AGENTS.md §4).
    ok = (
        report.get("P1_plugin_manifest_at_repo_root")
        and report.get("P2_hooks_json_at_conventional_path")
        and report.get("P5_control_discriminates")
    )
    n_absent = report.get("P2_n_absent", -1)
    if not ok:
        print("FAILED:docs-r5-probe precondition or control failed", file=sys.stderr)
        return 1
    print(
        f"SUCCESS:docs-r5-probe plugin_root_targets_absent={n_absent} "
        f"convention_exemplars={report.get('P4_hooks_by_convention_undeclared')} "
        f"control_metaswarm_absent={len(report.get('P5_control_metaswarm_absent', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
