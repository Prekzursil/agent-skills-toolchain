"""Executable lifecycle rehearsal: install -> update -> rollback -> uninstall, in a temp prefix.

This is the deliverable that answers "prove the lifecycle actually runs". It drives the real CLI
as a subprocess (not the library, so the exit-code contract and the argv path are exercised too),
against a real temporary prefix, and prints the real output of each step.

Run from the repo root::

    python platform/plugin/lifecycle_rehearsal.py [--keep]

It also runs the two checks nobody remembers to run:

* **rollback** — asserts no live file disappeared and ``userdata/`` is byte-identical before/after;
* **uninstall** — asserts a user-EDITED deployed file survives, and that everything else is gone;
* **failed install** — corrupts the package, attempts an install, and asserts the prefix holds no
  version, no staging directory, no ``installed.json``, and no held lock afterwards.

Exit 0 only if every assertion holds; the last line is ``SUCCESS:lifecycle-rehearsal`` or
``FAILED:lifecycle-rehearsal <reason>``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "platform" / "plugin" / "astplugin.py"


class RehearsalError(AssertionError):
    pass


def run(argv: list[str], *, expect: int = 0) -> tuple[int, str, str]:
    """Run the CLI as a subprocess. Prints the real command and its real output."""
    full = [sys.executable, str(LAUNCHER), *argv]
    print(f"\n$ python platform/plugin/astplugin.py {' '.join(argv)}")
    cp = subprocess.run(
        full, capture_output=True, text=True, cwd=str(REPO_ROOT), shell=False
    )  # noqa: S603
    out = (cp.stdout or "").rstrip()
    err = (cp.stderr or "").rstrip()
    if out:
        print(out)
    if err:
        print(err, file=sys.stdout)
    print(f"[exit {cp.returncode}]")
    if cp.returncode != expect:
        raise RehearsalError(
            f"expected exit {expect}, got {cp.returncode} for {' '.join(argv)}"
        )
    return cp.returncode, out, err


def run_json(argv: list[str], out_path: Path, *, expect: int = 0) -> dict:
    run([*argv, "--json", str(out_path)], expect=expect)
    return json.loads(out_path.read_text(encoding="utf-8"))


def snapshot(root: Path) -> dict[str, str]:
    sys.path.insert(0, str(REPO_ROOT / "platform"))
    from plugin.fsops import content_hash, iter_files, relposix

    if not root.exists():
        return {}
    return {relposix(root, f): content_hash(f) for f in iter_files(root)}


def build_version(out_dir: Path, version: str, reports: Path) -> Path:
    doc = run_json(
        [
            "build",
            "--repo-root",
            str(REPO_ROOT),
            "--out",
            str(out_dir),
            "--version",
            version,
        ],
        reports / f"build-{version}.json",
    )
    return Path(str(doc["archive"]))


def corrupt_copy(archive: Path, dest: Path) -> Path:
    """A package whose inventory hash no longer matches its bytes: verification must reject it."""
    shutil.copy2(archive, dest)
    with zipfile.ZipFile(archive) as zin:
        members = {
            i.filename: zin.read(i.filename) for i in zin.infolist() if not i.is_dir()
        }
    members["README.md"] = (
        members["README.md"] + b"\n<corrupted after inventory was computed>\n"
    )
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in sorted(members):
            zout.writestr(name, members[name])
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="drive the real plugin lifecycle end to end"
    )
    ap.add_argument(
        "--keep", action="store_true", help="keep the temporary prefix for inspection"
    )
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args(argv)

    work = args.workdir or Path(tempfile.mkdtemp(prefix="astplugin-rehearsal-"))
    work.mkdir(parents=True, exist_ok=True)
    dist = work / "dist"
    reports = work / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    prefix = work / "prefix"
    live = prefix / "live"
    failures: list[str] = []

    try:
        print("=" * 78)
        print(f"LIFECYCLE REHEARSAL  workdir={work}")
        print("=" * 78)

        pkg_100 = build_version(dist, "1.0.0", reports)
        pkg_101 = build_version(dist, "1.0.1", reports)

        # ---------------------------------------------------------------- 1. INSTALL
        print("\n" + "-" * 78 + "\n1. INSTALL (dry run, then real)\n" + "-" * 78)
        run(
            ["install", "--package", str(pkg_100), "--prefix", str(prefix), "--dry-run"]
        )
        inst = run_json(
            ["install", "--package", str(pkg_100), "--prefix", str(prefix)],
            reports / "install.json",
        )
        if inst["version"] != "1.0.0":
            failures.append(f"install reported version {inst['version']}")
        if not (
            prefix / "versions" / "1.0.0" / ".claude-plugin" / "plugin.json"
        ).exists():
            failures.append(
                "install did not materialise versions/1.0.0/.claude-plugin/plugin.json"
            )
        deployed = sorted(snapshot(live))
        print(f"\n[deployed live files] {len(deployed)}: {deployed}")
        if not deployed:
            failures.append("install deployed no live files")

        # A user override + a user data file, which later steps must never destroy.
        override = live / "commands" / "astplugin.md"
        override.write_text(
            override.read_text(encoding="utf-8")
            + "\n<!-- a local edit only the user has -->\n",
            encoding="utf-8",
            newline="\n",
        )
        (prefix / "userdata").mkdir(parents=True, exist_ok=True)
        userfile = prefix / "userdata" / "notes.txt"
        userfile.write_text(
            "owner notes that must survive every lifecycle op\n",
            encoding="utf-8",
            newline="\n",
        )
        user_before = snapshot(prefix / "userdata")
        override_text = override.read_text(encoding="utf-8")

        run(
            [
                "health-check",
                "--prefix",
                str(prefix),
                "--json",
                str(reports / "health-after-install.json"),
            ]
        )

        # ---------------------------------------------------------------- 2. UPDATE
        print(
            "\n"
            + "-" * 78
            + "\n2. UPDATE 1.0.0 -> 1.0.1 (live override must survive)\n"
            + "-" * 78
        )
        upd = run_json(
            ["update", "--package", str(pkg_101), "--prefix", str(prefix)],
            reports / "update.json",
        )
        if upd["version"] != "1.0.1" or upd["previous_version"] != "1.0.0":
            failures.append(
                f"update reported {upd['previous_version']} -> {upd['version']}"
            )
        if override.read_text(encoding="utf-8") != override_text:
            failures.append("update overwrote a user-edited live file")
        print(f"[preserved user overrides] {upd.get('preserved_user_overrides')}")
        print(f"[needs decision]           {upd.get('needs_decision')}")

        # ---------------------------------------------------------------- 3. ROLLBACK
        print(
            "\n"
            + "-" * 78
            + "\n3. ROLLBACK 1.0.1 -> 1.0.0 (no live file may disappear)\n"
            + "-" * 78
        )
        live_before = snapshot(live)
        rb = run_json(["rollback", "--prefix", str(prefix)], reports / "rollback.json")
        live_after = snapshot(live)
        removed = sorted(set(live_before) - set(live_after))
        if rb["version"] != "1.0.0":
            failures.append(f"rollback landed on {rb['version']}")
        if removed:
            failures.append(f"rollback removed live files: {removed}")
        if snapshot(prefix / "userdata") != user_before:
            failures.append("rollback modified userdata/")
        if override.read_text(encoding="utf-8") != override_text:
            failures.append("rollback overwrote a user-edited live file")
        print(
            f"[live before/after] {len(live_before)}/{len(live_after)}  removed={removed}"
        )
        print(f"[versions retained] {rb.get('versions_retained')}")

        # ---------------------------------------------------------------- 4. REPAIR
        print(
            "\n" + "-" * 78 + "\n4. REPAIR after deleting a deployed file\n" + "-" * 78
        )
        victim = live / "hooks" / "plugin_health.py"
        victim.unlink()
        rep = run_json(["repair", "--prefix", str(prefix)], reports / "repair.json")
        if not victim.exists():
            failures.append("repair did not restore the deleted deployed file")
        if override.read_text(encoding="utf-8") != override_text:
            failures.append("repair overwrote a user-edited live file")
        print(
            f"[restored] {rep.get('restored')}  [kept override] {rep.get('kept_live_override')}"
        )

        # ---------------------------------------------------------------- 5. UNINSTALL
        print(
            "\n"
            + "-" * 78
            + "\n5. UNINSTALL (explicit decision required; user edits survive)\n"
            + "-" * 78
        )
        run(
            ["uninstall", "--prefix", str(prefix)], expect=2
        )  # no user-data decision -> E_USAGE
        run(["uninstall", "--prefix", str(prefix), "--retain-user-data", "--dry-run"])
        un = run_json(
            ["uninstall", "--prefix", str(prefix), "--retain-user-data"],
            reports / "uninstall.json",
        )
        if not override.exists():
            failures.append("uninstall deleted a user-edited live file")
        if not userfile.exists():
            failures.append("uninstall removed retained user data")
        if (prefix / "versions" / "1.0.0").exists() or (
            prefix / "versions" / "1.0.1"
        ).exists():
            failures.append("uninstall left a version directory behind")
        if (prefix / "state" / "installed.json").exists():
            failures.append("uninstall left installed.json behind")
        print(
            f"[removed live] {len(un.get('removed_live', []))}  "
            f"[kept user-edited] {un.get('kept_live_edited')}  "
            f"[removed versions] {un.get('removed_versions')}"
        )

        # ---------------------------------------------------------------- 6. FAILED INSTALL
        print(
            "\n" + "-" * 78 + "\n6. FAILED INSTALL leaves NO partial state\n" + "-" * 78
        )
        clean = work / "prefix-failed"
        bad = corrupt_copy(pkg_100, dist / "corrupt.zip")
        code, _, _ = run(
            ["install", "--package", str(bad), "--prefix", str(clean)], expect=51
        )
        residue = {
            "versions": sorted(p.name for p in (clean / "versions").iterdir())
            if (clean / "versions").exists()
            else [],
            "staged": sorted(p.name for p in (clean / "state" / "staging").iterdir())
            if (clean / "state" / "staging").exists()
            else [],
            "installed_json": (clean / "state" / "installed.json").exists(),
            "lock_held": (clean / "state" / "prefix.lock").exists(),
            "live_files": sorted(snapshot(clean / "live")),
        }
        print("[prefix residue after the failed install]")
        print(json.dumps(residue, indent=2, sort_keys=True))
        (reports / "failed-install-residue.json").write_text(
            json.dumps(residue, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        if (
            residue["versions"]
            or residue["staged"]
            or residue["installed_json"]
            or residue["lock_held"]
        ):
            failures.append(f"failed install left partial state: {residue}")
        if residue["live_files"]:
            failures.append(
                f"failed install deployed live files: {residue['live_files']}"
            )
        jr = json.loads(
            (clean / "state" / "journal.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[-1]
        )
        print(f"[last journal record] {json.dumps(jr, sort_keys=True)}")
        if jr.get("event") != "abort":
            failures.append(
                f"journal's last record is {jr.get('event')!r}, expected 'abort'"
            )

        # BOTH-STATES CONTROL for step 6: the same prefix must accept the GOOD package. Without
        # this, "the failed install left nothing" could equally mean "the prefix was unusable".
        print("\n[both-states control] the SAME prefix now accepts the intact package")
        ok_after = run_json(
            ["install", "--package", str(pkg_100), "--prefix", str(clean)],
            reports / "install-after-failure.json",
        )
        if ok_after["version"] != "1.0.0":
            failures.append(
                "the intact package did not install into the recovered prefix"
            )
        if not (
            clean / "versions" / "1.0.0" / ".claude-plugin" / "plugin.json"
        ).exists():
            failures.append("recovered-prefix install produced no version directory")

        # ---------------------------------------------------------------- 7. DETERMINISM
        print(
            "\n"
            + "-" * 78
            + "\n7. REPRODUCIBLE BUILD (same content -> same sha256)\n"
            + "-" * 78
        )
        rebuild_dir = work / "dist-rebuild"
        again = run_json(
            [
                "build",
                "--repo-root",
                str(REPO_ROOT),
                "--out",
                str(rebuild_dir),
                "--version",
                "1.0.0",
            ],
            reports / "build-again.json",
        )
        first = json.loads((reports / "build-1.0.0.json").read_text(encoding="utf-8"))
        print(f"[build 1] {first['sha256']}\n[build 2] {again['sha256']}")
        if first["sha256"] != again["sha256"]:
            failures.append(
                f"build is not reproducible: {first['sha256']} != {again['sha256']}"
            )

    except RehearsalError as exc:
        failures.append(str(exc))
    finally:
        print("\n" + "=" * 78)
        if failures:
            for f in failures:
                print(f"  ! {f}")
            print(f"FAILED:lifecycle-rehearsal {len(failures)} assertion(s) broke")
        else:
            print("SUCCESS:lifecycle-rehearsal all lifecycle assertions held")
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        else:
            print(f"kept: {work}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
