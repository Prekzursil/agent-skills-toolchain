"""Disposable-prefix install / upgrade / rollback for ADV-0119.

Production platform/plugin is absent on this sparse worktree. The drill
packages N-1 (1.0.0) and N (1.0.1), installs them into a throwaway prefix,
and rolls back without touching anything outside that prefix.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

N1_VERSION = "1.0.0"
N_VERSION = "1.0.1"
PKG_N1 = "ast-integrate-platform-1.0.0.zip"
PKG_N = "ast-integrate-platform-1.0.1.zip"
USER_RELS = (
    "etc/user-config.json",
    "workflows/user-authored.yaml",
    "cache/user-artifact.bin",
)
COMMANDS_N1 = ("ast-journey", "ast-n1-only")
COMMANDS_N_ONLY = ("ast-n-only",)
USER_CONFIG = {
    "display_name": "adv-0119-owner",
    "theme": "user-dark",
    "custom_key": "must-survive-rollback",
}
USER_WORKFLOW = (
    "id: user-authored-workflow\n"
    "token: USER-WORKFLOW-ADV-0119\n"
    "owner: seeded-before-upgrade\n"
)
USER_CACHE = b"USER-CACHE-BYTES-ADV-0119\n"
ZIP_FIXED_TIME = (2026, 8, 24, 18, 0, 0)
INSTALLED_LIST = "var/installed-files.json"
STATE_REL = "var/state.json"
VERSION_REL = "var/installed-version.txt"
MANIFEST_REL = "var/ROLLBACK-MANIFEST.json"
CANARY_NAME = "LIVE-PROFILE-CANARY.txt"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _py_header() -> str:
    return "#!/usr/bin/env python3\n# ADV-0119 packaged command\n"


def _platform_rt(version: str, accept_v2: bool) -> str:
    accept = "1, 2" if accept_v2 else "1"
    return f'''{_py_header()}
"""Runtime that N-1 refuses leftover N-format state."""
from __future__ import annotations

import json
from pathlib import Path

VERSION = {version!r}
ACCEPT_SCHEMA = {{{accept}}}
ROOT = Path(__file__).resolve().parents[1]


def load_state(root: Path | None = None) -> dict:
    base = Path(root) if root is not None else ROOT
    path = base / "var" / "state.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    ver = int(doc.get("schema_version") or 0)
    if ver not in ACCEPT_SCHEMA:
        raise RuntimeError(f"n-1-cannot-read-schema-{{ver}}")
    return doc
'''


def _cmd_journey() -> str:
    return f'''{_py_header()}
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from platform_rt import load_state  # noqa: E402


def main() -> int:
    cfg = json.loads((ROOT / "etc" / "user-config.json").read_text(encoding="utf-8"))
    wf = (ROOT / "workflows" / "user-authored.yaml").read_text(encoding="utf-8")
    cache = (ROOT / "cache" / "user-artifact.bin").read_bytes()
    state = load_state(ROOT)
    out = {{
        "ok": True,
        "user": cfg.get("display_name"),
        "custom_key": cfg.get("custom_key"),
        "workflow_token": "USER-WORKFLOW-ADV-0119" in wf,
        "cache_ok": cache == {USER_CACHE!r},
        "schema_version": state.get("schema_version"),
        "runtime": "n-1",
    }}
    dest = ROOT / "var" / "journey-out.json"
    dest.write_text(json.dumps(out, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    print("JOURNEY-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _cmd_n1_only() -> str:
    return f'''{_py_header()}
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cfg = json.loads((ROOT / "etc" / "user-config.json").read_text(encoding="utf-8"))
    print("N1-COMMAND-OK " + str(cfg.get("custom_key")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _cmd_n_only() -> str:
    return f'''{_py_header()}
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("N-COMMAND-OK")
    (ROOT / "var" / "n-only-ran.txt").write_text("n\\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def n1_payload() -> dict[str, bytes]:
    state = {
        "schema_version": 1,
        "format": "n-1",
        "user_id": "adv-0119",
    }
    files = {
        "bin/ast-journey": _cmd_journey().encode("utf-8"),
        "bin/ast-n1-only": _cmd_n1_only().encode("utf-8"),
        "lib/platform_rt.py": _platform_rt(N1_VERSION, accept_v2=False).encode("utf-8"),
        STATE_REL: (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        VERSION_REL: (N1_VERSION + "\n").encode("utf-8"),
        "lib/README.txt": b"N-1 payload; user data is not in this package.\n",
    }
    files[INSTALLED_LIST] = (
        json.dumps(sorted(files.keys()), indent=2) + "\n"
    ).encode("utf-8")
    return files


def n_payload() -> dict[str, bytes]:
    state = {
        "schema_version": 2,
        "format": "n",
        "user_id": "adv-0119",
        "n_only_blob": "N-FORMAT-STATE-ADV-0119",
    }
    files = {
        "bin/ast-journey": _cmd_journey().encode("utf-8"),
        "bin/ast-n1-only": _cmd_n1_only().encode("utf-8"),
        "bin/ast-n-only": _cmd_n_only().encode("utf-8"),
        "lib/platform_rt.py": _platform_rt(N_VERSION, accept_v2=True).encode("utf-8"),
        STATE_REL: (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        VERSION_REL: (N_VERSION + "\n").encode("utf-8"),
        "lib/README.txt": b"N payload; introduces ast-n-only and schema v2.\n",
    }
    files[INSTALLED_LIST] = (
        json.dumps(sorted(files.keys()), indent=2) + "\n"
    ).encode("utf-8")
    return files


def write_zip(files: dict[str, bytes], dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(dest, "w", compression=ZIP_STORED) as zf:
        for name in sorted(files):
            info = ZipInfo(name)
            info.date_time = ZIP_FIXED_TIME
            info.compress_type = ZIP_STORED
            info.external_attr = 0o644 << 16
            zf.writestr(info, files[name])
    return sha256_file(dest)


def build_packages(dist: Path) -> dict:
    dist.mkdir(parents=True, exist_ok=True)
    n1_path = dist / PKG_N1
    n_path = dist / PKG_N
    n1_sha = write_zip(n1_payload(), n1_path)
    n_sha = write_zip(n_payload(), n_path)
    manifest = {
        "n_minus_1": {
            "version": N1_VERSION,
            "artifact": PKG_N1,
            "sha256": n1_sha,
            "bytes": n1_path.stat().st_size,
        },
        "n": {
            "version": N_VERSION,
            "artifact": PKG_N,
            "sha256": n_sha,
            "bytes": n_path.stat().st_size,
        },
        "note": (
            "N-1 must be fetchable and hash-equal before any downgrade. "
            "command-center/ROLLBACK-MANIFEST.md is absent on this worktree; "
            "this probe-local manifest is the drill's retrievability record."
        ),
    }
    man_path = dist / "ROLLBACK-MANIFEST.json"
    man_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "n1_zip": n1_path,
        "n_zip": n_path,
        "n1_sha256": n1_sha,
        "n_sha256": n_sha,
        "manifest": manifest,
        "manifest_path": man_path,
    }


def extract_package(zip_path: Path, prefix: Path) -> list[str]:
    prefix.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = info.filename.replace("\\", "/")
            if rel in USER_RELS:
                continue
            target = prefix / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            names.append(rel)
    return sorted(names)


def seed_user_data(prefix: Path) -> dict[str, str]:
    mapping = {
        "etc/user-config.json": (
            json.dumps(USER_CONFIG, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "workflows/user-authored.yaml": USER_WORKFLOW.encode("utf-8"),
        "cache/user-artifact.bin": USER_CACHE,
    }
    hashes = {}
    for rel, blob in mapping.items():
        path = prefix / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        hashes[rel] = sha256_bytes(blob)
    return hashes


def list_commands(prefix: Path) -> list[str]:
    bin_dir = prefix / "bin"
    if not bin_dir.is_dir():
        return []
    return sorted(p.name for p in bin_dir.iterdir() if p.is_file())


def load_state(prefix: Path) -> dict | None:
    path = prefix / STATE_REL
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"unreadable": True, "path": STATE_REL}
    return doc


def inventory(prefix: Path) -> dict:
    files = {}
    for rel in USER_RELS:
        path = prefix / rel
        files[rel] = {
            "present": path.is_file(),
            "sha256": sha256_file(path) if path.is_file() else None,
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
    version = None
    vpath = prefix / VERSION_REL
    if vpath.is_file():
        version = vpath.read_text(encoding="utf-8").strip()
    return {
        "files": files,
        "commands": list_commands(prefix),
        "state": load_state(prefix),
        "version": version,
    }


def _run_script(prefix: Path, name: str) -> dict:
    script = prefix / "bin" / name
    if not script.is_file():
        return {
            "command": name,
            "present": False,
            "ok": False,
            "rc": 127,
            "stdout": "",
            "stderr": "missing",
        }
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=str(prefix),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return {
        "command": name,
        "present": True,
        "ok": p.returncode == 0 and "OK" in (p.stdout or ""),
        "rc": p.returncode,
        "stdout": (p.stdout or "").strip(),
        "stderr": (p.stderr or "").strip()[-500:],
    }


def golden_journeys(prefix: Path) -> dict:
    rows = [
        _run_script(prefix, "ast-journey"),
        _run_script(prefix, "ast-n1-only"),
    ]
    journey_out = prefix / "var" / "journey-out.json"
    post = None
    if journey_out.is_file():
        try:
            post = json.loads(journey_out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            post = {"unreadable": True}
    n_only_present = (prefix / "bin" / "ast-n-only").is_file()
    all_ok = all(r["ok"] for r in rows) and isinstance(post, dict) and post.get("ok") is True
    return {
        "pass": bool(all_ok),
        "rows": rows,
        "journey_out": post,
        "n_only_command_present": n_only_present,
    }


def install_n1(zip_path: Path, prefix: Path, packages: dict) -> None:
    if prefix.exists():
        shutil.rmtree(prefix)
    prefix.mkdir(parents=True, exist_ok=True)
    names = extract_package(zip_path, prefix)
    (prefix / INSTALLED_LIST).write_text(
        json.dumps(names, indent=2) + "\n", encoding="utf-8"
    )
    man = dict(packages["manifest"])
    (prefix / MANIFEST_REL).write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha = sha256_file(zip_path)
    recorded = man["n_minus_1"]["sha256"]
    if live_sha != recorded:
        raise RuntimeError("n-1-hash-mismatch-before-install")


def upgrade_to_n(zip_path: Path, prefix: Path) -> None:
    names = extract_package(zip_path, prefix)
    (prefix / INSTALLED_LIST).write_text(
        json.dumps(names, indent=2) + "\n", encoding="utf-8"
    )
    state = {
        "schema_version": 2,
        "format": "n",
        "user_id": "adv-0119",
        "n_only_blob": "N-FORMAT-STATE-ADV-0119",
    }
    (prefix / STATE_REL).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (prefix / VERSION_REL).write_text(N_VERSION + "\n", encoding="utf-8")


def _package_names(zip_path: Path) -> set[str]:
    with ZipFile(zip_path, "r") as zf:
        return {
            i.filename.replace("\\", "/")
            for i in zf.infolist()
            if not i.is_dir()
        }


def rollback_honest(n1_zip: Path, prefix: Path, packages: dict) -> None:
    recorded = packages["manifest"]["n_minus_1"]["sha256"]
    live = sha256_file(n1_zip)
    if live != recorded:
        raise RuntimeError("n-1-unfetchable-or-hash-mismatch")
    n_names = set()
    listed = prefix / INSTALLED_LIST
    if listed.is_file():
        n_names = set(json.loads(listed.read_text(encoding="utf-8")))
    n1_names = _package_names(n1_zip)
    extract_package(n1_zip, prefix)
    for rel in sorted(n_names - n1_names):
        path = prefix / rel
        if path.is_file() and rel not in USER_RELS:
            path.unlink()
    (prefix / INSTALLED_LIST).write_text(
        json.dumps(sorted(n1_names), indent=2) + "\n", encoding="utf-8"
    )
    state = {
        "schema_version": 1,
        "format": "n-1",
        "user_id": "adv-0119",
    }
    (prefix / STATE_REL).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (prefix / VERSION_REL).write_text(N1_VERSION + "\n", encoding="utf-8")
    leftover = prefix / "var" / "n-only-ran.txt"
    if leftover.is_file():
        leftover.unlink()


def rollback_naive(n1_zip: Path, prefix: Path) -> None:
    """Restore N-1 bins/libs but leave N-format state and the N-only command."""
    state_path = prefix / STATE_REL
    saved_state = state_path.read_bytes() if state_path.is_file() else None
    n_only = prefix / "bin" / "ast-n-only"
    n_only_bytes = n_only.read_bytes() if n_only.is_file() else None
    extract_package(n1_zip, prefix)
    if saved_state is not None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_bytes(saved_state)
    if n_only_bytes is not None:
        n_only.parent.mkdir(parents=True, exist_ok=True)
        n_only.write_bytes(n_only_bytes)


def plant_n_format_state(prefix: Path) -> None:
    state = {
        "schema_version": 2,
        "format": "n",
        "user_id": "adv-0119",
        "n_only_blob": "PLANTED-LEFTOVER-N-FORMAT",
    }
    (prefix / STATE_REL).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_live_canary(outside: Path) -> Path:
    path = outside / CANARY_NAME
    path.write_text("do-not-touch-live-profile\n", encoding="utf-8")
    return path


def canary_intact(path: Path) -> bool:
    return (
        path.is_file()
        and path.read_text(encoding="utf-8") == "do-not-touch-live-profile\n"
    )


def diff_user_files(pre: dict, post: dict) -> dict:
    missing = []
    altered = []
    for rel in USER_RELS:
        a = (pre.get("files") or {}).get(rel) or {}
        b = (post.get("files") or {}).get(rel) or {}
        if a.get("present") and not b.get("present"):
            missing.append(rel)
        elif a.get("present") and b.get("present") and a.get("sha256") != b.get("sha256"):
            altered.append({"rel": rel, "pre": a.get("sha256"), "post": b.get("sha256")})
    pre_cmds = set(pre.get("commands") or [])
    post_cmds = set(post.get("commands") or [])
    missing_cmds = sorted(pre_cmds - post_cmds)
    leftover_cmds = sorted(post_cmds - pre_cmds)
    return {
        "missing_files": missing,
        "altered_files": altered,
        "missing_commands": missing_cmds,
        "leftover_commands": leftover_cmds,
        "user_byte_identical": not missing and not altered,
        "commands_restored": not missing_cmds,
        "no_n_only_leftover": "ast-n-only" not in leftover_cmds
        and "ast-n-only" not in post_cmds,
    }


def prefix_is_disposable(prefix: Path, tmp_root: Path) -> bool:
    try:
        prefix.resolve().relative_to(tmp_root.resolve())
        return True
    except ValueError:
        return False
