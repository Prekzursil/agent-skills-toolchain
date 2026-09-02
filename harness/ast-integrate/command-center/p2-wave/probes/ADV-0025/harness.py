"""ADV-0025 fixtures: one-abuse-per-variant packages, linter discovery, sandbox install.

Probe 1 submits each variant to the marketplace package linter (or records
fail-open absence). Probe 2 installs accepted variants only into a disposable
dest_home, never the live plugin tree.

This module does not implement a production marketplace linter. That is
IMP-0113; rebuilding it here is the ADV rebuild circle.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.installer import InstallerError, install_direct  # noqa: E402

UNIT = "ADV-0025"
OUT_REL = (
    "command-center/adversarial/ADV-0025-adversarial-package-linter-bypass.json"
)
SCHEMA_REL = "command-center/schema/exploit-proof.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0025/probe1_linter_accept_reject.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0025/probe2_sandbox_install.py"
)
SENTINEL = (
    "SUCCESS:ADV-0025 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0025 <reason>."
)
QUESTION = (
    "Which of the following does the marketplace linter fail to reject: "
    "excessive permission requests, an install-time script, a manifest field "
    "that shadows a platform field, a package that writes outside its own root, "
    "and a package whose declared and actual contents differ?"
)
OUTSIDE_MEMBER = "../OUTSIDE-ADV0025.txt"
OUTSIDE_BODY = b"ADV0025_OUTSIDE\n"
POSTINSTALL_BODY = (
    b"#!/bin/sh\n"
    b"echo ADV0025_POSTINSTALL > \"${ADV0025_BEACON:-/tmp/should-not-write}\"\n"
)

PLATFORM_FIELDS = (
    "package_id",
    "digest",
    "schema_version",
    "transaction_id",
    "projection_map",
    "payload_path",
    "declared_permissions",
)

LINTER_PATH_CANDIDATES = (
    "tools/marketplace/lint.py",
    "tools/marketplace/linter.py",
    "tools/marketplace/package_linter.py",
    "tools/marketplace/cli.py",
    "tools/marketplace/publisher.py",
    "tools/marketplace/validate.py",
    "tools/marketplace/schema/lint-report.schema.json",
)

ABUSE_TARGETS = (
    "T-EXCESSIVE-PERMISSIONS",
    "T-INSTALL-TIME-SCRIPT",
    "T-SHADOW-PLATFORM-FIELD",
    "T-WRITE-OUTSIDE-ROOT",
    "T-DECLARED-VS-ACTUAL",
)

ALL_VARIANTS = ("C-BENIGN",) + ABUSE_TARGETS


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def dumps(doc: Any) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, default=str)


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _manifest(extra: dict[str, Any], *, name: str) -> bytes:
    body: dict[str, Any] = {
        "name": name,
        "version": "1.0.0",
        "license": "MIT",
        "files": ["plugin.json", "bin/demo"],
        "permissions": {
            "fs_write_roots": ["."],
            "process_spawn": False,
            "network": False,
        },
    }
    body.update(extra)
    return (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _demo_bin() -> bytes:
    return b'#!/usr/bin/env python3\nprint("adv0025-ok")\n'


def write_tar(
    dest: Path,
    members: list[tuple[str, bytes]],
    modes: dict[str, int] | None = None,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    modes = modes or {}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.mode = int(modes.get(name, 0o644))
            tf.addfile(info, io.BytesIO(data))
    dest.write_bytes(buf.getvalue())


def _base_members(
    manifest: bytes, extra: list[tuple[str, bytes]] | None = None
) -> list[tuple[str, bytes]]:
    rows = [("plugin.json", manifest), ("bin/demo", _demo_bin())]
    if extra:
        rows.extend(extra)
    return rows


def tar_member_names(blob: Path) -> list[str]:
    with tarfile.open(blob, "r:*") as tf:
        return [m.name for m in tf.getmembers()]


def build_variant(dest_dir: Path, variant_id: str) -> dict[str, Any]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    blob = dest_dir / f"{variant_id}.tar.gz"
    pkg_id = "adv0025-" + variant_id.lower().replace("t-", "").replace("_", "-")
    projection = {"plugin.json": "plugin.json", "bin/demo": "bin/demo"}
    declared = ["fs:plugin-root"]
    extra_meta: dict[str, Any] = {}
    abuse: str | None

    if variant_id == "C-BENIGN":
        man = _manifest({}, name="adv0025-benign")
        write_tar(blob, _base_members(man), modes={"bin/demo": 0o755})
        abuse = None
    elif variant_id == "T-EXCESSIVE-PERMISSIONS":
        man = _manifest(
            {
                "permissions": {
                    "fs_write_roots": [
                        "/",
                        "/etc",
                        "/usr",
                        "/home",
                        "/root",
                        "/var",
                        "*",
                    ],
                    "process_spawn": True,
                    "network": True,
                    "raw_syscall": True,
                },
                "tool_permissions": [
                    "Bash",
                    "Write",
                    "Edit",
                    "Read",
                    "WebFetch",
                    "WebSearch",
                    "Task",
                    "*",
                ],
            },
            name="adv0025-excessive-perms",
        )
        write_tar(blob, _base_members(man), modes={"bin/demo": 0o755})
        declared = ["*", "fs:/", "process:spawn", "net:*"]
        abuse = "excessive-permission-requests"
    elif variant_id == "T-INSTALL-TIME-SCRIPT":
        man = _manifest(
            {
                "scripts": {
                    "install": "scripts/postinstall.sh",
                    "postinstall": "scripts/postinstall.sh",
                },
                "install": "scripts/postinstall.sh",
            },
            name="adv0025-install-script",
        )
        members = _base_members(
            man, extra=[("scripts/postinstall.sh", POSTINSTALL_BODY)]
        )
        write_tar(
            blob,
            members,
            modes={"bin/demo": 0o755, "scripts/postinstall.sh": 0o755},
        )
        projection["scripts/postinstall.sh"] = "scripts/postinstall.sh"
        abuse = "install-time-script"
    elif variant_id == "T-SHADOW-PLATFORM-FIELD":
        extra = {k: f"forged-{k}" for k in PLATFORM_FIELDS}
        extra["digest"] = "sha256:" + ("0" * 64)
        extra["schema_version"] = 99
        extra["projection_map"] = {"plugin.json": "../../shadow.json"}
        extra["payload_path"] = "/etc/passwd"
        extra["declared_permissions"] = ["*"]
        extra["package_id"] = "platform.core"
        man = _manifest(extra, name="adv0025-shadow")
        write_tar(blob, _base_members(man), modes={"bin/demo": 0o755})
        extra_meta["shadowed_fields"] = list(PLATFORM_FIELDS)
        abuse = "manifest-field-shadows-platform-field"
    elif variant_id == "T-WRITE-OUTSIDE-ROOT":
        man = _manifest({}, name="adv0025-write-outside")
        members = _base_members(man, extra=[(OUTSIDE_MEMBER, OUTSIDE_BODY)])
        write_tar(blob, members, modes={"bin/demo": 0o755})
        extra_meta["outside_member"] = OUTSIDE_MEMBER
        abuse = "writes-outside-own-root"
    elif variant_id == "T-DECLARED-VS-ACTUAL":
        man = _manifest(
            {"files": ["plugin.json", "bin/demo"]},
            name="adv0025-mismatch",
        )
        members = _base_members(
            man, extra=[("hidden/not-declared.py", b"# undeclared extra member\n")]
        )
        write_tar(blob, members, modes={"bin/demo": 0o755})
        extra_meta["undeclared_member"] = "hidden/not-declared.py"
        extra_meta["declared_files"] = ["plugin.json", "bin/demo"]
        abuse = "declared-vs-actual-contents"
    else:
        raise ValueError(f"unknown variant {variant_id}")

    names = tar_member_names(blob)
    return {
        "variant_id": variant_id,
        "package_id": pkg_id,
        "blob": str(blob),
        "digest": sha256_file(blob),
        "projection_map": projection,
        "declared_permissions": declared,
        "abuse": abuse,
        "tar_members": names,
        "has_dotdot_member": any(".." in Path(n).parts for n in names),
        **extra_meta,
    }


def build_all(work: Path) -> dict[str, dict[str, Any]]:
    return {vid: build_variant(work / "packages", vid) for vid in ALL_VARIANTS}


def discover_linter() -> dict[str, Any]:
    present_paths = [p for p in LINTER_PATH_CANDIDATES if (REPO / p).is_file()]
    marketplace = REPO / "tools" / "marketplace"
    py_files = sorted(marketplace.rglob("*.py")) if marketplace.is_dir() else []
    lint_defs: list[dict[str, Any]] = []
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            name = getattr(node, "name", "") or ""
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            lowered = name.lower()
            if "lint" in lowered or name in {"validate_package", "check_package"}:
                lint_defs.append(
                    {
                        "path": path.relative_to(REPO).as_posix(),
                        "kind": type(node).__name__,
                        "name": name,
                        "lineno": int(getattr(node, "lineno", 0) or 0),
                    }
                )
    callable_mod = None
    for rel in (
        "tools/marketplace/lint.py",
        "tools/marketplace/linter.py",
        "tools/marketplace/package_linter.py",
    ):
        if (REPO / rel).is_file():
            callable_mod = rel
            break
    return {
        "marketplace_dir": marketplace.is_dir(),
        "candidate_paths_present": present_paths,
        "lint_defs": lint_defs,
        "callable_module": callable_mod,
        "publisher_cli_present": (REPO / "tools/marketplace/cli.py").is_file()
        or (REPO / "tools/marketplace/publisher.py").is_file(),
        # name_linter.py (typosquat) is not the package-content linter.
        "present": bool(callable_mod),
        "name_linter_defs": [
            d
            for d in lint_defs
            if str(d.get("path") or "").endswith("name_linter.py")
        ],
    }


def _normalize_linter_result(result: Any, *, invoked: str) -> dict[str, Any]:
    rule_ids: list[str] = []
    accepted = True
    reason = f"invoked {invoked}"
    if isinstance(result, dict):
        findings = (
            result.get("findings") or result.get("hits") or result.get("rule_ids") or []
        )
        if isinstance(findings, list):
            for item in findings:
                if isinstance(item, str):
                    rule_ids.append(item)
                elif isinstance(item, dict):
                    rid = item.get("rule_id") or item.get("id") or item.get("rule")
                    if rid:
                        rule_ids.append(str(rid))
        if "ok" in result:
            accepted = bool(result["ok"])
        elif "accepted" in result:
            accepted = bool(result["accepted"])
        elif rule_ids:
            accepted = False
        reason = str(result.get("reason") or result.get("summary") or reason)
    elif isinstance(result, bool):
        accepted = bool(result)
    elif result is None:
        accepted = True
    else:
        accepted = not bool(result)
    return {
        "accepted": bool(accepted),
        "rejected": not bool(accepted),
        "rule_ids": rule_ids,
        "reason": reason,
        "invoked": invoked,
    }


def _try_call_linter(
    blob: Path, package_dir: Path, discovery: dict[str, Any]
) -> dict[str, Any] | None:
    mod_rel = discovery.get("callable_module")
    if not mod_rel:
        return None
    path = REPO / str(mod_rel)
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("adv0025_mkt_lint", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ("lint_package", "lint", "check_package", "validate_package"):
        fn = getattr(mod, attr, None)
        if not callable(fn):
            continue
        try:
            result = fn(str(package_dir))
        except TypeError:
            try:
                result = fn(str(blob))
            except Exception as exc:  # noqa: BLE001
                return {
                    "accepted": False,
                    "rejected": True,
                    "rule_ids": ["linter-raised"],
                    "reason": f"{attr} raised {type(exc).__name__}: {exc}",
                    "invoked": attr,
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "accepted": False,
                "rejected": True,
                "rule_ids": ["linter-raised"],
                "reason": f"{attr} raised {type(exc).__name__}: {exc}",
                "invoked": attr,
            }
        return _normalize_linter_result(result, invoked=attr)
    return None


def extract_tree(blob: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(blob, "r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            name = member.name.lstrip("/")
            if ".." in Path(name).parts:
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(member)
            if src is None:
                continue
            target.write_bytes(src.read())


def submit_to_linter(blob: Path, *, variant_id: str, work: Path) -> dict[str, Any]:
    discovery = discover_linter()
    pkg_dir = work / "unpacked" / variant_id
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    extract_tree(blob, pkg_dir)
    called = _try_call_linter(blob, pkg_dir, discovery)
    if called is not None:
        called["linter_present"] = True
        called["discovery"] = discovery
        called["variant_id"] = variant_id
        return called
    return {
        "variant_id": variant_id,
        "accepted": True,
        "rejected": False,
        "rule_ids": [],
        "reason": "linter-absent-fail-open",
        "invoked": None,
        "linter_present": False,
        "discovery": discovery,
    }


def unsafe_extract(blob: Path, dest: Path) -> list[str]:
    written: list[str] = []
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(blob, "r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            target = Path(os.path.normpath(str(dest / member.name)))
            target.parent.mkdir(parents=True, exist_ok=True)
            handle = tf.extractfile(member)
            if handle is None:
                continue
            target.write_bytes(handle.read())
            written.append(str(target))
    return written


def list_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    out: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() or path.is_symlink():
            out.append(path.relative_to(root).as_posix())
    return out


def files_outside(root: Path, home: Path) -> list[str]:
    hits: list[str] = []
    if not root.exists():
        return hits
    home_res = home.resolve()
    for path in root.rglob("*"):
        if not path.is_file() and not path.is_symlink():
            continue
        try:
            path.resolve().relative_to(home_res)
        except ValueError:
            hits.append(str(path))
    return hits


def _outside_byte_hits(root: Path, home: Path, needle: bytes) -> list[str]:
    """Files under root, outside home, whose entire contents equal needle."""
    hits: list[str] = []
    if not root.exists():
        return hits
    home_res = home.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if data != needle:
            continue
        try:
            path.resolve().relative_to(home_res)
        except ValueError:
            hits.append(str(path))
    return hits


def _postinstall_content_hits(root: Path) -> list[str]:
    """Paths whose contents carry the postinstall canary, excluding the script itself."""
    hits: list[str] = []
    if not root.exists():
        return hits
    for path in root.rglob("*"):
        if not path.is_file() or path.name == "postinstall.sh":
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"ADV0025_POSTINSTALL" in data:
            hits.append(str(path))
    return hits


def sandbox_install(
    spec: dict[str, Any],
    dest_home: Path,
    *,
    repo: Path = REPO,
) -> dict[str, Any]:
    dest_home = Path(dest_home)
    dest_home.mkdir(parents=True, exist_ok=True)
    if _is_inside(dest_home, repo):
        raise RuntimeError("refusing to install into the live worktree")
    blob = Path(spec["blob"])
    parent = dest_home.parent
    tmp_beacon = Path("/tmp/should-not-write")
    before_outside = set(files_outside(parent, dest_home))
    before_body = set(_outside_byte_hits(parent, dest_home, OUTSIDE_BODY))
    before_post = set(_postinstall_content_hits(parent))
    before_tmp = tmp_beacon.read_bytes() if tmp_beacon.is_file() else None
    raised = None
    installed = False
    placed: list[str] = []
    live_root = dest_home / "plugins" / spec["package_id"]
    old_beacon_env = os.environ.get("ADV0025_BEACON")
    os.environ["ADV0025_BEACON"] = str(parent / "ADV0025_BEACON")
    try:
        result = install_direct(
            payload_path=blob,
            dest_home=dest_home,
            package_id=spec["package_id"],
            projection_map=spec["projection_map"],
            transaction_id=f"txn-{spec['package_id']}",
            digest=spec["digest"],
            declared_permissions=list(spec.get("declared_permissions") or []),
        )
        installed = True
        placed = list(result.get("placed") or [])
    except (InstallerError, tarfile.TarError, OSError, ValueError, KeyError) as exc:
        raised = f"{type(exc).__name__}:{exc}"
    finally:
        if old_beacon_env is None:
            os.environ.pop("ADV0025_BEACON", None)
        else:
            os.environ["ADV0025_BEACON"] = old_beacon_env
    after_outside = files_outside(parent, dest_home)
    new_outside = [p for p in after_outside if p not in before_outside]
    live_files = list_files(live_root) if live_root.exists() else []
    after_body = _outside_byte_hits(parent, dest_home, OUTSIDE_BODY)
    outside_body_hits = [p for p in after_body if p not in before_body]
    after_post = _postinstall_content_hits(parent)
    new_post = [p for p in after_post if p not in before_post]
    after_tmp = tmp_beacon.read_bytes() if tmp_beacon.is_file() else None
    tmp_beacon_fired = after_tmp is not None and after_tmp != before_tmp and (
        b"ADV0025_POSTINSTALL" in after_tmp
    )
    local_beacon = parent / "ADV0025_BEACON"
    local_beacon_fired = local_beacon.is_file() and (
        b"ADV0025_POSTINSTALL" in local_beacon.read_bytes()
    )
    postinstall_fired = bool(new_post or tmp_beacon_fired or local_beacon_fired)
    wrote_outside = bool(new_outside or outside_body_hits)
    return {
        "variant_id": spec["variant_id"],
        "package_id": spec["package_id"],
        "installed": installed,
        "raised": raised,
        "placed": placed,
        "live_files": live_files,
        "wrote_outside_dest_home": wrote_outside,
        "new_outside_paths": new_outside[:20],
        "outside_body_hits": outside_body_hits[:20],
        "postinstall_fired": postinstall_fired,
        "postinstall_new_paths": new_post[:20],
        "tmp_beacon_fired": tmp_beacon_fired,
        "local_beacon_fired": local_beacon_fired,
        "dest_home": str(dest_home),
        "live_plugin_tree_used": False,
        "inside_repo": _is_inside(dest_home, repo),
    }


def with_work(fn: Callable[[Path], Any]) -> Any:
    tmp = tempfile.mkdtemp(prefix="adv0025-")
    try:
        return fn(Path(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
