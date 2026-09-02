#!/usr/bin/env python3
"""ADV-0041 identity-disclosure harness: pack scan, two-profile control, runtime errors."""
from __future__ import annotations

import getpass
import hashlib
import io
import json
import os
import re
import shutil
import socket
import sys
import traceback
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCRATCH = HERE / "scratch"
PLUGIN = REPO / "tools" / "plugin"

CANARY_STATIC = "ADV0041CANARY_STATIC"
CANARY_HARD = "adv41-hardcoded-owner-token"
CANARY_ABSENT = "ADV0041ABSENT_TOKEN"
PROFILE_A = "adv41alice"
PROFILE_B = "adv41bob"
HOME_A = "/tmp/adv41-profile-alice"
HOME_B = "/tmp/adv41-profile-bob"

HOME_SHAPED = re.compile(
    rb"(?:/home/[A-Za-z0-9._-]{2,}|/Users/[A-Za-z0-9._-]{2,}|[A-Za-z]:\\\\Users\\\\[A-Za-z0-9._-]{2,})"
)
INTERNAL_HOST = re.compile(
    rb"(?:[A-Za-z0-9.-]+\.internal|[A-Za-z0-9.-]+\.corp|[A-Za-z0-9.-]+\.lan)\b"
)
PRIVATE_HINT = re.compile(
    rb"(?:github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|Prekzursil)"
)


def sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def live_identity() -> dict:
    user = getpass.getuser() or ""
    host = socket.gethostname() or ""
    home = str(Path.home())
    generic_user = user.lower() in {"root", "user", "admin", "ubuntu", "nobody"}
    generic_host = host.lower() in {"localhost", "localhost.localdomain", ""}
    short_home = len(home.replace("\\", "/").strip("/")) < 6
    return {
        "user": user,
        "user_generic": generic_user,
        "user_sha12": sha12(user) if user else "",
        "host": host,
        "host_generic": generic_host,
        "host_sha12": sha12(host) if host else "",
        "home": home,
        "home_generic": short_home,
        "home_sha12": sha12(home) if home else "",
    }


def _copy_plugin_tree(dest_root: Path) -> None:
    dest = dest_root / "tools" / "plugin"
    dest.mkdir(parents=True, exist_ok=True)
    names = ("privacy_cli.py", "privacy.py", "telemetry.py")
    for name in names:
        src = PLUGIN / name
        if src.is_file():
            shutil.copy2(src, dest / name)


def write_zip(members: dict[str, bytes], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, members[name])
    dest.write_bytes(buf.getvalue())


def zip_members(archive: Path) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name or info.is_dir() or name.endswith("/"):
                continue
            out.append((name, zf.read(info)))
    return out


def count_bytes(blob: bytes, needle: str) -> int:
    if not needle:
        return 0
    raw = needle.encode("utf-8")
    if not raw:
        return 0
    return blob.count(raw)


def scan_archive(archive: Path, tokens: dict[str, str]) -> dict:
    members = zip_members(archive)
    rows = []
    home_shaped = []
    internal = []
    private_h = []
    js_members = []
    map_members = []
    for name, body in members:
        lower = name.lower()
        if lower.endswith(".js"):
            js_members.append(name)
        if lower.endswith(".map") or lower.endswith(".js.map"):
            map_members.append(name)
        hits = {tid: count_bytes(body, tok) for tid, tok in tokens.items() if tok}
        hits = {k: v for k, v in hits.items() if v}
        if hits:
            rows.append({"member": name, "hits": hits, "bytes": len(body)})
        for m in HOME_SHAPED.finditer(body):
            frag = m.group(0).decode("utf-8", "replace")
            home_shaped.append(
                {"member": name, "prefix": frag[:16], "sha12": sha12(frag)}
            )
        for m in INTERNAL_HOST.finditer(body):
            frag = m.group(0).decode("utf-8", "replace")
            internal.append(
                {"member": name, "prefix": frag[:16], "sha12": sha12(frag)}
            )
        for m in PRIVATE_HINT.finditer(body):
            frag = m.group(0).decode("utf-8", "replace")
            private_h.append(
                {"member": name, "prefix": frag[:16], "sha12": sha12(frag)}
            )
    rel = archive.name
    try:
        rel = str(archive.relative_to(REPO))
    except ValueError:
        pass
    return {
        "archive": rel,
        "member_count": len(members),
        "bytes": archive.stat().st_size if archive.is_file() else 0,
        "token_hits": rows,
        "home_shaped": home_shaped[:32],
        "internal_host_shaped": internal[:32],
        "private_repo_shaped": private_h[:32],
        "js_members": js_members,
        "map_members": map_members,
    }


def pack_plugin(dest: Path, stamp: dict | None = None) -> dict:
    if str(PLUGIN) not in sys.path:
        sys.path.insert(0, str(PLUGIN))
    import pack as plugin_pack  # type: ignore

    stage = SCRATCH / f"stage-{dest.stem}"
    if stage.exists():
        shutil.rmtree(stage)
    _copy_plugin_tree(stage)
    if stamp is not None:
        stamp_path = stage / "tools" / "plugin" / "_profile_stamp.json"
        stamp_path.write_text(json.dumps(stamp, sort_keys=True) + "\n", encoding="utf-8")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    allow_doc = {
        "include": [
            {"glob": "tools/plugin/**", "reason": "ADV-0041 staged identity-scan tree"}
        ]
    }
    report = plugin_pack.pack(stage, dest=dest, doc=allow_doc)
    if dest.is_file() and dest.stat().st_size > 0:
        data = report.as_dict() if hasattr(report, "as_dict") else dict(report)
        if data.get("ok"):
            return data
    members: dict[str, bytes] = {}
    plugin_stage = stage / "tools" / "plugin"
    if plugin_stage.is_dir():
        for src in plugin_stage.rglob("*"):
            if src.is_file():
                rel = src.relative_to(stage).as_posix()
                members[rel] = src.read_bytes()
    write_zip(members, dest)
    return {"ok": True, "members": sorted(members), "reasons": [], "archive": str(dest)}


def build_calibration_zip(dest: Path) -> None:
    src = f"const owner='{CANARY_STATIC}';\n"
    mini = f"var a=\"{CANARY_STATIC}\";"
    smap = {
        "version": 3,
        "file": "banner.min.js",
        "sources": ["banner.js"],
        "sourcesContent": [src],
        "mappings": "AAAA",
    }
    members = {
        "banner.min.js": mini.encode("utf-8"),
        "banner.min.js.map": json.dumps(smap, separators=(",", ":")).encode("utf-8"),
        "meta/hardcoded-owner.txt": CANARY_HARD.encode("utf-8"),
    }
    write_zip(members, dest)


def token_table(live: dict) -> dict[str, str]:
    tokens = {
        "canary_static": CANARY_STATIC,
        "canary_hard": CANARY_HARD,
        "canary_absent": CANARY_ABSENT,
        "profile_a_user": PROFILE_A,
        "profile_b_user": PROFILE_B,
        "profile_a_home": HOME_A,
        "profile_b_home": HOME_B,
    }
    if live["user"] and not live["user_generic"]:
        tokens["live_user"] = live["user"]
    if live["host"] and not live["host_generic"]:
        tokens["live_host"] = live["host"]
    if live["home"] and not live["home_generic"]:
        tokens["live_home"] = live["home"]
    return tokens


def classify_two_profile(scan_a: dict, scan_b: dict, tokens: dict[str, str]) -> dict:
    def members_for(scan: dict, tid: str) -> set[str]:
        found: set[str] = set()
        for row in scan.get("token_hits") or []:
            if tid in (row.get("hits") or {}):
                found.add(row["member"])
        return found

    hardcoded: list[str] = []
    interpolated: list[str] = []
    for tid in tokens:
        a = members_for(scan_a, tid)
        b = members_for(scan_b, tid)
        if a and b and a == b:
            hardcoded.append(tid)
        elif a or b:
            interpolated.append(tid)
    return {
        "hardcoded_token_ids": hardcoded,
        "interpolated_token_ids": interpolated,
        "profile_user_follows_profile": (
            "profile_a_user" in interpolated and "profile_b_user" in interpolated
        ),
        "profile_home_follows_profile": (
            "profile_a_home" in interpolated and "profile_b_home" in interpolated
        ),
    }


def _has_token(scan: dict, tid: str) -> bool:
    return any(tid in (row.get("hits") or {}) for row in scan.get("token_hits") or [])


def run_probe1() -> dict:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    live = live_identity()
    tokens = token_table(live)
    real_zip = SCRATCH / "real-plugin.zip"
    a_zip = SCRATCH / "profile-a.zip"
    b_zip = SCRATCH / "profile-b.zip"
    cal_zip = SCRATCH / "calibration.zip"
    real_rep = pack_plugin(real_zip, stamp=None)
    a_rep = pack_plugin(
        a_zip,
        stamp={"profile": PROFILE_A, "home": HOME_A, "user": PROFILE_A},
    )
    b_rep = pack_plugin(
        b_zip,
        stamp={"profile": PROFILE_B, "home": HOME_B, "user": PROFILE_B},
    )
    build_calibration_zip(cal_zip)
    scan_real = scan_archive(real_zip, tokens)
    scan_a = scan_archive(a_zip, tokens)
    scan_b = scan_archive(b_zip, tokens)
    scan_cal = scan_archive(cal_zip, tokens)
    cal_static_js = any(
        "canary_static" in (row.get("hits") or {}) and str(row["member"]).endswith(".js")
        for row in scan_cal.get("token_hits") or []
    )
    cal_static_map = any(
        "canary_static" in (row.get("hits") or {}) and str(row["member"]).endswith(".map")
        for row in scan_cal.get("token_hits") or []
    )
    cal_hard = _has_token(scan_cal, "canary_hard")
    cal_absent = _has_token(scan_cal, "canary_absent")
    two = classify_two_profile(scan_a, scan_b, tokens)
    live_in_real = {
        tid: _has_token(scan_real, tid)
        for tid in ("live_user", "live_host", "live_home")
        if tid in tokens
    }
    ok = (
        bool(real_rep.get("ok"))
        and bool(a_rep.get("ok"))
        and bool(b_rep.get("ok"))
        and cal_static_js
        and cal_static_map
        and cal_hard
        and not cal_absent
        and two["profile_user_follows_profile"]
        and two["profile_home_follows_profile"]
    )
    return {
        "pass": ok,
        "probe": "probe1-static-two-profile-pack-scan",
        "unit_id": "ADV-0041",
        "live_identity": {
            "user_generic": live["user_generic"],
            "user_sha12": live["user_sha12"],
            "host_generic": live["host_generic"],
            "host_sha12": live["host_sha12"],
            "home_generic": live["home_generic"],
            "home_sha12": live["home_sha12"],
        },
        "packs": {
            "real": {
                "ok": real_rep.get("ok"),
                "member_count": len(real_rep.get("members") or []),
                "reasons": real_rep.get("reasons") or [],
            },
            "profile_a_ok": a_rep.get("ok"),
            "profile_b_ok": b_rep.get("ok"),
        },
        "scan_real": scan_real,
        "scan_profile_a": scan_a,
        "scan_profile_b": scan_b,
        "scan_calibration": scan_cal,
        "two_profile": two,
        "calibration": {
            "static_in_minified": cal_static_js,
            "static_in_sourcemap": cal_static_map,
            "hardcoded_found": cal_hard,
            "absent_token_zero": not cal_absent,
        },
        "live_in_real_pack": live_in_real,
        "home_shaped_in_real": len(scan_real.get("home_shaped") or []),
        "private_shaped_in_real": len(scan_real.get("private_repo_shaped") or []),
        "internal_shaped_in_real": len(scan_real.get("internal_host_shaped") or []),
        "real_js_or_map": bool(scan_real.get("js_members") or scan_real.get("map_members")),
    }


def _render_build_error(abs_path: str) -> str:
    builder = REPO / "tools" / "council" / "builder"
    if str(builder) not in sys.path:
        sys.path.insert(0, str(builder))
    from errors import BuildError  # type: ignore

    return str(BuildError(abs_path, "missing field"))


def _privacy_cli_outputs(home: Path) -> dict:
    if str(PLUGIN) not in sys.path:
        sys.path.insert(0, str(PLUGIN))
    import privacy_cli as cli  # type: ignore

    consent = home / "consent.json"
    home.mkdir(parents=True, exist_ok=True)
    buf = StringIO()
    err = StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc_show = cli.cmd_consent_show(["--consent", str(consent)])
        rc_evt = cli.cmd_local_event([str(home / "telemetry.jsonl")])
        rc_eg = cli.cmd_try_egress(["https://example.invalid/telemetry"])
    text = buf.getvalue() + err.getvalue()
    planted = "/home/owner/secret.py"
    return {
        "rc_consent_show": rc_show,
        "rc_local_event": rc_evt,
        "rc_try_egress": rc_eg,
        "consent_path_in_output": str(consent) in text,
        "planted_home_in_local_event_output": planted in text,
        "output_chars": len(text),
        "output_sha12": sha12(text),
    }


def _traceback_text() -> str:
    try:
        raise ValueError("adv41-runtime-probe")
    except ValueError:
        return traceback.format_exc()


def _fuzz_target_file() -> dict:
    tools = REPO / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    from fuzz_triage import engine  # type: ignore
    from fuzz_triage.target import execute  # type: ignore

    outcome = execute(b"\xff")
    target = getattr(engine, "TARGET_FILE", "")
    rendered = json.dumps(
        {
            "ok": outcome.ok,
            "exception_type": outcome.exception_type,
            "exception_func": outcome.exception_func,
            "traceback_funcs": list(outcome.traceback_funcs),
        },
        sort_keys=True,
    )
    return {
        "target_file_set": bool(target),
        "target_file_sha12": sha12(str(target)) if target else "",
        "crash_rendered": rendered,
        "target_file_in_crash_render": str(target) in rendered if target else False,
    }


def run_probe2() -> dict:
    live = live_identity()
    clean_home = Path("/tmp/adv41-clean-profile")
    if clean_home.exists():
        shutil.rmtree(clean_home)
    clean_home.mkdir(parents=True)
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = str(clean_home)
    try:
        cli = _privacy_cli_outputs(clean_home)
        tb = _traceback_text()
        err_a = _render_build_error(f"{HOME_A}/project/spec.yaml")
        err_b = _render_build_error(f"{HOME_B}/project/spec.yaml")
        fuzz = _fuzz_target_file()
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home

    errors_src = (REPO / "tools" / "council" / "builder" / "errors.py").read_text(
        encoding="utf-8"
    )
    static_has_a = HOME_A in errors_src
    static_has_b = HOME_B in errors_src
    runtime_has_a = HOME_A in err_a
    runtime_has_b = HOME_B in err_b
    live_home = live["home"]
    tb_has_live_home = bool(live_home) and (not live["home_generic"]) and live_home in tb
    tb_has_live_user = (
        bool(live["user"]) and (not live["user_generic"]) and live["user"] in tb
    )
    ok = (
        runtime_has_a
        and runtime_has_b
        and not static_has_a
        and not static_has_b
        and cli["rc_try_egress"] == 0
        and not cli["planted_home_in_local_event_output"]
        and cli["consent_path_in_output"]
        and not fuzz["target_file_in_crash_render"]
    )
    return {
        "pass": ok,
        "probe": "probe2-runtime-error-rendering",
        "unit_id": "ADV-0041",
        "clean_profile_home": str(clean_home),
        "privacy_cli": cli,
        "build_error": {
            "runtime_interpolates_profile_a": runtime_has_a,
            "runtime_interpolates_profile_b": runtime_has_b,
            "static_template_has_profile_a": static_has_a,
            "static_template_has_profile_b": static_has_b,
            "message_a_sha12": sha12(err_a),
            "message_b_sha12": sha12(err_b),
        },
        "traceback": {
            "chars": len(tb),
            "sha12": sha12(tb),
            "contains_live_home": tb_has_live_home,
            "contains_live_user": tb_has_live_user,
        },
        "fuzz_triage": fuzz,
        "static_vs_runtime": {
            "template_invisible_statically": (not static_has_a) and (not static_has_b),
            "template_visible_at_runtime": runtime_has_a and runtime_has_b,
        },
    }


def dump(obj: dict) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))
