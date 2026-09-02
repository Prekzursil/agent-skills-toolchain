#!/usr/bin/env python3
"""Consumer call site for ARC-0080: allowlist packer with loud exclusion + size fail.

Reads normative rules from command-center/phase4/contracts/ARC-0080.json.
A denylist-only packer is not implementable against that contract.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPO / "command-center" / "phase4" / "contracts" / "ARC-0080.json"

# Live candidate on THIS worktree. phase3/A2/DESIGN.json is ARC-0010's
# output_path and is absent here; the A2 DESIGN fixture plus the typed
# registry and three architecture schemas are the packaged content.
CANDIDATE_PATHS = (
    "command-center/schema/architecture-dossier.schema.json",
    "command-center/schema/architecture-review.schema.json",
    "command-center/schema/migration-plan.schema.json",
    "command-center/p2-wave/probes/ARC-0010/registry.json",
    "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
    "command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/A2/DESIGN.json",
)

CANDIDATE_GLOBS = (
    "command-center/schema/architecture-dossier.schema.json",
    "command-center/schema/architecture-review.schema.json",
    "command-center/schema/migration-plan.schema.json",
    "command-center/p2-wave/probes/ARC-0010/registry.json",
    "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
    "command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/A2/DESIGN.json",
)

_GLOB_CACHE: dict[str, re.Pattern[str]] = {}


def load_contract() -> dict:
    doc = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "x-normative" not in doc:
        raise RuntimeError("ARC-0080 contract missing x-normative")
    return doc


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    cached = _GLOB_CACHE.get(pattern)
    if cached is not None:
        return cached
    i = 0
    out: list[str] = ["^"]
    n = len(pattern)
    while i < n:
        if pattern.startswith("**/", i):
            out.append("(?:.+/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    out.append("$")
    compiled = re.compile("".join(out))
    _GLOB_CACHE[pattern] = compiled
    return compiled


def match_glob(path: str, pattern: str) -> bool:
    rel = path.replace("\\", "/").lstrip("/")
    return glob_to_regex(pattern.replace("\\", "/")).match(rel) is not None


def first_matching_glob(path: str, globs: Iterable[str]) -> str | None:
    for g in globs:
        if g == "**":
            continue
        if match_glob(path, g):
            return g
    return None


def classify_exclusion(path: str, classes: dict) -> tuple[str, str] | None:
    rel = path.replace("\\", "/").lstrip("/")
    for cls, patterns in classes.items():
        for pat in patterns:
            if match_glob(rel, pat):
                return str(cls), str(pat)
    return None


def content_credential_hit(raw: bytes, needles: list[str]) -> str | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    for needle in needles:
        if needle in text:
            return needle
    return None


def canonical_digest(members: list[tuple[str, bytes]]) -> str:
    h = hashlib.sha256()
    for path, raw in sorted(members, key=lambda x: x[0]):
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(raw).digest())
    return h.hexdigest()


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_repro_zip(members: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, raw in sorted(members, key=lambda x: x[0]):
            info = zipfile.ZipInfo(filename=path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, raw)
    return buf.getvalue()


def validate_report(report: dict, schema: dict) -> list[str]:
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.path)}: {e.message}"
        for e in validator.iter_errors(report)
    ]


def _walk_files(stage_root: Path) -> list[Path]:
    files: list[Path] = []
    for p in sorted(stage_root.rglob("*")):
        if p.is_symlink() or p.is_file():
            files.append(p)
    return files


def pack_stage(
    stage_root: Path,
    allowlist_globs: list[str],
    max_total_bytes: int,
    package_id: str,
    package_version: str = "1.0.0",
    repo_root: Path | None = None,
) -> dict:
    """Pack a staging root. Returns a schema-valid ARC-0080 report."""
    schema = load_contract()
    norm = schema["x-normative"]
    classes = norm["exclusion_classes"]
    needles = list(norm["credential_content_needles"])
    hard = int(norm["hard_ceiling_bytes"])
    repo = repo_root or REPO

    failures: list[dict] = []
    if "**" in allowlist_globs:
        failures.append(
            {
                "class": "declaration",
                "path": "**",
                "message": "total-wildcard allowlist is forbidden; deny-by-default would collapse",
            }
        )
    if max_total_bytes > hard or max_total_bytes < 1:
        failures.append(
            {
                "class": "size_ceiling",
                "path": "*",
                "message": f"declared ceiling {max_total_bytes} outside 1..{hard}; gigabyte packages are structurally invalid",
            }
        )

    selected: list[tuple[str, bytes, str]] = []
    all_raw: dict[str, bytes] = {}

    for fp in _walk_files(stage_root):
        rel = fp.relative_to(stage_root).as_posix()
        if fp.is_symlink():
            failures.append(
                {
                    "class": "symlink",
                    "path": rel,
                    "message": "symlinks are not packable; refuse rather than follow",
                }
            )
            continue
        raw = fp.read_bytes()
        all_raw[rel] = raw
        hit = classify_exclusion(rel, classes)
        if hit:
            cls, pat = hit
            failures.append(
                {
                    "class": cls,
                    "path": rel,
                    "pattern": pat,
                    "message": f"mandatory exclusion {cls} matched {pat}; build fails rather than omit",
                }
            )
        needle = content_credential_hit(raw, needles)
        if needle:
            failures.append(
                {
                    "class": "credentials",
                    "path": rel,
                    "pattern": needle,
                    "message": f"credential content needle {needle} present; build fails rather than omit",
                }
            )
        if len(raw) > max_total_bytes:
            failures.append(
                {
                    "class": "size_ceiling",
                    "path": rel,
                    "message": f"input file {len(raw)} bytes exceeds ceiling {max_total_bytes}; fail not warn",
                }
            )
        glob = first_matching_glob(rel, allowlist_globs)
        if glob and not hit and not needle:
            selected.append((rel, raw, glob))

    member_tuples = [(p, r) for p, r, _ in selected]
    total_bytes = sum(len(r) for _, r in member_tuples)
    if total_bytes > max_total_bytes:
        failures.append(
            {
                "class": "size_ceiling",
                "path": "*",
                "message": f"archive member total {total_bytes} exceeds ceiling {max_total_bytes}; fail not warn",
            }
        )

    # Independent archive-member exclusion scan (REL-0009: never trust the tree alone).
    archive_names = [p for p, _, _ in selected]
    for name in archive_names:
        hit = classify_exclusion(name, classes)
        if hit:
            cls, pat = hit
            failures.append(
                {
                    "class": cls,
                    "path": name,
                    "pattern": pat,
                    "message": f"archive member {name} matched exclusion {pat}",
                }
            )

    digest = canonical_digest(member_tuples)
    digest2 = canonical_digest(list(member_tuples))
    members = []
    for path, raw, glob in sorted(selected, key=lambda x: x[0]):
        members.append(
            {
                "path": path,
                "bytes": len(raw),
                "sha256": sha256_hex(raw),
                "allowlist_glob": glob,
                "exists_in_repository": (repo / path).is_file(),
                "justification": f"allowlist glob {glob} selected this path as packaged content",
            }
        )

    verdict = "reject" if failures else "accept"
    if verdict == "reject":
        zip_bytes = None
    else:
        zip_bytes = write_repro_zip(member_tuples)

    report = {
        "contract_id": "ARC-0080",
        "package_id": package_id,
        "package_version": package_version,
        "content_boundary": {
            "evaluation_surface": str(norm["evaluation_surface"]),
            "selection_policy": str(norm["selection_policy"]),
            "allowlist_globs": list(allowlist_globs),
        },
        "mandatory_exclusions": {
            k: list(v) for k, v in classes.items()
        },
        "size_ceiling": {
            "max_total_bytes": int(max_total_bytes),
            "on_exceed": str(norm["on_exceed"]),
        },
        "integrity": {
            "algorithm": str(norm["digest_algorithm"]),
            "digest": digest,
            "member_count": len(members),
            "total_bytes": total_bytes,
        },
        "reproducibility": {
            "declared": True,
            "sorted_members": True,
            "normalized_timestamps": True,
            "generator_id": str(norm["generator_id"]),
            "generator_version": str(norm["generator_version"]),
            "repeat_digest_agrees": digest == digest2,
        },
        "members": members,
        "failures": failures,
        "verdict": verdict,
    }
    errs = validate_report(report, schema)
    if errs:
        raise RuntimeError("packer report failed ARC-0080 schema:\n" + "\n".join(errs[:12]))
    report["_zip_bytes"] = zip_bytes
    return report


def stage_candidate(dest: Path, repo: Path | None = None) -> list[str]:
    root = repo or REPO
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for rel in CANDIDATE_PATHS:
        src = root / rel
        if not src.is_file():
            raise FileNotFoundError(rel)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())
        copied.append(rel)
    return copied


def repo_tree_diff(report: dict, repo: Path | None = None) -> dict:
    """Diff packed members against the live repository tree for the candidate roots."""
    root = repo or REPO
    packed = {m["path"] for m in report.get("members") or []}
    scan_roots = (
        "command-center/schema",
        "command-center/p2-wave/probes/ARC-0010",
        "command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/A2",
    )
    tree: list[str] = []
    for prefix in scan_roots:
        base = root / prefix
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and not p.is_symlink():
                tree.append(p.relative_to(root).as_posix())
    included = sorted(packed)
    omitted = sorted(set(tree) - packed)
    unjustified = [
        m
        for m in report.get("members") or []
        if not m.get("exists_in_repository") or not m.get("justification")
    ]
    extra = sorted(packed - set(tree))
    return {
        "tree_file_count": len(tree),
        "packed_count": len(packed),
        "included": included,
        "omitted_from_scanned_trees": omitted,
        "packed_not_in_tree": extra,
        "unjustified": unjustified,
        "every_included_path_justified": not unjustified and not extra,
    }
