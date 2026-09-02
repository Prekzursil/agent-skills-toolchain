"""AUD-0093: ROLLBACK-MANIFEST versus already-executed actions.

Probe 1 reads each manifest entry and checks that every artifact it names
still exists. Probe 2 rehearses restore in a scratch tree and reports whether
prior bytes come back. A procedure that has never been run is unverified; a
procedure that cannot restore is not a rollback.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"

MANIFEST_CANDIDATES = (
    "command-center/ROLLBACK-MANIFEST.md",
    "ROLLBACK-MANIFEST.md",
    "command-center/rollback-manifest.md",
    "command-center/ROLLBACK.md",
)

EXECUTED_ACTIONS = (
    {
        "id": "delete-all-77",
        "title": "DELETE-ALL of 77 files",
        "keywords": ("delete-all", "77 file", "77 files", "retirement"),
        "risk": 100,
        "class": "destructive-delete",
    },
    {
        "id": "salvage-tools-lib",
        "title": "salvage into tools/lib",
        "keywords": ("salvage", "tools/lib", "tools/lib"),
        "risk": 60,
        "class": "move-or-copy",
    },
    {
        "id": "worktree-cleanup-20-to-6",
        "title": "worktree cleanup from 20 to 6",
        "keywords": ("worktree", "worktree", "20 to 6", "20 → 6"),
        "risk": 80,
        "class": "tree-removal",
    },
)

PATH_RE = re.compile(
    r"`([^`]+)`"
    r"|\((?:\.\/)?([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+)\)"
)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
IRREVERSIBLE_HINTS = (
    "delete-all",
    "irreversible",
    "no backup",
    "no-backup",
    "cannot restore",
    "destroyed",
    "shred",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def git_info(repo: Path = REPO) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "inside_work_tree": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    inside = proc.returncode == 0 and (proc.stdout or "").strip() == "true"
    reason = ""
    if not inside:
        reason = ((proc.stderr or proc.stdout or "").strip() or f"rc={proc.returncode}")[
            :400
        ]
    worktrees: list[str] | None = None
    if inside:
        wt = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if wt.returncode == 0:
            worktrees = [
                line[9:]
                for line in (wt.stdout or "").splitlines()
                if line.startswith("worktree ")
            ]
    return {
        "available": True,
        "inside_work_tree": inside,
        "reason": reason or None,
        "worktree_count": None if worktrees is None else len(worktrees),
        "worktrees_sample": (worktrees or [])[:8],
    }


def locate_manifest(repo: Path = REPO) -> dict[str, Any]:
    hits = []
    chosen = None
    for rel in MANIFEST_CANDIDATES:
        path = repo / rel
        rec = {
            "path": rel,
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
        hits.append(rec)
        if rec["exists"] and chosen is None:
            chosen = rec
    return {"present": chosen is not None, "chosen": chosen, "candidates": hits}


def _looks_like_path(token: str) -> bool:
    token = token.strip().strip("`").replace("\\", "/")
    if not token or token in {".", "..", "/"}:
        return False
    if token.startswith("http://") or token.startswith("https://"):
        return False
    if " " in token:
        return False
    if "/" in token:
        return True
    return "." in token and not token.startswith(".")


def extract_paths(text: str) -> list[str]:
    found: list[str] = []
    for match in PATH_RE.finditer(text):
        token = next((g for g in match.groups() if g), "")
        token = token.strip().strip("`").replace("\\", "/")
        if _looks_like_path(token) and token not in found:
            found.append(token)
    for line in text.splitlines():
        if "|" not in line:
            continue
        for cell in line.split("|"):
            cell = cell.strip().strip("`")
            if _looks_like_path(cell) and cell not in found:
                found.append(cell)
    return found


def _entry_from_block(
    eid: str, title: str, body: str, source: str, line: int
) -> dict[str, Any]:
    blob = f"{title}\n{body}".lower()
    irreversible = any(hint in blob for hint in IRREVERSIBLE_HINTS)
    refs = extract_paths(f"{title}\n{body}")
    restore_map = []
    for i in range(0, len(refs) - 1, 2):
        src, dst = refs[i], refs[i + 1]
        if "backup" in src.lower() or src != dst:
            restore_map.append({"from": src, "to": dst})
    return {
        "id": eid,
        "title": title,
        "source": source,
        "line": line,
        "body_preview": body[:400],
        "referenced_paths": refs,
        "restore_map": restore_map,
        "claims_irreversible": irreversible,
        "risk": 100 if irreversible else (80 if refs else 40),
    }


def parse_manifest_text(text: str, source: str) -> list[dict[str, Any]]:
    headings = list(HEADING_RE.finditer(text))
    if not headings:
        body = text.strip()
        if not body:
            return []
        return [_entry_from_block("entry-0", "unstructured-manifest-body", body, source, 1)]
    entries = []
    for i, match in enumerate(headings):
        title = match.group(2).strip()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        line_no = text[: match.start()].count("\n") + 1
        entries.append(_entry_from_block(f"entry-{i + 1}", title, body, source, line_no))
    return entries


def load_live_entries(repo: Path = REPO) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    loc = locate_manifest(repo)
    if not loc["present"]:
        return loc, []
    rel = loc["chosen"]["path"]
    text = (repo / rel).read_text(encoding="utf-8", errors="replace")
    loc["sha256"] = sha256_file(repo / rel)
    loc["chars"] = len(text)
    return loc, parse_manifest_text(text, rel)


def check_references(entry: dict[str, Any], repo: Path = REPO) -> dict[str, Any]:
    rows = []
    missing = 0
    for rel in entry.get("referenced_paths") or []:
        path = Path(rel)
        if not path.is_absolute():
            path = repo / rel
        exists = path.is_file() or path.is_dir()
        if not exists:
            missing += 1
        rows.append(
            {
                "path": rel,
                "exists": exists,
                "kind": "file" if path.is_file() else "dir" if path.is_dir() else "absent",
            }
        )
    return {
        "entry_id": entry["id"],
        "title": entry["title"],
        "referenced_n": len(rows),
        "missing_n": missing,
        "all_exist": missing == 0 and len(rows) > 0,
        "no_references": len(rows) == 0,
        "references": rows,
    }


def coverage_for_executed(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for action in EXECUTED_ACTIONS:
        matched = []
        for entry in entries:
            blob = f"{entry.get('title', '')}\n{entry.get('body_preview', '')}".lower()
            if any(key.lower() in blob for key in action["keywords"]):
                matched.append(entry["id"])
        rows.append(
            {
                "action_id": action["id"],
                "title": action["title"],
                "covered_by_manifest": bool(matched),
                "matching_entry_ids": matched,
                "risk": action["risk"],
                "class": action["class"],
            }
        )
    return rows


def snapshot_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = sha256_file(path)
    return out


def materialize(root: Path, files: dict[str, bytes]) -> None:
    if root.exists():
        shutil.rmtree(root)
    for rel, blob in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)


def apply_restore(root: Path, restore_map: list[dict[str, str]]) -> dict[str, Any]:
    copied = 0
    missing_src = []
    for item in restore_map:
        src = root / item["from"]
        dst = root / item["to"]
        if not src.is_file():
            missing_src.append(item["from"])
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return {"copied": copied, "missing_sources": missing_src}


def rehearse(
    *,
    prior_files: dict[str, bytes],
    damage_delete: list[str],
    restore_map: list[dict[str, str]],
    label: str,
) -> dict[str, Any]:
    scratch = Path(tempfile.mkdtemp(prefix=f"aud0093-{label}-"))
    try:
        materialize(scratch, prior_files)
        prior = snapshot_tree(scratch)
        for rel in damage_delete:
            target = scratch / rel
            if target.is_file():
                target.unlink()
        restore = apply_restore(scratch, restore_map)
        after = snapshot_tree(scratch)
        recovered = after == prior
        return {
            "label": label,
            "byte_recovered": recovered,
            "prior_files": len(prior),
            "after_files": len(after),
            "restore": restore,
            "missing_after": sorted(set(prior) - set(after)),
            "changed_after": sorted(
                p for p in prior if p in after and after[p] != prior[p]
            ),
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def fixture_controls() -> dict[str, Any]:
    payload = b"AUD-0093 prior-state marker v1\n"
    reversible = rehearse(
        prior_files={"keep.txt": payload, "backup/keep.txt": payload},
        damage_delete=["keep.txt"],
        restore_map=[{"from": "backup/keep.txt", "to": "keep.txt"}],
        label="reversible-copy",
    )
    irreversible = rehearse(
        prior_files={"gone.txt": payload},
        damage_delete=["gone.txt"],
        restore_map=[{"from": "backup/gone.txt", "to": "gone.txt"}],
        label="irreversible-delete-no-backup",
    )
    false_success = irreversible["byte_recovered"] is True
    always_red = reversible["byte_recovered"] is not True
    return {
        "reversible": reversible,
        "irreversible": irreversible,
        "irreversible_reported_failure": irreversible["byte_recovered"] is False,
        "reversible_reported_success": reversible["byte_recovered"] is True,
        "false_success_on_irreversible": false_success,
        "always_red_on_reversible": always_red,
        "control_pass": (not false_success) and (not always_red),
    }


def fixture_manifest_controls(repo: Path = REPO) -> dict[str, Any]:
    present_md = (FIXTURES / "present-entry.md").read_text(encoding="utf-8")
    missing_md = (FIXTURES / "missing-entry.md").read_text(encoding="utf-8")
    present_entries = parse_manifest_text(present_md, "fixtures/present-entry.md")
    missing_entries = parse_manifest_text(missing_md, "fixtures/missing-entry.md")
    present_check = check_references(present_entries[0], repo)
    missing_check = check_references(missing_entries[0], repo)
    ok = present_check["all_exist"] is True and missing_check["missing_n"] >= 1
    return {
        "present_entry_all_exist": present_check["all_exist"],
        "missing_entry_missing_n": missing_check["missing_n"],
        "present_paths": present_check["references"],
        "missing_paths": missing_check["references"],
        "control_pass": ok,
        "both_states": ok,
    }


def highest_risk_live(
    entries: list[dict[str, Any]], coverage: list[dict[str, Any]]
) -> dict[str, Any]:
    # Catalog question is the three already-executed actions. An unrelated
    # present manifest (register-gate undo, catalog seed --force) must not
    # become the rehearsal target while those actions remain uncovered.
    uncovered = [row for row in coverage if not row["covered_by_manifest"]]
    if uncovered:
        top_a = sorted(uncovered, key=lambda row: row["risk"], reverse=True)[0]
        return {
            "source": "executed-action-uncovered",
            "id": top_a["action_id"],
            "title": top_a["title"],
            "risk": top_a["risk"],
            "claims_irreversible": top_a["class"] == "destructive-delete",
            "restore_map": [],
            "referenced_paths": [],
        }
    if entries:
        top = sorted(entries, key=lambda e: int(e.get("risk") or 0), reverse=True)[0]
        return {
            "source": "manifest-entry",
            "id": top["id"],
            "title": top["title"],
            "risk": top["risk"],
            "claims_irreversible": top.get("claims_irreversible"),
            "restore_map": top.get("restore_map") or [],
            "referenced_paths": top.get("referenced_paths") or [],
        }
    return {
        "source": "none",
        "id": None,
        "title": None,
        "risk": 0,
        "claims_irreversible": False,
        "restore_map": [],
        "referenced_paths": [],
    }


def rehearse_live_highest(highest: dict[str, Any]) -> dict[str, Any]:
    payload = b"AUD-0093 live-rehearsal prior bytes\n"
    if highest["source"] == "manifest-entry" and highest.get("restore_map"):
        prior: dict[str, bytes] = {}
        damage: list[str] = []
        for item in highest["restore_map"]:
            prior[item["to"]] = payload
            prior[item["from"]] = payload
            damage.append(item["to"])
        result = rehearse(
            prior_files=prior,
            damage_delete=damage,
            restore_map=list(highest["restore_map"]),
            label="live-highest-manifest",
        )
        result["mode"] = "manifest-restore-map"
        return result
    result = rehearse(
        prior_files={
            "deleted/a.py": payload,
            "deleted/b.py": payload,
            "deleted/c.py": payload,
        },
        damage_delete=["deleted/a.py", "deleted/b.py", "deleted/c.py"],
        restore_map=[],
        label="live-highest-uncovered-delete",
    )
    result["mode"] = "uncovered-destructive-no-procedure"
    result["note"] = (
        "No restore map exists on the live manifest for this action; "
        "rehearsal applies empty restore after delete and must not report "
        "byte recovery."
    )
    return result


def tools_lib_census(repo: Path = REPO) -> dict[str, Any]:
    root = repo / "tools" / "lib"
    files = []
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files.append(
                    {
                        "path": path.relative_to(repo).as_posix(),
                        "bytes": path.stat().st_size,
                    }
                )
    return {
        "path": "tools/lib",
        "exists": root.is_dir(),
        "file_n": len(files),
        "files": files,
    }


def measure(repo: Path = REPO) -> dict[str, Any]:
    loc, entries = load_live_entries(repo)
    existence = [check_references(e, repo) for e in entries]
    coverage = coverage_for_executed(entries)
    fixture_exist = fixture_manifest_controls(repo)
    fixture_reh = fixture_controls()
    highest = highest_risk_live(entries, coverage)
    live_reh = rehearse_live_highest(highest)
    git = git_info(repo)
    salvage = tools_lib_census(repo)
    missing_refs = sum(row["missing_n"] for row in existence)
    covered_n = sum(1 for row in coverage if row["covered_by_manifest"])
    restore_possible = (
        loc["present"]
        and covered_n == len(coverage)
        and missing_refs == 0
        and live_reh["byte_recovered"] is True
        and fixture_reh["control_pass"]
    )
    return {
        "manifest": loc,
        "entries": entries,
        "existence": existence,
        "coverage": coverage,
        "covered_n": covered_n,
        "executed_n": len(coverage),
        "missing_reference_n": missing_refs,
        "fixture_existence": fixture_exist,
        "fixture_rehearsal": fixture_reh,
        "highest_risk": highest,
        "live_rehearsal": live_reh,
        "git": git,
        "salvage": salvage,
        "restore_possible": restore_possible,
        "answer_yes": restore_possible,
    }


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    print(dump(measure()))
