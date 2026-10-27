"""ADV-0021 Probe 2b: corrections + positive controls for the three detectors that were BROKEN in 2a.

2a defects being fixed here (disclosed, not hidden):
  * A2.bomb measured ratio 1:1 -- a bare zipfile.ZipInfo defaults to ZIP_STORED, so my "bomb"
    never compressed. The real packager sets info.compress_type explicitly (packager.py:136);
    my harness did not. => re-run with compress_type set.
  * H_lock crashed because MY harness still held the lock fd. The realistic Windows case is
    "holder process alive" vs "lock file orphaned". Both are measured here, via SUBPROCESS so
    the CLI's exit-code path is observed rather than the in-process exception.
  * Every absence-grep (A2/A3/C1/A4 static) had NO positive control. Each now proves the same
    matcher FINDS a known-present token in the same file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
PLUGIN = REPO / "platform" / "plugin"
sys.path.insert(0, str(REPO / "platform"))

from plugin import lifecycle  # noqa: E402
from plugin import packager  # noqa: E402
from plugin.errors import PluginError  # noqa: E402
from plugin.fsops import hash_bytes  # noqa: E402
from plugin.journal import Prefix  # noqa: E402

RESULTS: list[dict[str, object]] = []


def rec(cid: str, outcome: str, detail: str) -> None:
    RESULTS.append({"case": cid, "outcome": outcome, "detail": detail})
    print(f"[{cid}] {outcome} :: {detail}", flush=True)


def mk_manifest(version="1.0.0", targets=None, name="ast-integrate") -> dict:
    doc: dict = {
        "name": name, "version": version, "description": "probe package",
        "author": {"name": "probe"}, "license": "MIT",
        "compatibility": {"min_client": "1.0.0",
                          "platforms": ["windows", "macos", "linux"],
                          "shells": ["pwsh"], "schema_version": 1},
    }
    if targets is not None:
        doc["deploy"] = {"targets": targets}
    return doc


def mk_pkg(dest_zip: Path, *, manifest_doc: dict, files: dict[str, bytes]) -> Path:
    entries = [{"path": r, "sha256": hash_bytes(b), "bytes": len(b)} for r, b in sorted(files.items())]
    members = dict(files)
    members[".claude-plugin/plugin.json"] = (json.dumps(manifest_doc, indent=2, sort_keys=True) + "\n").encode()
    members["PLUGIN-INVENTORY.json"] = (json.dumps({"artifact": "plugin-inventory", "entries": entries},
                                                   indent=2, sort_keys=True) + "\n").encode()
    members["PLUGIN-ALLOWLIST.json"] = b'{"artifact":"plugin-allowlist"}\n'
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, blob in sorted(members.items()):
            i = zipfile.ZipInfo(filename=rel, date_time=(1980, 1, 1, 0, 0, 0))
            i.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(i, blob)
    return dest_zip


# ===================================================== FIX 1: a real zip bomb
def fix_zip_bomb(tmp: Path) -> None:
    payload = b"\x00" * (512 * 1024 * 1024)  # 512 MiB of zeros
    z = tmp / "bomb2.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        info = zipfile.ZipInfo(filename="bomb.bin", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED  # <-- the bug in probe 2a
        zf.writestr(info, payload)
    del payload
    zb = z.stat().st_size
    with zipfile.ZipFile(z) as zf:
        declared = zf.infolist()[0].file_size
    required = max(zb * 3, lifecycle.MIN_FREE_BYTES)
    rec("A2b.archive", "MEASURED",
        f"archive={zb}B declares uncompressed file_size={declared}B (ratio {declared/zb:.0f}:1); "
        f"lifecycle.preflight would require max({zb}*3, {lifecycle.MIN_FREE_BYTES}) = {required}B free")
    d = tmp / "out_bomb2"
    try:
        packager.unpack(z, d)
        on_disk = (d / "bomb.bin").stat().st_size
        rec("A2b.unpack", "BYPASSED",
            f"unpack wrote {on_disk}B from a {zb}B archive; expansion {on_disk/zb:.0f}x exceeds the "
            f"{required}B preflight budget by {on_disk - required}B; no ratio or size cap exists")
    except Exception as exc:  # noqa: BLE001
        rec("A2b.unpack", "BLOCKED", f"{type(exc).__name__}: {exc}")
    finally:
        import shutil as _sh
        _sh.rmtree(d, ignore_errors=True)
        z.unlink(missing_ok=True)


# ===================================================== FIX 2: absence-greps WITH positive controls
def fix_absence_controls() -> None:
    """Each absence claim must be paired with a token KNOWN to be present in the same corpus."""
    corpus = {m: (PLUGIN / m).read_text(encoding="utf-8") for m in
              ("packager.py", "lifecycle.py", "fsops.py", "cache.py", "deploy.py",
               "policy.py", "manifest.py", "proc.py")}

    def find(tokens, mods):
        return sorted(f"{m}:{t}" for m in mods for t in tokens if t in corpus[m])

    checks = [
        ("A2c", "uncompressed-size cap",
         ("file_size", "compress_size", "max_uncompressed", "decompress_limit"),
         ("packager.py", "lifecycle.py", "fsops.py", "cache.py"),
         ("ZIP_DEFLATED", "zipfile")),
        ("A3c", "publisher signature / pinned hash",
         ("signature", "gpg", "cosign", "minisign", "public_key", "pubkey", "expected_sha", "trust_anchor"),
         ("packager.py", "lifecycle.py", "manifest.py", "policy.py"),
         ("archive_sha256", "sha256")),
        ("C1c", "live-target allowlist / denylist policy",
         ("target_allowlist", "ALLOWED_TARGETS", "FORBIDDEN_TARGETS", "denylist"),
         ("deploy.py", "policy.py", "manifest.py"),
         ("deploy_targets", "safe_join")),
        ("A4c", "install-time content scan",
         ("scan_secrets", "classify_forbidden", "validate_package"),
         ("lifecycle.py", "packager.py"),
         ("_verify_staged", "content_hash")),
        ("B1c", "safe_join applied to the version directory",
         ("safe_join(self.versions", "safe_join(prefix.versions", "check_relpath(version"),
         ("lifecycle.py",),
         ("safe_join", "version_dir")),
    ]
    for cid, what, absent_toks, mods, control_toks in checks:
        hits = find(absent_toks, mods)
        ctrl = find(control_toks, mods)
        verdict = "ABSENT" if not hits else "PRESENT"
        detector = "PROVEN" if ctrl else "BROKEN-DETECTOR"
        rec(f"{cid}.absence", verdict, f"{what}: searched {list(mods)} for {list(absent_toks)} -> {hits or 'NO HITS'}")
        rec(f"{cid}.detector-control", detector,
            f"same matcher, same files, known-present tokens {list(control_toks)} -> {ctrl or 'NO HITS (matcher is inert!)'}")


# ===================================================== FIX 3: lock, measured via subprocess
def fix_lock(tmp: Path) -> None:
    pfx = Prefix(tmp / "pfx_lock2")
    pfx.root.mkdir(parents=True, exist_ok=True)
    pfx.ensure()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "platform")

    def cli(*args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "plugin.cli", *args],
                              capture_output=True, text=True, timeout=300, env=env, cwd=str(REPO))

    # (a) ORPHANED lock file (holder died, no open handle) -- fresh mtime, so NOT stale by policy
    pfx.lock.write_text("install pid=999999 at=9999999999\n", encoding="utf-8")
    age_note = "mtime is NOW, so stale_after=3600 would NOT consider it stale"
    cp = cli("health-check", "--prefix", str(pfx.root), "--clear-stale-lock")
    rec("E1b.orphan-clear", "BYPASSED" if not pfx.lock.exists() else "BLOCKED",
        f"--clear-stale-lock on a FRESH orphaned lock ({age_note}): exit={cp.returncode}; "
        f"lock_exists_after={pfx.lock.exists()}; stdout={cp.stdout.strip()[:120]!r}")

    # (b) holder process ALIVE and holding the OS handle
    holder = tmp / "holder.py"
    holder.write_text(
        "import sys, time\n"
        f"sys.path.insert(0, r'{REPO / 'platform'}')\n"
        "from pathlib import Path\n"
        "from plugin.journal import Prefix, PrefixLock\n"
        f"p = Prefix(Path(r'{pfx.root}'))\n"
        "lk = PrefixLock(p, op='install'); lk.__enter__()\n"
        "print('LOCKED', flush=True)\n"
        "time.sleep(25)\n", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(holder)], stdout=subprocess.PIPE, text=True, env=env)
    line = proc.stdout.readline().strip() if proc.stdout else ""
    rec("E1b.holder", "ALIVE", f"holder subprocess pid={proc.pid} says {line!r}; lock_exists={pfx.lock.exists()}")
    cp2 = cli("health-check", "--prefix", str(pfx.root), "--clear-stale-lock")
    stolen = not pfx.lock.exists()
    tail = (cp2.stderr or "").strip().splitlines()
    rec("E1b.steal-live", "BYPASSED" if stolen else "BLOCKED-BY-OS",
        f"exit={cp2.returncode}; lock_exists_after={pfx.lock.exists()}; "
        f"stderr_tail={tail[-1] if tail else '<none>'}")
    # is that failure CLASSIFIED by the taxonomy, or an unclassified traceback?
    classified = ("FAILED:" in (cp2.stdout or "")) or ("E_" in (cp2.stderr or ""))
    tb = "Traceback (most recent call last)" in (cp2.stderr or "")
    rec("E1b.classification", "UNCLASSIFIED-CRASH" if (tb and not classified) else "CLASSIFIED",
        f"exit={cp2.returncode} traceback_in_stderr={tb} taxonomy_code_present={classified}; "
        f"cli.main catches only PluginError/KeyboardInterrupt (cli.py:390-395)")
    try:
        proc.kill()
        proc.wait(timeout=20)
    except Exception:  # noqa: BLE001, S110
        pass


# ===================================================== FIX 4: state-tamper, cleaner probe
def fix_state_tamper(tmp: Path) -> None:
    """2a proved the traversal happened but died in relposix. Separate the two questions:
       (i) does an unvalidated active_version reach a manifest OUTSIDE the prefix? (arbitrary read)
       (ii) what terminal state does the operator see?"""
    pfx = Prefix(tmp / "pfx_state2")
    z = mk_pkg(tmp / "p.zip", manifest_doc=mk_manifest("1.0.0"), files={"skills/x.md": b"legit\n"})
    lifecycle.install(z, pfx, live_root=tmp / "live", deploy=False)
    outside = tmp / "OUTSIDE_TREE2"
    (outside / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (outside / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(mk_manifest("9.9.9", name="attacker-controlled-name"), indent=2), encoding="utf-8")
    rel = os.path.relpath(outside, pfx.versions).replace("\\", "/")
    doc = json.loads(pfx.installed.read_text(encoding="utf-8"))
    doc["active_version"] = rel
    pfx.installed.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # (i) arbitrary READ: does load_manifest parse the out-of-prefix file?
    from plugin.manifest import MANIFEST_RELPATH, load as load_manifest
    try:
        m = load_manifest(pfx.version_dir(rel) / MANIFEST_RELPATH)
        rec("D1b.arbitrary-read", "BYPASSED",
            f"version_dir({rel!r}) resolved OUTSIDE the prefix and its manifest parsed: "
            f"name={m.name!r} version={m.version!r}; no safe_join guards version_dir "
            f"(journal.py:81-82)")
    except PluginError as exc:
        rec("D1b.arbitrary-read", "BLOCKED", f"{exc.code}: {exc.detail}")

    # (ii) operator-visible terminal state, measured through the CLI
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "platform")
    cp = subprocess.run([sys.executable, "-m", "plugin.cli", "projection", "--prefix", str(pfx.root)],
                        capture_output=True, text=True, timeout=300, env=env, cwd=str(REPO))
    tb = "Traceback (most recent call last)" in (cp.stderr or "")
    rec("D1b.terminal-state", "UNCLASSIFIED-CRASH" if tb else "CLASSIFIED",
        f"`projection` on a tampered installed.json: exit={cp.returncode}; traceback={tb}; "
        f"stderr_tail={(cp.stderr or '').strip().splitlines()[-1] if (cp.stderr or '').strip() else '<none>'}")

    # control: with an UNtampered installed.json the same command must succeed
    pfx2 = Prefix(tmp / "pfx_state_ok")
    z2 = mk_pkg(tmp / "p2.zip",
                manifest_doc=mk_manifest("1.0.0", targets=[{"source": "skills", "target": "skills", "mode": "copy"}]),
                files={"skills/x.md": b"legit\n"})
    lifecycle.install(z2, pfx2, live_root=tmp / "live2", deploy=True)
    cp2 = subprocess.run([sys.executable, "-m", "plugin.cli", "projection", "--prefix", str(pfx2.root)],
                         capture_output=True, text=True, timeout=300, env=env, cwd=str(REPO))
    rec("D1b.control-good", "SILENT-AND-CORRECT" if cp2.returncode == 0 else "OVER-FIRES",
        f"untampered projection: exit={cp2.returncode}; stdout={cp2.stdout.strip()[:80]!r}")


# ===================================================== FIX 5: does the shipped test suite cover these?
def fix_test_coverage_of_findings() -> None:
    tests = {p.name: p.read_text(encoding="utf-8") for p in PLUGIN.glob("test_*.py")}
    probes = {
        "version-string traversal": ("1.0.0-..", "ADV0021", "version_dir(\"..", "prerelease"),
        "provenance live_path escape": ("../VICTIM", "live_path\": \"..", "..\", \"source_path"),
        "zip decompression bomb": ("file_size", "bomb", "decompress"),
        "package signature": ("signature", "cosign", "gpg"),
    }
    for what, toks in probes.items():
        hits = sorted(f"{n}:{t}" for n, txt in tests.items() for t in toks if t in txt)
        rec(f"T1.{what.replace(' ', '-')}", "UNTESTED" if not hits else "TESTED",
            f"searched {len(tests)} test files ({sorted(tests)}) -> {hits or 'NO HITS'}")
    # detector control: a token that IS in the suite
    ctrl = sorted(f"{n}" for n, txt in tests.items() if "diverged" in txt.lower())
    rec("T1.detector-control", "PROVEN" if ctrl else "BROKEN-DETECTOR",
        f"known-present token 'diverged' found in {ctrl or 'NOTHING (matcher inert!)'}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="adv0021b_"))
    print(f"TMPROOT={tmp}", flush=True)
    for name, fn, needs_tmp in [
        ("FIX1_zip_bomb", fix_zip_bomb, True),
        ("FIX2_absence_controls", fix_absence_controls, False),
        ("FIX3_lock", fix_lock, True),
        ("FIX4_state_tamper", fix_state_tamper, True),
        ("FIX5_test_coverage", fix_test_coverage_of_findings, False),
    ]:
        print(f"\n########## {name} ##########", flush=True)
        try:
            if needs_tmp:
                sub = tmp / name
                sub.mkdir(parents=True, exist_ok=True)
                fn(sub)
            else:
                fn()
        except Exception:  # noqa: BLE001
            tb = traceback.format_exc()
            rec(name, "HARNESS-ERROR", tb.strip().splitlines()[-1])
            print(tb, flush=True)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (tmp / "results.json")
    out.write_text(json.dumps({"tmproot": str(tmp), "results": RESULTS}, indent=2), encoding="utf-8")
    print(f"\nRESULTS_JSON={out}\nCASE_COUNT={len(RESULTS)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
