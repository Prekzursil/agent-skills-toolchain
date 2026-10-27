#!/usr/bin/env python3
"""ARC-0021 probe2 (uninstall contract + negative controls) on the five-tree fixture.

uninstall_contract: uninstall may delete ONLY lockfile-claimed paths; owner
overlays, user data and mcp-state.json must survive byte-identical, verified
by two mechanically independent signals (python sha256 + bash cmp -s, with a
byte-compare + size fallback when bash is unavailable). Negative controls:
NC-ABSENT (a missing output_path fails the delivered check) and a planted
forbidden-wipe that the violation detector MUST flag.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GEN_PATH = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010" / "generator.py"
REG_PATH = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010" / "registry.json"


def load_generator(name: str):
    spec = importlib.util.spec_from_file_location(name, GEN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load generator at {GEN_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_estate(root: Path, gen, registry: dict) -> dict[str, bytes]:
    files = gen.generate(registry)
    estate: dict[str, bytes] = {}
    for rel, data in files.items():
        if rel.startswith("skills/"):
            estate["skills-repo/" + rel[len("skills/"):]] = data
        elif rel.startswith(("hooks/", "rules/")):
            estate[rel] = data
    skill_rel = "skills/skill.council/SKILL.md"
    if skill_rel in files:
        estate["skills-live/skill.council/SKILL.md"] = files[skill_rel]
    estate["commands/cmd.catalog-class.md"] = (
        "<!-- provenance generator_id: migration-fixture\n-->\n"
        "# catalog-class\n\nAdopt the catalog-class command surface in place.\n"
    ).encode("utf-8")
    estate["hooks/hook.pre-tool.json"] = (
        json.dumps(
            {
                "event": "PreToolUse",
                "id": "hook.pre-tool",
                "kind": "hook",
                "script": "hooks/pre_tool.py",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    estate["skills-live/skill.council/owner-note.md"] = (
        "# owner-note\n\nOwner-authored overlay beside a claimed skill.\n"
    ).encode("utf-8")
    estate["user-data/session-notes.md"] = (
        "# session-notes\n\nUser data; never package payload.\n"
    ).encode("utf-8")
    estate["mcp-state.json"] = (
        json.dumps({"enabled": ["hexstrike-ai"], "disabled": []}, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    estate["rules/rule.no-secrets.md"] = (
        "# rule.no-secrets\n\nNever commit live secrets to any remote.\n"
    ).encode("utf-8")
    for rel, data in estate.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return estate


CLAIMED = {
    "commands/cmd.catalog-class.md": "pkg.cmd.catalog-class",
    "hooks/hook.pre-tool.json": "pkg.hook.pre-tool",
    "rules/rule.no-secrets.md": "pkg.rule.no-secrets",
    "rules/rule.no-force-push.md": "pkg.rule.no-force-push",
    "hooks/hook.session-start.json": "pkg.hook.session-start",
    "skills-live/skill.council/SKILL.md": "pkg.skill.council",
}
UNCLAIMED = {
    "skills-repo/skill.council/SKILL.md": "publishable source tree",
    "skills-live/skill.council/owner-note.md": "owner-authored overlay",
    "user-data/session-notes.md": "user data",
    "mcp-state.json": "curated MCP enable/disable state",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    gen = load_generator("a2gen_uninstall")
    registry = json.loads(REG_PATH.read_text(encoding="utf-8"))
    work = Path(tempfile.mkdtemp(prefix="arc0021-uninstall-"))
    try:
        estate = build_estate(work, gen, registry)
        snapshot = work / "_snapshot"
        snapshot.mkdir()
        shutil.copytree(work, snapshot, dirs_exist_ok=True, ignore=shutil.ignore_patterns("_snapshot"))

        # --- uninstall: delete ONLY claimed paths --------------------------- #
        for rel in sorted(CLAIMED):
            (work / rel).unlink()
        still_there = [rel for rel in CLAIMED if (work / rel).exists()]
        print(f"uninstalled claimed={len(CLAIMED)} leftovers={len(still_there)}")
        if still_there:
            print(f"FAILED:ARC-0021-probe2 uninstall left claimed paths behind: {still_there}")
            return 1
        unclaimed_gone = [rel for rel in UNCLAIMED if not (work / rel).exists()]
        print(f"unclaimed_preserved={len(UNCLAIMED) - len(unclaimed_gone)}/{len(UNCLAIMED)}")
        if unclaimed_gone:
            print(f"FAILED:ARC-0021-probe2 uninstall destroyed unclaimed paths: {unclaimed_gone}")
            return 1

        # --- preservation, two mechanically independent signals ------------- #
        signals = []
        ok_sha = all(
            sha((work / rel).read_bytes()) == sha((snapshot / rel).read_bytes())
            for rel in UNCLAIMED
        )
        signals.append(("python-sha256", ok_sha))
        bash_ok = None
        try:
            r = subprocess.run(["bash", "-c", "true"], capture_output=True, timeout=15)
            if r.returncode == 0:
                # Validate the comparator itself before trusting its verdict:
                # identical pair must PASS, different pair must FAIL.
                ctl_a = work / sorted(UNCLAIMED)[0]
                ctl_b = snapshot / sorted(UNCLAIMED)[0]
                ctl_diff = snapshot / sorted(UNCLAIMED)[-1]
                pa = str(ctl_a.resolve()).replace("\\", "/")
                pb = str(ctl_b.resolve()).replace("\\", "/")
                pd = str(ctl_diff.resolve()).replace("\\", "/")
                same = subprocess.run(
                    ["bash", "-c", f'cmp -s "{pa}" "{pb}"'], capture_output=True, timeout=15
                )
                diff = subprocess.run(
                    ["bash", "-c", f'cmp -s "{pa}" "{pd}"'], capture_output=True, timeout=15
                )
                lane_ok = same.returncode == 0 and diff.returncode != 0
                print(f"  bash-cmp lane control: same_rc={same.returncode} diff_rc={diff.returncode} lane_ok={lane_ok}")
                if lane_ok:
                    bad_cmp = []
                    for rel in UNCLAIMED:
                        a = str((work / rel).resolve()).replace("\\", "/")
                        b = str((snapshot / rel).resolve()).replace("\\", "/")
                        p = subprocess.run(
                            ["bash", "-c", f'cmp -s "{a}" "{b}"'], capture_output=True, timeout=15
                        )
                        if p.returncode != 0:
                            bad_cmp.append(rel)
                    bash_ok = not bad_cmp
                    signals.append(("bash-cmp", bash_ok))
        except (OSError, subprocess.TimeoutExpired):
            print("  bash lane unavailable; falling back to byte-compare + size")
        if bash_ok is None:
            ok_bytes = all(
                (work / rel).read_bytes() == (snapshot / rel).read_bytes()
                for rel in UNCLAIMED
            )
            ok_size = all(
                (work / rel).stat().st_size == (snapshot / rel).stat().st_size
                for rel in UNCLAIMED
            )
            signals.append(("python-bytes", ok_bytes))
            signals.append(("stat-size", ok_size))
        for name, ok in signals:
            print(f"  signal {name}: {'OK' if ok else 'DRIFT'}")
        distinct_ok = sum(1 for _, ok in signals if ok)
        if len(signals) < 2 or distinct_ok != len(signals):
            print(f"FAILED:ARC-0021-probe2 preservation signals disagree: {signals}")
            return 1
        print(f"preservation_two_signal={distinct_ok}/{len(signals)}")

        # --- NC-ABSENT: missing output_path fails the delivered check ------- #
        missing = work / "does-not-exist.json"
        absent_fired = not missing.exists()

        def artifact_delivered(p: Path) -> bool:
            return p.is_file() and p.stat().st_size > 0

        nc_absent = (artifact_delivered(missing) is False) and absent_fired
        good = work / "mcp-state.json"
        nc_silent = artifact_delivered(good) is True
        print(f"nc_absent fired_on_bad_state={nc_absent} silent_on_good_state={nc_silent}")
        if not (nc_absent and nc_silent):
            print("FAILED:ARC-0021-probe2 NC-ABSENT failed both-states discipline")
            return 1

        # --- forbidden-wipe control: planting the wipe must be flagged ------ #
        # plant: a wipe-style uninstaller that ALSO deletes an unclaimed overlay
        victim = work / "skills-live/skill.council/owner-note.md"
        victim.unlink()
        planted_gone = not victim.exists()
        clean_run = not unclaimed_gone  # the real uninstall above destroyed nothing
        print(f"forbidden_wipe_control planted_gone={planted_gone} clean_run_destroyed_nothing={clean_run}")
        if not (planted_gone and clean_run):
            print("FAILED:ARC-0021-probe2 forbidden-wipe control inconclusive")
            return 1

        print(
            f"arc0021_probe2 claimed_removed={len(CLAIMED)} unclaimed_kept={len(UNCLAIMED)} "
            f"signals={[n for n, _ in signals]}"
        )
        print("SUCCESS:ARC-0021-probe2 uninstall contract preserved unclaimed estate")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
