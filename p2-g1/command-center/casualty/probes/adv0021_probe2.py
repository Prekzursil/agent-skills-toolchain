"""ADV-0021 Probe 2: EXECUTABLE bypass attempts against every claimed mitigation.

Each case is (id, boundary, stride, what-the-control-claims, bypass-attempt, both-states control).
Every case prints a machine-readable line so the artifact can quote raw output verbatim.

Run:  python adv0021_probe2.py
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
sys.path.insert(0, str(REPO / "platform"))

from plugin import deploy as deploy_mod  # noqa: E402
from plugin import lifecycle  # noqa: E402
from plugin import manifest as manifest_mod  # noqa: E402
from plugin import packager  # noqa: E402
from plugin.errors import PluginError  # noqa: E402
from plugin.fsops import content_hash, hash_bytes  # noqa: E402
from plugin.journal import Prefix, read_journal  # noqa: E402

RESULTS: list[dict[str, object]] = []


def rec(cid: str, outcome: str, detail: str) -> None:
    RESULTS.append({"case": cid, "outcome": outcome, "detail": detail})
    print(f"[{cid}] {outcome} :: {detail}", flush=True)


# --------------------------------------------------------------------- helpers


def mk_manifest(version: str = "1.0.0", targets=None, name: str = "ast-integrate") -> dict:
    doc: dict = {
        "name": name,
        "version": version,
        "description": "probe package",
        "author": {"name": "probe"},
        "license": "MIT",
        "compatibility": {
            "min_client": "1.0.0",
            "platforms": ["windows", "macos", "linux"],
            "shells": ["pwsh"],
            "schema_version": 1,
        },
    }
    if targets is not None:
        doc["deploy"] = {"targets": targets}
    return doc


def mk_pkg(dest_zip: Path, *, manifest_doc: dict, files: dict[str, bytes],
           break_inventory: bool = False, extra_members: dict[str, bytes] | None = None) -> Path:
    """Build a zip that lifecycle._verify_staged accepts (unless break_inventory)."""
    entries = []
    for rel, blob in sorted(files.items()):
        sha = hash_bytes(blob)
        if break_inventory:
            sha = "0" * 64
        entries.append({"path": rel, "sha256": sha, "bytes": len(blob)})
    inventory = {"artifact": "plugin-inventory", "entries": entries}
    members: dict[str, bytes] = dict(files)
    members[".claude-plugin/plugin.json"] = (
        json.dumps(manifest_doc, indent=2, sort_keys=True) + "\n").encode()
    members["PLUGIN-INVENTORY.json"] = (
        json.dumps(inventory, indent=2, sort_keys=True) + "\n").encode()
    members["PLUGIN-ALLOWLIST.json"] = b'{"artifact":"plugin-allowlist"}\n'
    for k, v in (extra_members or {}).items():
        members[k] = v
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, blob in sorted(members.items()):
            zf.writestr(zipfile.ZipInfo(filename=rel, date_time=(1980, 1, 1, 0, 0, 0)), blob)
    return dest_zip


def raw_zip(dest: Path, members: list[tuple[str, bytes]]) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, blob in members:
            zf.writestr(zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0)), blob)
    return dest


# ===================================================================== TB-1 unpack containment
def case_a_unpack_containment(tmp: Path) -> None:
    """TB-1 / Tampering+EoP: does packager.unpack refuse a crafted entry name?
    BOTH-STATES: bad names must RAISE; a benign name must SUCCEED."""
    bad_names = ["../evil.txt", "../../evil.txt", "/etc/evil", "C:/evil.txt",
                 "//server/share/evil", r"..\..\evil.txt", "nul", "sub/CON.txt",
                 "  ../pad.txt", "./../dotdot.txt"]
    for i, nm in enumerate(bad_names):
        z = raw_zip(tmp / f"bad{i}.zip", [(nm, b"pwned\n")])
        d = tmp / f"out_bad{i}"
        d.mkdir(parents=True, exist_ok=True)
        try:
            packager.unpack(z, d)
            escaped = sorted(str(p) for p in tmp.rglob("evil.txt")) + \
                      sorted(str(p) for p in tmp.rglob("pad.txt"))
            rec("A1." + str(i), "BYPASSED",
                f"unpack accepted member {nm!r}; escapees={escaped}")
        except PluginError as exc:
            rec("A1." + str(i), "BLOCKED", f"member {nm!r} -> {exc.code}: {exc.detail}")
        except Exception as exc:  # noqa: BLE001
            rec("A1." + str(i), "ERROR", f"member {nm!r} -> {type(exc).__name__}: {exc}")
    # good-state control: the detector must be SILENT on a benign member
    z = raw_zip(tmp / "good.zip", [("ok/file.txt", b"hello\n")])
    d = tmp / "out_good"
    try:
        written = packager.unpack(z, d)
        ok = (d / "ok" / "file.txt").read_bytes() == b"hello\n"
        rec("A1.control-good", "SILENT-AND-CORRECT" if ok else "WRONG",
            f"benign member extracted: written={written} content_ok={ok}")
    except Exception as exc:  # noqa: BLE001
        rec("A1.control-good", "OVER-FIRES", f"{type(exc).__name__}: {exc}")


# ===================================================================== TB-1 DoS / zip bomb
def case_b_zip_bomb(tmp: Path) -> None:
    """TB-1 / Denial of Service: is there ANY uncompressed-size or ratio cap?"""
    payload = b"\x00" * (64 * 1024 * 1024)  # 64 MiB of zeros
    z = raw_zip(tmp / "bomb.zip", [("bomb.bin", payload)])
    zbytes = z.stat().st_size
    # what preflight would demand, per lifecycle.preflight: max(need*3, MIN_FREE_BYTES)
    required = max(zbytes * 3, lifecycle.MIN_FREE_BYTES)
    d = tmp / "out_bomb"
    try:
        packager.unpack(z, d)
        on_disk = (d / "bomb.bin").stat().st_size
        ratio = on_disk / zbytes
        rec("A2.bomb", "BYPASSED",
            f"archive={zbytes}B expanded to {on_disk}B on disk (ratio {ratio:.0f}:1); "
            f"preflight would have required only {required}B free for this archive")
    except Exception as exc:  # noqa: BLE001
        rec("A2.bomb", "BLOCKED", f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        z.unlink(missing_ok=True)
    # static corroboration: does any install-path module consult the declared sizes?
    hits = []
    for mod in ("packager.py", "lifecycle.py", "fsops.py", "cache.py"):
        txt = (REPO / "platform" / "plugin" / mod).read_text(encoding="utf-8")
        for tok in ("file_size", "compress_size", "ratio", "max_uncompressed"):
            if tok in txt:
                hits.append(f"{mod}:{tok}")
    rec("A2.static", "NO-CAP" if not hits else "CAP-FOUND",
        f"tokens found in install path = {hits or 'NONE'}")


# ===================================================================== TB-1 integrity is self-referential
def case_c_self_referential_integrity(tmp: Path) -> None:
    """TB-1 / Spoofing+Tampering: the only integrity check is the inventory INSIDE the archive.
    BOTH-STATES: (bad) tamper payload WITHOUT fixing inventory -> must FAIL;
                 (attack) tamper payload AND fix inventory -> if it INSTALLS, the check is self-referential."""
    # state 1 (known-broken): inventory disagrees -> the detector must fire
    z1 = mk_pkg(tmp / "p_broken.zip", manifest_doc=mk_manifest("1.0.0"),
                files={"skills/x.md": b"legit\n"}, break_inventory=True)
    pfx1 = Prefix(tmp / "pfx_broken")
    try:
        lifecycle.install(z1, pfx1, live_root=tmp / "live_broken", deploy=False)
        rec("A3.control-bad", "DETECTOR-INERT", "install accepted a payload whose inventory hash was wrong")
    except PluginError as exc:
        rec("A3.control-bad", "FIRED", f"{exc.code}: {exc.detail}")
    # state 2 (attack): attacker rewrites BOTH the payload and the inventory it is checked against
    evil = b"import os\nos.system('calc')  # attacker-supplied\n"
    z2 = mk_pkg(tmp / "p_evil.zip", manifest_doc=mk_manifest("1.0.0"),
                files={"skills/x.md": b"legit\n", "hooks/pwn.py": evil})
    pfx2 = Prefix(tmp / "pfx_evil")
    try:
        res = lifecycle.install(z2, pfx2, live_root=tmp / "live_evil", deploy=False)
        landed = (pfx2.version_dir("1.0.0") / "hooks" / "pwn.py")
        rec("A3.attack", "BYPASSED",
            f"install ok={res.ok} version={res.version}; attacker file present={landed.exists()} "
            f"bytes={landed.stat().st_size if landed.exists() else 0}; "
            f"no publisher signature was required or checked")
    except PluginError as exc:
        rec("A3.attack", "BLOCKED", f"{exc.code}: {exc.detail}")
    # is the recorded archive sha ever COMPARED to an expected value?
    src = (REPO / "platform" / "plugin" / "lifecycle.py").read_text(encoding="utf-8")
    cmp_hits = [ln.strip() for ln in src.splitlines()
                if "archive_sha" in ln and ("==" in ln or "!=" in ln)]
    rec("A3.static", "RECORD-ONLY" if not cmp_hits else "COMPARED",
        f"lifecycle.py lines comparing archive_sha256: {cmp_hits or 'NONE'}")


# ===================================================================== TB-2 manifest version -> prefix layout
def case_d_version_traversal(tmp: Path) -> None:
    """TB-2 / Tampering+EoP: manifest.version flows into prefix.version_dir() with NO safe_join.
    SEMVER_RE allows an arbitrary prerelease suffix after '-'."""
    probe = "1.0.0-../../../../ADV0021_ESCAPE"
    try:
        parsed = manifest_mod.parse_semver(probe, where="probe")
        rec("B1.regex", "ACCEPTED", f"parse_semver({probe!r}) -> {parsed} (no path validation)")
    except PluginError as exc:
        rec("B1.regex", "REJECTED", f"{exc.code}: {exc.detail}")
        return
    pfx = Prefix(tmp / "deep" / "a" / "b" / "pfx")
    vd = pfx.version_dir(probe)
    resolved = Path(os.path.normpath(str(vd)))
    inside = str(resolved).startswith(str(Path(os.path.normpath(str(pfx.root)))) + os.sep)
    rec("B1.pathmath", "ESCAPES" if not inside else "CONTAINED",
        f"version_dir -> {vd} ; normpath -> {resolved} ; inside prefix={inside}")
    # now execute the real install and see where the version tree lands
    z = mk_pkg(tmp / "p_trav.zip", manifest_doc=mk_manifest(probe),
               files={"skills/x.md": b"legit\n"})
    try:
        res = lifecycle.install(z, pfx, live_root=tmp / "live_trav", deploy=False)
        landed = Path(str(res.detail.get("version_root")))
        outside = not str(Path(os.path.normpath(str(landed)))).startswith(
            str(Path(os.path.normpath(str(pfx.root)))) + os.sep)
        rec("B1.install", "BYPASSED" if outside else "CONTAINED",
            f"install ok={res.ok}; version_root={landed}; exists={landed.exists()}; "
            f"outside_prefix={outside}")
    except PluginError as exc:
        rec("B1.install", "BLOCKED", f"{exc.code}: {exc.detail}")
    except Exception as exc:  # noqa: BLE001
        rec("B1.install", "ERROR", f"{type(exc).__name__}: {exc}")
    # good-state control: a plain semver must stay inside
    pfx2 = Prefix(tmp / "pfx_plain")
    z2 = mk_pkg(tmp / "p_plain.zip", manifest_doc=mk_manifest("2.0.0"),
                files={"skills/x.md": b"legit\n"})
    res2 = lifecycle.install(z2, pfx2, live_root=tmp / "live_plain", deploy=False)
    vr = Path(str(res2.detail.get("version_root")))
    rec("B1.control-good", "CONTAINED" if str(vr).startswith(str(pfx2.root)) else "WRONG",
        f"plain version 2.0.0 -> {vr}")


# ===================================================================== TB-3 deploy target containment
def case_e_deploy_target(tmp: Path) -> None:
    """TB-3 / EoP: can a manifest deploy target write outside live_root? safe_join is the claimed control."""
    for i, tgt in enumerate(["../../../ADV0021_LIVE_ESCAPE", "/abs_escape", "C:/abs_escape"]):
        pfx = Prefix(tmp / f"pfx_dt{i}")
        live = tmp / f"live_dt{i}"
        z = mk_pkg(tmp / f"p_dt{i}.zip",
                   manifest_doc=mk_manifest("1.0.0",
                                            targets=[{"source": "skills", "target": tgt, "mode": "copy"}]),
                   files={"skills/x.md": b"payload\n"})
        try:
            res = lifecycle.install(z, pfx, live_root=live, deploy=True)
            esc = sorted(str(p) for p in tmp.rglob("ADV0021_LIVE_ESCAPE")) + \
                  sorted(str(p) for p in tmp.rglob("abs_escape"))
            rec(f"C1.{i}", "BYPASSED", f"target={tgt!r} deployed; written={res.detail.get('deploy')}; escapees={esc}")
        except PluginError as exc:
            rec(f"C1.{i}", "BLOCKED", f"target={tgt!r} -> {exc.code}: {exc.detail}")
        except Exception as exc:  # noqa: BLE001
            rec(f"C1.{i}", "ERROR", f"target={tgt!r} -> {type(exc).__name__}: {exc}")
    # good-state control: a benign target must actually deploy
    pfx = Prefix(tmp / "pfx_dtok")
    live = tmp / "live_dtok"
    z = mk_pkg(tmp / "p_dtok.zip",
               manifest_doc=mk_manifest("1.0.0",
                                        targets=[{"source": "skills", "target": "skills", "mode": "copy"}]),
               files={"skills/x.md": b"payload\n"})
    res = lifecycle.install(z, pfx, live_root=live, deploy=True)
    landed = live / "skills" / "x.md"
    rec("C1.control-good", "SILENT-AND-CORRECT" if landed.exists() else "WRONG",
        f"benign target deployed -> {landed} exists={landed.exists()}")
    # And: is there ANY policy restricting WHICH live paths a manifest may target?
    dep = (REPO / "platform" / "plugin" / "deploy.py").read_text(encoding="utf-8")
    pol = (REPO / "platform" / "plugin" / "policy.py").read_text(encoding="utf-8")
    man = (REPO / "platform" / "plugin" / "manifest.py").read_text(encoding="utf-8")
    toks = [t for t in ("target_allowlist", "ALLOWED_TARGETS", "forbid", "deny")
            if t in dep or t in pol or t in man]
    rec("C1.policy", "NO-TARGET-POLICY" if not toks else "POLICY-FOUND",
        f"allowlist/deny tokens across deploy.py+policy.py+manifest.py = {toks or 'NONE'}")


# ===================================================================== TB-4 state-file tamper
def case_f_installed_json_tamper(tmp: Path) -> None:
    """TB-4 / Tampering: read_installed() does no schema validation; active_version flows into version_dir."""
    pfx = Prefix(tmp / "pfx_state")
    z = mk_pkg(tmp / "p_state.zip", manifest_doc=mk_manifest("1.0.0"),
               files={"skills/x.md": b"legit\n"})
    lifecycle.install(z, pfx, live_root=tmp / "live_state", deploy=False)
    # plant an out-of-prefix version tree the tamper will point at
    outside = tmp / "OUTSIDE_TREE"
    (outside / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (outside / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(mk_manifest("9.9.9", targets=[{"source": "s", "target": "s", "mode": "copy"}]),
                   indent=2), encoding="utf-8")
    (outside / "s").mkdir(parents=True, exist_ok=True)
    (outside / "s" / "attacker.md").write_text("ATTACKER CONTENT\n", encoding="utf-8")
    rel = os.path.relpath(outside, pfx.versions).replace("\\", "/")
    doc = json.loads(pfx.installed.read_text(encoding="utf-8"))
    doc["active_version"] = rel
    pfx.installed.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    rec("D1.setup", "PLANTED", f"installed.json active_version set to {rel!r}")
    live = tmp / "live_state2"
    try:
        res = lifecycle.repair(pfx, live_root=live, dry_run=False)
        got = live / "s" / "attacker.md"
        rec("D1.repair", "BYPASSED" if got.exists() else "NO-EFFECT",
            f"repair read a manifest from OUTSIDE the prefix; restored={res.detail.get('restored')}; "
            f"attacker file deployed to live={got.exists()}")
    except PluginError as exc:
        rec("D1.repair", "BLOCKED", f"{exc.code}: {exc.detail}")
    except Exception as exc:  # noqa: BLE001
        rec("D1.repair", "ERROR", f"{type(exc).__name__}: {exc}")


# ===================================================================== TB-4 provenance tamper -> arbitrary unlink
def case_g_provenance_unlink(tmp: Path) -> None:
    """TB-4 / EoP+Tampering: lifecycle.uninstall joins provenance live_path with a RAW `lr / live_rel`
    (lifecycle.py:576) instead of safe_join, unlike deploy.classify which DOES use safe_join."""
    pfx = Prefix(tmp / "pfx_prov")
    z = mk_pkg(tmp / "p_prov.zip",
               manifest_doc=mk_manifest("1.0.0",
                                        targets=[{"source": "skills", "target": "skills", "mode": "copy"}]),
               files={"skills/x.md": b"legit\n"})
    live = tmp / "prov_live"
    lifecycle.install(z, pfx, live_root=live, deploy=True)
    victim = tmp / "VICTIM.txt"
    victim.write_text("precious owner data\n", encoding="utf-8")
    vhash = content_hash(victim)
    prov_path = pfx.state / deploy_mod.PROVENANCE_NAME
    doc = json.loads(prov_path.read_text(encoding="utf-8"))
    doc["records"].append({
        "live_path": "../VICTIM.txt", "source_path": "skills/x.md", "version": "1.0.0",
        "content_sha256": vhash, "deployed_at": 0.0, "mode": "copy",
    })
    doc["record_count"] = len(doc["records"])
    prov_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    rec("D2.setup", "PLANTED",
        f"provenance record live_path='../VICTIM.txt' sha256={vhash[:16]}... victim_exists={victim.exists()}")
    try:
        res = lifecycle.uninstall(pfx, live_root=live, user_data="retain", dry_run=False)
        rec("D2.uninstall", "BYPASSED" if not victim.exists() else "NO-EFFECT",
            f"removed_live={res.detail.get('removed_live')}; victim_still_exists={victim.exists()}")
    except PluginError as exc:
        rec("D2.uninstall", "BLOCKED", f"{exc.code}: {exc.detail}")
    except Exception as exc:  # noqa: BLE001
        rec("D2.uninstall", "ERROR", f"{type(exc).__name__}: {exc}")
    # good-state control: an untampered provenance must only remove files inside live/
    pfx2 = Prefix(tmp / "pfx_prov_ok")
    live2 = tmp / "prov_live_ok"
    z2 = mk_pkg(tmp / "p_prov_ok.zip",
                manifest_doc=mk_manifest("1.0.0",
                                         targets=[{"source": "skills", "target": "skills", "mode": "copy"}]),
                files={"skills/x.md": b"legit\n"})
    lifecycle.install(z2, pfx2, live_root=live2, deploy=True)
    bystander = tmp / "BYSTANDER.txt"
    bystander.write_text("untouched\n", encoding="utf-8")
    res2 = lifecycle.uninstall(pfx2, live_root=live2, user_data="retain", dry_run=False)
    rec("D2.control-good",
        "SILENT-AND-CORRECT" if bystander.exists() and not (live2 / "skills" / "x.md").exists() else "WRONG",
        f"untampered uninstall removed={res2.detail.get('removed_live')}; "
        f"bystander_outside_live_intact={bystander.exists()}")


# ===================================================================== TB-6 lock
def case_h_lock(tmp: Path) -> None:
    """TB-6 / DoS+Tampering: PrefixLock is O_CREAT|O_EXCL, but `health-check --clear-stale-lock`
    unlinks it with NO age check (cli.py:307-308)."""
    from plugin.journal import PrefixLock
    pfx = Prefix(tmp / "pfx_lock")
    pfx.root.mkdir(parents=True, exist_ok=True)
    pfx.ensure()
    # (a) concurrent-op detection must FIRE
    with PrefixLock(pfx, op="install"):
        try:
            with PrefixLock(pfx, op="update"):
                rec("E1.concurrent", "BYPASSED", "second lock acquired while the first was held")
        except PluginError as exc:
            rec("E1.concurrent", "BLOCKED", f"{exc.code}: {exc.detail}")
    # (b) good-state control: after release, the lock must be acquirable
    try:
        with PrefixLock(pfx, op="install"):
            pass
        rec("E1.control-good", "SILENT-AND-CORRECT", "lock re-acquired after release")
    except PluginError as exc:
        rec("E1.control-good", "OVER-FIRES", f"{exc.code}: {exc.detail}")
    # (c) bypass: --clear-stale-lock on a FRESH (non-stale) lock
    from plugin import cli as cli_mod
    lk = PrefixLock(pfx, op="install")
    lk.__enter__()
    held_before = pfx.lock.exists()
    code = cli_mod.main(["health-check", "--prefix", str(pfx.root), "--clear-stale-lock"])
    rec("E1.clear-stale", "BYPASSED" if held_before and not pfx.lock.exists() else "BLOCKED",
        f"lock_held_before={held_before}; lock_exists_after={pfx.lock.exists()}; cli_exit={code}; "
        f"no age check at cli.py:307-308")
    try:
        lk.__exit__()
    except Exception:  # noqa: BLE001, S110
        pass


# ===================================================================== TB-7 crash recovery containment
def case_i_recover_containment(tmp: Path) -> None:
    """TB-7 / EoP: recover() rmtrees journal-named dirs. The claimed control is
    `p.relative_to(prefix.root)` (journal.py:291-293). BOTH-STATES."""
    from plugin.journal import recover
    # known-BAD state: journal names a dir OUTSIDE the prefix -> control must keep it
    pfx = Prefix(tmp / "pfx_rec")
    pfx.root.mkdir(parents=True, exist_ok=True)
    pfx.ensure()
    outside = tmp / "REC_OUTSIDE"
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "keepme.txt").write_text("do not delete\n", encoding="utf-8")
    with open(pfx.journal, "ab") as fh:
        fh.write((json.dumps({"ts": 1, "event": "open", "op": "install", "txn": "deadbeef"}) + "\n").encode())
        fh.write((json.dumps({"ts": 2, "event": "step", "op": "install", "txn": "deadbeef",
                              "kind": "stage", "staged_dir": str(outside)}) + "\n").encode())
    out = recover(pfx)
    rec("F1.outside", "BLOCKED" if outside.exists() else "BYPASSED",
        f"recover() removed={out['removed']}; outside dir still exists={outside.exists()}")
    # known-GOOD (in-prefix) state: the SAME code must actually delete residue -> proves not inert
    inside = pfx.staging / "cafebabe"
    inside.mkdir(parents=True, exist_ok=True)
    (inside / "residue.txt").write_text("partial\n", encoding="utf-8")
    with open(pfx.journal, "ab") as fh:
        fh.write((json.dumps({"ts": 3, "event": "open", "op": "install", "txn": "cafebabe"}) + "\n").encode())
        fh.write((json.dumps({"ts": 4, "event": "step", "op": "install", "txn": "cafebabe",
                              "kind": "stage", "staged_dir": str(inside)}) + "\n").encode())
    out2 = recover(pfx)
    rec("F1.control-inside", "FIRED" if not inside.exists() else "DETECTOR-INERT",
        f"recover() removed={out2['removed']}; in-prefix residue exists={inside.exists()}")


# ===================================================================== TB-5 interpreter / PATH
def case_j_interpreter(tmp: Path) -> None:
    """TB-5 / EoP: check_interpreters() EXECUTES a PATH-resolved binary during install."""
    from plugin import proc
    # (a) command-string injection must be refused (argv-array-only rule)
    try:
        proc.run("echo hi && whoami")  # type: ignore[arg-type]
        rec("G1.argv", "BYPASSED", "proc.run accepted a command STRING")
    except PluginError as exc:
        rec("G1.argv", "BLOCKED", f"{exc.code}: {exc.detail}")
    # (b) is the interpreter resolved via PATH (hijackable) or pinned absolute?
    src = (REPO / "platform" / "plugin" / "proc.py").read_text(encoding="utf-8").splitlines()
    which_lines = [f"proc.py:{i+1}: {ln.strip()}" for i, ln in enumerate(src) if "shutil.which(" in ln]
    p = proc.probe_interpreter("python3")
    rec("G1.path", "PATH-RESOLVED", f"probe_interpreter('python3') executed {p.path!r}; "
        f"which() call sites = {which_lines}")
    # (c) does install actually execute it? (manifest declaring an interpreter)
    pfx = Prefix(tmp / "pfx_interp")
    doc = mk_manifest("1.0.0")
    doc["interpreters"] = [{"id": "python3", "floor": "3.10.0", "required": True}]
    z = mk_pkg(tmp / "p_interp.zip", manifest_doc=doc, files={"skills/x.md": b"legit\n"})
    try:
        res = lifecycle.install(z, pfx, live_root=tmp / "live_interp", deploy=False)
        rec("G1.exec-on-install", "EXECUTED",
            f"install probed interpreters -> {res.detail.get('interpreters')}")
    except PluginError as exc:
        rec("G1.exec-on-install", "BLOCKED", f"{exc.code}: {exc.detail}")
    # (d) the pwsh launch adapter's flags
    pw = proc.INTERPRETERS["pwsh"].exec_prefix
    rec("G1.pwsh", "POLICY-BYPASS" if "Bypass" in " ".join(pw) else "OK",
        f"pwsh exec_prefix = {list(pw)} (proc.py:83)")


# ===================================================================== TB-8 uninstall user-data gate
def case_k_userdata_gate(tmp: Path) -> None:
    """TB-8 / Tampering(destruction): uninstall must refuse without an explicit decision."""
    pfx = Prefix(tmp / "pfx_ud")
    z = mk_pkg(tmp / "p_ud.zip", manifest_doc=mk_manifest("1.0.0"), files={"skills/x.md": b"legit\n"})
    lifecycle.install(z, pfx, live_root=tmp / "live_ud", deploy=False)
    (pfx.userdata / "notes.txt").write_text("user notes\n", encoding="utf-8")
    try:
        lifecycle.uninstall(pfx, live_root=tmp / "live_ud", user_data=None, dry_run=False)
        rec("H1.gate", "BYPASSED", "uninstall proceeded with NO user-data decision")
    except PluginError as exc:
        rec("H1.gate", "BLOCKED", f"{exc.code}: {exc.detail}")
    # good-state control: with 'retain', userdata must survive
    res = lifecycle.uninstall(pfx, live_root=tmp / "live_ud", user_data="retain", dry_run=False)
    kept = (pfx.userdata / "notes.txt").exists()
    rec("H1.control-good", "SILENT-AND-CORRECT" if kept else "WRONG",
        f"retain kept userdata={kept}; result={res.detail.get('userdata_retained')}")


# ===================================================================== TB-1b install-time content scan
def case_l_install_time_scan(tmp: Path) -> None:
    """TB-1 / Info-disclosure + EoP: the secret scan and forbidden-class allowlist run at BUILD time.
    Does INSTALL of a third-party archive scan anything?"""
    lc = (REPO / "platform" / "plugin" / "lifecycle.py").read_text(encoding="utf-8")
    pk = (REPO / "platform" / "plugin" / "packager.py").read_text(encoding="utf-8")
    toks = [t for t in ("scan_secrets", "classify_forbidden", "validate_package", "collect(")
            if t in lc or t in pk]
    rec("A4.static", "NO-INSTALL-SCAN" if not toks else "SCAN-FOUND",
        f"install-path references to scanners = {toks or 'NONE'}")
    # executable: install an archive carrying a forbidden class + a credential-shaped string
    pfx = Prefix(tmp / "pfx_scan")
    files = {
        "skills/x.md": b"legit\n",
        ".git/config": b"[core]\n",
        "secrets.env": b'AWS_SECRET_ACCESS_KEY="AKIAIOSFODNN7EXAMPLEabcdefghijklmnopqrstuv"\n',
    }
    z = mk_pkg(tmp / "p_scan.zip", manifest_doc=mk_manifest("1.0.0"), files=files)
    try:
        res = lifecycle.install(z, pfx, live_root=tmp / "live_scan", deploy=False)
        got = sorted(str(p.relative_to(pfx.version_dir("1.0.0"))).replace("\\", "/")
                     for p in pfx.version_dir("1.0.0").rglob("*") if p.is_file())
        rec("A4.exec", "BYPASSED", f"install ok={res.ok}; landed files={got}")
    except PluginError as exc:
        rec("A4.exec", "BLOCKED", f"{exc.code}: {exc.detail}")
    # control: does the BUILD-time scanner actually fire on the same content?
    from plugin.payload import classify_forbidden, scan_secrets
    tf = tmp / "cred.env"
    tf.write_bytes(files["secrets.env"])
    fnd = scan_secrets(tf, "secrets.env")
    cls = classify_forbidden(".git/config")
    rec("A4.control-build", "FIRED" if (fnd or cls) else "DETECTOR-INERT",
        f"build-time scan_secrets -> {[(f.rule, f.severity) for f in fnd]}; "
        f"classify_forbidden('.git/config') -> {cls!r}")


# ===================================================================== main
def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="adv0021_"))
    print(f"TMPROOT={tmp}", flush=True)
    cases = [
        ("A_unpack_containment", case_a_unpack_containment),
        ("B_zip_bomb", case_b_zip_bomb),
        ("C_self_referential_integrity", case_c_self_referential_integrity),
        ("D_version_traversal", case_d_version_traversal),
        ("E_deploy_target", case_e_deploy_target),
        ("F_installed_json_tamper", case_f_installed_json_tamper),
        ("G_provenance_unlink", case_g_provenance_unlink),
        ("H_lock", case_h_lock),
        ("I_recover_containment", case_i_recover_containment),
        ("J_interpreter", case_j_interpreter),
        ("K_userdata_gate", case_k_userdata_gate),
        ("L_install_time_scan", case_l_install_time_scan),
    ]
    for name, fn in cases:
        print(f"\n########## {name} ##########", flush=True)
        sub = tmp / name
        sub.mkdir(parents=True, exist_ok=True)
        try:
            fn(sub)
        except Exception:  # noqa: BLE001
            tb = traceback.format_exc()
            rec(name, "HARNESS-ERROR", tb.strip().splitlines()[-1])
            print(tb, flush=True)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (tmp / "results.json")
    out.write_text(json.dumps({"tmproot": str(tmp), "results": RESULTS}, indent=2), encoding="utf-8")
    print(f"\nRESULTS_JSON={out}", flush=True)
    print(f"CASE_COUNT={len(RESULTS)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
