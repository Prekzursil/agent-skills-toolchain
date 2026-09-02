"""Platform-hostility measurements for ARC-0106.

Live command-center validators are exercised on this Linux box against UTF-8
BOM, CRLF vs LF (blob via git cat-file -p, never git archive), reserved device
names, long paths, and case-insensitive collisions. Phase-4 contract files are
recorded present-or-absent; they are not invented.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC = REPO / "tools" / "command-center"
if str(CC) not in sys.path:
    sys.path.insert(0, str(CC))

import catalog as cat  # noqa: E402
import register_parse as rp  # noqa: E402
import render  # noqa: E402
import seed  # noqa: E402
import unit_manifest as um  # noqa: E402
import validate as val  # noqa: E402

BOM = b"\xef\xbb\xbf"
CRLF = b"\r\n"
WIN_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
TARGET = "notes/sample.md"
REGISTER_FIXTURE = """# REGISTER fixture for ARC-0106

## 1. OUTSTANDING

### 1A. Program A - toolchain / Prompt Two (32)

| ID | Title | Notes | Effort |
| --- | --- | --- | --- |
| R-A99 | Platform hostility fixture row | encoding and path controls | S |
"""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def describe(raw: bytes) -> dict[str, Any]:
    lf = raw.replace(CRLF, b"\n")
    return {
        "bytes": len(raw),
        "crlf": raw.count(CRLF),
        "sha256": sha256_bytes(raw),
        "sha256_lf_norm": sha256_bytes(lf),
        "lf_bytes": len(lf),
    }


def git(args: list[str], cwd: Path, binary: bool = True) -> tuple[int, bytes, bytes]:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True)
    return r.returncode, r.stdout, r.stderr


def worktree_git_attempt() -> dict[str, Any]:
    """Honest: this delivery worktree is not a git repo. Still invoke both tools."""
    readings = {}
    for args, label in (
        (["rev-parse", "--is-inside-work-tree"], "rev-parse"),
        (["cat-file", "-p", "HEAD:command-center/WORK-UNIT-CATALOG.json"], "git cat-file -p"),
        (["archive", "HEAD", "--", "command-center/WORK-UNIT-CATALOG.json"], "git archive"),
    ):
        rc, out, err = git(args, REPO)
        readings[label] = {
            "rc": rc,
            "stdout_bytes": len(out),
            "stderr_head": err.decode("utf-8", "replace")[:240],
        }
    return {
        "is_git_repo": (REPO / ".git").exists(),
        "readings": readings,
        "note": "Worktree has no .git; blob method is proved on a throwaway lab repo.",
    }


def lab_blob_method(tmp: Path) -> dict[str, Any]:
    """Prove cat-file vs archive vs working-tree on a scratch repo (not this worktree)."""
    repo = tmp / "blob-lab"
    repo.mkdir()
    (repo / "notes").mkdir()
    lf = b"alpha\nbeta\nomega\n"
    (repo / TARGET).write_bytes(lf)
    env_cmds = [
        ["git", "init", "-b", "main"],
        ["git", "config", "user.email", "arc0106@local"],
        ["git", "config", "user.name", "ARC-0106"],
        ["git", "config", "core.autocrlf", "false"],
        ["git", "add", TARGET],
        ["git", "commit", "-m", "lf-blob"],
    ]
    for args in env_cmds:
        r = subprocess.run(args, cwd=str(repo), capture_output=True)
        if r.returncode != 0:
            return {
                "ok": False,
                "failed_cmd": args,
                "stderr": (r.stderr or b"").decode("utf-8", "replace")[:400],
            }
    rc_cat, cat, err_cat = git(["cat-file", "-p", f"HEAD:{TARGET}"], repo)
    tarp = repo / "a.tar"
    rc_arch, _, err_arch = git(["archive", "-o", str(tarp), "HEAD", "--", TARGET], repo)
    arch = b""
    if rc_arch == 0 and tarp.is_file():
        with tarfile.open(tarp) as tf:
            member = tf.getmember(TARGET)
            fh = tf.extractfile(member)
            arch = fh.read() if fh else b""
    (repo / TARGET).write_bytes(lf.replace(b"\n", CRLF))
    working_crlf = (repo / TARGET).read_bytes()
    rc_cat2, cat_after, _ = git(["cat-file", "-p", f"HEAD:{TARGET}"], repo)
    return {
        "ok": True,
        "target": TARGET,
        "method": "git cat-file -p on a throwaway lab repo; git archive recorded only as the contrast reading",
        "never_git_archive_for_blob": True,
        "worktree_is_git_repo": False,
        "readings": {
            "git cat-file -p": {**describe(cat), "rc": rc_cat, "stderr_head": err_cat.decode("utf-8", "replace")[:160]},
            "git archive": {**describe(arch), "rc": rc_arch, "stderr_head": err_arch.decode("utf-8", "replace")[:160]},
            "working-tree after CRLF rewrite": describe(working_crlf),
            "git cat-file -p after working-tree CRLF rewrite": {**describe(cat_after), "rc": rc_cat2},
        },
        "archive_equals_blob": arch == cat and bool(cat),
        "cat_file_is_lf": cat.count(CRLF) == 0 and cat == lf,
        "working_tree_crlf_shown": working_crlf.count(CRLF) > 0,
        "working_tree_differs_from_blob": working_crlf != cat,
        "blob_unchanged_after_crlf_rewrite": cat_after == cat,
    }


def _reach6(violations: list) -> list[dict[str, str]]:
    return [
        {"check": v.get("check", ""), "detail": v.get("detail", "")}
        for v in violations
        if v.get("check") == "REACH-6"
    ]


def crlf_both_states(tmp: Path) -> dict[str, Any]:
    """One validator on CRLF working-tree bytes and on the LF blob bytes."""
    lab = tmp / "crlf-lab"
    lab.mkdir()
    lf = REGISTER_FIXTURE.replace("\r\n", "\n").encode("utf-8")
    if not lf.endswith(b"\n"):
        lf += b"\n"
    crlf = lf.replace(b"\n", CRLF)
    lf_path = lab / "REGISTER.lf.md"
    crlf_path = lab / "REGISTER.crlf.md"
    lf_path.write_bytes(lf)
    crlf_path.write_bytes(crlf)
    overlay = lab / "overlay.json"
    overlay.write_text(json.dumps({"items": {}}, indent=2) + "\n", encoding="utf-8")

    built_lf = seed.build_catalog(lf_path, overlay)
    built_crlf = seed.build_catalog(crlf_path, overlay)
    v_lf, _ = val.validate(built_lf, register_path=lf_path)
    v_crlf, _ = val.validate(built_crlf, register_path=crlf_path)
    raw_crlf_digest = sha256_bytes(crlf)
    norm_digest = sha256_bytes(lf)
    seed_digest = str(built_crlf.get("provenance", {}).get("register_sha256", ""))

    um_root = lab / "um"
    (um_root / "command-center" / "receipts").mkdir(parents=True)
    artifact = um_root / "out.txt"
    artifact.write_bytes(b"known-good\r\n")
    receipt = {"unit_id": "ARC-0106", "artifacts": [{"path": "out.txt"}]}
    (um_root / "command-center" / "receipts" / "ARC-0106.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    derived = um.derive(um_root)
    um_sha = derived["artifacts"][0]["sha256"]
    naive = sha256_bytes(b"known-good\r\n")
    normalised = sha256_bytes(b"known-good\n")

    parsed_crlf = rp.parse_file(crlf_path)
    parsed_lf = rp.parse_file(lf_path)

    render_root = lab / "cc-render"
    render_root.mkdir()
    (render_root / "STATUS.md").write_bytes(b"# status\r\nline-two\r\n")
    (render_root / "OWNER-DECISIONS.md").write_bytes(b"# od\n")
    manifest = render.render_manifest(render_root)
    status_row = next(r for r in manifest["artifacts"] if r["path"].endswith("STATUS.md"))
    status_raw = (render_root / "STATUS.md").read_bytes()
    status_norm = sha256_bytes(status_raw.replace(CRLF, b"\n"))

    return {
        "register_lf": describe(lf),
        "register_crlf": describe(crlf),
        "seed_sha256_from_crlf_tree": seed_digest,
        "seed_matches_lf_blob_digest": seed_digest == norm_digest,
        "naive_raw_crlf_digest": raw_crlf_digest,
        "naive_raw_would_mismatch_blob": raw_crlf_digest != norm_digest,
        "validate_lf_blob": {
            "reach6": _reach6(v_lf),
            "violation_count": len(v_lf),
            "clean_reach6": _reach6(v_lf) == [],
        },
        "validate_crlf_working_tree": {
            "reach6": _reach6(v_crlf),
            "violation_count": len(v_crlf),
            "clean_reach6": _reach6(v_crlf) == [],
        },
        "both_verdicts_recorded": True,
        "verdicts_agree": _reach6(v_lf) == _reach6(v_crlf),
        "register_parse_row_counts": {
            "lf": len(parsed_lf.rows),
            "crlf": len(parsed_crlf.rows),
        },
        "unit_manifest": {
            "sha256": um_sha,
            "normalised_sha256": normalised,
            "naive_raw_sha256": naive,
            "survives_crlf": um_sha == normalised,
            "naive_would_break": naive != normalised,
        },
        "render_manifest": {
            "status_sha256": status_row.get("sha256"),
            "status_norm_sha256": status_norm,
            "survives_crlf": status_row.get("sha256") == status_norm,
        },
    }


def bom_both_states(tmp: Path) -> dict[str, Any]:
    lab = tmp / "bom-lab"
    lab.mkdir()
    payload = {"items": [], "schema_version": 1, "defaults": {}}
    body = json.dumps(payload).encode("utf-8")
    clean = lab / "clean.json"
    bombed = lab / "bombed.json"
    overlay_bom = lab / "overlay.bom.json"
    clean.write_bytes(body)
    bombed.write_bytes(BOM + body)
    overlay_bom.write_bytes(BOM + json.dumps({"items": {}}).encode("utf-8"))

    def load_case(path: Path) -> dict[str, Any]:
        try:
            cat.load(path)
            return {"ok": True, "error": None}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def json_text_case(path: Path) -> dict[str, Any]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            return {"ok": True, "error": None}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def json_sig_case(path: Path) -> dict[str, Any]:
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
            return {"ok": True, "error": None}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    um_root = lab / "um-bom"
    (um_root / "command-center" / "receipts").mkdir(parents=True)
    (um_root / "out.txt").write_bytes(b"x\n")
    (um_root / "command-center" / "receipts" / "BOM.json").write_bytes(
        BOM + json.dumps({"unit_id": "BOM-1", "artifacts": [{"path": "out.txt"}]}).encode("utf-8")
    )
    try:
        um.derive(um_root)
        um_bom = {"ok": True, "error": None}
    except Exception as exc:
        um_bom = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    seed_overlay = {"ok": None, "error": None}
    lf_reg = lab / "REGISTER.md"
    lf_reg.write_bytes(REGISTER_FIXTURE.replace("\r\n", "\n").encode("utf-8"))
    try:
        seed.build_catalog(lf_reg, overlay_bom)
        seed_overlay = {"ok": True, "error": None}
    except Exception as exc:
        seed_overlay = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return {
        "without_bom": load_case(clean),
        "with_bom": load_case(bombed),
        "json_loads_utf8_with_bom": json_text_case(bombed),
        "json_loads_utf8_sig_with_bom": json_sig_case(bombed),
        "unit_manifest_receipt_with_bom": um_bom,
        "seed_overlay_with_bom": seed_overlay,
        "catalog_load_breaks_on_bom": load_case(bombed)["ok"] is False
        and load_case(clean)["ok"] is True,
    }


def _relative(root: Path, target: Path) -> dict[str, Any]:
    try:
        rel = target.resolve().relative_to(root.resolve())
        return {"ok": True, "crashed": False, "relative": rel.as_posix(), "refused": False}
    except ValueError as exc:
        return {"ok": False, "crashed": False, "refused": True, "reason": str(exc)}
    except OSError as exc:
        return {"ok": False, "crashed": False, "refused": True, "reason": f"{type(exc).__name__}: {exc}"}


def reserved_name_control(tmp: Path) -> dict[str, Any]:
    """Create NUL through the Linux analogue of the Windows extended-length prefix."""
    lab = tmp / "reserved-lab"
    lab.mkdir()
    created: dict[str, Any] = {}
    for name in ("NUL", "CON"):
        posix = lab / name
        win_extended = r"\\?\\" + str(posix.resolve()).replace("/", "\\")
        try:
            posix.write_bytes(b"not-a-device\n")
            created[name] = {
                "created": True,
                "posix": str(posix),
                "windows_extended_prefix": win_extended,
                "is_file": posix.is_file(),
                "size": posix.stat().st_size,
                "error": None,
            }
        except OSError as exc:
            created[name] = {
                "created": False,
                "posix": str(posix),
                "windows_extended_prefix": win_extended,
                "is_file": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

    um_root = lab / "um-root"
    (um_root / "command-center" / "receipts").mkdir(parents=True)
    nul_art = um_root / "NUL"
    nul_art.write_bytes(b"canary-nul\n")
    (um_root / "command-center" / "receipts" / "NUL.json").write_text(
        json.dumps({"unit_id": "RSV-NUL", "artifacts": [{"path": "NUL"}]}),
        encoding="utf-8",
    )
    um_result: dict[str, Any]
    try:
        derived = um.derive(um_root)
        um_result = {
            "crashed": False,
            "ok": True,
            "sha256": derived["artifacts"][0]["sha256"],
            "path": derived["artifacts"][0]["path"],
            "handled": True,
            "explicit_refuse": False,
        }
    except Exception as exc:
        um_result = {
            "crashed": not isinstance(exc, um.ManifestError),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "handled": isinstance(exc, um.ManifestError),
            "explicit_refuse": isinstance(exc, um.ManifestError),
        }

    rel = _relative(lab, lab / "NUL") if created.get("NUL", {}).get("created") else {
        "ok": False,
        "crashed": False,
        "refused": True,
        "reason": "NUL not created",
    }
    live_has_guard = any(
        "reserved" in (CC / name).read_text(encoding="utf-8").lower()
        and "NUL" in (CC / name).read_text(encoding="utf-8")
        for name in ("catalog.py", "validate.py", "unit_manifest.py", "seed.py", "render.py")
    )
    no_crash = (not um_result.get("crashed")) and created.get("NUL", {}).get("created", False)
    return {
        "created": created,
        "unit_manifest": um_result,
        "relative_path_computation": rel,
        "live_source_has_reserved_guard": live_has_guard,
        "handled_or_refused_without_crash": no_crash or bool(um_result.get("explicit_refuse")),
        "windows_note": (
            "On Windows, open('NUL') hits the device namespace; the extended-length "
            "prefix \\\\?\\ is the documented way to create a file of that name. This "
            "Linux host created the basename NUL as the analogue of that prefix."
        ),
    }


def long_path_control(tmp: Path) -> dict[str, Any]:
    lab = tmp / "long-lab"
    parts = ["L" * 40] * 8 + ["end.json"]
    rel = "/".join(parts)
    assert len(rel) > 260, rel
    um_root = lab / "um-root"
    target = um_root / Path(rel)
    failure_mode = "none-on-linux"
    try:
        target.parent.mkdir(parents=True)
        target.write_bytes(b'{"long":true}\n')
        created = True
        create_error = None
    except OSError as exc:
        created = False
        create_error = f"{type(exc).__name__}: {exc}"
        failure_mode = create_error
    um_result: dict[str, Any] = {"ok": False}
    if created:
        (um_root / "command-center" / "receipts").mkdir(parents=True)
        (um_root / "command-center" / "receipts" / "LONG.json").write_text(
            json.dumps({"unit_id": "LONG-1", "artifacts": [{"path": rel}]}),
            encoding="utf-8",
        )
        try:
            derived = um.derive(um_root)
            um_result = {
                "ok": True,
                "crashed": False,
                "sha256": derived["artifacts"][0]["sha256"],
                "bytes": derived["artifacts"][0]["bytes"],
            }
        except Exception as exc:
            failure_mode = f"{type(exc).__name__}: {exc}"
            um_result = {
                "ok": False,
                "crashed": not isinstance(exc, um.ManifestError),
                "error": failure_mode,
            }
    abs_len = len(str(target))
    return {
        "relative_path": rel,
        "relative_len": len(rel),
        "absolute_len": abs_len,
        "beyond_win_max_path": len(rel) > 260 and abs_len > 260,
        "created": created,
        "create_error": create_error,
        "unit_manifest": um_result,
        "failure_mode": failure_mode,
        "windows_expected_without_extended_prefix": (
            "FileNotFoundError / WinError 3 or 206 (filename or extension too long) "
            "once the path exceeds MAX_PATH=260 without \\\\?\\"
        ),
    }


def case_collision_control(tmp: Path) -> dict[str, Any]:
    lab = tmp / "case-lab"
    lab.mkdir()
    a = lab / "Manifest.json"
    b = lab / "manifest.json"
    a.write_bytes(b'{"k":"A"}\n')
    b.write_bytes(b'{"k":"B"}\n')
    names = sorted(p.name for p in lab.iterdir() if p.is_file())
    folded: dict[str, list[str]] = {}
    for name in names:
        folded.setdefault(name.casefold(), []).append(name)
    collisions = {k: v for k, v in folded.items() if len(v) > 1}
    um_root = lab / "um-root"
    (um_root / "command-center" / "receipts").mkdir(parents=True)
    (um_root / "A.json").write_bytes(b'{"k":"A"}\n')
    # Plant both spellings as artifact paths; on Linux they are two files.
    (um_root / "Manifest.json").write_bytes(b'{"k":"A"}\n')
    (um_root / "manifest.json").write_bytes(b'{"k":"B"}\n')
    (um_root / "command-center" / "receipts" / "CASE.json").write_text(
        json.dumps(
            {
                "unit_id": "CASE-1",
                "artifacts": [
                    {"path": "Manifest.json"},
                    {"path": "manifest.json"},
                ],
            }
        ),
        encoding="utf-8",
    )
    derived = um.derive(um_root)
    shas = [row["sha256"] for row in derived["artifacts"]]
    source = (CC / "unit_manifest.py").read_text(encoding="utf-8")
    return {
        "linux_names": names,
        "linux_distinct_files": len(names),
        "casefold_collisions": collisions,
        "unit_manifest_rows": len(derived["artifacts"]),
        "unit_manifest_distinct_sha256": len(set(shas)),
        "live_code_detects_casefold_collision": "casefold" in source or "case-insensitive" in source.lower(),
        "windows_note": (
            "A case-insensitive volume cannot hold both Manifest.json and manifest.json; "
            "the second create overwrites. unit_manifest.py hashes path strings as-is and "
            "does not fail closed on casefold duplicates."
        ),
    }


def contract_presence() -> list[dict[str, Any]]:
    rows = []
    for uid in ("ARC-0078", "ARC-0080", "ARC-0084"):
        rel = f"command-center/phase4/contracts/{uid}.json"
        path = REPO / rel
        rows.append(
            {
                "id": uid,
                "path": rel,
                "present": path.is_file() and path.stat().st_size > 0,
            }
        )
    return rows


def validator_presence() -> list[dict[str, Any]]:
    rows = []
    for vid, rel in (
        ("cc-validate", "tools/command-center/validate.py"),
        ("cc-seed", "tools/command-center/seed.py"),
        ("cc-catalog-load", "tools/command-center/catalog.py"),
        ("cc-render-manifest", "tools/command-center/render.py"),
        ("cc-unit-manifest", "tools/command-center/unit_manifest.py"),
        ("cc-register-parse", "tools/command-center/register_parse.py"),
        ("plugin-manifest-validator", "tools/plugin/validate.py"),
        ("package-boundary-validator", "tools/package/boundary.py"),
    ):
        path = REPO / rel
        rows.append({"id": vid, "path": rel, "present": path.is_file()})
    return rows


def source_guards() -> dict[str, Any]:
    files = {
        "validate.py": CC / "validate.py",
        "seed.py": CC / "seed.py",
        "catalog.py": CC / "catalog.py",
        "render.py": CC / "render.py",
        "unit_manifest.py": CC / "unit_manifest.py",
        "register_parse.py": CC / "register_parse.py",
    }
    out = {}
    for name, path in files.items():
        text = path.read_text(encoding="utf-8")
        out[name] = {
            "lf_normalize": ".replace(b\"\\r\\n\", b\"\\n\")" in text
            or ".replace('\\r\\n', '\\n')" in text
            or '.replace("\\r\\n", "\\n")' in text,
            "utf8_sig": "utf-8-sig" in text,
            "reserved_device_guard": ("NUL" in text and "reserved" in text.lower()),
            "max_path_260": "260" in text or "MAX_PATH" in text,
            "casefold": "casefold" in text,
        }
    return out


def host_info() -> dict[str, Any]:
    return {
        "system": platform.platform(),
        "python": sys.version.split()[0],
        "git_worktree_repo": (REPO / ".git").is_dir(),
        "os_name": os.name,
        "path_sep": os.sep,
    }


def measure_probe1() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="arc0106-p1-") as td:
        tmp = Path(td)
        blob = lab_blob_method(tmp)
        crlf = crlf_both_states(tmp)
        bom = bom_both_states(tmp)
        wt = worktree_git_attempt()
        return {
            "probe": "probe1-crlf-blob-bom",
            "host": host_info(),
            "worktree_git": wt,
            "blob_method": blob,
            "crlf_both_states": crlf,
            "bom_both_states": bom,
            "source_guards": source_guards(),
        }


def measure_probe2() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="arc0106-p2-") as td:
        tmp = Path(td)
        reserved = reserved_name_control(tmp)
        longp = long_path_control(tmp)
        casec = case_collision_control(tmp)
        return {
            "probe": "probe2-reserved-longpath-case",
            "host": host_info(),
            "reserved_name": reserved,
            "long_path": longp,
            "case_collision": casec,
            "contracts": contract_presence(),
            "validators": validator_presence(),
            "source_guards": source_guards(),
        }
