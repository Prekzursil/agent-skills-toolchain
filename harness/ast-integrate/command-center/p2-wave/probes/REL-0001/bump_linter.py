#!/usr/bin/env python3
"""Diff-derived semantic-version bump linter (REL-0001).

Derives the REQUIRED bump from a previous tree vs a new tree (the same
comparison git-tag..HEAD materializes) and exits non-zero when the
declared version is lower than the derived bump.

Stdout is a single JSON object. Diagnostics go to stderr.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFAULT_RULES = HERE / "change_class_rules.json"
RANK = {"NONE": 0, "PATCH": 1, "MINOR": 2, "MAJOR": 3}
SKIP_DIR_NAMES = {".git", "__pycache__", ".pyc"}


def load_rules(path: Path | None = None) -> dict:
    p = path or DEFAULT_RULES
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("rules"):
        raise ValueError(f"invalid rule table: {p}")
    return data


def rule_bump(rules: dict, rule_id: str) -> str:
    for row in rules.get("rules") or []:
        if isinstance(row, dict) and row.get("id") == rule_id:
            bump = str(row.get("bump") or "NONE").upper()
            if bump not in RANK:
                raise ValueError(f"unknown bump {bump} for {rule_id}")
            return bump
    raise KeyError(f"rule id not in table: {rule_id}")


def parse_semver(text: str) -> tuple[int, int, int]:
    core = str(text or "0.0.0").strip()
    core = core.split("+")[0].split("-")[0]
    parts = core.split(".")
    nums: list[int] = []
    for i in range(3):
        try:
            nums.append(int(parts[i]) if i < len(parts) else 0)
        except ValueError:
            nums.append(0)
    return nums[0], nums[1], nums[2]


def bump_between(old: str, new: str) -> str:
    o, n = parse_semver(old), parse_semver(new)
    if n < o:
        return "DOWNGRADE"
    if n[0] > o[0]:
        return "MAJOR"
    if n[1] > o[1]:
        return "MINOR"
    if n[2] > o[2]:
        return "PATCH"
    return "NONE"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def iter_files(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        out[rel] = path.read_bytes()
    return out


def loads(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def permission_set(obj: Any, fields: list[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in fields:
                if isinstance(val, list):
                    found.update(str(x) for x in val)
                elif isinstance(val, dict):
                    for subk, subv in val.items():
                        if isinstance(subv, list):
                            found.update(f"{subk}:{x}" for x in subv)
                        else:
                            found.add(f"{subk}:{subv}")
                elif val is not None:
                    found.add(str(val))
            else:
                found.update(permission_set(val, fields))
    elif isinstance(obj, list):
        for item in obj:
            found.update(permission_set(item, fields))
    return found


def blueprint_ids(obj: Any) -> set[str]:
    ids: set[str] = set()
    if not isinstance(obj, dict):
        return ids
    bp = obj.get("blueprints")
    if isinstance(bp, list):
        for item in bp:
            if isinstance(item, dict) and item.get("id"):
                ids.add(str(item["id"]))
            elif isinstance(item, str):
                ids.add(item)
    elif isinstance(bp, dict):
        ids.update(str(k) for k in bp.keys())
    return ids


def strip_version_fields(obj: Any, fields: set[str]) -> Any:
    if isinstance(obj, dict):
        return {
            k: strip_version_fields(v, fields)
            for k, v in obj.items()
            if k not in fields
        }
    if isinstance(obj, list):
        return [strip_version_fields(x, fields) for x in obj]
    return obj


def collect_required(schema: Any, path: str = "$") -> dict[str, set[str]]:
    rows: dict[str, set[str]] = {}
    if isinstance(schema, dict):
        req = schema.get("required")
        if isinstance(req, list):
            rows[path] = {str(x) for x in req}
        for key, val in schema.items():
            if key == "required":
                continue
            rows.update(collect_required(val, f"{path}.{key}"))
    elif isinstance(schema, list):
        for i, val in enumerate(schema):
            rows.update(collect_required(val, f"{path}[{i}]"))
    return rows


def surface_for(rel: str, obj: Any) -> str:
    name = Path(rel).name.lower()
    posix = rel.replace("\\", "/").lower()
    if name == "plugin.json":
        return "plugin_package"
    if "marketplace" in name or "/marketplace/" in posix:
        return "registry_entry"
    if name == "pack.json":
        return "blueprint_pack"
    if "councilspec" in name or "council-spec" in name:
        return "councilspec_schema"
    if isinstance(obj, dict):
        if obj.get("blueprints") is not None and obj.get("id"):
            return "blueprint_pack"
        if "$schema" in obj and (
            "councilspec" in str(obj.get("title") or "").lower()
            or "councilspec" in str(obj.get("$id") or "").lower()
        ):
            return "councilspec_schema"
        if obj.get("kind") == "plugin_manifest":
            return "plugin_package"
        if obj.get("kind") == "marketplace_entry":
            return "registry_entry"
    if "/hooks/" in posix or name.startswith("hook."):
        return "plugin_package"
    return "other"


def finding(rules: dict, rule_id: str, surface: str, path: str, detail: str) -> dict:
    return {
        "rule_id": rule_id,
        "bump": rule_bump(rules, rule_id),
        "surface": surface,
        "path": path,
        "detail": detail,
    }


def classify_json(
    rules: dict,
    surface: str,
    rel: str,
    old_obj: Any,
    new_obj: Any,
) -> list[dict]:
    out: list[dict] = []
    if old_obj is None and new_obj is None:
        return out
    if old_obj is not None and new_obj is None:
        if surface != "other":
            out.append(
                finding(
                    rules,
                    "contract_artifact_unparseable",
                    surface,
                    rel,
                    "new tree is not valid JSON",
                )
            )
        return out
    if old_obj is None and new_obj is not None:
        if surface != "other":
            out.append(
                finding(
                    rules,
                    "optional_contract_key_added",
                    surface,
                    rel,
                    "new contract artifact added",
                )
            )
        return out

    version_fields = set(rules.get("version_fields") or ["version"])
    if strip_version_fields(old_obj, version_fields) == strip_version_fields(
        new_obj, version_fields
    ):
        return out

    desc_fields = set(rules.get("description_fields") or [])
    hook_fields = set(rules.get("hook_contract_fields") or [])
    perm_fields = list(rules.get("permission_fields") or [])
    required = list(
        (rules.get("required_keys_by_surface") or {}).get(surface) or []
    )

    if isinstance(old_obj, dict) and isinstance(new_obj, dict):
        for key in required:
            if key in old_obj and key not in new_obj:
                out.append(
                    finding(
                        rules,
                        "required_manifest_key_removed",
                        surface,
                        rel,
                        f"removed required key '{key}'",
                    )
                )

        old_perm = permission_set(old_obj, perm_fields)
        new_perm = permission_set(new_obj, perm_fields)
        extra = sorted(new_perm - old_perm)
        if extra:
            out.append(
                finding(
                    rules,
                    "permission_widened",
                    surface,
                    rel,
                    "added permissions: " + ",".join(extra),
                )
            )

        for key in sorted(hook_fields):
            if key in old_obj and key not in new_obj:
                out.append(
                    finding(
                        rules,
                        "hook_contract_signature_changed",
                        surface,
                        rel,
                        f"hook field '{key}' removed",
                    )
                )
            elif key in old_obj and key in new_obj and old_obj[key] != new_obj[key]:
                out.append(
                    finding(
                        rules,
                        "hook_contract_signature_changed",
                        surface,
                        rel,
                        f"hook field '{key}' changed",
                    )
                )

        if surface == "blueprint_pack" or "blueprints" in old_obj or "blueprints" in new_obj:
            retired = sorted(blueprint_ids(old_obj) - blueprint_ids(new_obj))
            if retired:
                out.append(
                    finding(
                        rules,
                        "blueprint_id_retired",
                        surface if surface != "other" else "blueprint_pack",
                        rel,
                        "retired blueprint ids: " + ",".join(retired),
                    )
                )

        if surface == "councilspec_schema" or (
            isinstance(old_obj, dict) and "$schema" in old_obj
        ):
            old_req = collect_required(old_obj)
            new_req = collect_required(new_obj)
            grew: list[str] = []
            for spath, old_set in old_req.items():
                added = sorted((new_req.get(spath) or set()) - old_set)
                for name in added:
                    grew.append(f"{spath}:{name}")
            for spath, new_set in new_req.items():
                if spath not in old_req and new_set:
                    for name in sorted(new_set):
                        grew.append(f"{spath}:{name}")
            if grew:
                out.append(
                    finding(
                        rules,
                        "schema_field_became_required",
                        "councilspec_schema",
                        rel,
                        "newly required: " + ",".join(grew),
                    )
                )

        skip_value = set(version_fields) | hook_fields | set(perm_fields) | {"blueprints", "required"}
        old_keys = set(old_obj) - version_fields
        new_keys = set(new_obj) - version_fields
        for key in sorted(new_keys - old_keys):
            if key in required:
                continue
            out.append(
                finding(
                    rules,
                    "optional_contract_key_added",
                    surface if surface != "other" else "plugin_package",
                    rel,
                    f"added optional key '{key}'",
                )
            )

        for key in sorted(old_keys & new_keys):
            if key in skip_value:
                continue
            if old_obj[key] == new_obj[key]:
                continue
            if key in desc_fields or (
                isinstance(old_obj[key], str) and isinstance(new_obj[key], str)
            ):
                out.append(
                    finding(
                        rules,
                        "documentation_or_noncontract_edit",
                        surface,
                        rel,
                        f"documentation field '{key}' changed",
                    )
                )
            elif isinstance(old_obj[key], dict) and isinstance(new_obj[key], dict):
                nested_surface = surface
                out.extend(
                    classify_json(rules, nested_surface, f"{rel}#{key}", old_obj[key], new_obj[key])
                )
            elif isinstance(old_obj[key], list) and isinstance(new_obj[key], list):
                if key == "hooks" and old_obj[key] != new_obj[key]:
                    # list of hook paths: dropping one is a signature/registration change
                    old_h = {str(x) for x in old_obj[key]}
                    new_h = {str(x) for x in new_obj[key]}
                    dropped = sorted(old_h - new_h)
                    if dropped:
                        out.append(
                            finding(
                                rules,
                                "hook_contract_signature_changed",
                                surface,
                                rel,
                                "hook registration removed: " + ",".join(dropped),
                            )
                        )
                    added_h = sorted(new_h - old_h)
                    if added_h:
                        out.append(
                            finding(
                                rules,
                                "optional_contract_key_added",
                                surface,
                                rel,
                                "hook registration added: " + ",".join(added_h),
                            )
                        )
                else:
                    out.append(
                        finding(
                            rules,
                            "documentation_or_noncontract_edit",
                            surface,
                            rel,
                            f"list field '{key}' changed",
                        )
                    )
            else:
                out.append(
                    finding(
                        rules,
                        "documentation_or_noncontract_edit",
                        surface,
                        rel,
                        f"value of '{key}' changed",
                    )
                )
        return out

    if old_obj != new_obj:
        out.append(
            finding(
                rules,
                "documentation_or_noncontract_edit",
                surface,
                rel,
                "non-object JSON changed",
            )
        )
    return out


def match_renames(
    old_files: dict[str, bytes], new_files: dict[str, bytes]
) -> list[tuple[str, str]]:
    old_only = set(old_files) - set(new_files)
    new_only = set(new_files) - set(old_files)
    old_by_hash: dict[str, list[str]] = {}
    for path in old_only:
        old_by_hash.setdefault(digest_bytes(old_files[path]), []).append(path)
    new_by_hash: dict[str, list[str]] = {}
    for path in new_only:
        new_by_hash.setdefault(digest_bytes(new_files[path]), []).append(path)
    pairs: list[tuple[str, str]] = []
    used_old: set[str] = set()
    used_new: set[str] = set()
    for path in sorted(new_only):
        h = digest_bytes(new_files[path])
        ocands = [p for p in old_by_hash.get(h, []) if p not in used_old]
        ncands = [p for p in new_by_hash.get(h, []) if p not in used_new]
        if len(ocands) == 1 and len(ncands) == 1:
            pairs.append((ocands[0], ncands[0]))
            used_old.add(ocands[0])
            used_new.add(ncands[0])
    return pairs


def read_version(files: dict[str, bytes]) -> str | None:
    for name in ("plugin.json", "marketplace.json", "pack.json"):
        if name in files:
            obj = loads(files[name])
            if isinstance(obj, dict) and obj.get("version"):
                return str(obj["version"])
    for rel, raw in files.items():
        if Path(rel).name == "plugin.json":
            obj = loads(raw)
            if isinstance(obj, dict) and obj.get("version"):
                return str(obj["version"])
    return None


def max_bump(findings: list[dict]) -> str:
    best = "NONE"
    for row in findings:
        bump = str(row.get("bump") or "NONE").upper()
        if RANK.get(bump, 0) > RANK[best]:
            best = bump
    return best


def classify_trees(
    old_files: dict[str, bytes],
    new_files: dict[str, bytes],
    rules: dict,
) -> tuple[list[dict], list[dict]]:
    findings: list[dict] = []
    renames = match_renames(old_files, new_files)
    renamed_old = {a for a, _ in renames}
    renamed_new = {b for _, b in renames}
    rename_rows = []
    for old_p, new_p in renames:
        row = finding(
            rules,
            "pure_rename_byte_identical",
            surface_for(old_p, loads(old_files[old_p])),
            f"{old_p}->{new_p}",
            "byte-identical rename",
        )
        findings.append(row)
        rename_rows.append(
            {
                "from": old_p,
                "to": new_p,
                "sha256": digest_bytes(old_files[old_p]),
                "bump": "NONE",
            }
        )

    changed_paths = sorted(
        (set(old_files) & set(new_files))
        | (set(old_files) - set(new_files) - renamed_old)
        | (set(new_files) - set(old_files) - renamed_new)
    )
    for rel in changed_paths:
        if rel in renamed_old or rel in renamed_new:
            continue
        old_raw = old_files.get(rel)
        new_raw = new_files.get(rel)
        if old_raw is not None and new_raw is not None and digest_bytes(old_raw) == digest_bytes(new_raw):
            continue
        old_obj = loads(old_raw) if old_raw is not None else None
        new_obj = loads(new_raw) if new_raw is not None else None
        surface = surface_for(rel, new_obj if new_obj is not None else old_obj)
        if old_raw is not None and new_raw is None:
            if surface == "plugin_package" and Path(rel).name == "plugin.json":
                findings.append(
                    finding(
                        rules,
                        "required_manifest_key_removed",
                        surface,
                        rel,
                        "plugin.json deleted",
                    )
                )
            elif surface == "blueprint_pack":
                obj = loads(old_raw)
                retired = sorted(blueprint_ids(obj) if isinstance(obj, dict) else [])
                findings.append(
                    finding(
                        rules,
                        "blueprint_id_retired",
                        surface,
                        rel,
                        "pack removed; ids: " + ",".join(retired),
                    )
                )
            elif surface == "plugin_package" and (
                "/hooks/" in rel.replace("\\", "/") or Path(rel).name.startswith("hook")
            ):
                findings.append(
                    finding(
                        rules,
                        "hook_contract_signature_changed",
                        surface,
                        rel,
                        "hook file deleted",
                    )
                )
            elif surface != "other":
                findings.append(
                    finding(
                        rules,
                        "required_manifest_key_removed",
                        surface,
                        rel,
                        "contract file deleted",
                    )
                )
            else:
                findings.append(
                    finding(
                        rules,
                        "documentation_or_noncontract_edit",
                        "other",
                        rel,
                        "non-contract file deleted",
                    )
                )
            continue
        if old_raw is None and new_raw is not None:
            if surface == "other" or new_obj is None:
                findings.append(
                    finding(
                        rules,
                        "documentation_or_noncontract_edit",
                        surface,
                        rel,
                        "file added",
                    )
                )
            else:
                findings.extend(classify_json(rules, surface, rel, {}, new_obj))
            continue
        # modified
        assert old_raw is not None and new_raw is not None
        if old_obj is None and new_obj is None:
            findings.append(
                finding(
                    rules,
                    "documentation_or_noncontract_edit",
                    surface,
                    rel,
                    "non-JSON bytes changed",
                )
            )
            continue
        if old_obj is not None and new_obj is None:
            findings.append(
                finding(
                    rules,
                    "contract_artifact_unparseable",
                    surface if surface != "other" else "plugin_package",
                    rel,
                    "JSON became unparseable",
                )
            )
            continue
        before_n = len(findings)
        findings.extend(classify_json(rules, surface, rel, old_obj, new_obj))
        version_fields = set(rules.get("version_fields") or ["version"])
        if (
            len(findings) == before_n
            and digest_bytes(old_raw) != digest_bytes(new_raw)
            and strip_version_fields(old_obj, version_fields)
            != strip_version_fields(new_obj, version_fields)
        ):
            findings.append(
                finding(
                    rules,
                    "documentation_or_noncontract_edit",
                    surface,
                    rel,
                    "bytes changed without a higher-class detector",
                )
            )
    return findings, rename_rows


def lint_files(
    old_files: dict[str, bytes],
    new_files: dict[str, bytes],
    rules: dict,
    declared_override: str | None = None,
) -> dict:
    findings, rename_rows = classify_trees(old_files, new_files, rules)
    derived = max_bump(findings)
    prev = read_version(old_files) or "0.0.0"
    declared = declared_override or read_version(new_files) or prev
    declared_bump = bump_between(prev, declared)
    if declared_bump == "DOWNGRADE":
        ok = False
        exit_code = 1
    else:
        ok = RANK[declared_bump] >= RANK[derived]
        exit_code = 0 if ok else 1
    return {
        "ok": ok,
        "exit_code": exit_code,
        "derived_bump": derived,
        "declared_bump": declared_bump,
        "previous_version": prev,
        "declared_version": declared,
        "findings": findings,
        "renames": rename_rows,
        "files_old": len(old_files),
        "files_new": len(new_files),
    }


def lint_dirs(
    old_dir: Path,
    new_dir: Path,
    rules: dict | None = None,
    declared_override: str | None = None,
) -> dict:
    return lint_files(
        iter_files(old_dir),
        iter_files(new_dir),
        rules or load_rules(),
        declared_override=declared_override,
    )


def git_inside(cwd: Path) -> bool:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0 and p.stdout.strip() == "true"


def git_previous_tag(cwd: Path) -> str:
    p = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "git describe failed").strip())
    return p.stdout.strip()


def extract_git_ref(cwd: Path, ref: str, dest: Path) -> None:
    p = subprocess.run(
        ["git", "archive", ref],
        cwd=str(cwd),
        capture_output=True,
        timeout=60,
    )
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(err or f"git archive {ref} failed")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(p.stdout), mode="r:") as tf:
        tf.extractall(dest)


def invoke_cli(old: Path, new: Path, extra: list[str] | None = None) -> tuple[int, dict]:
    """Run this file as a fresh process so the exit code is the linter's."""
    cmd = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--old",
        str(old),
        "--new",
        str(new),
    ]
    if extra:
        cmd.extend(extra)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    try:
        doc = json.loads(p.stdout)
    except json.JSONDecodeError:
        doc = {
            "ok": False,
            "exit_code": p.returncode,
            "stdout": (p.stdout or "")[-2000:],
            "stderr": (p.stderr or "")[-2000:],
        }
    return p.returncode, doc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="REL-0001 semver bump linter")
    p.add_argument("--old", type=Path, help="previous tree (tag materialization)")
    p.add_argument("--new", type=Path, help="new tree (HEAD materialization)")
    p.add_argument("--from-ref", help="git ref for the previous tree")
    p.add_argument("--to-ref", default="HEAD", help="git ref for the new tree")
    p.add_argument(
        "--previous-tag",
        action="store_true",
        help="use git describe --tags --abbrev=0 as --from-ref",
    )
    p.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    p.add_argument("--declared-version", help="override declared version")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rules = load_rules(args.rules)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": f"rules:{exc}"}, sort_keys=True))
        return 2

    old_dir = args.old
    new_dir = args.new
    tmp_hold: list[Path] = []
    if args.previous_tag or args.from_ref:
        if not git_inside(REPO):
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "not-a-git-repository",
                        "derived_bump": None,
                        "exit_code": 2,
                    },
                    sort_keys=True,
                )
            )
            print("FAILED:REL-0001-linter not a git repository", file=sys.stderr)
            return 2
        from_ref = args.from_ref
        if args.previous_tag:
            try:
                from_ref = git_previous_tag(REPO)
            except RuntimeError as exc:
                print(
                    json.dumps(
                        {"ok": False, "error": f"previous-tag:{exc}", "exit_code": 2},
                        sort_keys=True,
                    )
                )
                return 2
        import tempfile

        old_tmp = Path(tempfile.mkdtemp(prefix="rel0001-old-"))
        new_tmp = Path(tempfile.mkdtemp(prefix="rel0001-new-"))
        tmp_hold.extend([old_tmp, new_tmp])
        try:
            extract_git_ref(REPO, from_ref, old_tmp)
            extract_git_ref(REPO, args.to_ref, new_tmp)
        except RuntimeError as exc:
            print(
                json.dumps(
                    {"ok": False, "error": f"git-archive:{exc}", "exit_code": 2},
                    sort_keys=True,
                )
            )
            return 2
        old_dir, new_dir = old_tmp, new_tmp

    if old_dir is None or new_dir is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "usage: --old/--new or --from-ref/--previous-tag",
                    "exit_code": 2,
                },
                sort_keys=True,
            )
        )
        return 2
    if not Path(old_dir).is_dir() or not Path(new_dir).is_dir():
        print(
            json.dumps(
                {"ok": False, "error": "old-or-new-missing", "exit_code": 2},
                sort_keys=True,
            )
        )
        return 2

    report = lint_dirs(
        Path(old_dir),
        Path(new_dir),
        rules=rules,
        declared_override=args.declared_version,
    )
    report["rules_path"] = (
        args.rules.relative_to(REPO).as_posix()
        if args.rules.is_absolute() and REPO in args.rules.parents
        else str(args.rules)
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"derived={report['derived_bump']} declared={report['declared_bump']} "
        f"rc={report['exit_code']}",
        file=sys.stderr,
    )
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
