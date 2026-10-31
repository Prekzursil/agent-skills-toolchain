#!/usr/bin/env python3
# REL-0017 hand-to-plugin migration drill (rebuilt 2026-10-25, shard16 resume).
# Rebuilt from the closing receipt recorded design. Policy encoded:
#   BYTE-IDENTICAL -> skip; EOL-ONLY -> skip (honest vs naive raw compare);
#   SOURCE-ONLY -> create into the plugin layout; BOTH-UNIQUE -> refuse by
#   default, merge only for the plugin.json allowlist (preserve source-unique
#   listings AND plugin-only paths); a create landing on an already-present
#   owner-authored target is CAUGHT and refused (planted owner file control).
#   Inverses: create_file -> delete_file ONLY within the installer created_set;
#   overwrite_file -> restore_from_backup. Isolation: refuse to run against
#   Path.home()/.claude or the frozen fixtures/captured original.
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

MERGE_ALLOW = {"plugin.json"}


class Refusal(Exception):
    pass


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    return sha_bytes(Path(p).read_bytes())


def tree_hashes(root: Path):
    return {p.relative_to(root).as_posix(): sha_bytes(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def build_captured(dest: Path):
    # Frozen captured layout: hand/ (source) + plugin/ (target).
    hand = dest / "hand"
    plugin = dest / "plugin"
    (hand / "skills").mkdir(parents=True)
    (hand / "rules").mkdir(parents=True)
    (hand / "hooks").mkdir(parents=True)
    (plugin / "skills" / "skill.council").mkdir(parents=True)
    (plugin / "rules").mkdir(parents=True)
    (plugin / "hooks").mkdir(parents=True)
    council = ("---\nname: council\ndescription: council skill\n---\n\n"
               "Council of models.\n")
    (hand / "skills" / "skill.council.md").write_text(council, encoding="utf-8", newline="\n")
    (plugin / "skills" / "skill.council" / "SKILL.md").write_text(council, encoding="utf-8", newline="\n")
    (hand / "skills" / "owner-skill.md").write_text(
        "---\nname: owner-skill\ndescription: owner-authored skill\n---\n\n"
        "Owner-authored body.\n", encoding="utf-8", newline="\n")
    no_secrets = "# No secrets\n\nNever commit live credentials.\n"
    (hand / "rules" / "rule.no-secrets.md").write_text(no_secrets, encoding="utf-8", newline="\n")
    (plugin / "rules" / "rule.no-secrets.md").write_text(no_secrets.replace("\n", "\r\n"),
                                                         encoding="utf-8", newline="\n")
    (hand / "rules" / "rule.owner-local.md").write_text(
        "# Owner-local rule\n\nHand-edited on this estate.\n", encoding="utf-8", newline="\n")
    (hand / "rules" / "rule.security.md").write_text(
        "# Security rule (hand version)\n\nHand-edited divergence.\n", encoding="utf-8", newline="\n")
    (plugin / "rules" / "rule.security.md").write_text(
        "# Security rule (repo version)\n\nRepository divergence.\n", encoding="utf-8", newline="\n")
    (plugin / "rules" / "rule.plugin-only.md").write_text(
        "# Plugin-only rule\n\nPre-dates the conversion; never removable by an inverse.\n",
        encoding="utf-8", newline="\n")
    hooks = {"PreToolUse": [{"matcher": "Bash", "command": "hooks/pre-tool.sh"}]}
    (hand / "hooks.json").write_text(json.dumps(hooks, indent=1) + "\n", encoding="utf-8", newline="\n")
    (plugin / "hooks" / "hook.pre-tool.json").write_text(json.dumps(hooks, indent=1) + "\n",
                                                         encoding="utf-8", newline="\n")
    pret = "#!/bin/sh\nexit 0\n"
    (hand / "hooks" / "pre-tool.sh").write_text(pret, encoding="utf-8", newline="\n")
    (plugin / "hooks" / "pre-tool.sh").write_text(pret, encoding="utf-8", newline="\n")
    (hand / "hooks" / "owner-local.sh").write_text("#!/bin/sh\n# owner hook\necho owner\n",
                                                   encoding="utf-8", newline="\n")
    pj_hand = {"name": "p2-plugin", "sourceUniques": ["skills/owner-skill.md", "rules/rule.owner-local.md"]}
    pj_plugin = {"name": "p2-plugin", "pluginOnly": ["rules/rule.plugin-only.md"]}
    (hand / "plugin.json").write_text(json.dumps(pj_hand, indent=1) + "\n", encoding="utf-8", newline="\n")
    (plugin / "plugin.json").write_text(json.dumps(pj_plugin, indent=1) + "\n", encoding="utf-8", newline="\n")
    return hand, plugin


def assert_copy_allowed(copy_root: Path, captured_original: Path):
    r = str(copy_root.resolve())
    home = str(Path.home().resolve())
    live = home + os.sep + ".claude"
    if r == live or r.startswith(live + os.sep):
        raise Refusal("refusing to run against the live profile: " + r)
    if copy_root.resolve() == Path(captured_original).resolve():
        raise Refusal("refusing to run against the captured original")


def classify(src: Path, tgt: Path):
    sb = src.read_bytes()
    tb = tgt.read_bytes()
    if sb == tb:
        return "BYTE-IDENTICAL"
    if sb.replace(b"\r\n", b"\n") == tb.replace(b"\r\n", b"\n"):
        return "EOL-ONLY"
    return "BOTH-UNIQUE"


MAPPING = [("skills/skill.council.md", "skills/skill.council/SKILL.md"),
           ("skills/owner-skill.md", "skills/owner-skill/SKILL.md"),
           ("hooks.json", "hooks/hook.pre-tool.json"),
           ("hooks.json", "hooks/hook.owner-local.json")]


def plan_dry_run(hand: Path, plugin: Path):
    plan = []
    for src in sorted(hand.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(hand).as_posix()
        targets = [t for s, t in MAPPING if s == rel] or [rel]
        for tgt_rel in targets:
            tgt = plugin / tgt_rel
            if not tgt.is_file():
                plan.append({"op": "create", "source_rel": rel, "target_rel": tgt_rel,
                             "classification": "SOURCE-ONLY",
                             "reason": "create from " + rel + " (SOURCE-ONLY)",
                             "content_sha256": sha_bytes(src.read_bytes()),
                             "bytes": src.stat().st_size})
            elif rel in MERGE_ALLOW:
                merged = json.loads(src.read_text(encoding="utf-8"))
                existing = json.loads(tgt.read_text(encoding="utf-8"))
                for k, v in existing.items():
                    merged.setdefault(k, v)
                merged_b = (json.dumps(merged, indent=1) + chr(10)).encode("utf-8")
                plan.append({"op": "overwrite", "source_rel": rel, "target_rel": tgt_rel,
                             "classification": "BOTH-UNIQUE",
                             "reason": "add preserved source-unique listings; keep plugin-only paths",
                             "content_sha256": sha_bytes(merged_b),
                             "bytes": len(merged_b)})
            else:
                cls = classify(src, tgt)
                if cls in ("BYTE-IDENTICAL", "EOL-ONLY"):
                    plan.append({"op": "skip", "source_rel": rel, "target_rel": tgt_rel,
                                 "classification": cls,
                                 "reason": cls + " classified unchanged; no write",
                                 "content_sha256": None, "bytes": 0})
                else:
                    plan.append({"op": "refuse", "source_rel": rel, "target_rel": tgt_rel,
                                 "classification": "BOTH-UNIQUE",
                                 "reason": "one-directional overwrite refused: unique content on the other side (classification=BOTH-UNIQUE, policy=default)",
                                 "content_sha256": None, "bytes": 0})
    return plan


def backup_target(backup_root: Path, plugin: Path, rel: str):
    dst = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plugin / rel, dst)


def backup_tree(plugin: Path, backup_root: Path):
    if backup_root.exists():
        shutil.rmtree(backup_root)
    shutil.copytree(plugin, backup_root)


def restore_tree(plugin: Path, backup_root: Path):
    if plugin.exists():
        shutil.rmtree(plugin)
    shutil.copytree(backup_root, plugin)


def apply_plan(hand: Path, plugin: Path, plan, backup_root: Path):
    applied = []
    for row in plan:
        op = row["op"]
        if op in ("skip", "refuse"):
            continue
        tgt = plugin / row["target_rel"]
        src = hand / row["source_rel"]
        if op == "create":
            if tgt.is_file():
                raise Refusal("planted owner file caught: refusing create over pre-existing "
                              "owner-authored target " + row["target_rel"])
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_bytes(src.read_bytes())
            applied.append({"op": "create", "target_rel": row["target_rel"],
                            "content_sha256": sha_bytes(tgt.read_bytes()),
                            "bytes": tgt.stat().st_size})
        elif op == "overwrite":
            backup_target(backup_root, plugin, row["target_rel"])
            merged = json.loads(src.read_text(encoding="utf-8"))
            existing = json.loads(tgt.read_text(encoding="utf-8"))
            for k, v in existing.items():
                merged.setdefault(k, v)
            tgt.write_text(json.dumps(merged, indent=1) + "\n", encoding="utf-8", newline="\n")
            applied.append({"op": "overwrite", "target_rel": row["target_rel"],
                            "content_sha256": sha_bytes(tgt.read_bytes()),
                            "bytes": tgt.stat().st_size})
    return applied


def delete_file_inverse(plugin: Path, rel: str, created_set):
    # invariant: an inverse may never remove a path the installer did not create
    if rel not in created_set:
        raise Refusal("an inverse may never remove a path the installer did not create: "
                      + rel + " not in created_set")
    p = plugin / rel
    if p.is_file():
        p.unlink()


def overwrite_inverse(plugin: Path, backup_root: Path, rel: str):
    # invariant: after the inverse, bytes equal the conversion backup snapshot
    src = backup_root / rel
    if not src.is_file():
        raise Refusal("no backup row for " + rel)
    tgt = plugin / rel
    if tgt.is_file():
        tgt.write_bytes(src.read_bytes())
