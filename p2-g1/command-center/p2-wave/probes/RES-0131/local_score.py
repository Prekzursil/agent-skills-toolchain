"""Offline quality components computable from published package bytes."""
from __future__ import annotations

import io
import json
import tarfile

COMPONENT_KEYS = (
    "has_license",
    "readme_norm",
    "has_changelog",
    "has_linter",
    "has_ignore_or_files",
    "has_test_script",
    "has_test_files",
    "not_deprecated",
    "has_security_md",
    "no_binary_artifacts",
    "has_lockfile",
    "no_unlocked_deps",
)


def extract_features(tar_bytes: bytes) -> dict:
    names: list[str] = []
    pkg: dict = {}
    readme_bytes = 0
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            rel = member.name.split("/", 1)[-1]
            names.append(rel)
            low = rel.lower()
            base = low.split("/")[-1]
            if rel == "package.json":
                fh = tf.extractfile(member)
                if fh is not None:
                    pkg = json.loads(fh.read().decode("utf-8", errors="replace"))
            if base.startswith("readme"):
                readme_bytes += int(member.size or 0)
    low_names = [n.lower() for n in names]
    bases = [n.split("/")[-1] for n in low_names]
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    deps = pkg.get("dependencies") if isinstance(pkg.get("dependencies"), dict) else {}
    unlocked = 0
    for ver in deps.values():
        s = str(ver).strip()
        if s in {"*", "latest", ">=0.0.0", ">0.0.0"}:
            unlocked += 1
    license_field = pkg.get("license")
    has_license_field = bool(license_field) and str(license_field).strip() not in {
        "",
        "UNLICENSED",
        "UNLICENCED",
    }
    has_license_file = any(
        b.startswith("license") or b.startswith("licence") or b == "copying"
        for b in bases
    )
    has_changelog = any(
        b.startswith("changelog") or b.startswith("changes") or b.startswith("history")
        for b in bases
    )
    linter_needles = (
        "eslint",
        "prettier",
        "jshint",
        "jscs",
        "standard",
        "biome",
        "xo.config",
    )
    has_linter = any(any(x in n for x in linter_needles) for n in low_names)
    if isinstance(pkg.get("eslintConfig"), dict) or pkg.get("prettier"):
        has_linter = True
    if any(k in scripts for k in ("lint", "eslint", "prettier")):
        has_linter = True
    test_cmd = str(scripts.get("test") or "").strip()
    has_test_script = bool(test_cmd) and "no test specified" not in test_cmd.lower()
    has_test_files = any(
        part in {"test", "tests", "__tests__", "spec"}
        for n in low_names
        for part in n.split("/")[:-1]
    ) or any(".test." in b or ".spec." in b for b in bases)
    has_npmignore = any(b == ".npmignore" for b in bases)
    has_files_field = isinstance(pkg.get("files"), list) and bool(pkg.get("files"))
    has_security = any(b.startswith("security") for b in bases)
    has_lock = any(
        b
        in {
            "package-lock.json",
            "npm-shrinkwrap.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        }
        for b in bases
    )
    binary_hits = [
        n
        for n in names
        if n.lower().endswith((".exe", ".dll", ".so", ".dylib", ".a"))
    ]
    return {
        "file_count": len(names),
        "readme_bytes": readme_bytes,
        "has_license_field": has_license_field,
        "has_license_file": has_license_file,
        "has_changelog": has_changelog,
        "has_linter": has_linter,
        "has_npmignore": has_npmignore,
        "has_files_field": has_files_field,
        "has_test_script": has_test_script,
        "has_test_files": has_test_files,
        "has_security_md": has_security,
        "has_lockfile": has_lock,
        "binary_artifact_count": len(binary_hits),
        "unlocked_dep_count": unlocked,
        "deprecated_in_manifest": bool(pkg.get("deprecated")),
        "license": license_field
        if isinstance(license_field, str)
        else json.dumps(license_field)
        if license_field
        else None,
        "scripts_keys": sorted(scripts),
        "repository": pkg.get("repository"),
        "sample_files": sorted(names)[:80],
    }


def offline_components(feat: dict) -> dict[str, float]:
    return {
        "has_license": 1.0
        if feat["has_license_field"] or feat["has_license_file"]
        else 0.0,
        "readme_norm": min(float(feat["readme_bytes"]) / 400.0, 1.0),
        "has_changelog": 1.0 if feat["has_changelog"] else 0.0,
        "has_linter": 1.0 if feat["has_linter"] else 0.0,
        "has_ignore_or_files": 1.0
        if feat["has_npmignore"] or feat["has_files_field"]
        else 0.0,
        "has_test_script": 1.0 if feat["has_test_script"] else 0.0,
        "has_test_files": 1.0 if feat["has_test_files"] else 0.0,
        "not_deprecated": 0.0 if feat["deprecated_in_manifest"] else 1.0,
        "has_security_md": 1.0 if feat["has_security_md"] else 0.0,
        "no_binary_artifacts": 1.0 if feat["binary_artifact_count"] == 0 else 0.0,
        "has_lockfile": 1.0 if feat["has_lockfile"] else 0.0,
        "no_unlocked_deps": 1.0 if feat["unlocked_dep_count"] == 0 else 0.0,
    }


def offline_score(feat: dict) -> float:
    parts = offline_components(feat)
    return sum(parts[k] for k in COMPONENT_KEYS) / float(len(COMPONENT_KEYS))


def recompute_from_file_list(feat: dict) -> dict[str, float]:
    """Independent rail: re-derive file-based bits from sample_files + sizes."""
    names = [str(n) for n in (feat.get("sample_files") or [])]
    bases = [n.lower().split("/")[-1] for n in names]
    low_names = [n.lower() for n in names]
    has_license_file = any(
        b.startswith("license") or b.startswith("licence") or b == "copying"
        for b in bases
    )
    has_changelog = any(
        b.startswith("changelog") or b.startswith("changes") or b.startswith("history")
        for b in bases
    )
    has_security = any(b.startswith("security") for b in bases)
    has_lock = any(
        b
        in {
            "package-lock.json",
            "npm-shrinkwrap.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        }
        for b in bases
    )
    has_test_files = any(
        part in {"test", "tests", "__tests__", "spec"}
        for n in low_names
        for part in n.split("/")[:-1]
    ) or any(".test." in b or ".spec." in b for b in bases)
    binary_hits = [
        n
        for n in names
        if n.lower().endswith((".exe", ".dll", ".so", ".dylib", ".a"))
    ]
    return {
        "has_license_file": has_license_file,
        "has_changelog": has_changelog,
        "has_security_md": has_security,
        "has_lockfile": has_lock,
        "has_test_files": has_test_files,
        "no_binary_artifacts": len(binary_hits) == 0,
    }
