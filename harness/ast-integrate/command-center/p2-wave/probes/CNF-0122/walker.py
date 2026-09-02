#!/usr/bin/env python3
"""Independent filesystem walker for CNF-0122.

Compares command-center/ARTIFACT-MANIFEST.json against files actually on disk.
This module MUST NOT import tools.command-center.render (the manifest writer)
or tools.command-center.unit_manifest. The contracted filename list below is
copied from Prompt Two (_USER-PROMPTS.md:10590-10603), not imported from the
writer, so a shared bug cannot certify itself.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# Prompt Two contracted command-center files plus the append-only event log.
# Duplicated here on purpose. Importing render.CONTRACTED_ARTIFACTS would couple
# the auditor to the writer it is supposed to check.
CHARTER_FILENAMES: tuple[str, ...] = (
    "PROGRAM-CHARTER.md",
    "OWNER-DECISIONS.md",
    "WORK-UNIT-CATALOG.json",
    "DEPENDENCY-GRAPH.json",
    "ARTIFACT-MANIFEST.json",
    "CLAIM-REGISTRY.json",
    "TEST-REGISTRY.json",
    "RISK-REGISTER.md",
    "UNKNOWNS-REGISTER.md",
    "RELEASE-CHECKLIST.md",
    "ROLLBACK-MANIFEST.md",
    "RUNBOOK.md",
    "STATUS.md",
    "events/EVENTS.jsonl",
)

HASH_BASIS = "worktree-bytes-lf-normalized"
HASH_BASIS_NOTE = (
    "SHA-256 of worktree file bytes after CRLF-to-LF normalization. "
    "Committed git-blob bytes are not the hash basis: on this platform a "
    "Windows checkout with core.autocrlf=true materializes CRLF while git "
    "stores LF, so worktree and committed digests differ. The writer in "
    "tools/command-center/render.py:render_manifest has the same LF-normalize "
    "rule; this walker reimplements it instead of calling that function."
)
SELF_SENTINELS = frozenset({"(self)", "(SELF)", "self"})
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "render",
        "unit_manifest",
        "tools.command-center.render",
        "tools.command-center.unit_manifest",
        "tools.command_center.render",
        "tools.command_center.unit_manifest",
    }
)
WALKER_REL = "command-center/p2-wave/probes/CNF-0122/walker.py"


def worktree_digest(path: Path) -> tuple[str, int]:
    """Hash worktree bytes (LF-normalized). Not committed git-blob bytes."""
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def committed_digest(repo_root: Path, rel_posix: str) -> dict[str, Any]:
    """Best-effort git blob digest. Absence is recorded, never guessed."""
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return {
            "available": False,
            "sha256": None,
            "reason": "no .git directory on this worktree",
        }
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"HEAD:{rel_posix}"],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "sha256": None, "reason": str(exc)}
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace")[-200:]
        return {
            "available": False,
            "sha256": None,
            "reason": tail or f"git show exit {proc.returncode}",
        }
    raw = proc.stdout.replace(b"\r\n", b"\n")
    return {
        "available": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "reason": "git show HEAD:<path> then LF-normalize",
    }


def _is_forbidden_import(name: str) -> bool:
    n = name.strip()
    if n in FORBIDDEN_IMPORT_ROOTS:
        return True
    parts = n.split(".")
    if parts and parts[-1] in {"render", "unit_manifest"}:
        return True
    return False


def forbidden_imports_in(source: str) -> list[str]:
    tree = ast.parse(source)
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_import(alias.name):
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if _is_forbidden_import(mod):
                bad.append(mod)
            for alias in node.names:
                combined = f"{mod}.{alias.name}" if mod else alias.name
                if _is_forbidden_import(combined) or _is_forbidden_import(alias.name):
                    bad.append(combined)
    return sorted(set(bad))


def independence_report(source_path: Path | None = None) -> dict[str, Any]:
    path = source_path or Path(__file__).resolve()
    text = path.read_text(encoding="utf-8")
    bad = forbidden_imports_in(text)
    return {
        "walker_path": WALKER_REL,
        "writer_path": "tools/command-center/render.py",
        "writer_function": "render_manifest",
        "imports_manifest_writer": bool(bad),
        "forbidden_imports": bad,
        "independent": not bad,
    }


def _norm_rel(value: str) -> str:
    rel = value.replace("\\", "/").lstrip("./")
    if rel.startswith("command-center/"):
        return rel
    return f"command-center/{rel}"


def load_manifest(
    cc_root: Path,
) -> tuple[dict[str, Any] | None, str, list[dict[str, Any]]]:
    path = cc_root / "ARTIFACT-MANIFEST.json"
    if not path.is_file():
        return None, "absent", []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"unparseable:{type(exc).__name__}", []
    if not isinstance(data, dict):
        return None, "not-object", []
    rows = data.get("artifacts")
    if not isinstance(rows, list):
        return data, "missing-artifacts-array", []
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("path"), str):
            cleaned.append(row)
    return data, "ok", cleaned


def walk_disk(cc_root: Path) -> dict[str, Path]:
    """Walk the charter artifact tree without consulting the writer.

    Scope: contracted filenames (stat each) plus every non-directory file at
    command-center/ top level and command-center/events/*. This is the tree
    ARTIFACT-MANIFEST.json claims to describe. Unit outputs under p2-wave/
    and confirmation/ are out of scope for the charter manifest.
    """
    found: dict[str, Path] = {}
    if not cc_root.is_dir():
        return found
    for name in CHARTER_FILENAMES:
        path = cc_root / name
        if path.is_file():
            found[_norm_rel(name)] = path
    for path in sorted(cc_root.iterdir()):
        if path.is_file():
            found[_norm_rel(path.name)] = path
    events = cc_root / "events"
    if events.is_dir():
        for path in sorted(events.iterdir()):
            if path.is_file():
                found[_norm_rel(f"events/{path.name}")] = path
    return found


def walk_and_compare(repo_root: Path) -> dict[str, Any]:
    """Compare the charter manifest against disk. Independent of render.py.

    This function is the walker cited at file:line in the confirmation artifact.
    """
    repo_root = repo_root.resolve()
    cc_root = repo_root / "command-center"
    manifest_obj, manifest_status, rows = load_manifest(cc_root)
    disk = walk_disk(cc_root)
    claimed: dict[str, dict[str, Any]] = {}
    for row in rows:
        claimed[_norm_rel(row["path"])] = row

    on_disk = set(disk)
    manifested = set(claimed)
    unmanifested_paths = sorted(on_disk - manifested)
    absent_paths = sorted(manifested - on_disk)
    common = sorted(on_disk & manifested)

    unmanifested: list[dict[str, Any]] = []
    for rel in unmanifested_paths:
        sha, n = worktree_digest(disk[rel])
        unmanifested.append(
            {
                "path": rel,
                "present": True,
                "worktree_sha256": sha,
                "worktree_bytes": n,
                "hash_basis": HASH_BASIS,
            }
        )

    absent: list[dict[str, Any]] = []
    for rel in absent_paths:
        row = claimed[rel]
        absent.append(
            {
                "path": rel,
                "present": False,
                "manifest_present_claim": row.get("present"),
                "manifest_sha256": row.get("sha256"),
                "manifest_bytes": row.get("bytes"),
            }
        )

    mismatches: list[dict[str, Any]] = []
    matching: list[dict[str, Any]] = []
    self_entries: list[dict[str, Any]] = []
    for rel in common:
        row = claimed[rel]
        path = disk[rel]
        live_sha, live_n = worktree_digest(path)
        claimed_sha = row.get("sha256")
        committed = committed_digest(repo_root, rel)
        rec: dict[str, Any] = {
            "path": rel,
            "worktree_sha256": live_sha,
            "worktree_bytes": live_n,
            "manifest_sha256": claimed_sha,
            "manifest_bytes": row.get("bytes"),
            "manifest_present_claim": row.get("present"),
            "hash_basis": HASH_BASIS,
            "committed": committed,
        }
        if rel.endswith("ARTIFACT-MANIFEST.json") and str(claimed_sha) in SELF_SENTINELS:
            rec["self_referential"] = True
            self_entries.append(rec)
            continue
        if claimed_sha == live_sha and row.get("present") is True:
            matching.append(rec)
        else:
            rec["kind"] = (
                "hash-mismatch" if claimed_sha != live_sha else "present-claim-mismatch"
            )
            mismatches.append(rec)

    charter_present = []
    charter_absent = []
    for name in CHARTER_FILENAMES:
        rel = _norm_rel(name)
        if rel in disk:
            charter_present.append(rel)
        else:
            charter_absent.append(rel)

    describes_reality = (
        manifest_status == "ok"
        and not unmanifested
        and not absent
        and not mismatches
    )
    return {
        "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        "manifest_status": manifest_status,
        "manifest_present": manifest_status == "ok",
        "hash_basis": HASH_BASIS,
        "hash_basis_note": HASH_BASIS_NOTE,
        "committed_bytes_used_for_comparison": False,
        "walker_source": walker_source_anchor(),
        "charter_files_present": charter_present,
        "charter_files_absent": charter_absent,
        "on_disk_count": len(disk),
        "manifested_count": len(claimed),
        "on_disk_but_unmanifested": unmanifested,
        "manifested_but_absent": absent,
        "hash_mismatches": mismatches,
        "matching": matching,
        "self_referential": self_entries,
        "manifest_describes_reality": describes_reality,
        "schema_version_in_manifest": (
            manifest_obj.get("schema_version") if isinstance(manifest_obj, dict) else None
        ),
        "derivation_in_manifest": (
            manifest_obj.get("derivation") if isinstance(manifest_obj, dict) else None
        ),
    }


def walker_source_anchor() -> str:
    """Return repo-relative file:line of walk_and_compare."""
    start = walk_and_compare.__code__.co_firstlineno
    return f"{WALKER_REL}:{start}"


def plant_fixture(repo_root: Path) -> dict[str, str]:
    """Known-broken command-center tree used by the unmanifested-file control."""
    cc = repo_root / "command-center"
    cc.mkdir(parents=True)
    (cc / "PROGRAM-CHARTER.md").write_bytes(b"charter-ok\n")
    (cc / "STATUS.md").write_bytes(b"status-live\n")
    (cc / "UNMANIFESTED-CONTROL.txt").write_bytes(b"planted-unmanifested\n")
    charter_sha, charter_n = worktree_digest(cc / "PROGRAM-CHARTER.md")
    status_sha, status_n = worktree_digest(cc / "STATUS.md")
    wrong_sha = "0" * 64
    manifest = {
        "schema_version": 1,
        "contract": "CNF-0122-known-broken-fixture",
        "derivation": "CNF-0122 fixture (not tools/command-center/render.py)",
        "verified_on_disk": False,
        "present": 3,
        "expected": 4,
        "artifacts": [
            {
                "path": "command-center/PROGRAM-CHARTER.md",
                "present": True,
                "bytes": charter_n,
                "sha256": charter_sha,
            },
            {
                "path": "command-center/STATUS.md",
                "present": True,
                "bytes": status_n,
                "sha256": wrong_sha,
            },
            {
                "path": "command-center/OWNER-DECISIONS.md",
                "present": True,
                "bytes": 10,
                "sha256": "ab" * 32,
            },
            {
                "path": "command-center/ARTIFACT-MANIFEST.json",
                "present": True,
                "bytes": 0,
                "sha256": "(self)",
            },
        ],
    }
    (cc / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "unmanifested": "command-center/UNMANIFESTED-CONTROL.txt",
        "hash_mismatch": "command-center/STATUS.md",
        "absent": "command-center/OWNER-DECISIONS.md",
        "matching": "command-center/PROGRAM-CHARTER.md",
        "wrong_sha": wrong_sha,
        "expected_status_sha": status_sha,
    }


def plant_clean_fixture(repo_root: Path) -> None:
    """Negative control: every on-disk charter file is manifested with matching hash."""
    cc = repo_root / "command-center"
    cc.mkdir(parents=True)
    (cc / "PROGRAM-CHARTER.md").write_bytes(b"charter-ok\n")
    (cc / "STATUS.md").write_bytes(b"status-live\n")
    rows: list[dict[str, Any]] = []
    for name in ("PROGRAM-CHARTER.md", "STATUS.md"):
        sha, n = worktree_digest(cc / name)
        rows.append(
            {
                "path": f"command-center/{name}",
                "present": True,
                "bytes": n,
                "sha256": sha,
            }
        )
    rows.append(
        {
            "path": "command-center/ARTIFACT-MANIFEST.json",
            "present": True,
            "bytes": 0,
            "sha256": "(self)",
        }
    )
    manifest = {
        "schema_version": 1,
        "contract": "CNF-0122-clean-fixture",
        "derivation": "CNF-0122 fixture (not tools/command-center/render.py)",
        "artifacts": rows,
    }
    (cc / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_unmanifested_control() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0122-broken-") as tmp:
        root = Path(tmp)
        facts = plant_fixture(root)
        result = walk_and_compare(root)
        unman = [e["path"] for e in result["on_disk_but_unmanifested"]]
        absent = [e["path"] for e in result["manifested_but_absent"]]
        mism = [e["path"] for e in result["hash_mismatches"]]
        matching = [e["path"] for e in result["matching"]]
        reported = facts["unmanifested"] in unman
        return {
            "planted_path": facts["unmanifested"],
            "reported": reported,
            "unmanifested_paths": unman,
            "absent_paths": absent,
            "hash_mismatch_paths": mism,
            "matching_paths": matching,
            "expected_absent": facts["absent"],
            "expected_mismatch": facts["hash_mismatch"],
            "expected_matching": facts["matching"],
            "comparison": result,
        }


def run_clean_control() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0122-clean-") as tmp:
        root = Path(tmp)
        plant_clean_fixture(root)
        result = walk_and_compare(root)
        unman = [e["path"] for e in result["on_disk_but_unmanifested"]]
        return {
            "unmanifested_paths": unman,
            "absent_paths": [e["path"] for e in result["manifested_but_absent"]],
            "hash_mismatch_paths": [e["path"] for e in result["hash_mismatches"]],
            "silent_on_clean": (
                not unman
                and not result["manifested_but_absent"]
                and not result["hash_mismatches"]
            ),
            "comparison": result,
        }


if __name__ == "__main__":
    root = Path(os.environ.get("CNF0122_ROOT") or Path(__file__).resolve().parents[4])
    print(json.dumps(walk_and_compare(root), indent=2, sort_keys=True))
