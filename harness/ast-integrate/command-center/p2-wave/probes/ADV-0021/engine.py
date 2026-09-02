#!/usr/bin/env python3
"""Code-derived STRIDE model of the plugin install/update/repair/rollback/uninstall path."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.crypto import verify_signature  # noqa: E402
from marketplace.handoff import build_handoff, validate_handoff  # noqa: E402
from marketplace.install import install as marketplace_install  # noqa: E402
from plugin.errors import (  # noqa: E402
    DigestMismatchError,
    MissingTransactionIdError,
    PermissionWideningBlocked,
    ProjectionError,
)
from plugin.install import install_from_handoff  # noqa: E402
from plugin.payload import payload_digest  # noqa: E402
from plugin.uninstall import UninstallError, uninstall_plugin  # noqa: E402

UNIT = "ADV-0021"
OUT_REL = "command-center/adversarial/ADV-0021-install-path-stride-threat-model.json"
SCHEMA_REL = "command-center/schema/threat-model.schema.json"
SENTINEL = "SUCCESS:ADV-0021"
COMPLETION = (
    "SUCCESS:ADV-0021 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0021 <reason>."
)
QUESTION = (
    "What trust boundaries are crossed during install, update, repair, rollback "
    "and uninstall, and for each boundary which STRIDE category has no mitigating "
    "control?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0021/probe1_code_flows.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0021/probe2_bypass.py"
)
PROBE1_TEXT = (
    "Probe 1: enumerate data flows and trust boundaries from the code (not the "
    "design doc) and populate a STRIDE cell per boundary, marking each mitigated "
    "/ partially mitigated / unmitigated with a file:line for the control."
)
PROBE2_TEXT = (
    "Probe 2 (mechanically different): for every cell marked mitigated, execute "
    "the control's bypass attempt; a mitigation with no executable check is "
    "downgraded to unmitigated."
)

STRIDE = ("S", "T", "R", "I", "D", "E")
STRIDE_NAME = {
    "S": "Spoofing",
    "T": "Tampering",
    "R": "Repudiation",
    "I": "Information disclosure",
    "D": "Denial of service",
    "E": "Elevation of privilege",
}

SRC = {
    "install": "tools/plugin/install.py",
    "handoff": "tools/marketplace/handoff.py",
    "mkt_install": "tools/marketplace/install.py",
    "placement": "tools/plugin/placement.py",
    "payload": "tools/plugin/payload.py",
    "perm": "tools/plugin/permission_diff.py",
    "uninstall": "tools/plugin/uninstall.py",
    "crypto": "tools/marketplace/crypto.py",
    "journal": "tools/plugin/txn_journal.py",
    "policy": "tools/plugin/exec_policy.py",
    "intercept": "tools/plugin/intercept.py",
    "boot": "tools/plugin/boot.py",
}


def loc(rel: str, needle: str) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"{rel}:missing"
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return f"{rel}:0"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def calls_name(rel: str, func: str) -> bool:
    path = REPO / rel
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == func:
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr == func:
                return True
    return False


def write_payload(root: Path, *, name: str, version: str, perms: list[str], note: str) -> Path:
    payload = root / f"payload-{version}"
    (payload / "skills" / "skill.demo").mkdir(parents=True)
    manifest = {
        "name": name,
        "version": version,
        "description": "ADV-0021 disposable fixture",
        "permissions": perms,
        "skills": ["skills/skill.demo/SKILL.md"],
    }
    (payload / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (payload / "skills" / "skill.demo" / "SKILL.md").write_text(
        f"# {name} {version}\n{note}\n", encoding="utf-8"
    )
    return payload


def caught(exc_type: type[BaseException], fn: Callable[[], Any]) -> dict:
    try:
        fn()
        return {"raised": False, "exc": None, "msg": ""}
    except exc_type as exc:
        return {"raised": True, "exc": type(exc).__name__, "msg": str(exc)[:240]}
    except Exception as exc:
        return {
            "raised": False,
            "exc": type(exc).__name__,
            "msg": f"unexpected {type(exc).__name__}: {exc}"[:240],
        }


def cell(
    boundary: str,
    cat: str,
    status: str,
    anchor: str,
    control: str,
    *,
    executable: bool,
) -> dict:
    return {
        "id": f"{boundary}-{cat}",
        "boundary_id": boundary,
        "category": cat,
        "category_name": STRIDE_NAME[cat],
        "status": status,
        "control_anchor": anchor,
        "control": control,
        "executable_check_required": status == "mitigated",
        "probe1_claimed_executable": executable,
    }


def enumerate_from_code() -> dict:
    files_ok = {k: (REPO / v).is_file() for k, v in SRC.items()}
    missing = [v for k, v in SRC.items() if not files_ok[k]]
    sig_on_mkt = calls_name(SRC["mkt_install"], "verify_signature")
    journal_on_install = calls_name(SRC["install"], "recover") or calls_name(
        SRC["install"], "open_txn"
    )
    registry_hits = []
    for rel in SRC.values():
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "winreg" in text or "HKEY_" in text:
            registry_hits.append(rel)

    none = "none-on-this-path"
    a_h = loc(SRC["handoff"], "transaction_id is required")
    a_d = loc(SRC["install"], "payload_digest(payload)")
    a_c = loc(SRC["install"], "staged census does not match")
    a_p = loc(SRC["placement"], "dst.write_bytes")
    a_g = loc(SRC["perm"], "raise PermissionWideningBlocked")
    a_u = loc(SRC["uninstall"], "refusing uninstall")
    a_e = loc(SRC["uninstall"], "claimed path escapes profile")
    a_x = loc(SRC["uninstall"], "outside plugins/")
    a_s = loc(SRC["crypto"], "def verify_signature")
    a_j = loc(SRC["journal"], "def recover")
    a_r = loc(SRC["install"], "shutil.rmtree(dest_root)")
    a_i = loc(SRC["intercept"], "def install")
    a_boot = loc(SRC["boot"], "POLICY-DENIED")

    boundaries = [
        {
            "id": "TB-HANDOFF",
            "from": "untyped caller / marketplace",
            "to": "plugin installer",
            "operation": "install",
            "code_anchor": loc(SRC["handoff"], "def validate_handoff"),
            "crosses": "typed install-handoff object plus transaction_id",
        },
        {
            "id": "TB-DIGEST",
            "from": "payload bytes on disk",
            "to": "installer activation",
            "operation": "install/update",
            "code_anchor": a_d,
            "crosses": "sha256 payload digest vs handoff.digest.value",
        },
        {
            "id": "TB-PROJECTION",
            "from": "handoff.projection_map source/dest strings",
            "to": "filesystem under dest_root / staging",
            "operation": "install/update",
            "code_anchor": loc(SRC["placement"], "def place_payload_files"),
            "crosses": "single placement writer with no root confinement",
        },
        {
            "id": "TB-PERMISSIONS",
            "from": "candidate declared_permissions",
            "to": "already-installed dest_root",
            "operation": "update",
            "code_anchor": loc(SRC["perm"], "def gate_update"),
            "crosses": "lattice plus raw-set permission diff",
        },
        {
            "id": "TB-ACTIVATE",
            "from": "staging directory",
            "to": "live dest_root",
            "operation": "install/update",
            "code_anchor": a_r,
            "crosses": "rmtree(dest_root) then staging.rename; journal unused",
        },
        {
            "id": "TB-UNINSTALL",
            "from": "claim object",
            "to": "profile filesystem and shared JSON",
            "operation": "uninstall",
            "code_anchor": loc(SRC["uninstall"], "def uninstall_plugin"),
            "crosses": "claimed_paths under a disposable-profile marker",
        },
        {
            "id": "TB-SIGNATURE",
            "from": "marketplace payload / fixture publisher",
            "to": "marketplace.install",
            "operation": "install",
            "code_anchor": loc(SRC["mkt_install"], "IMP-0086"),
            "crosses": "HMAC-SHA256 verify_signature (not invoked on this path)",
        },
        {
            "id": "TB-REPAIR-ROLLBACK",
            "from": "interrupted install / prior dest_root",
            "to": "recovered dest_root",
            "operation": "repair/rollback",
            "code_anchor": a_j,
            "crosses": "txn_journal.recover exists and is not called from install.py",
        },
        {
            "id": "TB-RUNTIME",
            "from": "plugin-shipped script",
            "to": "spawn/write/connect in this interpreter",
            "operation": "post-install exec",
            "code_anchor": loc(SRC["policy"], "userspace intercept"),
            "crosses": "userspace intercept, not an OS sandbox; no Windows registry surface",
        },
    ]

    cells = [
        cell("TB-HANDOFF", "S", "mitigated", a_h, "typed handoff + transaction_id UUID", executable=True),
        cell("TB-HANDOFF", "T", "mitigated", a_h, "schema-valid handoff required before placement", executable=True),
        cell("TB-HANDOFF", "R", "partially-mitigated", a_h, "transaction_id on success; no durable audit log", executable=False),
        cell("TB-HANDOFF", "I", "unmitigated", none, "handoff carries local payload_path; no confidentiality control", executable=False),
        cell("TB-HANDOFF", "D", "unmitigated", none, "no rate-limit or size cap at the handoff validator", executable=False),
        cell("TB-HANDOFF", "E", "mitigated", a_h, "untyped/missing-tx call cannot place files", executable=True),
        cell("TB-DIGEST", "S", "mitigated", a_d, "digest mismatch refuses install", executable=True),
        cell("TB-DIGEST", "T", "mitigated", a_d, "payload bytes must match handoff digest", executable=True),
        cell("TB-DIGEST", "R", "partially-mitigated", a_d, "mismatch raises; no signed receipt of the check", executable=False),
        cell("TB-DIGEST", "I", "unmitigated", none, "digest does not cover projection sources outside the payload tree", executable=False),
        cell("TB-DIGEST", "D", "unmitigated", none, "no payload size/file-count cap before hashing", executable=False),
        cell("TB-DIGEST", "E", "mitigated", a_d, "wrong digest cannot activate dest_root", executable=True),
        cell("TB-PROJECTION", "S", "unmitigated", a_p, "placement trusts caller-supplied source/dest strings", executable=False),
        cell("TB-PROJECTION", "T", "unmitigated", a_p, "dest/source .. is not confined; census may fail after write", executable=False),
        cell("TB-PROJECTION", "R", "partially-mitigated", a_c, "census mismatch raises ProjectionError after writes", executable=False),
        cell("TB-PROJECTION", "I", "unmitigated", a_p, "source may read files outside payload_root", executable=False),
        cell("TB-PROJECTION", "D", "unmitigated", none, "no dest-count cap; rmtree of dest_root is unconditional on update", executable=False),
        cell("TB-PROJECTION", "E", "unmitigated", a_p, "escaped dest can write outside staging before census abort", executable=False),
        cell("TB-PERMISSIONS", "S", "mitigated", a_g, "widening without version-specific consent halts", executable=True),
        cell("TB-PERMISSIONS", "T", "mitigated", a_g, "halt occurs before placement when dest_root.exists()", executable=True),
        cell("TB-PERMISSIONS", "R", "partially-mitigated", a_g, "rendered_diff names added perms; not persisted", executable=False),
        cell("TB-PERMISSIONS", "I", "unmitigated", none, "first-install skips plugin.json re-validation", executable=False),
        cell("TB-PERMISSIONS", "D", "unmitigated", none, "no lock around dest_root during the gate-then-rmtree window", executable=False),
        cell("TB-PERMISSIONS", "E", "mitigated", a_g, "lattice widen is halt, not warn", executable=True),
        cell("TB-ACTIVATE", "S", "unmitigated", a_r, "rename is not bound to a journaled intent", executable=False),
        cell("TB-ACTIVATE", "T", "unmitigated", a_r, "live dest_root is deleted before staging rename", executable=False),
        cell("TB-ACTIVATE", "R", "unmitigated", none, "install.py does not append txn_journal records", executable=False),
        cell("TB-ACTIVATE", "I", "unmitigated", none, "staging dir name embeds only the UUID prefix", executable=False),
        cell("TB-ACTIVATE", "D", "unmitigated", a_r, "crash after rmtree and before rename loses dest_root", executable=False),
        cell("TB-ACTIVATE", "E", "unmitigated", a_r, "no restore path in install_from_handoff", executable=False),
        cell("TB-UNINSTALL", "S", "mitigated", a_u, "missing disposable marker refuses uninstall", executable=True),
        cell("TB-UNINSTALL", "T", "mitigated", a_e, "claimed path .. escape is refused", executable=True),
        cell("TB-UNINSTALL", "R", "partially-mitigated", loc(SRC["uninstall"], '"ok": True'), "result object; no journal", executable=False),
        cell("TB-UNINSTALL", "I", "mitigated", a_x, "claimed_paths must stay under plugins/<name>/", executable=True),
        cell("TB-UNINSTALL", "D", "partially-mitigated", a_u, "live profile is protected; disposable profile is fully in-scope", executable=False),
        cell("TB-UNINSTALL", "E", "mitigated", a_e, "path escape cannot reach outside the profile", executable=True),
        cell("TB-SIGNATURE", "S", "unmitigated", a_s, "verify_signature not called from marketplace.install", executable=False),
        cell("TB-SIGNATURE", "T", "unmitigated", a_s, "unsigned local payload installs", executable=False),
        cell("TB-SIGNATURE", "R", "unmitigated", none, "UNSIGNED is a crypto.py status, not an install gate", executable=False),
        cell("TB-SIGNATURE", "I", "unmitigated", none, "fixture HMAC secret is a documented non-credential in-repo", executable=False),
        cell("TB-SIGNATURE", "D", "unmitigated", none, "no revocation/lockfile gate on this path (IMP-0086)", executable=False),
        cell("TB-SIGNATURE", "E", "unmitigated", loc(SRC["mkt_install"], "must still never place files"), "marketplace.install builds a handoff then places via installer", executable=False),
        cell("TB-REPAIR-ROLLBACK", "S", "unmitigated", a_j, "no repair/rollback CLI on the install path", executable=False),
        cell("TB-REPAIR-ROLLBACK", "T", "unmitigated", a_j, "txn_journal.recover is not invoked by install.py", executable=False),
        cell("TB-REPAIR-ROLLBACK", "R", "unmitigated", a_j, "install path writes no journal records", executable=False),
        cell("TB-REPAIR-ROLLBACK", "I", "unmitigated", none, "no repair command; nothing to disclose on that interface", executable=False),
        cell("TB-REPAIR-ROLLBACK", "D", "unmitigated", a_j, "failed update has no rollback of the destroyed dest_root", executable=False),
        cell("TB-REPAIR-ROLLBACK", "E", "unmitigated", a_j, "no repair command to re-establish a known-good tree", executable=False),
        cell("TB-RUNTIME", "S", "partially-mitigated", a_boot, "boot.py fail-closed if intercept cannot install", executable=False),
        cell("TB-RUNTIME", "T", "partially-mitigated", loc(SRC["policy"], "def check_write"), "write intercept is userspace, not kernel", executable=False),
        cell("TB-RUNTIME", "R", "partially-mitigated", a_i, "violations recorded if log env set", executable=False),
        cell("TB-RUNTIME", "I", "partially-mitigated", loc(SRC["policy"], "def check_network"), "connect intercept; ctypes/native is out of scope", executable=False),
        cell("TB-RUNTIME", "D", "unmitigated", none, "no CPU/memory budget in exec_policy", executable=False),
        cell("TB-RUNTIME", "E", "partially-mitigated", loc(SRC["policy"], "def check_spawn"), "spawn allowlist; native children inherit the user token", executable=False),
    ]

    return {
        "probe": "probe1-code-flows",
        "unit_id": UNIT,
        "method": "ast-and-line-scan-of-install-path-modules",
        "files": files_ok,
        "missing_files": missing,
        "signature_called_from_marketplace_install": sig_on_mkt,
        "journal_called_from_install": journal_on_install,
        "windows_registry_hits": registry_hits,
        "boundaries": boundaries,
        "stride_cells": cells,
        "boundary_count": len(boundaries),
        "cell_count": len(cells),
        "mitigated": sum(1 for c in cells if c["status"] == "mitigated"),
        "partial": sum(1 for c in cells if c["status"] == "partially-mitigated"),
        "unmitigated": sum(1 for c in cells if c["status"] == "unmitigated"),
    }


def _run_bypasses(work: Path) -> dict:
    name = "stride-kit"
    payload = write_payload(
        work,
        name=name,
        version="1.0.0",
        perms=[f"fs:write:plugins/{name}"],
        note="benign",
    )
    dest = work / "dest"
    attempts: list[dict] = []

    def rec(cell_id: str, **kwargs: Any) -> None:
        attempts.append({"cell_id": cell_id, **kwargs})

    handoff = build_handoff(payload, source="direct")
    result = install_from_handoff(handoff, dest)
    benign_ok = dest.is_dir() and bool(result.get("placed"))
    rec(
        "CONTROL-BENIGN-INSTALL",
        kind="control",
        bypass_succeeded=False,
        control_held=benign_ok,
        detail=f"placed={len(result.get('placed') or [])}",
    )
    if not benign_ok:
        raise RuntimeError("benign install failed; probe is vacuous")

    r_raw = caught(MissingTransactionIdError, lambda: install_from_handoff("raw", work / "d-raw"))  # type: ignore[arg-type]
    rec("TB-HANDOFF-S", kind="bypass", bypass_succeeded=not r_raw["raised"], control_held=r_raw["raised"], detail=r_raw)
    rec("TB-HANDOFF-E", kind="bypass", bypass_succeeded=not r_raw["raised"], control_held=r_raw["raised"], detail=r_raw)
    r_miss = caught(
        MissingTransactionIdError,
        lambda: install_from_handoff({"payload_path": str(payload)}, work / "d-miss"),
    )
    rec("TB-HANDOFF-T", kind="bypass", bypass_succeeded=not r_miss["raised"], control_held=r_miss["raised"], detail=r_miss)
    if (work / "d-raw").exists() or (work / "d-miss").exists():
        raise RuntimeError("untyped handoff placed files")

    bad = dict(handoff)
    bad["digest"] = {"alg": "sha256", "value": "0" * 64}
    r_dig = caught(DigestMismatchError, lambda: install_from_handoff(bad, work / "d-dig"))
    rec("TB-DIGEST-S", kind="bypass", bypass_succeeded=not r_dig["raised"], control_held=r_dig["raised"], detail=r_dig)
    rec("TB-DIGEST-T", kind="bypass", bypass_succeeded=not r_dig["raised"], control_held=r_dig["raised"], detail=r_dig)
    rec("TB-DIGEST-E", kind="bypass", bypass_succeeded=not r_dig["raised"], control_held=r_dig["raised"], detail=r_dig)
    if (work / "d-dig").exists():
        raise RuntimeError("digest mismatch still placed dest")

    snapshot = {p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob("*") if p.is_file()}
    wide_payload = write_payload(
        work,
        name=name,
        version="2.0.0",
        perms=[f"fs:write:plugins/{name}", "net:connect:example"],
        note="widen",
    )
    wide = build_handoff(wide_payload, source="direct")
    r_wide = caught(PermissionWideningBlocked, lambda: install_from_handoff(wide, dest))
    after_same = {
        p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob("*") if p.is_file()
    } == snapshot
    rec("TB-PERMISSIONS-S", kind="bypass", bypass_succeeded=not r_wide["raised"], control_held=r_wide["raised"] and after_same, detail=r_wide)
    rec("TB-PERMISSIONS-T", kind="bypass", bypass_succeeded=not r_wide["raised"], control_held=r_wide["raised"] and after_same, detail={"raised": r_wide["raised"], "unchanged": after_same})
    rec("TB-PERMISSIONS-E", kind="bypass", bypass_succeeded=not r_wide["raised"], control_held=r_wide["raised"] and after_same, detail=r_wide)

    live = work / "live-profile"
    live.mkdir()
    r_live = caught(
        UninstallError,
        lambda: uninstall_plugin(
            live, {"plugin_name": name, "claimed_paths": [f"plugins/{name}/plugin.json"]}
        ),
    )
    rec("TB-UNINSTALL-S", kind="bypass", bypass_succeeded=not r_live["raised"], control_held=r_live["raised"], detail=r_live)

    profile = work / "disp-profile"
    profile.mkdir()
    (profile / ".disposable-profile.json").write_text(
        json.dumps({"disposable": True, "unit_id": UNIT}) + "\n", encoding="utf-8"
    )
    (profile / "plugins" / name).mkdir(parents=True)
    (profile / "plugins" / name / "plugin.json").write_text("{}\n", encoding="utf-8")
    r_esc = caught(
        UninstallError,
        lambda: uninstall_plugin(
            profile,
            {"plugin_name": name, "claimed_paths": [f"plugins/{name}/../../secret"]},
        ),
    )
    rec("TB-UNINSTALL-T", kind="bypass", bypass_succeeded=not r_esc["raised"], control_held=r_esc["raised"], detail=r_esc)
    rec("TB-UNINSTALL-E", kind="bypass", bypass_succeeded=not r_esc["raised"], control_held=r_esc["raised"], detail=r_esc)
    r_pre = caught(
        UninstallError,
        lambda: uninstall_plugin(
            profile,
            {"plugin_name": name, "claimed_paths": ["plugins/other/plugin.json"]},
        ),
    )
    rec("TB-UNINSTALL-I", kind="bypass", bypass_succeeded=not r_pre["raised"], control_held=r_pre["raised"], detail=r_pre)

    leak_dest = work / "proj-dest"
    leak_h = dict(handoff)
    leak_h["transaction_id"] = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
    proj = dict(leak_h["projection_map"])
    entries = [dict(e) for e in proj["entries"]]
    entries[0] = dict(entries[0])
    entries[0]["dest"] = "../escape-canary.txt"
    proj["entries"] = entries
    leak_h["projection_map"] = proj
    r_trav = caught(ProjectionError, lambda: install_from_handoff(leak_h, leak_dest))
    escaped = work / "escape-canary.txt"
    rec(
        "TB-PROJECTION-E",
        kind="demonstration",
        bypass_succeeded=escaped.is_file(),
        control_held=not escaped.is_file(),
        detail={"raised": r_trav["raised"], "escaped_exists": escaped.is_file()},
    )
    rec(
        "TB-PROJECTION-T",
        kind="demonstration",
        bypass_succeeded=escaped.is_file(),
        control_held=not escaped.is_file(),
        detail={"raised": r_trav["raised"], "escaped_exists": escaped.is_file()},
    )

    secret = payload.parent / "secret.txt"
    secret.write_text("ADV0021-SECRET-NOT-A-CREDENTIAL\n", encoding="utf-8")
    src_h = dict(handoff)
    src_h["transaction_id"] = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
    src_proj = dict(src_h["projection_map"])
    src_entries = [dict(e) for e in src_proj["entries"]]
    src_entries.append({"source": "../secret.txt", "dest": f"plugins/{name}/stolen.txt"})
    src_proj["entries"] = src_entries
    src_h["projection_map"] = src_proj
    steal_dest = work / "steal-dest"
    r_src = caught(Exception, lambda: install_from_handoff(src_h, steal_dest))
    stolen = steal_dest / "plugins" / name / "stolen.txt"
    rec(
        "TB-PROJECTION-I",
        kind="demonstration",
        bypass_succeeded=stolen.is_file(),
        control_held=not stolen.is_file(),
        detail={"raised": r_src["raised"], "exc": r_src["exc"], "stolen": stolen.is_file()},
    )

    unsigned_dest = work / "unsigned-dest"
    mkt = marketplace_install(payload, unsigned_dest)
    unsigned_ok = unsigned_dest.is_dir() and bool((mkt.get("result") or {}).get("placed"))
    rec(
        "TB-SIGNATURE-S",
        kind="demonstration",
        bypass_succeeded=unsigned_ok,
        control_held=not unsigned_ok,
        detail={"marketplace_install_without_signature": unsigned_ok},
    )
    rec(
        "TB-SIGNATURE-T",
        kind="demonstration",
        bypass_succeeded=unsigned_ok,
        control_held=not unsigned_ok,
        detail={"marketplace_install_without_signature": unsigned_ok},
    )

    unsigned_status = verify_signature({"n": 1}, None)
    flipped = verify_signature(
        {"n": 1},
        {"algorithm": "HMAC-SHA256", "digest": "00", "key_id": "x", "signature": "00"},
    )
    rec(
        "NC-CRYPTO-NOT-VACUOUS",
        kind="negative-control",
        bypass_succeeded=False,
        control_held=unsigned_status == "UNSIGNED" and unsigned_status != flipped,
        detail={"unsigned": unsigned_status, "bad_record": flipped},
    )

    return {"benign_ok": benign_ok, "attempts": attempts, "payload_digest": payload_digest(payload)}


def run_bypasses() -> dict:
    work = Path(tempfile.mkdtemp(prefix="adv0021-"))
    try:
        return _run_bypasses(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def apply_bypass_to_cells(model: dict, bypass: dict) -> dict:
    by_cell: dict[str, list[dict]] = {}
    for att in bypass["attempts"]:
        by_cell.setdefault(att["cell_id"], []).append(att)
    downgraded: list[str] = []
    cells = []
    for item in model["stride_cells"]:
        updated = dict(item)
        hits = by_cell.get(item["id"]) or []
        updated["bypass_attempts"] = hits
        if item["status"] == "mitigated":
            if not hits:
                updated["status"] = "unmitigated"
                updated["downgrade_reason"] = "no-executable-check"
                downgraded.append(item["id"])
            elif any(h.get("bypass_succeeded") for h in hits):
                updated["status"] = "unmitigated"
                updated["downgrade_reason"] = "bypass-succeeded"
                downgraded.append(item["id"])
            elif not all(h.get("control_held") for h in hits):
                updated["status"] = "unmitigated"
                updated["downgrade_reason"] = "control-did-not-hold"
                downgraded.append(item["id"])
        elif hits and any(h.get("kind") == "demonstration" and h.get("bypass_succeeded") for h in hits):
            updated["demonstration_confirmed"] = True
        cells.append(updated)
    out = dict(model)
    out["stride_cells"] = cells
    out["downgraded"] = downgraded
    out["mitigated"] = sum(1 for c in cells if c["status"] == "mitigated")
    out["partial"] = sum(1 for c in cells if c["status"] == "partially-mitigated")
    out["unmitigated"] = sum(1 for c in cells if c["status"] == "unmitigated")
    out["bypass"] = {
        "benign_ok": bypass["benign_ok"],
        "attempt_count": len(bypass["attempts"]),
        "downgraded": downgraded,
    }
    return out


FOLLOW_UPS = {
    "TB-PROJECTION": ("ADV-0027", "Archive/path traversal on install/import; projection dest/source confinement is the sibling gap."),
    "TB-SIGNATURE": ("ADV-0028", "Signature/provenance verification bypass on install."),
    "TB-ACTIVATE": ("ADV-0030", "TOCTOU / activate-without-recheck between validation and the live tree."),
    "TB-DIGEST": ("ADV-0030", "Digest covers payload files, not projection sources; sibling of validate-then-install TOCTOU."),
    "TB-PERMISSIONS": ("ADV-0022", "First-install skips plugin.json re-validation; runtime permission enforcement is ADV-0022."),
    "TB-RUNTIME": ("ADV-0022", "Userspace intercept is not an OS sandbox; declared-vs-actual capability is ADV-0022."),
    "TB-HANDOFF": ("ADV-0025", "DoS/size and confidentiality of the handoff object are outside the typed-schema gate."),
    "TB-UNINSTALL": ("ADV-0120", "Shared-JSON semantic-empty vs claimed-path uninstall (already modeled)."),
}

RESIDUALS = {
    "TB-REPAIR-ROLLBACK": (
        "install_from_handoff rmtree(dest_root) then rename with no journal. "
        "tools/plugin/txn_journal.py recover exists but is not called from install.py. "
        "A crash after delete and before rename loses the previous tree. Owner-visible "
        "impact: update is not crash-safe; operators must restore dest_root from backup. "
        "No Windows registry surface exists on this Linux worktree."
    ),
}


def dispositions_for(cells: list[dict]) -> list[dict]:
    out: list[dict] = []
    for item in cells:
        if item["status"] != "unmitigated":
            continue
        bid = item["boundary_id"]
        fu = FOLLOW_UPS.get(bid)
        if fu:
            out.append(
                {
                    "cell_id": item["id"],
                    "kind": "follow-up-unit",
                    "follow_up_unit": fu[0],
                    "impact_statement": fu[1],
                }
            )
        else:
            stmt = RESIDUALS.get(bid) or (
                f"Unmitigated {item['category_name']} on {bid} with no named follow-up unit; "
                "owner-visible residual on the install path."
            )
            out.append(
                {
                    "cell_id": item["id"],
                    "kind": "accepted-residual",
                    "follow_up_unit": "",
                    "impact_statement": stmt,
                }
            )
    return out


def closure_ok(cells: list[dict], disp: list[dict]) -> tuple[bool, str]:
    needed = {c["id"] for c in cells if c["status"] == "unmitigated"}
    covered = {d["cell_id"] for d in disp}
    missing = sorted(needed - covered)
    if missing:
        return False, f"unmitigated cells without disposition: {missing}"
    for item in disp:
        if item["kind"] == "follow-up-unit" and not item.get("follow_up_unit"):
            return False, f"{item['cell_id']} follow-up unnamed"
        if item["kind"] == "accepted-residual" and len(str(item.get("impact_statement") or "")) < 24:
            return False, f"{item['cell_id']} residual too short"
    return True, "ok"


def targets_from(model: dict) -> list[dict]:
    cells = model["stride_cells"]
    unmit = [c for c in cells if c["status"] == "unmitigated"]
    mit = [c for c in cells if c["status"] == "mitigated"]
    by_b: dict[str, list[dict]] = {}
    for item in cells:
        by_b.setdefault(item["boundary_id"], []).append(item)

    def v_for(boundary: str) -> str:
        stats = {c["status"] for c in by_b[boundary]}
        if stats == {"mitigated"}:
            return "REFUTED"
        if "unmitigated" in stats and "mitigated" in stats:
            return "PARTIAL"
        if "unmitigated" in stats:
            return "CONFIRMED"
        return "PARTIAL"

    targets = [
        {
            "id": "T-UNMITIGATED-EXISTS",
            "question": "Does any STRIDE cell on the install/update/repair/rollback/uninstall path lack a mitigating control?",
            "verdict": "CONFIRMED" if unmit else "REFUTED",
            "meaning": "CONFIRMED means at least one unmitigated cell was measured from code plus bypass.",
        },
        {
            "id": "T-MITIGATED-CONTROLS-HOLD",
            "question": "Do the cells marked mitigated actually refuse their bypass attempts?",
            "verdict": "REFUTED" if mit and not model.get("downgraded") else "CONFIRMED",
            "meaning": "REFUTED means claimed mitigations held under executable bypass (the attack did not land).",
        },
    ]
    labels = (
        ("TB-HANDOFF", "typed handoff / missing transaction_id"),
        ("TB-DIGEST", "payload digest mismatch"),
        ("TB-PROJECTION", "projection dest/source confinement"),
        ("TB-PERMISSIONS", "permission widening without consent"),
        ("TB-ACTIVATE", "staging activate / rollback"),
        ("TB-UNINSTALL", "uninstall path/profile confinement"),
        ("TB-SIGNATURE", "marketplace signature gate on install"),
        ("TB-REPAIR-ROLLBACK", "repair and rollback commands"),
        ("TB-RUNTIME", "post-install userspace exec policy"),
    )
    for bid, meta in labels:
        targets.append(
            {
                "id": f"T-{bid}",
                "question": f"Which STRIDE categories on {bid} ({meta}) have no mitigating control?",
                "verdict": v_for(bid),
                "meaning": "CONFIRMED = gap on that boundary; REFUTED = all six STRIDE cells mitigated; PARTIAL = mix.",
            }
        )
    return targets


def probe1_payload() -> dict:
    model = enumerate_from_code()
    if model["missing_files"]:
        model["pass"] = False
        model["reason"] = f"missing {model['missing_files']}"
        return model
    if model["boundary_count"] < 5 or model["cell_count"] < 30:
        model["pass"] = False
        model["reason"] = "enumeration too small to be a STRIDE model"
        return model
    if model["mitigated"] < 1 or model["unmitigated"] < 1:
        model["pass"] = False
        model["reason"] = "model is not two-sided (need both mitigated and unmitigated cells)"
        return model
    if model["signature_called_from_marketplace_install"]:
        model["pass"] = False
        model["reason"] = "marketplace.install unexpectedly calls verify_signature; model must be rebuilt"
        return model
    if model["journal_called_from_install"]:
        model["pass"] = False
        model["reason"] = "install.py unexpectedly journals; TB-ACTIVATE/REPAIR must be rebuilt"
        return model
    if model["windows_registry_hits"]:
        model["pass"] = False
        model["reason"] = f"unexpected registry references {model['windows_registry_hits']}"
        return model
    model["pass"] = True
    model["reason"] = "ok"
    return model


def probe2_payload() -> dict:
    model = enumerate_from_code()
    try:
        bypass = run_bypasses()
    except Exception as exc:
        return {
            "probe": "probe2-bypass",
            "unit_id": UNIT,
            "pass": False,
            "reason": f"bypass harness failed: {exc}",
            "traceback": traceback.format_exc()[-2000:],
        }
    merged = apply_bypass_to_cells(model, bypass)
    disp = dispositions_for(merged["stride_cells"])
    ok, why = closure_ok(merged["stride_cells"], disp)
    mit_cells = [c for c in merged["stride_cells"] if c["status"] == "mitigated"]
    missing_exec = [c["id"] for c in mit_cells if not c.get("bypass_attempts")]
    crypto_nc = next(
        (a for a in bypass["attempts"] if a["cell_id"] == "NC-CRYPTO-NOT-VACUOUS"),
        None,
    )
    merged.update(
        {
            "probe": "probe2-bypass",
            "dispositions": disp,
            "closure_ok": ok,
            "closure_reason": why,
            "missing_executable_checks": missing_exec,
            "crypto_negative_control": crypto_nc,
        }
    )
    if missing_exec:
        merged["pass"] = False
        merged["reason"] = f"mitigated cells without executable check: {missing_exec}"
        return merged
    if not ok:
        merged["pass"] = False
        merged["reason"] = why
        return merged
    if not bypass["benign_ok"]:
        merged["pass"] = False
        merged["reason"] = "benign install control failed"
        return merged
    if crypto_nc is None or not crypto_nc.get("control_held"):
        merged["pass"] = False
        merged["reason"] = "crypto negative control did not fire"
        return merged
    if merged["mitigated"] < 1:
        merged["pass"] = False
        merged["reason"] = "no mitigated cell survived executable bypass"
        return merged
    merged["pass"] = True
    merged["reason"] = "ok"
    return merged
