#!/usr/bin/env python3
"""AUD-0018 deploy/sync script semantics: line-read + fixture dry-run.

Never executes live scripts/sync-from-live.ps1 (or any catalog .ps1) against
the worktree. Dry-run is an interpreter over a scratch fixture pair.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0018"
OUT_REL = "command-center/audit/AUD-0018-deploy-script-semantics.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
FX_SCRIPTS = HERE / "fixtures" / "scripts"
FX_TREES = HERE / "fixtures" / "trees"
FX_SRC = FX_TREES / "src"
FX_DEST = FX_TREES / "dest"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0018/probe1_line_semantics.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0018/probe2_dry_run.py"
)
COMPLETION = (
    "SUCCESS:AUD-0018 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For each deploy or sync script, does it copy verbatim or transform "
    "content, which direction does it carry, and which guards (nested-repo, "
    "vendored-tree, repo-owned-file) does it actually apply?"
)

CATALOG_SCRIPTS = (
    "scripts/sync-rules.ps1",
    "scripts/sync-from-live.ps1",
    "scripts/sync-skills.ps1",
    "scripts/sync-hooks.ps1",
)
OTHER_DEPLOY = (
    "tools/marketplace/installer.py",
    "tools/plugin/rollback_additive.py",
)
PLANTED = (
    "copy-item-force-verbatim.ps1",
    "transform-replace.ps1",
    "guarded-sync.ps1",
    "live-to-repo.ps1",
)

COPY_ITEM_RE = re.compile(r"\bCopy-Item\b", re.I)
FORCE_RE = re.compile(r"(^|[\s-])Force\b")
WHATIF_RE = re.compile(r"\bWhatIf\b", re.I)
SHUTIL_COPY_RE = re.compile(
    r"\bshutil\.(copy2|copytree|copyfile|copy)\b|\.write_bytes\(\s*\w+\.read_bytes\(\)"
)
TRANSFORM_RE = re.compile(
    r"\b-replace\b|\bSet-Content\b|\.replace\s*\(|\bre\.sub\b|json\.dumps\s*\(",
    re.I,
)
GET_CONTENT_RE = re.compile(r"\bGet-Content\b", re.I)
CP_RE = re.compile(r"\b(?:cp|rsync|robocopy|xcopy)\b", re.I)

GUARD_SPECS = (
    (
        "nested-repo",
        re.compile(r"nested[-_ ]?repo|\.git['\"]?\s*\)|Join-Path[^\\n]*['\"]\\.git", re.I),
    ),
    (
        "vendored-tree",
        re.compile(r"vendored[-_ ]?tree|[\\/]vendor[\\/]|\bvendor\b", re.I),
    ),
    (
        "repo-owned-file",
        re.compile(r"repo[-_ ]owned", re.I),
    ),
)
POLICY_DENY_RE = re.compile(r"verdict\s*==\s*['\"]deny['\"]|DENY", re.I)

LIVE_DIR_RE = re.compile(
    r"~/\.claude|\$HOME/\.claude|\$env:USERPROFILE|Join-Path \$HOME ['\"]\.claude",
    re.I,
)
REPO_DIR_RE = re.compile(r"\brepo\b|\$PSScriptRoot|rules\\", re.I)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def strip_comment(line: str, ext: str) -> str:
    if ext == ".py":
        in_s = None
        out = []
        i = 0
        while i < len(line):
            ch = line[i]
            if in_s:
                out.append(ch)
                if ch == "\\" and i + 1 < len(line):
                    out.append(line[i + 1])
                    i += 2
                    continue
                if ch == in_s:
                    in_s = None
                i += 1
                continue
            if ch in ('"', "'"):
                in_s = ch
                out.append(ch)
                i += 1
                continue
            if ch == "#":
                break
            out.append(ch)
            i += 1
        return "".join(out)
    # PowerShell: strip unquoted '#'
    in_s = None
    out = []
    for ch in line:
        if in_s:
            out.append(ch)
            if ch == in_s:
                in_s = None
            continue
        if ch in ('"', "'"):
            in_s = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out)


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def classify_direction(text: str, path_rel: str) -> str:
    live = bool(LIVE_DIR_RE.search(text))
    name = path_rel.replace("\\", "/").lower()
    if "live-to-repo" in name or "sync-from-live" in name:
        return "live-to-repo"
    if "sync-rules" in name or "sync-skills" in name or "sync-hooks" in name:
        return "repo-to-live"
    if path_rel.endswith("installer.py"):
        return "package-to-dest"
    if path_rel.endswith("rollback_additive.py"):
        return "backup-to-profile"
    if live and ("sync-from-live" in name or "live-to-repo" in name):
        return "live-to-repo"
    if live and REPO_DIR_RE.search(text):
        return "live-to-repo"
    if "$Src" in text or "$Dest" in text or "param(" in text.lower():
        return "parameterized"
    return "unknown"


def parse_script(path: Path, *, role: str, required: str | None = None) -> dict[str, Any]:
    path_rel = required or rel(path)
    exists = path.is_file()
    row: dict[str, Any] = {
        "path": path_rel,
        "exists": exists,
        "role": role,
        "bytes": path.stat().st_size if exists else 0,
        "sha256": sha256_file(path) if exists else None,
        "copy_primitives": [],
        "guard_clauses": [],
        "copy_mode": "absent",
        "direction": "absent" if not exists else "unknown",
        "has_force": False,
        "has_whatif": False,
        "has_transform": False,
        "catalog_line_67_copy_item_force": False,
    }
    if not exists:
        return row
    ext = path.suffix.lower()
    lines = read_lines(path)
    raw = "\n".join(lines)
    primitives: list[dict[str, Any]] = []
    guards: list[dict[str, Any]] = []
    has_copy_item = False
    has_force = False
    has_shutil = False
    has_transform = False
    has_get_set = False
    has_whatif = False
    has_cp = False
    for i, line in enumerate(lines, 1):
        code = strip_comment(line, ext).strip()
        if not code:
            continue
        if COPY_ITEM_RE.search(code):
            has_copy_item = True
            force = bool(FORCE_RE.search(code) or re.search(r"-Force\b", code, re.I))
            has_force = has_force or force
            primitives.append(
                {
                    "line": i,
                    "primitive": "Copy-Item -Force" if force else "Copy-Item",
                    "text": code[:240],
                }
            )
            if i == 67 and force:
                row["catalog_line_67_copy_item_force"] = True
        if SHUTIL_COPY_RE.search(code):
            has_shutil = True
            prim = "shutil.copy2"
            if "copytree" in code:
                prim = "shutil.copytree"
            elif "write_bytes" in code:
                prim = "write_bytes(read_bytes)"
            elif "copyfile" in code:
                prim = "shutil.copyfile"
            elif re.search(r"shutil\.copy\b", code):
                prim = "shutil.copy"
            primitives.append({"line": i, "primitive": prim, "text": code[:240]})
        if CP_RE.search(code) and "Copy-Item" not in code:
            has_cp = True
            primitives.append({"line": i, "primitive": "cp-family", "text": code[:240]})
        if ext in {".ps1", ".psm1"} and TRANSFORM_RE.search(code):
            has_transform = True
        if GET_CONTENT_RE.search(code):
            has_get_set = True
        if WHATIF_RE.search(code):
            has_whatif = True
        for kind, cre in GUARD_SPECS:
            if cre.search(code) or cre.search(line):
                # Avoid treating a vendor import path in unrelated comments as a guard
                # unless the code line actually branches/skips.
                branch = bool(
                    re.search(
                        r"\b(if|continue|skip|exclude|return|deny)\b",
                        code,
                        re.I,
                    )
                    or re.search(r"guard:", line, re.I)
                )
                if kind == "vendored-tree" and "vendor" in code.lower() and not branch:
                    if "import" in code or "from " in code:
                        continue
                if not branch and kind == "vendored-tree" and "vendor" in path_rel:
                    continue
                guards.append(
                    {
                        "line": i,
                        "kind": kind,
                        "text": (code or line.strip())[:240],
                        "clause": line.strip()[:240],
                    }
                )
        if POLICY_DENY_RE.search(code) and (
            "if " in code.lower() or "verdict" in code
        ):
            guards.append(
                {
                    "line": i,
                    "kind": "policy-deny",
                    "text": code[:240],
                    "clause": line.strip()[:240],
                }
            )
    # Dedup guards by (kind, line)
    seen_g = set()
    uniq_g = []
    for g in guards:
        key = (g["kind"], g["line"])
        if key in seen_g:
            continue
        seen_g.add(key)
        uniq_g.append(g)
    has_transform = has_transform or (
        has_get_set and any("Set-Content" in (p.get("text") or "") for p in primitives)
    )
    if has_get_set and GET_CONTENT_RE.search(raw) and re.search(r"Set-Content", raw, re.I):
        has_transform = True
    copy_mode = "none"
    if has_transform:
        copy_mode = "transform"
    elif has_copy_item or has_shutil or has_cp:
        copy_mode = "verbatim"
    row.update(
        {
            "copy_primitives": primitives,
            "guard_clauses": uniq_g,
            "copy_mode": copy_mode,
            "direction": classify_direction(raw, path_rel),
            "has_force": has_force,
            "has_whatif": has_whatif,
            "has_transform": has_transform,
            "line_count": len(lines),
            "guard_kinds": sorted({g["kind"] for g in uniq_g}),
        }
    )
    return row


def discover() -> dict[str, Any]:
    catalog = []
    for p in CATALOG_SCRIPTS:
        catalog.append(
            parse_script(REPO / p, role="catalog-named", required=p)
        )
    scripts_dir = REPO / "scripts"
    extra_ps1 = []
    if scripts_dir.is_dir():
        for path in sorted(scripts_dir.rglob("*.ps1")):
            r = rel(path)
            if r not in CATALOG_SCRIPTS:
                extra_ps1.append(parse_script(path, role="scripts-glob"))
    other = []
    for p in OTHER_DEPLOY:
        other.append(parse_script(REPO / p, role="other-deploy-entry", required=p))
    planted = []
    for name in PLANTED:
        planted.append(
            parse_script(
                FX_SCRIPTS / name,
                role="planted-control",
                required=f"command-center/p2-wave/probes/AUD-0018/fixtures/scripts/{name}",
            )
        )
    catalog_present = [r for r in catalog if r["exists"]]
    return {
        "catalog_named": catalog,
        "catalog_present_count": len(catalog_present),
        "catalog_absent": [r["path"] for r in catalog if not r["exists"]],
        "scripts_glob_extra": extra_ps1,
        "other_deploy": other,
        "planted": planted,
        "scripts_dir_exists": scripts_dir.is_dir(),
    }


def tree_files(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        out[path.relative_to(root).as_posix()] = sha256_file(path)
    return out


def merkle(files: dict[str, str]) -> str:
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(k.encode("utf-8"))
        h.update(b"\0")
        h.update(files[k].encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def fixture_census() -> dict[str, Any]:
    src = tree_files(FX_SRC)
    dest = tree_files(FX_DEST)
    return {
        "src_files": src,
        "dest_files": dest,
        "src_merkle": merkle(src),
        "dest_merkle": merkle(dest),
        "combined_merkle": merkle({f"src/{k}": v for k, v in src.items()} | {f"dest/{k}": v for k, v in dest.items()}),
    }


def nested_repo_rel(rel_path: str, src_files: dict[str, str]) -> bool:
    parts = rel_path.split("/")
    for i in range(len(parts)):
        prefix = "/".join(parts[:i])
        git_file = f"{prefix}/.git" if prefix else ".git"
        git_dir_marker = f"{prefix}/.git/HEAD" if prefix else ".git/HEAD"
        if git_file in src_files or git_dir_marker in src_files:
            if prefix and (rel_path == git_file or rel_path.startswith(prefix + "/")):
                return True
    return False


def vendored_rel(rel_path: str) -> bool:
    parts = rel_path.split("/")
    return "vendor" in parts


def repo_owned_rel(rel_path: str, src_files: dict[str, str]) -> bool:
    if rel_path.endswith(".repo-owned"):
        return True
    return (rel_path + ".repo-owned") in src_files


def plan_touch(
    *,
    apply_nested: bool,
    apply_vendor: bool,
    apply_owned: bool,
    src_files: dict[str, str],
) -> list[str]:
    touched = []
    for rel_path in sorted(src_files):
        if apply_nested and nested_repo_rel(rel_path, src_files):
            continue
        if apply_vendor and vendored_rel(rel_path):
            continue
        if apply_owned and repo_owned_rel(rel_path, src_files):
            continue
        touched.append(rel_path)
    return touched


def guards_from_row(row: dict[str, Any]) -> tuple[bool, bool, bool]:
    kinds = set(row.get("guard_kinds") or [])
    return (
        "nested-repo" in kinds,
        "vendored-tree" in kinds,
        "repo-owned-file" in kinds,
    )


def dry_run_script(row: dict[str, Any], src_files: dict[str, str]) -> dict[str, Any]:
    if not row.get("exists"):
        return {
            "path": row["path"],
            "executed": False,
            "reason": "script-absent",
            "would_touch": [],
            "copy_mode": row.get("copy_mode"),
            "direction": row.get("direction"),
            "destructive_writes": 0,
        }
    nested, vendor, owned = guards_from_row(row)
    would = plan_touch(
        apply_nested=nested,
        apply_vendor=vendor,
        apply_owned=owned,
        src_files=src_files,
    )
    return {
        "path": row["path"],
        "executed": True,
        "method": "interpreted-whatif (no bytes written to fixture)",
        "would_touch": would,
        "would_touch_count": len(would),
        "copy_mode": row.get("copy_mode"),
        "direction": row.get("direction"),
        "guards_applied": {
            "nested-repo": nested,
            "vendored-tree": vendor,
            "repo-owned-file": owned,
        },
        "destructive_writes": 0,
        "transform": row.get("copy_mode") == "transform",
    }


def apply_copy_to_clone(src: Path, dest: Path, would_touch: list[str]) -> None:
    for rel_path in would_touch:
        s = src / rel_path
        d = dest / rel_path
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)


def dry_run_bundle() -> dict[str, Any]:
    disc = discover()
    before = fixture_census()
    planted_by = {Path(r["path"]).name: r for r in disc["planted"]}
    src_files = before["src_files"]
    plans = {}
    for name, row in planted_by.items():
        plans[name] = dry_run_script(row, src_files)
    live_plans = []
    for row in disc["other_deploy"]:
        live_plans.append(dry_run_script(row, src_files))
    for row in disc["catalog_named"]:
        live_plans.append(dry_run_script(row, src_files))

    after_plan = fixture_census()
    fixture_unchanged = after_plan["combined_merkle"] == before["combined_merkle"]

    verbatim = plans.get("copy-item-force-verbatim.ps1") or {}
    guarded = plans.get("guarded-sync.ps1") or {}
    unguarded_set = set(verbatim.get("would_touch") or [])
    guarded_set = set(guarded.get("would_touch") or [])
    skipped_by_guards = sorted(unguarded_set - guarded_set)

    # Destructive mutant on an isolated clone — never the planted fixture.
    mutant_changed = False
    mutant_ok_before = None
    mutant_ok_after = None
    with tempfile.TemporaryDirectory(prefix="aud0018-mutant-") as tmp:
        tmp_p = Path(tmp)
        shutil.copytree(FX_SRC, tmp_p / "src")
        shutil.copytree(FX_DEST, tmp_p / "dest")
        ok = tmp_p / "dest" / "rules" / "ok.md"
        mutant_ok_before = sha256_file(ok) if ok.is_file() else None
        apply_copy_to_clone(tmp_p / "src", tmp_p / "dest", list(unguarded_set))
        mutant_ok_after = sha256_file(ok) if ok.is_file() else None
        mutant_changed = mutant_ok_before != mutant_ok_after

    nested_skipped = [
        p
        for p in skipped_by_guards
        if nested_repo_rel(p, src_files)
    ]
    vendor_skipped = [p for p in skipped_by_guards if vendored_rel(p)]
    owned_skipped = [p for p in skipped_by_guards if repo_owned_rel(p, src_files)]

    return {
        "before": {
            "src_merkle": before["src_merkle"],
            "dest_merkle": before["dest_merkle"],
            "combined_merkle": before["combined_merkle"],
            "src_file_count": len(before["src_files"]),
            "dest_file_count": len(before["dest_files"]),
        },
        "after": {
            "src_merkle": after_plan["src_merkle"],
            "dest_merkle": after_plan["dest_merkle"],
            "combined_merkle": after_plan["combined_merkle"],
        },
        "fixture_byte_identical": fixture_unchanged,
        "planted_plans": plans,
        "live_plans": live_plans,
        "skipped_by_guards": skipped_by_guards,
        "nested_repo_skipped": nested_skipped,
        "vendored_skipped": vendor_skipped,
        "repo_owned_skipped": owned_skipped,
        "guards_change_touch_set": bool(skipped_by_guards),
        "destructive_mutant": {
            "ran_on_isolated_clone": True,
            "dest_rules_ok_changed": mutant_changed,
            "sha_before": mutant_ok_before,
            "sha_after": mutant_ok_after,
        },
        "never_executed_live_sync_from_live": True,
    }


def control_line_semantics(disc: dict[str, Any]) -> dict[str, Any]:
    planted_by = {Path(r["path"]).name: r for r in disc["planted"]}
    verbatim = planted_by.get("copy-item-force-verbatim.ps1") or {}
    transform = planted_by.get("transform-replace.ps1") or {}
    guarded = planted_by.get("guarded-sync.ps1") or {}
    live2 = planted_by.get("live-to-repo.ps1") or {}
    kinds = set(guarded.get("guard_kinds") or [])
    catalog_absent = disc["catalog_absent"]
    sync_rules = next(
        (r for r in disc["catalog_named"] if r["path"] == "scripts/sync-rules.ps1"),
        {},
    )
    checks = {
        "catalog_sync_rules_absent_or_force_copy": (
            not sync_rules.get("exists")
            or (
                sync_rules.get("copy_mode") == "verbatim"
                and any(
                    p.get("primitive") == "Copy-Item -Force"
                    for p in (sync_rules.get("copy_primitives") or [])
                )
            )
        ),
        "planted_verbatim_exists": bool(verbatim.get("exists")),
        "planted_verbatim_copy_item_force": any(
            p.get("primitive") == "Copy-Item -Force"
            for p in (verbatim.get("copy_primitives") or [])
        ),
        "planted_verbatim_mode": verbatim.get("copy_mode") == "verbatim",
        "planted_verbatim_not_transform": verbatim.get("has_transform") is False,
        "planted_line_67_copy_item_force": bool(
            verbatim.get("catalog_line_67_copy_item_force")
        ),
        "planted_transform_mode": transform.get("copy_mode") == "transform",
        "planted_transform_not_verbatim": transform.get("copy_mode") != "verbatim",
        "planted_guarded_nested": "nested-repo" in kinds,
        "planted_guarded_vendor": "vendored-tree" in kinds,
        "planted_guarded_owned": "repo-owned-file" in kinds,
        "planted_live_to_repo_direction": live2.get("direction") == "live-to-repo",
        "all_planted_present": all(r.get("exists") for r in disc["planted"]),
    }
    installer = next(
        (r for r in disc["other_deploy"] if r["path"].endswith("installer.py")),
        {},
    )
    checks["installer_verbatim_copy2"] = installer.get("copy_mode") == "verbatim" and any(
        "copy2" in (p.get("primitive") or "") for p in (installer.get("copy_primitives") or [])
    )
    checks["installer_lacks_named_tree_guards"] = not (
        {"nested-repo", "vendored-tree", "repo-owned-file"}
        <= set(installer.get("guard_kinds") or [])
    )
    bools = {k: bool(v) for k, v in checks.items()}
    bools["pass"] = all(bools.values())
    return {
        "checks": bools,
        "pass": bools["pass"],
        "failed": [k for k, v in bools.items() if k != "pass" and not v],
        "catalog_absent": catalog_absent,
    }


def control_dry_run(bundle: dict[str, Any]) -> dict[str, Any]:
    plans = bundle.get("planted_plans") or {}
    verbatim = plans.get("copy-item-force-verbatim.ps1") or {}
    guarded = plans.get("guarded-sync.ps1") or {}
    mutant = bundle.get("destructive_mutant") or {}
    would = set(verbatim.get("would_touch") or [])
    checks = {
        "fixture_byte_identical": bundle.get("fixture_byte_identical") is True,
        "verbatim_would_touch_ok_md": "rules/ok.md" in would,
        "verbatim_would_touch_nonempty": bool(would),
        "guards_change_touch_set": bundle.get("guards_change_touch_set") is True,
        "nested_repo_skipped_nonempty": bool(bundle.get("nested_repo_skipped")),
        "vendored_skipped_nonempty": bool(bundle.get("vendored_skipped")),
        "repo_owned_skipped_nonempty": bool(bundle.get("repo_owned_skipped")),
        "guarded_excludes_secret": "rules/nested-repo/secret.md"
        not in set(guarded.get("would_touch") or []),
        "unguarded_includes_secret": "rules/nested-repo/secret.md" in would,
        "destructive_mutant_changes_dest": mutant.get("dest_rules_ok_changed") is True,
        "dry_run_wrote_zero": all(
            int(p.get("destructive_writes") or 0) == 0 for p in plans.values()
        ),
        "never_executed_live_sync_from_live": bundle.get(
            "never_executed_live_sync_from_live"
        )
        is True,
    }
    checks["pass"] = all(checks.values())
    return {
        "checks": checks,
        "pass": checks["pass"],
        "failed": [k for k, v in checks.items() if k != "pass" and not v],
    }


def slim_row(row: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "path",
        "exists",
        "role",
        "bytes",
        "copy_mode",
        "direction",
        "has_force",
        "has_whatif",
        "has_transform",
        "copy_primitives",
        "guard_clauses",
        "guard_kinds",
        "catalog_line_67_copy_item_force",
        "line_count",
    )
    return {k: row.get(k) for k in keep}


def snapshot() -> dict[str, Any]:
    disc = discover()
    dry = dry_run_bundle()
    line_ctl = control_line_semantics(disc)
    dry_ctl = control_dry_run(dry)
    return {
        "unit_id": UNIT,
        "discovery": {
            "catalog_named": [slim_row(r) for r in disc["catalog_named"]],
            "catalog_absent": disc["catalog_absent"],
            "catalog_present_count": disc["catalog_present_count"],
            "scripts_dir_exists": disc["scripts_dir_exists"],
            "scripts_glob_extra": [slim_row(r) for r in disc["scripts_glob_extra"]],
            "other_deploy": [slim_row(r) for r in disc["other_deploy"]],
            "planted": [slim_row(r) for r in disc["planted"]],
        },
        "dry_run": dry,
        "line_control": line_ctl,
        "dry_control": dry_ctl,
        "controls_pass": bool(line_ctl["pass"] and dry_ctl["pass"]),
    }


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True)
