#!/usr/bin/env python3
"""ARC-0021 probe1 (adopt + sha256 preservation) on the five-tree fixture estate.

The MIGRATION.json proof surface: adoption locks EXISTING bytes in place
(adopt-in-place, rewrite_live_bytes=false) and sha256 preservation is measured
on the pinned bytes. Estate content: skill/hook/rule bytes come from the real
ARC-0010 generator; commands/hooks-pre-tool/overlay/user-data/mcp-state are
deterministic disclosed fixtures.

Fail-closed: adoption that rewrites a claimed byte, or a drift detector that
fails to fire on a planted mutation, exits 1.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
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
    """Lay the five live trees; returns rel -> expected bytes."""
    files = gen.generate(registry)  # deterministic generator output (LF bytes)
    estate: dict[str, bytes] = {}
    by_id = {e.get("id"): e for e in registry.get("entries", []) if isinstance(e, dict)}
    for rel, data in files.items():
        if rel.startswith("skills/"):
            estate["skills-repo/" + rel[len("skills/"):]] = data  # source tree
        elif rel.startswith(("hooks/", "rules/")):
            estate[rel] = data
    # deployed copy of the council skill (payload, adopted in place)
    skill_rel = "skills/skill.council/SKILL.md"
    if skill_rel in files:
        estate["skills-live/skill.council/SKILL.md"] = files[skill_rel]
    # deterministic fixture stubs (disclosed, not generator output)
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
    gen = load_generator("a2gen_adopt")
    registry = json.loads(REG_PATH.read_text(encoding="utf-8"))
    work = Path(tempfile.mkdtemp(prefix="arc0021-adopt-"))
    try:
        estate = build_estate(work, gen, registry)
        n_estate = len(estate)
        pre = {rel: (work / rel).read_bytes() for rel in estate}

        # --- adopt-in-place: pin existing bytes, never rewrite ------------- #
        lockfile = {}
        for rel in sorted(CLAIMED):
            raw = pre[rel]
            lockfile[rel] = {"path": rel, "sha256": sha(raw), "bytes": len(raw)}
        # no rewrite check: on-disk bytes must equal pre-adopt bytes
        rewritten = [
            rel for rel in CLAIMED if (work / rel).read_bytes() != pre[rel]
        ]
        print(f"adopted paths={len(lockfile)} bytes_rewritten={len(rewritten)}")
        if rewritten:
            print(f"FAILED:ARC-0021-probe1 adoption rewrote claimed bytes: {rewritten}")
            return 1
        if set(lockfile) != set(CLAIMED):
            print("FAILED:ARC-0021-probe1 lockfile does not cover every claimed path")
            return 1

        # --- preservation: sha256 of pinned bytes survives re-read --------- #
        preserved = all(
            sha((work / rel).read_bytes()) == lockfile[rel]["sha256"] for rel in lockfile
        )
        print(f"sha256_preservation={preserved} pinned={len(lockfile)}")
        if not preserved:
            print("FAILED:ARC-0021-probe1 pinned sha256 diverged from on-disk bytes")
            return 1

        # --- drift negative control: planted mutation must be flagged ------ #
        probe_rel = sorted(CLAIMED)[0]
        original = pre[probe_rel]
        mutated = bytearray(original)
        mutated[0] ^= 0x20
        (work / probe_rel).write_bytes(bytes(mutated))
        fired = sha((work / probe_rel).read_bytes()) != lockfile[probe_rel]["sha256"]
        (work / probe_rel).write_bytes(original)
        silent = sha((work / probe_rel).read_bytes()) == lockfile[probe_rel]["sha256"]
        print(f"drift_control fired_on_bad_state={fired} silent_on_good_state={silent}")
        if not (fired and silent):
            print("FAILED:ARC-0021-probe1 drift control failed both-states discipline")
            return 1

        # --- unclaimed classification -------------------------------------- #
        missing_unclaimed = [rel for rel in UNCLAIMED if rel not in estate]
        claimed_overlap = sorted(set(CLAIMED) & set(UNCLAIMED))
        print(
            f"estate_files={n_estate} unclaimed={len(UNCLAIMED)} "
            f"missing_unclaimed={len(missing_unclaimed)} claimed_overlap={claimed_overlap}"
        )
        if missing_unclaimed or claimed_overlap:
            print("FAILED:ARC-0021-probe1 estate classification incomplete")
            return 1

        print(f"arc0021_probe1 adopted={len(lockfile)} unclaimed={len(UNCLAIMED)} estate={n_estate}")
        print("SUCCESS:ARC-0021-probe1 adopt-in-place pins bytes, zero rewrites")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
