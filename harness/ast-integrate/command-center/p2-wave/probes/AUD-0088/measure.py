"""Live AUD-0088 measurements: declared include list vs unpacked archive."""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from plugin.payload_paths import expand_payload_paths, load_allowlist  # noqa: E402

import hygiene as H  # noqa: E402
import scratch_pack as P  # noqa: E402

ALLOWLIST_REL = "tools/plugin/payload-allowlist.json"
PLUGIN_MANIFEST = ".claude-plugin/plugin.json"
PACK_PY = "tools/plugin/pack.py"
DECLARED_MUST_FIND = "tools/plugin/payload-allowlist.json"
STRAY_NAME = "STRAY-AUD-0088.bin"
GIT_PLANT = "staged/.git/config"
CRED_PLANT = "credentials.json"
PLANT_BODY = b"AUD-0088-PLANT-NOT-A-SECRET\n"


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def independent_include_expand(repo: Path, allowlist: dict) -> list[str]:
    """Directory listing of include globs via matcher B. Does not call expand_payload_paths."""
    sys.path.insert(0, str(repo / "tools" / "plugin"))
    from payload_allowlist import expand, listed_paths  # noqa: WPS433

    _src, census = listed_paths(repo)
    return list(expand(census, allowlist, matcher="b"))


def _included(rel: str, patterns: list[str]) -> bool:
    from fnmatch import fnmatch

    for pat in patterns:
        if fnmatch(rel, pat):
            return True
        if pat.endswith("/**") and (rel == pat[:-3] or rel.startswith(pat[:-3] + "/")):
            return True
    return False


def _excluded(rel: str, patterns: list[str]) -> bool:
    return _included(rel, patterns) if patterns else False


def file_rows(repo: Path, paths: list[str]) -> list[dict]:
    rows = []
    for rel in paths:
        p = repo / rel
        size = p.stat().st_size if p.is_file() else 0
        rows.append({"path": rel, "source_bytes": size, "present": p.is_file()})
    return rows


def probe1_packager_file_list(repo: Path | None = None) -> dict:
    repo = repo or REPO
    allow = load_allowlist(repo)
    declared = expand_payload_paths(repo)
    independent = independent_include_expand(repo, allow)
    rows = file_rows(repo, declared)
    missing = [r["path"] for r in rows if not r["present"]]
    agree = declared == independent
    listing = "\n".join(declared)
    return {
        "probe": "probe1-packager-file-list",
        "unit_id": "AUD-0088",
        "allowlist_path": ALLOWLIST_REL,
        "deny_by_default": allow.get("deny_by_default") is True,
        "include": list(allow.get("include") or []),
        "exclude": list(allow.get("exclude") or []),
        "declared_count": len(declared),
        "declared_source_bytes": sum(r["source_bytes"] for r in rows),
        "declared_paths": declared,
        "declared_rows": rows,
        "independent_count": len(independent),
        "independent_paths": independent,
        "lists_agree": agree,
        "missing_on_disk": missing,
        "listing_sha256": sha256_text(listing),
        "plugin_manifest_in_allowlist": PLUGIN_MANIFEST in declared,
        "plugin_manifest_present": (repo / PLUGIN_MANIFEST).is_file(),
        "pack_py_present": (repo / PACK_PY).is_file(),
        "pack_py_path": PACK_PY,
    }


def _diff(declared: list[str], archive_paths: list[str]) -> dict:
    d, a = set(declared), set(archive_paths)
    return {
        "only_in_declared": sorted(d - a),
        "only_in_archive": sorted(a - d),
        "agree": d == a,
    }


def probe2_unpack_archive(repo: Path | None = None) -> dict:
    repo = repo or REPO
    p1 = probe1_packager_file_list(repo)
    declared = list(p1["declared_paths"])
    with tempfile.TemporaryDirectory(prefix="aud0088-") as td:
        root = Path(td)
        clean_zip = root / "clean" / "plugin.zip"
        dirty_zip = root / "dirty" / "plugin.zip"
        extract_clean = root / "extract-clean"
        extract_dirty = root / "extract-dirty"
        P.write_archive(repo, declared, clean_zip)
        extra = {
            GIT_PLANT: b"[core]\n\trepositoryformatversion = 0\n",
            CRED_PLANT: PLANT_BODY,
            STRAY_NAME: b"stray-not-in-allowlist\n",
        }
        P.write_archive(repo, declared, dirty_zip, extra=extra)
        clean_entries = P.list_archive(clean_zip)
        dirty_entries = P.list_archive(dirty_zip)
        unpack_clean = P.extract_file_names(clean_zip, extract_clean)
        unpack_dirty = P.extract_file_names(dirty_zip, extract_dirty)
        zip_names = [e["path"] for e in clean_entries]
        dirty_names = [e["path"] for e in dirty_entries]
        # Second enumerator: walk the extracted tree (not ZipInfo).
        walked = sorted(
            p.relative_to(extract_clean).as_posix()
            for p in extract_clean.rglob("*")
            if p.is_file()
        )
        zip_vs_walk = zip_names == walked == unpack_clean
        diff = _diff(declared, zip_names)
        clean_flags = H.prohibited_rows(zip_names)
        dirty_flags = H.prohibited_rows(dirty_names)
        dirty_flag_set = {r["path"]: r["flags"] for r in dirty_flags}
        declared_found = DECLARED_MUST_FIND in unpack_clean
        git_flagged = "repo-metadata" in dirty_flag_set.get(GIT_PLANT, [])
        cred_flagged = "credential-shaped" in dirty_flag_set.get(CRED_PLANT, [])
        stray_detected = STRAY_NAME in dirty_names and STRAY_NAME not in declared
        clean_silent = len(clean_flags) == 0
        control_ok = (
            declared_found
            and git_flagged
            and cred_flagged
            and stray_detected
            and clean_silent
            and zip_vs_walk
        )
        top = sorted(clean_entries, key=lambda r: (-r["uncompressed_bytes"], r["path"]))[:10]
        return {
            "probe": "probe2-unpack-archive",
            "unit_id": "AUD-0088",
            "scratch_build": True,
            "production_pack_py_used": False,
            "archive_entry_count": len(clean_entries),
            "archive_uncompressed_bytes": sum(e["uncompressed_bytes"] for e in clean_entries),
            "archive_file_bytes": clean_zip.stat().st_size,
            "archive_entries": clean_entries,
            "unpack_names": unpack_clean,
            "zip_vs_extract_agree": zip_vs_walk,
            "declared_vs_archive": diff,
            "declared_vs_archive_agree": diff["agree"],
            "prohibited_in_clean": clean_flags,
            "declared_file_found_in_unpack": declared_found,
            "declared_must_find": DECLARED_MUST_FIND,
            "top_entries_by_size": top,
            "control": {
                "declared_file_found": declared_found,
                "dot_git_flagged": git_flagged,
                "credential_flagged": cred_flagged,
                "stray_detected": stray_detected,
                "clean_silent": clean_silent,
                "zip_vs_extract_agree": zip_vs_walk,
                "ok": control_ok,
                "dirty_flagged_paths": sorted(dirty_flag_set),
                "dirty_only_in_archive": sorted(set(dirty_names) - set(declared)),
            },
        }


def both(repo: Path | None = None) -> tuple[dict, dict]:
    repo = repo or REPO
    p1 = probe1_packager_file_list(repo)
    p2 = probe2_unpack_archive(repo)
    return p1, p2
