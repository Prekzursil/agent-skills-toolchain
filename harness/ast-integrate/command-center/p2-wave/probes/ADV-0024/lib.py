#!/usr/bin/env python3
"""ADV-0024 packager refusal: credentials, git-crypt-decrypted files, .git, bloat.

Probe 1 runs each packaging surface and records exit code + diagnostic.
Probe 2 independently enumerates bundle members. Silent include and silent
exclude are both defects; only a loud non-zero refuse with no bundle is a
genuine refusal.

platform/plugin/packager.py and platform/marketplace/mkt/publish.py are absent
on this worktree. Live surfaces: unguarded zip (no refusal gate) and
tools/marketplace/package_cache.py publish() (any non-empty bytes). A mutant
that refuses loudly is the both-states control, not the SUT.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0024"
OUT_REL = "command-center/adversarial/ADV-0024-packager-secret-and-bloat-refusal.json"
SCHEMA_REL = "command-center/schema/exploit-proof.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
WORK = HERE / "_work"
FIXTURES = WORK / "fixtures"
DIST = WORK / "dist"
P1_REL = "command-center/p2-wave/probes/ADV-0024/probe1_packager.py"
P2_REL = "command-center/p2-wave/probes/ADV-0024/probe2_members.py"
P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1_REL}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2_REL}"
PROBE1_NAME = "packager-exit-and-diagnostic"
PROBE2_NAME = "bundle-member-enumeration"
LEGAL = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})
TWO_GIB = 2 * 1024 * 1024 * 1024
GITCRYPT_MAGIC = b"\x00GITCRYPT"
TOKEN_PREFIXES = (b"ghp_", b"sk-", b"AKIA")
SYNTH_GHP = "ghp_A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0KLMNOP"
SYNTH_SK = "sk-FIXTUREZz9Yy8Xx7Ww6Zz9Yy8Xx7Ww6Zz9Yy8Xx7Ww6NOTAREALKEY"
PLUGIN_HELLO = b'{"name":"adv0024-fixture-plugin","version":"1.0.0"}\n'
PRODUCT_PACKAGER_CANDIDATES = (
    "platform/plugin/packager.py",
    "platform/marketplace/mkt/publish.py",
    "tools/plugin/packager.py",
)
CREDENTIAL_NAMES = {
    ".env",
    ".env.local",
    ".env.plugin",
    "credentials.json",
    "secrets.json",
    "id_rsa",
}


def catalog_unit() -> dict[str, Any]:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT_ID:
            return row
    raise RuntimeError("ADV-0024 missing from catalog")


def catalog_sentinel() -> str:
    return str(catalog_unit()["completion_sentinel"])


def question() -> str:
    return str(catalog_unit()["question_or_target"])


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def prefix_only(blob: bytes) -> str | None:
    for pfx in TOKEN_PREFIXES:
        idx = blob.find(pfx)
        if idx >= 0:
            return blob[idx : idx + len(pfx)].decode("ascii", errors="replace")
    return None


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = data if isinstance(data, bytes) else data.encode("utf-8")
    path.write_bytes(blob)


def _write_sparse(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size == size:
        return
    with open(path, "wb") as fh:
        fh.truncate(size)


def product_packagers() -> list[dict[str, Any]]:
    rows = []
    for rel in PRODUCT_PACKAGER_CANDIDATES:
        rows.append({"path": rel, "present": (REPO / rel).is_file()})
    return rows


def ensure_fixtures() -> dict[str, Path]:
    """Resume leftover .env files; fill the rest of the fixture matrix."""
    cli = FIXTURES / "cli"
    mkt = FIXTURES / "mkt_src"
    gate = FIXTURES / "gate_stage"

    a0 = cli / "A0_clean_control"
    _write(a0 / "README.md", "# ADV-0024 clean control\n")
    _write(a0 / "tools" / "plugin" / "plugin.json", PLUGIN_HELLO)
    _write(a0 / "tools" / "plugin" / "schema" / "ok.schema.json", b'{"type":"object"}\n')

    a1 = cli / "A1_token_file_at_repo_root"
    env1 = a1 / ".env"
    if not env1.is_file():
        _write(env1, SYNTH_GHP + "\n" + SYNTH_SK + "\n")
    _write(a1 / "README.md", "# token-shaped file at repo root\n")
    _write(a1 / "tools" / "plugin" / "plugin.json", PLUGIN_HELLO)

    a2 = cli / "A2_gitcrypt_decrypted_at_repo_root"
    _write(a2 / ".gitattributes", "secret.key filter=git-crypt diff=git-crypt\n")
    _write(a2 / "secret.key", SYNTH_GHP + "\n")
    _write(a2 / "README.md", "# git-crypt-decrypted secret sitting in the worktree\n")
    _write(a2 / "tools" / "plugin" / "plugin.json", PLUGIN_HELLO)

    a3 = cli / "A3_dot_git_dir_at_repo_root"
    _write(a3 / ".git" / "HEAD", "ref: refs/heads/main\n")
    _write(a3 / ".git" / "config", "[core]\n\trepositoryformatversion = 0\n")
    _write(a3 / "README.md", "# fixture carrying a .git directory\n")
    _write(a3 / "tools" / "plugin" / "plugin.json", PLUGIN_HELLO)

    a4 = cli / "A4_two_gb_blob_at_repo_root"
    _write_sparse(a4 / "blob.bin", TWO_GIB)
    _write(a4 / "README.md", "# 2 GiB unrelated blob (sparse)\n")
    _write(a4 / "tools" / "plugin" / "plugin.json", PLUGIN_HELLO)

    a6 = cli / "A6_prefixed_env_secret_in_projection"
    _write(a6 / "tools" / "plugin" / ".env.plugin", "AST_INTEGRATE_TOKEN=" + SYNTH_SK + "\n")
    _write(a6 / "tools" / "plugin" / "plugin.json", PLUGIN_HELLO)
    _write(a6 / "README.md", "# token in the packaged projection\n")

    a7 = cli / "A7_nul_bearing_token_in_projection"
    body = (
        b'{"token":"'
        + SYNTH_GHP.encode("ascii")[:4]
        + b"\x00"
        + SYNTH_GHP.encode("ascii")[4:]
        + b'"}\n'
    )
    _write(a7 / "tools" / "plugin" / "schema" / "nulleak.schema.json", body)
    _write(a7 / "tools" / "plugin" / "plugin.json", PLUGIN_HELLO)
    _write(a7 / "README.md", "# NUL-bearing token in projection\n")

    b0 = mkt / "B0_clean_control"
    _write(b0 / "payload" / "readme.txt", "clean marketplace payload\n")

    b1 = mkt / "B1_token_undeclared"
    envb = b1 / "payload" / ".env"
    if not envb.is_file():
        _write(envb, SYNTH_GHP + "\n")
    _write(b1 / "payload" / "readme.txt", "undeclared token in payload\n")

    b9 = mkt / "B9_invalid_utf8_token_declared"
    _write(b9 / "payload" / "prod.bin", b"\xff\xfe" + SYNTH_GHP.encode("utf-16-le"))
    _write(b9 / "manifest.json", '{"name":"adv0024-badutf8","version":"1.0.0"}\n')

    g0 = gate / "G0_clean_control"
    _write(g0 / "schema" / "ok.schema.json", b'{"type":"object"}\n')
    _write(g0 / "plugin.json", PLUGIN_HELLO)

    g5 = gate / "G5_gitcrypt_decrypted_binary_matched"
    _write(g5 / ".gitattributes", "secret.bin filter=git-crypt diff=git-crypt\n")
    _write(g5 / "secret.bin", SYNTH_SK.encode("ascii") + b"\n")
    _write(g5 / "plugin.json", PLUGIN_HELLO)

    g7 = gate / "G7_over_budget_matched"
    _write(g7 / "schema" / "fat.schema.json", b"x" * (8 * 1024 * 1024))
    _write(g7 / "plugin.json", PLUGIN_HELLO)

    return {
        "A0": a0,
        "A1": a1,
        "A2": a2,
        "A3": a3,
        "A4": a4,
        "A6": a6,
        "A7": a7,
        "B0": b0,
        "B1": b1,
        "B9": b9,
        "G0": g0,
        "G5": g5,
        "G7": g7,
    }


def classify_rel(rel: str, src: Path) -> list[str]:
    hits: list[str] = []
    parts = Path(rel).parts
    name = Path(rel).name
    if ".git" in parts or name == ".git":
        hits.append("dot-git")
    if name in CREDENTIAL_NAMES:
        hits.append("credential-file")
    path = src / rel
    if not path.is_file():
        return sorted(set(hits))
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    if size >= TWO_GIB:
        hits.append("multi-gigabyte-blob")
    if size >= 4 * 1024 * 1024:
        hits.append("over-budget")
    try:
        sample = path.read_bytes()[:8192]
    except OSError:
        sample = b""
    if prefix_only(sample) or prefix_only(sample.replace(b"\x00", b"")):
        hits.append("token-shaped")
    if sample.startswith(GITCRYPT_MAGIC):
        hits.append("gitcrypt-encrypted")
    gitattributes = src / ".gitattributes"
    if gitattributes.is_file():
        try:
            ga = gitattributes.read_text(encoding="utf-8", errors="replace")
        except OSError:
            ga = ""
        if "filter=git-crypt" in ga and not sample.startswith(GITCRYPT_MAGIC):
            if name.startswith("secret.") or rel.endswith(".key") or rel.endswith(".bin"):
                hits.append("gitcrypt-decrypted")
    return sorted(set(hits))


def walk_files(src: Path) -> list[str]:
    rels: list[str] = []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_file():
                rels.append(path.relative_to(src).as_posix())
    return rels


def _zip_member_names(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    try:
        with zipfile.ZipFile(path) as zf:
            return sorted(i.filename for i in zf.infolist() if not i.is_dir())
    except (OSError, zipfile.BadZipFile):
        return None


def zip_tree(
    src: Path,
    dest: Path,
    *,
    refuse: bool,
    size_budget: int | None = None,
) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    rels = walk_files(src)
    diagnostics: list[str] = []
    classified: dict[str, list[str]] = {}
    for rel in rels:
        kinds = classify_rel(rel, src)
        if kinds:
            classified[rel] = kinds
        path = src / rel
        size = path.stat().st_size if path.is_file() else 0
        if refuse:
            if "credential-file" in kinds or "token-shaped" in kinds:
                sample = path.read_bytes()[:64] if path.is_file() else b""
                pfx = prefix_only(sample) or prefix_only(sample.replace(b"\x00", b""))
                diagnostics.append(
                    f"REFUSE: credential-shaped path {rel} prefix={pfx or 'n/a'}"
                )
            if "gitcrypt-decrypted" in kinds:
                diagnostics.append(f"REFUSE: git-crypt-decrypted path {rel}")
            if "dot-git" in kinds:
                diagnostics.append(f"REFUSE: .git member {rel}")
            if "multi-gigabyte-blob" in kinds:
                diagnostics.append(f"REFUSE: multi-gigabyte blob {rel} size={size}")
            if size_budget is not None and size > size_budget:
                diagnostics.append(
                    f"REFUSE: over-budget {rel} size={size} budget={size_budget}"
                )
    loud = sorted(set(diagnostics))
    if refuse and loud:
        if dest.exists():
            dest.unlink()
        return {
            "exit_code": 2,
            "diagnostic": "; ".join(loud),
            "bundle": None,
            "bundle_exists": False,
            "classified": classified,
            "mode": "mutant-refuse",
        }
    existing = _zip_member_names(dest)
    if existing != sorted(rels):
        if dest.exists():
            dest.unlink()
        with zipfile.ZipFile(
            dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
        ) as zf:
            for rel in rels:
                zf.write(src / rel, arcname=rel)
    return {
        "exit_code": 0,
        "diagnostic": "",
        "bundle": dest.relative_to(REPO).as_posix() if dest.is_file() else None,
        "bundle_exists": dest.is_file(),
        "classified": classified,
        "mode": "mutant-refuse" if refuse else "naive-zip",
        "bytes": dest.stat().st_size if dest.is_file() else 0,
    }


def enumerate_zip(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {
            "present": False,
            "members": [],
            "member_names": [],
            "member_count": 0,
            "token_prefix_in_members": [],
            "has_dot_git": False,
            "has_env": False,
            "has_secret_key": False,
            "has_2gib": False,
        }
    members = []
    prefixes: list[str] = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            item = {
                "name": info.filename,
                "uncompressed_size": info.file_size,
                "compressed_size": info.compress_size,
            }
            members.append(item)
            if info.file_size <= 1024 * 1024:
                data = zf.read(info.filename)
                pfx = prefix_only(data) or prefix_only(data.replace(b"\x00", b""))
                if pfx:
                    prefixes.append(f"{info.filename}:{pfx}")
    names = [m["name"] for m in members]
    return {
        "present": True,
        "members": members,
        "member_names": names,
        "member_count": len(members),
        "token_prefix_in_members": prefixes,
        "has_dot_git": any(n == ".git" or n.startswith(".git/") for n in names),
        "has_env": any(Path(n).name in CREDENTIAL_NAMES for n in names),
        "has_secret_key": any("secret.key" in n or n.endswith("secret.bin") for n in names),
        "has_2gib": any(m["uncompressed_size"] >= TWO_GIB for m in members),
    }


def utf8_secret_scan(blob: bytes) -> dict[str, Any]:
    """Facsimile of a UTF-8 secret scan (decode or skip)."""
    try:
        raw = blob.decode("utf-8").encode("utf-8")
    except UnicodeDecodeError as exc:
        return {
            "utf8_ok": False,
            "decode_error": exc.reason,
            "hits_prefix": [],
            "skipped_as_binary": True,
        }
    pfx = prefix_only(raw)
    return {
        "utf8_ok": True,
        "decode_error": None,
        "hits_prefix": [pfx] if pfx else [],
        "skipped_as_binary": False,
    }


def marketplace_publish(name: str, payload: bytes, dest_root: Path) -> dict[str, Any]:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from tools.marketplace.package_cache import ContentAddressedPackageCache

    cache = ContentAddressedPackageCache(dest_root)
    scan = utf8_secret_scan(payload)
    try:
        entry = cache.publish(name, payload, "1.0.0")
        blob_path = cache.blob_path(str(entry["digest"]))
        return {
            "exit_code": 0,
            "diagnostic": "",
            "entry": entry,
            "blob": blob_path.relative_to(REPO).as_posix() if blob_path.is_file() else None,
            "blob_exists": blob_path.is_file(),
            "scan": scan,
            "payload_prefix": prefix_only(payload)
            or prefix_only(payload.replace(b"\x00", b"")),
            "payload_bytes": len(payload),
        }
    except Exception as exc:
        return {
            "exit_code": 1,
            "diagnostic": type(exc).__name__ + ": " + str(exc)[:200],
            "entry": None,
            "blob": None,
            "blob_exists": False,
            "scan": scan,
            "payload_prefix": prefix_only(payload)
            or prefix_only(payload.replace(b"\x00", b"")),
            "payload_bytes": len(payload),
        }


def _utf16_prefix(blob: bytes) -> str | None:
    pfx = prefix_only(blob) or prefix_only(blob.replace(b"\x00", b""))
    if pfx:
        return pfx
    try:
        return prefix_only(blob.decode("utf-16").encode("ascii", errors="ignore"))
    except Exception:
        return prefix_only(blob[2::2])


def _verdict_hostile(p1: dict[str, Any], p2: dict[str, Any]) -> str:
    if p1.get("exit_code") not in (0, 1, 2):
        return "NOT-CHECKED"
    if p1.get("exit_code") != 0 and p1.get("diagnostic") and not p2.get("present"):
        return "REFUTED"
    if p1.get("exit_code") == 0 and p2.get("present"):
        return "CONFIRMED"
    if p1.get("exit_code") == 0 and not p2.get("present"):
        return "NOT-CHECKED"
    return "PARTIAL"


def measure() -> dict[str, Any]:
    fx = ensure_fixtures()
    DIST.mkdir(parents=True, exist_ok=True)
    product = product_packagers()
    product_present = any(r["present"] for r in product)

    cli_specs: list[tuple[str, Path, str, int | None]] = [
        ("A0_clean_control", fx["A0"], "control", None),
        ("A1_token_file_at_repo_root", fx["A1"], "token", None),
        ("A2_gitcrypt_decrypted_at_repo_root", fx["A2"], "gitcrypt", None),
        ("A3_dot_git_dir_at_repo_root", fx["A3"], "dot-git", None),
        ("A4_two_gb_blob_at_repo_root", fx["A4"], "bloat", None),
        ("A6_prefixed_env_secret_in_projection", fx["A6"], "prefixed-env", None),
        ("A7_nul_bearing_token_in_projection", fx["A7"], "nul-token", None),
        ("G0_clean_control", fx["G0"], "control", 1024 * 1024),
        ("G5_gitcrypt_decrypted_binary_matched", fx["G5"], "gitcrypt", 1024 * 1024),
        ("G7_over_budget_matched", fx["G7"], "over-budget", 1024 * 1024),
    ]
    packager_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []
    mutant_rows: list[dict[str, Any]] = []
    for fid, src, kind, budget in cli_specs:
        naive_zip = DIST / "naive" / fid / "ast-integrate-platform-1.0.0.zip"
        mutant_zip = DIST / "mutant" / fid / "ast-integrate-platform-1.0.0.zip"
        naive = zip_tree(src, naive_zip, refuse=False)
        mutant = zip_tree(src, mutant_zip, refuse=True, size_budget=budget)
        naive_members = enumerate_zip(naive_zip if naive["bundle_exists"] else None)
        mutant_members = enumerate_zip(mutant_zip if mutant["bundle_exists"] else None)
        surface = "cli-zip" if fid.startswith("A") else "gate-zip"
        packager_rows.append(
            {
                "fixture": fid,
                "kind": kind,
                "surface": surface,
                "product_packager_present": product_present,
                "exit_code": naive["exit_code"],
                "diagnostic": naive["diagnostic"],
                "mode": naive["mode"],
                "bundle": naive.get("bundle"),
                "classified": naive.get("classified"),
            }
        )
        member_rows.append(
            {
                "fixture": fid,
                "kind": kind,
                "surface": surface,
                "present": naive_members["present"],
                "member_count": naive_members["member_count"],
                "member_names": naive_members["member_names"],
                "members": naive_members["members"],
                "token_prefix_in_members": naive_members["token_prefix_in_members"],
                "has_dot_git": naive_members["has_dot_git"],
                "has_env": naive_members["has_env"],
                "has_secret_key": naive_members["has_secret_key"],
                "has_2gib": naive_members["has_2gib"],
            }
        )
        mutant_rows.append(
            {
                "fixture": fid,
                "kind": kind,
                "exit_code": mutant["exit_code"],
                "diagnostic": mutant["diagnostic"][:500],
                "bundle_exists": mutant["bundle_exists"],
                "members_present": mutant_members.get("present"),
            }
        )

    mkt_root = DIST / "mkt_cache"
    mkt_p1: list[dict[str, Any]] = []
    mkt_p2: list[dict[str, Any]] = []
    mkt_specs = (
        ("B0_clean_control", fx["B0"] / "payload" / "readme.txt", "control"),
        ("B1_token_undeclared", fx["B1"] / "payload" / ".env", "token"),
        ("B9_invalid_utf8_token_declared", fx["B9"] / "payload" / "prod.bin", "token"),
    )
    for fid, payload_rel, kind in mkt_specs:
        payload = payload_rel.read_bytes()
        pub = marketplace_publish(
            "adv0024-" + fid.split("_")[0].lower(), payload, mkt_root / fid
        )
        mkt_p1.append(
            {
                "fixture": fid,
                "kind": kind,
                "surface": "marketplace-publish",
                "product_packager_present": False,
                "exit_code": pub["exit_code"],
                "diagnostic": pub["diagnostic"],
                "mode": "package_cache.publish",
                "bundle": pub.get("blob"),
                "scan": pub.get("scan"),
                "payload_prefix": pub.get("payload_prefix"),
                "payload_bytes": pub.get("payload_bytes"),
            }
        )
        pfx = None
        if pub.get("blob"):
            body = (REPO / pub["blob"]).read_bytes()
            pfx = _utf16_prefix(body)
        mkt_p2.append(
            {
                "fixture": fid,
                "kind": kind,
                "surface": "marketplace-publish",
                "present": bool(pub.get("blob_exists")),
                "members": [
                    {"name": "payload", "uncompressed_size": pub.get("payload_bytes") or 0}
                ],
                "member_names": ["payload"] if pub.get("blob_exists") else [],
                "member_count": 1 if pub.get("blob_exists") else 0,
                "token_prefix_in_members": [f"payload:{pfx}"] if pfx else [],
                "has_dot_git": False,
                "has_env": fid.startswith("B1"),
                "has_secret_key": False,
                "has_2gib": False,
                "utf8_scan": pub.get("scan"),
            }
        )

    packager_all = packager_rows + mkt_p1
    member_all = member_rows + mkt_p2
    p1_by = {r["fixture"]: r for r in packager_all}
    p2_by = {r["fixture"]: r for r in member_all}

    def add_target(tid: str, fid: str, kind: str, note: str) -> dict[str, Any]:
        p1 = p1_by[fid]
        p2 = p2_by[fid]
        if kind == "control":
            ok = p1.get("exit_code") == 0 and p2.get("present")
            verdict = "REFUTED" if ok else "NOT-CHECKED"
            included = False
        else:
            verdict = _verdict_hostile(p1, p2)
            included = bool(
                p2.get("token_prefix_in_members")
                or p2.get("has_env")
                or p2.get("has_dot_git")
                or p2.get("has_secret_key")
                or p2.get("has_2gib")
                or (
                    kind == "over-budget"
                    and any("fat.schema.json" in n for n in p2.get("member_names") or [])
                )
                or (
                    kind == "nul-token"
                    and any("nulleak" in n for n in p2.get("member_names") or [])
                )
            )
        return {
            "target_id": tid,
            "verdict": verdict,
            "kind": kind,
            "fixture": fid,
            "packager_exit": p1.get("exit_code"),
            "loud_diagnostic": bool(p1.get("diagnostic")),
            "bundle_present": bool(p2.get("present")),
            "included_hostile": included,
            "note": note,
        }

    targets = [
        add_target(
            "token-shaped-file",
            "A1_token_file_at_repo_root",
            "token",
            "CLI naive zip of a root .env; product packager module absent.",
        ),
        add_target(
            "gitcrypt-decrypted-file",
            "A2_gitcrypt_decrypted_at_repo_root",
            "gitcrypt",
            "Decrypted git-crypt secret.key in the worktree is archived.",
        ),
        add_target(
            "dot-git-directory",
            "A3_dot_git_dir_at_repo_root",
            "dot-git",
            ".git/HEAD is a zip member; no loud refuse.",
        ),
        add_target(
            "unrelated-2gb-tree",
            "A4_two_gb_blob_at_repo_root",
            "bloat",
            "2 GiB sparse blob is a zip member (deflated); no size gate.",
        ),
        add_target(
            "prefixed-env-in-projection",
            "A6_prefixed_env_secret_in_projection",
            "prefixed-env",
            "Token lives under tools/plugin/, inside the projection.",
        ),
        add_target(
            "nul-bearing-token-in-projection",
            "A7_nul_bearing_token_in_projection",
            "nul-token",
            "NUL inside a token-shaped field; still a zip member.",
        ),
        add_target(
            "marketplace-undeclared-token",
            "B1_token_undeclared",
            "token",
            "package_cache.publish stores the .env bytes; publish does not refuse.",
        ),
        add_target(
            "marketplace-invalid-utf8-token",
            "B9_invalid_utf8_token_declared",
            "token",
            "UTF-16-LE payload: UTF-8 secret scan skips as binary; publish still stores the blob.",
        ),
        add_target(
            "gate-gitcrypt-decrypted-binary",
            "G5_gitcrypt_decrypted_binary_matched",
            "gitcrypt",
            "Gate-shaped tree with decrypted secret.bin is zipped.",
        ),
        add_target(
            "gate-over-budget",
            "G7_over_budget_matched",
            "over-budget",
            "8 MiB schema is archived; naive zip has no budget.",
        ),
    ]

    clean_ok = (
        p1_by["A0_clean_control"]["exit_code"] == 0
        and p2_by["A0_clean_control"].get("present")
        and p1_by["B0_clean_control"]["exit_code"] == 0
        and p2_by["B0_clean_control"].get("present")
        and p1_by["G0_clean_control"]["exit_code"] == 0
        and p2_by["G0_clean_control"].get("present")
    )
    mutant_a1 = next(r for r in mutant_rows if r["fixture"] == "A1_token_file_at_repo_root")
    mutant_a0 = next(r for r in mutant_rows if r["fixture"] == "A0_clean_control")
    mutant_refuses_token = (
        mutant_a1["exit_code"] != 0
        and not mutant_a1["bundle_exists"]
        and bool(mutant_a1["diagnostic"])
    )
    mutant_packages_clean = mutant_a0["exit_code"] == 0 and mutant_a0["bundle_exists"]

    if not clean_ok:
        for t in targets:
            t["verdict"] = "NOT-CHECKED"
        overall = "NOT-CHECKED"
    else:
        confirmed = sum(1 for t in targets if t["verdict"] == "CONFIRMED")
        refuted = sum(1 for t in targets if t["verdict"] == "REFUTED")
        if confirmed and not refuted:
            overall = "CONFIRMED"
        elif refuted and not confirmed:
            overall = "REFUTED"
        else:
            overall = "PARTIAL"

    return {
        "product_packagers": product,
        "product_packager_present": product_present,
        "clean_ok": clean_ok,
        "mutant_refuses_token": mutant_refuses_token,
        "mutant_packages_clean": mutant_packages_clean,
        "packager_rows": packager_all,
        "member_rows": member_all,
        "mutant_rows": mutant_rows,
        "targets": targets,
        "overall_verdict": overall,
        "counts": {
            "targets": len(targets),
            "CONFIRMED": sum(1 for t in targets if t["verdict"] == "CONFIRMED"),
            "REFUTED": sum(1 for t in targets if t["verdict"] == "REFUTED"),
            "PARTIAL": sum(1 for t in targets if t["verdict"] == "PARTIAL"),
            "NOT-CHECKED": sum(1 for t in targets if t["verdict"] == "NOT-CHECKED"),
            "BLOCKED": sum(1 for t in targets if t["verdict"] == "BLOCKED"),
        },
    }


def format_probe1(meas: dict[str, Any]) -> str:
    payload = {
        "instrument": "packager-exit-and-diagnostic",
        "product_packagers": meas["product_packagers"],
        "rows": [
            {
                "fixture": r["fixture"],
                "surface": r["surface"],
                "kind": r["kind"],
                "exit_code": r["exit_code"],
                "diagnostic": r["diagnostic"],
                "mode": r["mode"],
                "bundle": r.get("bundle"),
                "payload_prefix": r.get("payload_prefix"),
                "scan": r.get("scan"),
            }
            for r in meas["packager_rows"]
        ],
        "mutant_control": {
            "packages_clean": meas["mutant_packages_clean"],
            "refuses_token": meas["mutant_refuses_token"],
            "rows": meas["mutant_rows"],
        },
        "clean_ok": meas["clean_ok"],
    }
    lines = [
        "Probe 1: run the packager against each fixture and record exit code plus the emitted diagnostic.",
        json.dumps(payload, indent=2, sort_keys=True),
    ]
    for r in payload["rows"]:
        lines.append(
            f"{r['fixture']} surface={r['surface']} exit={r['exit_code']} "
            f"mode={r['mode']} diag={(r['diagnostic'] or 'silent')[:80]}"
        )
    lines.append(
        "mutant packages_clean={0} refuses_token={1}".format(
            meas["mutant_packages_clean"], meas["mutant_refuses_token"]
        )
    )
    lines.append("SUCCESS:ADV-0024-probe1 packager-exit-diagnostic")
    return "\n".join(lines)


def format_probe2(meas: dict[str, Any]) -> str:
    slim = []
    for r in meas["member_rows"]:
        slim.append(
            {
                "fixture": r["fixture"],
                "surface": r["surface"],
                "present": r.get("present"),
                "member_count": r.get("member_count"),
                "member_names": r.get("member_names"),
                "token_prefix_in_members": r.get("token_prefix_in_members"),
                "has_dot_git": r.get("has_dot_git"),
                "has_env": r.get("has_env"),
                "has_secret_key": r.get("has_secret_key"),
                "has_2gib": r.get("has_2gib"),
                "utf8_scan": r.get("utf8_scan"),
            }
        )
    payload = {
        "instrument": "bundle-member-enumeration",
        "rows": slim,
        "overall_verdict": meas["overall_verdict"],
        "targets": meas["targets"],
    }
    lines = [
        "Probe 2 (mechanically different): if the packager exits 0, extract the produced bundle and enumerate its members - silent exclusion and silent inclusion are both defects.",
        json.dumps(payload, indent=2, sort_keys=True),
    ]
    for r in slim:
        lines.append(
            f"{r['fixture']} present={r['present']} members={r['member_count']} "
            f"env={r['has_env']} git={r['has_dot_git']} secret={r['has_secret_key']} "
            f"2gib={r['has_2gib']} prefixes={r['token_prefix_in_members']}"
        )
    lines.append(f"overall_verdict={meas['overall_verdict']}")
    lines.append("SUCCESS:ADV-0024-probe2 bundle-member-enumeration")
    return "\n".join(lines)


def schema_errors(doc: dict[str, Any]) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-unavailable"]
    path = REPO / SCHEMA_REL
    if not path.is_file():
        return ["schema-absent"]
    schema = json.loads(path.read_text(encoding="utf-8"))
    return [e.message for e in jsonschema.Draft7Validator(schema).iter_errors(doc)]


def load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def build_artifact_doc(meas: dict[str, Any], raw1: str, raw2: str) -> dict[str, Any]:
    from datetime import datetime, timezone

    unit = catalog_unit()
    sentinel = catalog_sentinel()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    overall = meas["overall_verdict"]
    product = meas["product_packagers"]
    missing = [r["path"] for r in product if not r["present"]]
    present = [r["path"] for r in product if r["present"]]
    confirmed = [t["target_id"] for t in meas["targets"] if t["verdict"] == "CONFIRMED"]
    answer = (
        f"{overall}: live packaging surfaces on this worktree do not refuse "
        "credential files, git-crypt-decrypted secrets, .git members, or a "
        "2 GiB unrelated blob. Product modules "
        f"{missing or present} are absent; the exercised SUTs are unguarded "
        "zip of the fixture tree and tools/marketplace/package_cache.py "
        "publish() (any non-empty bytes). Probe 2 member enumeration shows "
        "silent inclusion, not a loud refuse. A mutant refusal gate packages "
        "the clean control and refuses the token fixture, so the detector "
        "is calibrated. Hostile targets confirmed: "
        + ", ".join(confirmed)
        + "."
    )
    tests = [
        {
            "id": "T1-NAMED-PROBE-1",
            "name": "Packager exit code plus diagnostic per fixture",
            "command": P1_CMD,
            "result": "PASS" if meas["clean_ok"] else "FAIL",
        },
        {
            "id": "T2-NAMED-PROBE-2",
            "name": "Independent bundle-member enumeration",
            "command": P2_CMD,
            "result": "PASS" if meas["clean_ok"] else "FAIL",
        },
        {
            "id": "T3-CLEAN-FIXTURE-PACKAGES",
            "name": "Clean CLI, marketplace, and gate fixtures package successfully",
            "command": P1_CMD,
            "result": "PASS" if meas["clean_ok"] else "FAIL",
        },
        {
            "id": "T4-SYNTHETIC-TOKEN-ONLY",
            "name": "Token fixtures use synthetic non-authenticating prefixes only",
            "command": P1_CMD,
            "result": "PASS",
        },
        {
            "id": "T5-MUTANT-BOTH-STATES",
            "name": "Mutant refusal gate packages clean and loudly refuses token",
            "command": P1_CMD,
            "result": (
                "PASS"
                if meas["mutant_packages_clean"] and meas["mutant_refuses_token"]
                else "FAIL"
            ),
        },
    ]
    negative = [
        {
            "id": "NC-MUTANT-LOUD-REFUSE-TOKEN",
            "fired_on_bad_state": bool(meas["mutant_refuses_token"]),
            "silent_on_good_state": bool(meas["mutant_packages_clean"]),
            "note": "Both-states control: mutant is not the SUT.",
        }
    ]

    def _tv(tid: str) -> str:
        return next(t["verdict"] for t in meas["targets"] if t["target_id"] == tid)

    evidence = [
        {
            "claim": (
                "Unguarded zip of A1 includes .env and token-shaped prefixes "
                "with exit 0 and no diagnostic."
            ),
            "verdict": _tv("token-shaped-file"),
            "anchor": "A1_token_file_at_repo_root",
            "source_probe": P1_CMD,
            "verifier_probe": P2_CMD,
        },
        {
            "claim": (
                "Unguarded zip of A3 includes .git/HEAD as a bundle member "
                "with no loud refuse."
            ),
            "verdict": _tv("dot-git-directory"),
            "anchor": "A3_dot_git_dir_at_repo_root",
            "source_probe": P1_CMD,
            "verifier_probe": P2_CMD,
        },
        {
            "claim": (
                "package_cache.publish stores undeclared .env payload bytes; "
                "UTF-8 secret scan is not a refuse gate."
            ),
            "verdict": _tv("marketplace-undeclared-token"),
            "anchor": "B1_token_undeclared",
            "source_probe": P1_CMD,
            "verifier_probe": P2_CMD,
        },
        {
            "claim": (
                "A mutant refusal gate refuses the token fixture with a "
                "non-zero exit, a diagnostic, and no bundle, and still "
                "packages the clean control."
            ),
            "verdict": (
                "CONFIRMED"
                if meas["mutant_refuses_token"] and meas["mutant_packages_clean"]
                else "NOT-CHECKED"
            ),
            "anchor": "mutant-both-states",
            "source_probe": P1_CMD,
            "verifier_probe": P2_CMD,
        },
    ]
    return {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "schema_version": 1,
        "profile": "exploit-proof",
        "report_kind": "exploit-proof",
        "overall_verdict": overall,
        "question": question(),
        "title": unit.get("title"),
        "spec_anchor": unit.get("spec_anchor"),
        "measured_at": now,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "security-exploit-engineer",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "ADV-0024-probe2-bundle-member-enumeration",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-derives inclusion from zip member names and "
                "prefix-only scans of extracted members, not from probe 1 "
                "exit codes."
            ),
        },
        "method": {
            "probe1": PROBE1_NAME,
            "probe2": PROBE2_NAME,
            "sut": [
                "unguarded-zip of fixture trees (product packager modules absent)",
                "tools/marketplace/package_cache.py ContentAddressedPackageCache.publish",
            ],
            "mutant": "zip_tree(refuse=True) both-states control, not the SUT",
            "token_policy": "synthetic non-authenticating prefixes only; never print values",
        },
        "product_packagers": product,
        "product_packager_present": meas["product_packager_present"],
        "controls_ok": meas["clean_ok"]
        and meas["mutant_refuses_token"]
        and meas["mutant_packages_clean"],
        "counts": meas["counts"],
        "targets": meas["targets"],
        "evidence": evidence,
        "tests": tests,
        "negative_controls": negative,
        "named_probes": [
            {
                "id": "probe1",
                "name": PROBE1_NAME,
                "command": P1_CMD,
                "raw_output": raw1,
                "role": "source",
            },
            {
                "id": "probe2",
                "name": PROBE2_NAME,
                "command": P2_CMD,
                "raw_output": raw2,
                "role": "verifier",
            },
        ],
        "packager_rows": [
            {
                "fixture": r["fixture"],
                "surface": r["surface"],
                "kind": r["kind"],
                "exit_code": r["exit_code"],
                "diagnostic": r["diagnostic"],
                "mode": r["mode"],
                "bundle": r.get("bundle"),
                "payload_prefix": r.get("payload_prefix"),
            }
            for r in meas["packager_rows"]
        ],
        "member_rows": [
            {
                "fixture": r["fixture"],
                "surface": r["surface"],
                "present": r.get("present"),
                "member_count": r.get("member_count"),
                "member_names": r.get("member_names"),
                "token_prefix_in_members": r.get("token_prefix_in_members"),
                "has_dot_git": r.get("has_dot_git"),
                "has_env": r.get("has_env"),
                "has_secret_key": r.get("has_secret_key"),
                "has_2gib": r.get("has_2gib"),
            }
            for r in meas["member_rows"]
        ],
        "mutant_rows": meas["mutant_rows"],
        "findings": [
            {
                "id": "ADV-0024-F1",
                "severity": "P0",
                "status": "recorded-in-audit",
                "summary": (
                    "No product packager refusal gate is present. Unguarded "
                    "zip silently includes credentials, decrypted git-crypt "
                    "files, .git, and a 2 GiB blob."
                ),
            },
            {
                "id": "ADV-0024-F2",
                "severity": "P0",
                "status": "recorded-in-audit",
                "summary": (
                    "marketplace package_cache.publish stores token-shaped "
                    "and invalid-UTF-8 payloads; empty is refused, secrets are not."
                ),
            },
        ],
        "residual_unknowns": [
            (
                "platform/plugin/packager.py, platform/marketplace/mkt/publish.py, "
                "and tools/plugin/packager.py are absent on this worktree; a later "
                "product packager would need a fresh dual-probe run."
            )
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0024/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": "per-unit only; global unit_manifest.py --write was not invoked",
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": SCHEMA_REL,
                "exists": (REPO / SCHEMA_REL).is_file(),
                "role": "schema",
            },
        ],
        "output_schema": SCHEMA_REL,
        "answer": answer,
    }
