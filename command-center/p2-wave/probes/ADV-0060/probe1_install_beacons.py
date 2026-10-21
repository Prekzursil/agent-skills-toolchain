#!/usr/bin/env python
"""ADV-0060 named probe 1: install the fixture in a sandbox and check for the beacon
written by each vector.

Mechanism: per-vector FILESYSTEM beacon (stdout is not the execution oracle). A beacon
script is shipped inside the package through EVERY declared/plausible vector; if any
lifecycle phase (install / update / rollback / repair / uninstall) or any marketplace
gate executes it, the beacon file appears under <sandbox>/beacons/. A second instrument
(monkeypatched subprocess.run) records every external command the pipeline spawns, joined
to the phase that spawned it, so "no beacon" can be attributed (nothing ran) rather than
assumed.

Sandbox: a fresh temp directory OUTSIDE the repository; every install/update/uninstall
happens in it. No live network, no repo mutation.
"""

from __future__ import annotations

import json
import shutil
import subprocess as real_subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "platform"))
sys.path.insert(0, str(REPO / "platform" / "marketplace"))

from plugin import lifecycle, proc  # noqa: E402
from plugin.errors import PluginError  # noqa: E402
from plugin.journal import Prefix  # noqa: E402
from plugin.manifest import parse as parse_manifest  # noqa: E402
from plugin.packager import build_archive  # noqa: E402
from plugin.payload import AllowRule, collect  # noqa: E402

BEACON_TEXT = "adv0060-beacon\n"
VECTORS = [
    "lifecycle-preinstall",
    "lifecycle-postinstall",
    "lifecycle-uninstall",
    "postinstall-hook",
    "auto-load-config",
    "build-step",
    "command-entrypoint",
]

# --------------------------------------------------------------------------- trace

TRACE: list[dict[str, object]] = []
_PHASE = {"name": "outside-lifecycle"}
_REAL_RUN = real_subprocess.run


def _traced_run(argv, *a, **kw):  # noqa: ANN001, ANN002, ANN003
    try:
        argv_list = [str(x) for x in argv]
    except Exception:  # noqa: BLE001
        argv_list = ["<unstringifiable>"]
    TRACE.append({"phase": _PHASE["name"], "argv": argv_list})
    return _REAL_RUN(argv, *a, **kw)


real_subprocess.run = _traced_run


def _set_phase(name: str) -> None:
    _PHASE["name"] = name


def _beacons(beacon_dir: Path) -> list[str]:
    if not beacon_dir.exists():
        return []
    return sorted(p.name for p in beacon_dir.iterdir() if p.is_file())


def _beacon_script(beacon_dir: Path, vector: str) -> str:
    return (
        "import pathlib\n"
        f"p = pathlib.Path(r'{str(beacon_dir)}') / '{vector}.beacon'\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        "p.write_text('adv0060-beacon' + chr(10), encoding='utf-8')\n"
    )


# --------------------------------------------------------------------------- plugin fixture


def _manifest_dict(version: str, *, extra_root: dict | None = None) -> dict:
    d: dict = {
        "name": "beacon-fixture",
        "version": version,
        "description": "ADV-0060 fixture: ships beacon code through every plausible vector",
        "author": {"name": "adv0060-probe", "email": "nobody@example.invalid"},
        "license": "MIT",
        "compatibility": {"min_client": "1.0.0",
                          "platforms": ["windows", "macos", "linux"]},
        "interpreters": [{"id": "python3", "floor": "3.8.0", "required": True}],
        "entrypoints": [
            {
                "id": "greet",
                "kind": "command",
                "path": "scripts/greet.py",
                "interpreter": "python3",
                "args": [],
                "description": "beacon command",
            },
            {
                "id": "on-event",
                "kind": "hook",
                "path": "hooks/on_event.py",
                "interpreter": "python3",
                "args": [],
                "description": "beacon hook (automatic per policy)",
            },
            {
                "id": "helper",
                "kind": "script",
                "path": "scripts/helper.py",
                "interpreter": "python3",
                "args": [],
                "description": "beacon script",
            },
        ],
        "payload": {"max_bytes": 1048576, "max_files": 64},
    }
    if extra_root:
        d.update(extra_root)
    return d


def _parse_manifest_obj(d: dict):
    return parse_manifest(json.dumps(d, indent=2, sort_keys=True))


def _stage_plugin_fixture(stage: Path, version: str, beacon_dir: Path) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "scripts").mkdir(exist_ok=True)
    (stage / "hooks").mkdir(exist_ok=True)
    (stage / "config").mkdir(exist_ok=True)
    body = _beacon_script(beacon_dir, "placeholder")
    # every vector carries the same writer with its own name
    files = {
        "scripts/greet.py": _beacon_script(beacon_dir, "command-entrypoint"),
        "hooks/on_event.py": _beacon_script(beacon_dir, "postinstall-hook"),
        "scripts/helper.py": _beacon_script(beacon_dir, "lifecycle-postinstall"),
        "scripts/preinstall.py": _beacon_script(beacon_dir, "lifecycle-preinstall"),
        "scripts/uninstall.py": _beacon_script(beacon_dir, "lifecycle-uninstall"),
        "scripts/build.py": _beacon_script(beacon_dir, "build-step"),
        "config/auto-load.py": _beacon_script(beacon_dir, "auto-load-config"),
        "README.md": "fixture\n",
    }
    for rel, text in files.items():
        (stage / rel).write_text(text, encoding="utf-8", newline="\n")
    assert body  # noqa: S101


def _build_plugin_pkg(stage: Path, out: Path, version: str, beacon_dir: Path) -> Path:
    _stage_plugin_fixture(stage, version, beacon_dir)
    manifest = _parse_manifest_obj(_manifest_dict(version))
    rules = [AllowRule(glob=g, reason="adv0060 fixture") for g in
             ("scripts/*", "hooks/*", "config/*", "README.md")]
    payload = collect(stage, rules, budget_bytes=1048576, budget_files=64)
    allow_doc = {
        "artifact": "payload-allowlist",
        "policy": "deny-by-default",
        "rules": [{"glob": r.glob, "reason": r.reason} for r in rules],
        "budget": {"max_bytes": 1048576, "max_files": 64},
    }
    res = build_archive(payload, manifest, out / f"beacon-fixture-{version}.zip",
                        allowlist_doc=allow_doc)
    return res.archive


# --------------------------------------------------------------------------- marketplace fixture


def _build_marketplace_beacon_pkg(sources: Path, beacon_dir: Path) -> Path:
    src = sources / "beacon-skill-1.0.0"
    if src.exists():
        shutil.rmtree(src)
    src.mkdir(parents=True)
    payload = src / "payload"
    payload.mkdir()
    (payload / "LICENSE").write_text("MIT\n", encoding="utf-8")
    beacons = {
        "postinstall.py": "lifecycle-postinstall",
        "hooks/on-install.py": "postinstall-hook",
        "preinstall.py": "lifecycle-preinstall",
        "uninstall.py": "lifecycle-uninstall",
        "build.py": "build-step",
        "autoload.py": "auto-load-config",
        "greet.py": "command-entrypoint",
    }
    # __file__-RELATIVE markers: the marketplace secret scanner (SEC-2) rightly refuses
    # absolute local user paths, so this surface's beacon writes next to itself. If any
    # marketplace lifecycle step executed the file, `beacon-ran.marker` appears beside it.
    for rel, vector in beacons.items():
        f = payload / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            "import pathlib\n"
            "p = pathlib.Path(__file__).resolve().parent / 'beacon-ran.marker'\n"
            "p.write_text('" + vector + "' + chr(10), encoding='utf-8')\n",
            encoding="utf-8", newline="\n")
    (payload / "README.md").write_text("beacon fixture\n", encoding="utf-8")
    spec = {
        "name": "beacon-skill",
        "version": "1.0.0",
        "channel": "stable",
        "kind": "skill",
        "summary": "ADV-0060 beacon package for the marketplace surface",
        "description": "Ships beacon code through every plausible lifecycle vector.",
        "license": {"spdx": "MIT", "notice_required": False, "aggregate_verified": True},
        "permissions": ["fs:read:packages/beacon-skill/**"],
        "compatibility": {"platforms": ["any"],
                          "clients": [{"id": "claude-code", "range": ">=2.0.0"}]},
        "provenance": {
            "source": "https://fixture.invalid/beacon-skill",
            "source_revision": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "builder": "mkt-fixture/1.0.0",
            "reproducible": True,
        },
        "payload_files": sorted(["LICENSE", "README.md", *beacons.keys()]),
        "file_licenses": {rel: "MIT" for rel in
                          sorted(["LICENSE", "README.md", *beacons.keys()])},
        "categories": ["docs"],
        "tags": ["fixture", "beacon"],
        "tests": "python -c 'print(1)'",
    }
    (src / "package.json").write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return src


# --------------------------------------------------------------------------- main


def main() -> int:
    out_lines: list[str] = []
    say = out_lines.append

    sandbox = Path(tempfile.mkdtemp(prefix="adv0060-"))
    beacon_dir = sandbox / "beacons"
    say(f"PROBE-1-BEGIN:ADV-0060")
    say(f"mechanism=per-vector filesystem beacon; stdout is not the execution oracle")
    say(f"SANDBOX root={sandbox} disposable=true "
        f"inside_repo={str(sandbox).startswith(str(REPO))}")

    results: dict[str, object] = {
        "sandbox": str(sandbox),
        "vectors": VECTORS,
        "phases": {},
        "strict_field": {},
        "trace": TRACE,
        "controls": {},
        "marketplace": {},
    }
    rc = 0
    try:
        # ---------- CONTROL: beacon mechanism proven by running it directly once
        direct = sandbox / "direct-control.py"
        direct.write_text(_beacon_script(beacon_dir, "DIRECT-CONTROL"),
                          encoding="utf-8")
        _set_phase("control-direct-beacon")
        cp = proc.run([sys.executable, str(direct)])
        direct_ok = cp.ok and (beacon_dir / "DIRECT-CONTROL.beacon").is_file()
        say(f"CONTROL direct_beacon rc={cp.returncode} beacon={direct_ok}")
        results["controls"]["direct_beacon"] = {
            "rc": cp.returncode, "beacon_written": direct_ok,
        }
        (beacon_dir / "DIRECT-CONTROL.beacon").unlink()
        if not direct_ok:
            say("FAILED control: beacon mechanism does not work; probe is void")
            rc = 1

        # ---------- plugin surface: build fixture packages v1.0.0 / v1.0.1
        _set_phase("build-fixture")
        v1 = _build_plugin_pkg(sandbox / "stage-100", sandbox, "1.0.0", beacon_dir)
        v2 = _build_plugin_pkg(sandbox / "stage-101", sandbox, "1.0.1", beacon_dir)
        say(f"SUBJECT plugin_pkg_v1={v1.name} v2={v2.name}")

        prefix = Prefix(sandbox / "prefix")
        prefix.ensure()
        live = sandbox / "live"

        def phase(name: str, fn) -> None:  # noqa: ANN001
            _set_phase(name)
            before = _beacons(beacon_dir)
            err = None
            try:
                fn()
            except PluginError as exc:
                err = f"{exc.code}: {exc.detail[:120]}"
            except Exception as exc:  # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"[:160]
            after = _beacons(beacon_dir)
            new = [b for b in after if b not in before]
            results["phases"][name] = {"error": err, "new_beacons": new,
                                       "beacons_after": after}
            say(f"OP phase={name} ok={err is None} err={err} new_beacons={new}")
            for vector in VECTORS:
                present = (beacon_dir / f"{vector}.beacon").is_file()
                results["phases"][name].setdefault("vector_state", {})[vector] = present

        phase("install", lambda: lifecycle.install(v1, prefix, live_root=live))

        # ---------- explicit-invocation control (production exec wrapper)
        _set_phase("explicit-entrypoint-control")
        shipped = None
        for root in (live, prefix.root):
            hits = sorted(root.rglob("greet.py")) if root.exists() else []
            if hits:
                shipped = hits[0]
                break
        if shipped is not None:
            cp = proc.run([sys.executable, str(shipped)])
            explicit_beacon = (beacon_dir / "command-entrypoint.beacon").is_file()
            say(f"CONTROL explicit_entrypoint rc={cp.returncode} beacon={explicit_beacon} "
                f"path={shipped}")
            results["controls"]["explicit_entrypoint"] = {
                "rc": cp.returncode, "beacon_written": explicit_beacon,
                "path": str(shipped),
                "note": "explicit invocation via plugin.proc.run executed UNSANDBOXED on "
                        "this host; this is the policy's explicit-invocation surface",
            }
            (beacon_dir / "command-entrypoint.beacon").unlink()
        else:
            say("CONTROL explicit_entrypoint shipped greet.py not found in live/prefix")

        phase("update", lambda: lifecycle.update(v2, prefix, live_root=live))
        phase("rollback", lambda: lifecycle.rollback(prefix, live_root=live))
        phase("repair", lambda: lifecycle.repair(prefix, live_root=live))
        phase("uninstall",
              lambda: lifecycle.uninstall(prefix, live_root=live,
                                          user_data="retain"))

        # ---------- STRICT-FIELD: manifest parser vs lifecycle-script root fields
        _set_phase("strict-field-mutants")
        for field in ("preinstall", "postinstall", "uninstall", "build", "scripts",
                      "hooks", "lifecycle"):
            try:
                _parse_manifest_obj(
                    _manifest_dict("9.9.9", extra_root={field: "scripts/x.py"}))
                accepted = True
                err = ""
            except PluginError as exc:
                accepted = False
                err = f"{exc.code}: {exc.detail[:100]}"
            except Exception as exc:  # noqa: BLE001
                accepted = False
                err = f"{type(exc).__name__}: {exc}"[:120]
            results["strict_field"][field] = {"accepted": accepted, "error": err}
            say(f"STRICT-FIELD field={field} accepted={accepted} error={err[:110]}")

        # ---------- NEGATIVE CONTROL: detector both states
        _set_phase("negative-control")
        good_state = _beacons(beacon_dir)
        silent_on_good = good_state == []
        (beacon_dir / "NEG.beacon").write_text(BEACON_TEXT, encoding="utf-8")
        fired_on_bad = _beacons(beacon_dir) != []
        (beacon_dir / "NEG.beacon").unlink()
        silent_after_clear = _beacons(beacon_dir) == []
        results["controls"]["negative_control"] = {
            "silent_on_good_state": silent_on_good,
            "fired_on_bad_state": fired_on_bad,
            "silent_after_clear": silent_after_clear,
        }
        say(f"NEGATIVE-CONTROL silent_on_good={silent_on_good} fired_on_bad="
            f"{fired_on_bad} silent_after_clear={silent_after_clear}")

        # ---------- marketplace surface
        _set_phase("marketplace-fixture-build")
        from mkt import fixture as mkt_fixture  # noqa: PLC0415
        from mkt import install as mkt_install  # noqa: PLC0415
        from mkt import publish as mkt_publish  # noqa: PLC0415
        from mkt import registry as reg  # noqa: PLC0415

        work = sandbox / "mkt"
        built = mkt_fixture.build(work)
        rroot = built["registry_root"]
        policy = built["trust_policy"]
        results["marketplace"]["fixture_entries"] = [
            f"{e['name']}@{e['version']}" for e in built["index"]["entries"]]
        say(f"SUBJECT marketplace root={rroot} entries="
            f"{len(built['index']['entries'])}")

        pkg_dir = _build_marketplace_beacon_pkg(work / "sources", beacon_dir)
        license_basis = pkg_dir / "payload" / "LICENSE"
        pub = None
        pub_err = None
        _set_phase("marketplace-publish-beacon-pkg")
        secret, _pub_key = mkt_fixture.keys_for("pub:alpha-tools")
        try:
            pub = mkt_publish.publish_into(
                pkg_dir, rroot,
                secret_hex=secret,
                publisher_id="pub:alpha-tools",
                maintainer_secret_hex=built["root_secret_hex"],
                trust_policy=policy,
                governance=built["governance"],
                license_basis_path=license_basis,
            )
        except Exception as exc:  # noqa: BLE001
            pub_err = f"{type(exc).__name__}: {exc}"[:300]
        results["marketplace"]["publish_beacon_pkg"] = {
            "refused": pub is None, "refusal": pub_err,
            "entry": (pub.entry if pub is not None and hasattr(pub, "entry") else None),
        }
        say(f"OP surface=marketplace phase=publish ok={pub is not None} "
            f"refusal={pub_err}")

        before = _beacons(beacon_dir)
        if pub is not None:
            _set_phase("marketplace-install-beacon-pkg")
            inst_err = None
            try:
                installer = mkt_install.Installer(
                    rroot, work / "installed", policy, use_federation=False)
                receipt = installer.install("beacon-skill", "=1.0.0",
                                            channel="stable")
                gates = [g["gate"] for g in receipt.get("gates", [])]
                results["marketplace"]["install"] = {
                    "ok": True, "gates": gates,
                    "files_extracted": receipt.get("installed_files"),
                }
                say(f"OP surface=marketplace phase=install ok=true gates={len(gates)}")
            except Exception as exc:  # noqa: BLE001
                inst_err = f"{type(exc).__name__}: {exc}"[:300]
                results["marketplace"]["install"] = {"ok": False, "error": inst_err}
                say(f"OP surface=marketplace phase=install ok=false error={inst_err}")
        after = _beacons(beacon_dir)
        new_beacons = [b for b in after if b not in before]
        markers = sorted(str(m.relative_to(work)) for m in work.rglob("beacon-ran.marker"))
        results["marketplace"]["new_beacons_after_publish_install"] = new_beacons
        results["marketplace"]["beacon_ran_markers"] = markers
        say(f"VECTOR surface=marketplace beacons_after={after} new={new_beacons} "
            f"ran_markers={markers}")

        # control: the KNOWN-GOOD fixture package still installs through its gates, so a
        # refusal above cannot be read as "marketplace globally broken" (catalog control)
        _set_phase("marketplace-install-known-good")
        try:
            installer2 = mkt_install.Installer(
                rroot, work / "installed", policy, use_federation=False)
            rec = installer2.install("hello-skill", "=1.0.0", channel="stable")
            gates2 = [g["gate"] for g in rec.get("gates", [])]
            results["marketplace"]["known_good_install"] = {
                "ok": True, "gates": len(gates2)}
            say(f"CONTROL marketplace_known_good install=ok gates={len(gates2)}")
        except Exception as exc:  # noqa: BLE001
            results["marketplace"]["known_good_install"] = {
                "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
            say(f"CONTROL marketplace_known_good install=REFUSED "
                f"{type(exc).__name__}: {str(exc)[:120]}")

        # marketplace undeclared-payload refusal (both directions allowlist)
        _set_phase("marketplace-undeclared-payload")
        bad = work / "sources" / "beacon-skill-1.0.0-undeclared"
        shutil.copytree(pkg_dir, bad)
        (bad / "payload" / "undeclared.py").write_text(
            _beacon_script(beacon_dir, "marketplace-undeclared"), encoding="utf-8")
        und_err = None
        try:
            mkt_publish.publish(
                bad, rroot, secret_hex=secret, publisher_id="pub:alpha-tools",
                trust_policy=policy, governance=built["governance"],
                license_basis_path=bad / "payload" / "LICENSE")
        except Exception as exc:  # noqa: BLE001
            und_err = f"{type(exc).__name__}: {exc}"[:200]
        results["marketplace"]["undeclared_payload_publish"] = {
            "refused": und_err is not None, "refusal": und_err}
        say(f"STRICT-FIELD surface=marketplace undeclared_payload_refused="
            f"{und_err is not None} {und_err}")

        # ---------- summary
        shipped_beacons = sorted(
            b for b in _beacons(beacon_dir)
            if b.replace(".beacon", "") in VECTORS
        )
        results["shipped_code_beacons"] = len(shipped_beacons)
        lifecycle_cmds = [
            t for t in TRACE
            if t["phase"] not in ("outside-lifecycle", "control-direct-beacon",
                                  "explicit-entrypoint-control")
        ]
        results["lifecycle_external_commands"] = len(lifecycle_cmds)
        say(f"MEASURE shipped_code_beacons={len(shipped_beacons)} "
            f"lifecycle_external_commands={len(lifecycle_cmds)}")
        for t in lifecycle_cmds:
            say(f"TRACE phase={t['phase']} argv={' '.join(t['argv'])[:110]}")
        say("PROBE-1-COMPLETE:ADV-0060")
    except Exception:  # noqa: BLE001
        rc = 1
        say("PROBE-1-ERROR")
        say(traceback.format_exc()[-1800:])
    finally:
        real_subprocess.run = _REAL_RUN

    out_path = Path(__file__).resolve().parent / "probe1-results.json"
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    raw = Path(__file__).resolve().parent / "probe1-install-beacons.raw.txt"
    raw.write_text("\n".join(out_lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(out_lines))
    print(f"OUT={out_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
