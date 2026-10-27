#!/usr/bin/env python3
# REL-0006 downgrade drill (rebuilt 2026-10-25, shard16-wave2 resume).
# Self-contained fixture rehearsal, per the closing receipt's recorded design:
#   * a fixture release store holds n-1.zip plus ROLLBACK-MANIFEST.md carrying
#     the recorded sha256 of n-1.zip;
#   * the retrievability precondition fetches n-1.zip and requires sha equality
#     BEFORE any downgrade starts; a corrupted control copy must be refused;
#   * the canary installs a candidate whose acceptance probe emits
#     BEHAVIOR:n-candidate (installed state N), the downgrade restores the n-1
#     package whose probe emits BEHAVIOR:n-1-accept;
#   * the version file is deliberately DISQUALIFIED as an acceptance signal
#     (T2): before the downgrade the version file can read n-1 while behaviour
#     is still the candidate;
#   * MTTR = wall-clock from retrievability-gate-begin to N-1 acceptance pass,
#     time.perf_counter_ns + time.time_ns, SLO 30.0s; a tiny-SLO control
#     (1e-12) must REJECT the same measurement (negative control);
#   * isolation: the canary HOME is a temp dir; the owner profile is never
#     touched (isolation control rejects the owner home).
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

SLO_SECONDS = 30.0
TINY_SLO_SECONDS = 1e-12


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def make_package(version, behavior):
    buf = tempfile.mkdtemp(prefix="rel0006-pkg-")
    plugin = Path(buf) / "plugin"
    (plugin / "hooks").mkdir(parents=True)
    (plugin / "VERSION").write_text(version + "\n", encoding="utf-8")
    (plugin / "hooks" / "on_session.py").write_text(
        "#!/usr/bin/env python3\n"
        "print(" + json.dumps("BEHAVIOR:" + behavior) + ")\n",
        encoding="utf-8", newline="\n")
    return plugin


def zip_dir(src: Path, dest: Path, prefix: str = ""):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                arc = (prefix + "/" + p.relative_to(src).as_posix()) if prefix else p.relative_to(src).as_posix()
                z.write(p, arc)


def build_store(store: Path):
    """Fixture release store: n-1.zip + ROLLBACK-MANIFEST.md with its sha."""
    plugin = make_package("1.0.0-n-1", "n-1-accept")
    store.mkdir(parents=True, exist_ok=True)
    zpath = store / "n-1.zip"
    zip_dir(plugin, zpath, prefix="plugin")
    shutil.rmtree(plugin, ignore_errors=True)
    sha = sha256_file(zpath)
    (store / "ROLLBACK-MANIFEST.md").write_text(
        "# ROLLBACK-MANIFEST (fixture)\n\n"
        "| artifact | sha256 |\n|---|---|\n"
        "| n-1.zip | " + sha + " |\n",
        encoding="utf-8", newline="\n")
    return sha


def parse_manifest_sha(store: Path):
    text = (store / "ROLLBACK-MANIFEST.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| n-1.zip |"):
            return line.split("|")[2].strip()
    raise SystemExit("manifest row missing")


def fetch_and_check(store: Path, workdir: Path, corrupt=False):
    """Fetch n-1.zip (or a corrupted control) and check sha against the manifest."""
    src = store / "n-1.zip"
    dst = workdir / "n-1.zip"
    dst.write_bytes(src.read_bytes())
    if corrupt:
        data = dst.read_bytes()
        dst.write_bytes(data[:-3] + bytes([data[-3] ^ 0xFF]) + data[-2:])
    fetched = sha256_file(dst)
    recorded = parse_manifest_sha(store)
    return {"fetched_sha256": fetched, "manifest_sha256": recorded,
            "match": fetched == recorded}


def run_acceptance(home: Path):
    """The N-1 acceptance probe: run the installed hook, observe behaviour."""
    plugin = home / "plugin"
    cmd = [sys_executable(), "-B", str(plugin / "hooks" / "on_session.py")]
    import subprocess
    env = dict(os.environ)
    env["PYTHONHOME"] = ""
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = (p.stdout or "").strip().splitlines()
    output = out[-1] if out else ""
    return {"passed": output == "BEHAVIOR:n-1-accept", "output": output,
            "command": cmd[0] + " -B " + str(plugin / "hooks" / "on_session.py")}


def sys_executable():
    import sys
    return sys.executable


def install(home: Path, zpath: Path):
    if home.exists():
        shutil.rmtree(home)
    home.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(home)


def write_version_disqualified_marker(home: Path, version_text):
    """T2 support: the version FILE may be flipped without touching behaviour."""
    (home / "plugin" / "VERSION").write_text(version_text + "\n", encoding="utf-8")


def zip_dir_to_path(src, dest, prefix="plugin"):
    """Zip a package dir to an explicit path (probe-owned store/candidate)."""
    zip_dir(src, dest, prefix=prefix)
    return dest


SLO_SECONDS = SLO_SECONDS  # re-export clarity
TINY_SLO_SECONDS = TINY_SLO_SECONDS
