#!/usr/bin/env python3
"""Convert a captured hand-managed layout into a plugin-managed layout.

Runs only on a copy. Dry-run prints the mutation plan; apply must match it
when the post-apply tree delta is measured independently. Source-unique
files are preserved or the conversion refuses. EOL-only differences are
UNCHANGED, not conflicts. Restore uses the conversion's own backup.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent

from scenario import (  # noqa: E402
    BOTH_UNIQUE_REL,
    CAPTURED,
    HAND,
    PLANTED_LINE,
    PLANTED_SOURCE,
    PLANTED_TARGET,
    PLUGIN,
    PLUGIN_ONLY_RULE,
    build_captured,
    dump_json,
)

CREATE = "create"
OVERWRITE = "overwrite"
SKIP = "skip"
REFUSE = "refuse"

BYTE_IDENTICAL = "BYTE-IDENTICAL"
EOL_ONLY = "EOL-ONLY"
JSON_IDENTICAL = "JSON-IDENTICAL"
SOURCE_ONLY = "SOURCE-ONLY"
TARGET_ONLY = "TARGET-ONLY"
SOURCE_SUPERSET = "SOURCE-SUPERSET"
TARGET_SUPERSET = "TARGET-SUPERSET"
BOTH_UNIQUE = "BOTH-UNIQUE"
ABSENT = "ABSENT-BOTH"

# REL-0002 typed inverses (encoded here; REL-0002 receipt is not on this tree).
INVERSES: dict[str, dict[str, Any]] = {
    "create_file": {
        "inverse": "delete_file",
        "total": True,
        "residue": None,
        "invariant": (
            "after inverse, the path is absent AND the path is in the "
            "installer_created_set recorded at apply time"
        ),
        "may_remove_preexisting": False,
        "impact_if_irreversible": None,
    },
    "overwrite_file": {
        "inverse": "restore_from_backup",
        "total": True,
        "residue": None,
        "invariant": "after inverse, bytes equal the conversion backup snapshot",
        "may_remove_preexisting": False,
        "impact_if_irreversible": None,
    },
    "backup_tree": {
        "inverse": "none_required",
        "total": True,
        "residue": None,
        "invariant": "backup directory remains readable until restore completes",
        "may_remove_preexisting": False,
        "impact_if_irreversible": None,
    },
    "delete_file": {
        "inverse": "restore_from_backup",
        "total": True,
        "residue": None,
        "invariant": "delete is only legal for installer_created_set members",
        "may_remove_preexisting": False,
        "impact_if_irreversible": None,
    },
}

INVARIANT_NO_REMOVE_FOREIGN = (
    "an inverse may never remove a path the installer did not create"
)
INVARIANT_NO_REMOVE_PREEXISTING = (
    "an inverse may never remove a command, skill or setting that pre-dated the install"
)

RESUME_NAME = ".rel0017-resume.json"


class IsolationError(RuntimeError):
    pass


class InverseViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class Entry:
    source_rel: str
    target_rel: str
    data: bytes
    kind: str


def lf_bytes(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def lf_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_raw(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_lf(raw: bytes) -> str:
    return hashlib.sha256(lf_bytes(raw)).hexdigest()


def lines_of(raw: bytes) -> list[str]:
    body = lf_bytes(raw).decode("utf-8", errors="replace")
    if body == "":
        return []
    parts = body.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def line_set(raw: bytes) -> set[str]:
    return set(lines_of(raw))


def read_bytes(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    return path.read_bytes()


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def walk_files(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel == RESUME_NAME or rel.startswith(".rel0017-"):
            continue
        out[rel] = p.read_bytes()
    return out


def hash_set(root: Path) -> dict[str, str]:
    return {rel: sha256_raw(data) for rel, data in sorted(walk_files(root).items())}


def dump_canonical(obj: object) -> bytes:
    return dump_json(obj)


def try_json(raw: bytes) -> Any | None:
    try:
        return json.loads(lf_bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def classify_pair(src: bytes | None, dst: bytes | None) -> str:
    if src is None and dst is None:
        return ABSENT
    if src is None:
        return TARGET_ONLY
    if dst is None:
        return SOURCE_ONLY
    if src == dst:
        return BYTE_IDENTICAL
    if lf_bytes(src) == lf_bytes(dst):
        return EOL_ONLY
    if line_set(src) == line_set(dst):
        return EOL_ONLY
    sj, dj = try_json(src), try_json(dst)
    if sj is not None and dj is not None and sj == dj:
        return JSON_IDENTICAL
    rs, ls = line_set(src), line_set(dst)
    if rs > ls and ls <= rs:
        return SOURCE_SUPERSET
    if ls > rs and rs <= ls:
        return TARGET_SUPERSET
    return BOTH_UNIQUE


def classify_naive_no_eol(src: bytes | None, dst: bytes | None) -> str:
    """Wrong classifier: treats CRLF-vs-LF as a conflict."""
    if src is None or dst is None:
        return classify_pair(src, dst)
    if src != dst:
        return "CONFLICT"
    return BYTE_IDENTICAL


def forbidden_live_roots() -> list[Path]:
    home = Path.home()
    return [
        home / ".claude",
        home / ".cursor",
        home / ".agents",
        home / "AppData" / "Roaming" / "Claude",
        home / "AppData" / "Roaming" / "Cursor",
    ]


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def assert_copy(path: Path, *, mutating: bool) -> None:
    resolved = path.expanduser().resolve()
    for live in forbidden_live_roots():
        try:
            live_res = live.expanduser().resolve()
        except OSError:
            live_res = live
        if resolved == live_res or _is_under(resolved, live):
            raise IsolationError(
                f"refusing to touch live profile path {resolved} (marker {live})"
            )
    if mutating:
        captured_plugin = PLUGIN.resolve()
        captured_hand = HAND.resolve()
        if resolved == captured_plugin or resolved == captured_hand:
            raise IsolationError(
                f"refusing to mutate the captured original {resolved}"
            )
        if _is_under(resolved, CAPTURED.resolve()):
            raise IsolationError(
                f"refusing to mutate inside captured original {CAPTURED}"
            )


def map_skill_rel(rel: str) -> str:
    if rel.endswith("/SKILL.md"):
        return rel
    if rel.startswith("skills/") and rel.endswith(".md") and rel.count("/") == 1:
        stem = Path(rel).stem
        return f"skills/{stem}/SKILL.md"
    return rel


def collect_source_entries(hand_root: Path) -> list[Entry]:
    entries: list[Entry] = []
    skills = hand_root / "skills"
    if skills.is_dir():
        for p in sorted(skills.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(hand_root).as_posix()
            entries.append(Entry(rel, map_skill_rel(rel), p.read_bytes(), "skill"))
    rules = hand_root / "rules"
    if rules.is_dir():
        for p in sorted(rules.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(hand_root).as_posix()
            entries.append(Entry(rel, rel, p.read_bytes(), "rule"))
    hooks_json = hand_root / "hooks.json"
    if hooks_json.is_file():
        doc = json.loads(lf_bytes(hooks_json.read_bytes()).decode("utf-8"))
        if not isinstance(doc, list):
            raise ValueError("hooks.json must be an array of hook objects")
        for item in doc:
            if not isinstance(item, dict) or "id" not in item:
                raise ValueError(f"hook entry missing id: {item!r}")
            hid = str(item["id"])
            target = f"hooks/{hid}.json"
            entries.append(
                Entry("hooks.json", target, dump_canonical(item), "hook")
            )
    hooks_dir = hand_root / "hooks"
    if hooks_dir.is_dir():
        for p in sorted(hooks_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(hand_root).as_posix()
            if rel == "hooks.json":
                continue
            entries.append(Entry(rel, rel, p.read_bytes(), "hook-script"))
    return entries


def decide(classification: str, *, policy: str) -> str:
    if policy == "take-target":
        if classification in {
            SOURCE_ONLY,
            SOURCE_SUPERSET,
            BOTH_UNIQUE,
            EOL_ONLY,
            BYTE_IDENTICAL,
            JSON_IDENTICAL,
        }:
            return REFUSE
        return SKIP
    if classification in {BYTE_IDENTICAL, EOL_ONLY, JSON_IDENTICAL}:
        return SKIP
    if classification == SOURCE_ONLY:
        return CREATE
    if classification == SOURCE_SUPERSET:
        return OVERWRITE
    if classification in {BOTH_UNIQUE, TARGET_SUPERSET, TARGET_ONLY}:
        return REFUSE
    return REFUSE


def mutation(
    *,
    op: str,
    source_rel: str,
    target_rel: str,
    classification: str,
    data: bytes | None,
    reason: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "op": op,
        "source_rel": source_rel,
        "target_rel": target_rel,
        "classification": classification,
        "reason": reason,
        "content_sha256": sha256_raw(data) if data is not None else None,
        "content_sha256_lf": sha256_lf(data) if data is not None else None,
        "bytes": len(data) if data is not None else 0,
    }
    return row


def kind_bucket(kind: str) -> str | None:
    return {
        "skill": "skills",
        "hook": "hooks",
        "rule": "rules",
    }.get(kind)


def expected_plugin_json(
    existing: dict[str, Any], entries: Iterable[Entry], plan: list[dict[str, Any]]
) -> dict[str, Any]:
    out = dict(existing)
    created = {
        m["target_rel"]
        for m in plan
        if m["op"] in {CREATE, OVERWRITE} and m.get("target_rel") != "plugin.json"
    }
    by_kind = {"skills": set(out.get("skills") or []), "hooks": set(out.get("hooks") or []), "rules": set(out.get("rules") or [])}
    kinds = {e.target_rel: e.kind for e in entries}
    for rel in created:
        bucket = kind_bucket(kinds.get(rel, ""))
        if bucket:
            by_kind[bucket].add(rel)
        elif rel.startswith("skills/") and rel.endswith("/SKILL.md"):
            by_kind["skills"].add(rel)
        elif rel.startswith("hooks/") and rel.endswith(".json"):
            by_kind["hooks"].add(rel)
        elif rel.startswith("rules/") and rel.endswith(".md"):
            by_kind["rules"].add(rel)
    for key in ("skills", "hooks", "rules"):
        out[key] = sorted(by_kind[key])
    return out


def plan_conversion(
    hand_root: Path,
    plugin_root: Path,
    *,
    policy: str = "default",
) -> list[dict[str, Any]]:
    assert_copy(hand_root, mutating=False)
    assert_copy(plugin_root, mutating=True)
    entries = collect_source_entries(hand_root)
    plan: list[dict[str, Any]] = []
    for entry in entries:
        dst = read_bytes(plugin_root / entry.target_rel)
        classification = classify_pair(entry.data, dst)
        op = decide(classification, policy=policy)
        if op == SKIP:
            reason = f"{classification} classified unchanged; no write"
            data = None
        elif op == REFUSE:
            reason = (
                "one-directional overwrite refused: unique content on the "
                f"other side (classification={classification}, policy={policy})"
            )
            data = None
        else:
            reason = f"{op} from {entry.source_rel} ({classification})"
            data = entry.data
        plan.append(
            mutation(
                op=op,
                source_rel=entry.source_rel,
                target_rel=entry.target_rel,
                classification=classification,
                data=data,
                reason=reason,
            )
        )
    plugin_path = plugin_root / "plugin.json"
    existing_raw = read_bytes(plugin_path) or dump_canonical(
        {"name": "harness", "version": "0.0.0", "skills": [], "hooks": [], "rules": []}
    )
    existing_obj = try_json(existing_raw) or {}
    if not isinstance(existing_obj, dict):
        existing_obj = {}
    merged = expected_plugin_json(existing_obj, entries, plan)
    new_raw = dump_canonical(merged)
    cls = classify_pair(new_raw, existing_raw)
    if cls in {BYTE_IDENTICAL, JSON_IDENTICAL, EOL_ONLY}:
        plan.append(
            mutation(
                op=SKIP,
                source_rel="plugin.json",
                target_rel="plugin.json",
                classification=cls,
                data=None,
                reason="plugin.json listings already complete",
            )
        )
    else:
        plan.append(
            mutation(
                op=OVERWRITE,
                source_rel="plugin.json",
                target_rel="plugin.json",
                classification=cls,
                data=new_raw,
                reason="add preserved source-unique listings; keep plugin-only paths",
            )
        )
    return plan


def snapshot_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for rel, data in walk_files(src).items():
        write_bytes(dest / rel, data)


def restore_tree(backup: Path, dest: Path) -> dict[str, str]:
    """Restore dest from the conversion's own backup. Exact raw bytes."""
    if not backup.is_dir():
        raise FileNotFoundError(f"backup missing: {backup}")
    assert_copy(dest, mutating=True)
    snapshot_tree(backup, dest)
    return hash_set(dest)


def inverse_delete(path_rel: str, created_set: set[str]) -> None:
    if path_rel not in created_set:
        raise InverseViolation(
            f"{INVARIANT_NO_REMOVE_FOREIGN}: {path_rel} not in created_set"
        )


def record_resume(work: Path, phase: str, extra: dict[str, Any] | None = None) -> None:
    payload = {"phase": phase, "unit_id": "REL-0017"}
    if extra:
        payload.update(extra)
    write_bytes(work / RESUME_NAME, dump_canonical(payload))


def apply_plan(
    plugin_root: Path,
    plan: list[dict[str, Any]],
    *,
    payload_by_target: dict[str, bytes],
) -> list[dict[str, Any]]:
    """Execute planned writes. Journal is the plan rows as executed, in order."""
    assert_copy(plugin_root, mutating=True)
    journal: list[dict[str, Any]] = []
    for row in plan:
        op = row["op"]
        rel = row["target_rel"]
        if op in {SKIP, REFUSE}:
            journal.append(dict(row))
            continue
        data = payload_by_target.get(rel)
        if data is None:
            raise RuntimeError(f"apply missing payload for {rel}")
        if row.get("content_sha256") != sha256_raw(data):
            raise RuntimeError(f"apply payload sha mismatch for {rel}")
        dest = plugin_root / rel
        existed = dest.is_file()
        write_bytes(dest, data)
        executed = dict(row)
        executed["existed_before"] = existed
        journal.append(executed)
    return journal


def payloads_from_plan(
    hand_root: Path, plugin_root: Path, plan: list[dict[str, Any]]
) -> dict[str, bytes]:
    """Rebuild write payloads from source+plan so apply does not trust a side channel."""
    entries = {e.target_rel: e for e in collect_source_entries(hand_root)}
    out: dict[str, bytes] = {}
    for row in plan:
        if row["op"] not in {CREATE, OVERWRITE}:
            continue
        rel = row["target_rel"]
        if rel == "plugin.json":
            existing_raw = read_bytes(plugin_root / "plugin.json") or b"{}"
            existing_obj = try_json(existing_raw) or {}
            if not isinstance(existing_obj, dict):
                existing_obj = {}
            merged = expected_plugin_json(existing_obj, entries.values(), plan)
            out[rel] = dump_canonical(merged)
        else:
            out[rel] = entries[rel].data
    return out


def measure_writes(pre: dict[str, bytes], post: dict[str, bytes]) -> list[dict[str, Any]]:
    measured: list[dict[str, Any]] = []
    for rel in sorted(set(pre) | set(post)):
        a, b = pre.get(rel), post.get(rel)
        if a is None and b is not None:
            measured.append(
                {
                    "op": CREATE,
                    "target_rel": rel,
                    "content_sha256": sha256_raw(b),
                    "bytes": len(b),
                }
            )
        elif a is not None and b is None:
            measured.append(
                {
                    "op": "delete",
                    "target_rel": rel,
                    "content_sha256": sha256_raw(a),
                    "bytes": len(a),
                }
            )
        elif a is not None and b is not None and a != b:
            measured.append(
                {
                    "op": OVERWRITE,
                    "target_rel": rel,
                    "content_sha256": sha256_raw(b),
                    "bytes": len(b),
                }
            )
    return measured


def plan_vs_applied(
    plan: list[dict[str, Any]], pre: dict[str, bytes], post: dict[str, bytes]
) -> list[dict[str, Any]]:
    """Independent comparison: predicted writes vs measured tree delta.

    Skip/refuse targets must be byte-identical after apply. Unexpected deletes fail.
    """
    diffs: list[dict[str, Any]] = []
    predicted = []
    for row in plan:
        if row["op"] in {CREATE, OVERWRITE}:
            predicted.append(
                (row["op"], row["target_rel"], row["content_sha256"], row["bytes"])
            )
        elif row["op"] in {SKIP, REFUSE}:
            rel = row["target_rel"]
            if pre.get(rel) != post.get(rel):
                diffs.append(
                    {
                        "kind": "non-write-mutated",
                        "target_rel": rel,
                        "op": row["op"],
                        "classification": row.get("classification"),
                    }
                )
    measured = measure_writes(pre, post)
    got = [
        (m["op"], m["target_rel"], m["content_sha256"], m["bytes"]) for m in measured
    ]
    pred_set, got_set = set(predicted), set(got)
    for item in sorted(pred_set - got_set):
        diffs.append(
            {
                "kind": "predicted-write-missing",
                "op": item[0],
                "target_rel": item[1],
                "content_sha256": item[2],
            }
        )
    for item in sorted(got_set - pred_set):
        diffs.append(
            {
                "kind": "unpredicted-tree-delta",
                "op": item[0],
                "target_rel": item[1],
                "content_sha256": item[2],
            }
        )
    return diffs


def copy_capture(work: Path) -> tuple[Path, Path]:
    build_captured()
    hand = work / "hand"
    plugin = work / "plugin"
    if hand.exists():
        shutil.rmtree(hand)
    if plugin.exists():
        shutil.rmtree(plugin)
    shutil.copytree(HAND, hand)
    shutil.copytree(PLUGIN, plugin)
    assert_copy(hand, mutating=False)
    assert_copy(plugin, mutating=True)
    return hand, plugin


def source_unique_report(plan: list[dict[str, Any]]) -> dict[str, Any]:
    preserved = [
        m
        for m in plan
        if m["op"] == CREATE and m.get("classification") == SOURCE_ONLY
    ]
    refused = [
        m
        for m in plan
        if m["op"] == REFUSE
        and m.get("classification") in {BOTH_UNIQUE, TARGET_SUPERSET}
    ]
    return {
        "preserved": len(preserved),
        "refused": len(refused),
        "preserved_paths": [m["target_rel"] for m in preserved],
        "refused_paths": [m["target_rel"] for m in refused],
        "preserved_source_rels": [m["source_rel"] for m in preserved],
        "refused_source_rels": [m["source_rel"] for m in refused],
    }


def verify_source_unique_hashes(hand: Path, plugin: Path, plan: list[dict[str, Any]]) -> list[str]:
    failed: list[str] = []
    entries = {e.target_rel: e for e in collect_source_entries(hand)}
    for row in plan:
        if row["op"] != CREATE or row.get("classification") != SOURCE_ONLY:
            continue
        rel = row["target_rel"]
        got = read_bytes(plugin / rel)
        want = entries[rel].data
        if got != want:
            failed.append(rel)
            continue
        if sha256_raw(got) != sha256_raw(want):
            failed.append(rel)
    return failed


def planted_oracle(hand: Path, plugin: Path) -> dict[str, Any]:
    """Reviewer: try to destroy the planted owner file via take-target; oracle refuses."""
    planted_src = hand / PLANTED_SOURCE
    planted_raw = planted_src.read_bytes()
    if PLANTED_LINE.encode("utf-8") not in planted_raw:
        return {"pass": False, "reason": "planted-line-absent-from-source"}
    hostile = plan_conversion(hand, plugin, policy="take-target")
    planted_rows = [m for m in hostile if m["target_rel"] == PLANTED_TARGET]
    refused = bool(planted_rows) and all(m["op"] == REFUSE for m in planted_rows)
    honest = plan_conversion(hand, plugin, policy="default")
    payloads = payloads_from_plan(hand, plugin, honest)
    # Do not apply hostile plan. Apply honest plan on a sibling check happens in rehearse.
    both_unique = [
        m for m in honest if m["target_rel"] == BOTH_UNIQUE_REL and m["op"] == REFUSE
    ]
    return {
        "pass": refused and bool(both_unique),
        "planted_source": PLANTED_SOURCE,
        "planted_target": PLANTED_TARGET,
        "planted_line": PLANTED_LINE,
        "take_target_refused": refused,
        "take_target_rows": planted_rows,
        "both_unique_refused": bool(both_unique),
        "planted_source_sha256": sha256_raw(planted_raw),
        "hostile_policy": "take-target",
        "payloads_planned_for_plant": PLANTED_TARGET in payloads,
    }


def inverse_control(created_set: set[str]) -> dict[str, Any]:
    try:
        inverse_delete(PLUGIN_ONLY_RULE, created_set)
        caught = False
        error = None
    except InverseViolation as exc:
        caught = True
        error = str(exc)
    return {
        "pass": caught,
        "attempted_path": PLUGIN_ONLY_RULE,
        "in_created_set": PLUGIN_ONLY_RULE in created_set,
        "invariant": INVARIANT_NO_REMOVE_FOREIGN,
        "error": error,
    }


def rehearse(work: Path) -> dict[str, Any]:
    """Full drill on a copy under work/. Restores plugin from backup at the end of restore check."""
    work.mkdir(parents=True, exist_ok=True)
    hand, plugin = copy_capture(work)
    copy_path = str(work.resolve())
    isolation_ok = True
    isolation_error = None
    try:
        assert_copy(plugin, mutating=True)
        for live in forbidden_live_roots():
            if plugin.resolve() == live.resolve() or _is_under(plugin, live):
                isolation_ok = False
    except IsolationError as exc:
        isolation_ok = False
        isolation_error = str(exc)

    plan = plan_conversion(hand, plugin, policy="default")
    pre_files = walk_files(plugin)
    pre_hashes = {rel: sha256_raw(data) for rel, data in pre_files.items()}
    backup = work / "backup"
    snapshot_tree(plugin, backup)
    record_resume(
        work,
        "post-backup",
        {"backup_path": str(backup), "copy_path": copy_path},
    )
    payloads = payloads_from_plan(hand, plugin, plan)
    journal = apply_plan(plugin, plan, payload_by_target=payloads)
    post_files = walk_files(plugin)
    diffs = plan_vs_applied(plan, pre_files, post_files)
    unique = source_unique_report(plan)
    hash_failures = verify_source_unique_hashes(hand, plugin, plan)
    created_set = {
        m["target_rel"]
        for m in journal
        if m["op"] == CREATE
    }
    oracle = planted_oracle(hand, plugin)
    inv = inverse_control(created_set)
    planted_after = read_bytes(plugin / PLANTED_TARGET)
    planted_ok = (
        planted_after is not None
        and PLANTED_LINE.encode("utf-8") in planted_after
        and sha256_raw(planted_after) == sha256_raw((hand / PLANTED_SOURCE).read_bytes())
    )

    eol_rows = [m for m in plan if m["target_rel"] == "rules/rule.no-secrets.md"]
    eol = eol_rows[0] if eol_rows else {}
    naive = classify_naive_no_eol(
        (hand / "rules" / "rule.no-secrets.md").read_bytes(),
        pre_files.get("rules/rule.no-secrets.md"),
    )
    plugin_only_survived = (plugin / PLUGIN_ONLY_RULE).is_file() and sha256_raw(
        (plugin / PLUGIN_ONLY_RULE).read_bytes()
    ) == pre_hashes.get(PLUGIN_ONLY_RULE)

    restored_hashes = restore_tree(backup, plugin)
    restore_ok = restored_hashes == pre_hashes
    record_resume(work, "restored", {"restore_ok": restore_ok})

    return {
        "copy_path": copy_path,
        "hand_path": str(hand.resolve()),
        "plugin_path": str(plugin.resolve()),
        "backup_path": str(backup.resolve()),
        "captured_hand": str(HAND.resolve()),
        "captured_plugin": str(PLUGIN.resolve()),
        "isolation_ok": isolation_ok,
        "isolation_error": isolation_error,
        "ran_against_copy": copy_path != str(CAPTURED.resolve())
        and str(plugin.resolve()) != str(PLUGIN.resolve()),
        "plan": plan,
        "journal": journal,
        "measured_writes": measure_writes(pre_files, post_files),
        "plan_vs_applied_diff": diffs,
        "plan_applied_identical": diffs == [],
        "source_unique": unique,
        "source_unique_hash_failures": hash_failures,
        "source_unique_hashes_intact": hash_failures == [],
        "pre_hash_set": pre_hashes,
        "restored_hash_set": restored_hashes,
        "restore_ok": restore_ok,
        "restore_hash_count": len(pre_hashes),
        "eol": {
            "path": "rules/rule.no-secrets.md",
            "classification": eol.get("classification"),
            "op": eol.get("op"),
            "naive_without_eol_norm": naive,
            "honest_unchanged": eol.get("classification") == EOL_ONLY
            and eol.get("op") == SKIP,
        },
        "planted": {
            **oracle,
            "survived_apply_hash_intact": planted_ok,
        },
        "inverse_control": inv,
        "plugin_only_survived": plugin_only_survived,
        "created_set": sorted(created_set),
        "inverses": INVERSES,
        "invariants": [
            INVARIANT_NO_REMOVE_FOREIGN,
            INVARIANT_NO_REMOVE_PREEXISTING,
        ],
    }


def isolation_negative_control() -> dict[str, Any]:
    """Calling apply against a live-profile path must fail closed."""
    live = Path.home() / ".claude" / "rel0017-must-not-exist"
    caught = False
    error = None
    try:
        assert_copy(live, mutating=True)
    except IsolationError as exc:
        caught = True
        error = str(exc)
    captured_caught = False
    try:
        assert_copy(PLUGIN, mutating=True)
    except IsolationError as exc:
        captured_caught = True
        error = (error or "") + " | " + str(exc)
    return {
        "pass": caught and captured_caught,
        "live_path_refused": caught,
        "captured_original_refused": captured_caught,
        "error": error,
    }


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rel0017-cli-") as tmp:
        result = rehearse(Path(tmp))
    print(
        json.dumps(
            {
                "copy_path": result["copy_path"],
                "plan_applied_identical": result["plan_applied_identical"],
                "source_unique": result["source_unique"],
                "restore_ok": result["restore_ok"],
                "eol": result["eol"],
                "planted_pass": result["planted"].get("pass"),
                "isolation": result["ran_against_copy"],
            },
            indent=2,
        )
    )
