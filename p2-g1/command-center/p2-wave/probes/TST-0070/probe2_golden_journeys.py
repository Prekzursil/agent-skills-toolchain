#!/usr/bin/env python3
"""TST-0070 probe2: golden journeys against the INSTALLED payload.

Mechanically different from probe1 (which rebuilds and installs): this
runs the three stdlib-only journeys from the installed kit, enforces the
deterministic exists+parses+min-bytes postcondition on every journey
output, then proves both negative controls: a corrupted journey output
fails the postcondition, and hiding jsonschema makes
tools/plugin/exec_policy.validate_policy raise RuntimeError."""
from __future__ import annotations

import builtins
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0070"
UNIT = "TST-0070"
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def postcondition(path: Path, min_bytes: int = 256) -> dict:
    ok = path.exists() and path.stat().st_size >= min_bytes
    parses = False
    err = None
    if path.exists():
        try:
            json.loads(path.read_text(encoding="utf-8"))
            parses = True
        except Exception as exc:
            err = type(exc).__name__ + ": " + str(exc)[:80]
    return {"exists": path.exists(), "bytes": path.stat().st_size if path.exists() else 0,
            "parses": parses, "min_bytes": min_bytes, "ok": ok and parses, "parse_error": err}


def main() -> int:
    td = tempfile.mkdtemp(prefix="tst0070-p2-")
    try:
        profile = Path(td) / "empty-profile" / "site"
        profile.mkdir(parents=True)
        with tarfile.open(HERE / "kit_src.tgz", "w:gz") if False else tarfile.open(Path(td) / "art.tar.gz", "w:gz") as tf:
            for f in sorted((HERE / "kit").rglob("*")):
                if f.is_file():
                    tf.add(str(f), arcname="golden-kit/" + f.relative_to(HERE / "kit").as_posix())
        with tarfile.open(Path(td) / "art.tar.gz", "r:gz") as tf:
            tf.extractall(profile)
        kit = profile / "golden-kit"
        outd = Path(td) / "journey-out"
        outd.mkdir()
        results = {}
        for jname, outname in [("hook_fire.py", "journey-hook-fire.json"),
                               ("identity_manifest.py", "journey-identity-manifest.json"),
                               ("skill_checksum.py", "journey-skill-checksum.json")]:
            r = subprocess.run([sys.executable, "-B", str(kit / "journeys" / jname), str(kit), str(outd / outname)],
                               capture_output=True, text=True, timeout=60)
            pc = postcondition(outd / outname)
            results[jname] = {"rc": r.returncode, **pc}
            chk(r.returncode == 0 and pc["ok"], "journey:" + jname, (r.stderr or "")[:120] + " " + json.dumps(pc))
        chk(all(v["bytes"] >= 256 for v in results.values()), "all-journeys-min-bytes")
        # negative control 1: corrupted journey output fails the postcondition
        bad = outd / "journey-hook-fire.json"
        good_bytes = bad.read_bytes()
        bad.write_bytes(b"{")
        pc_bad = postcondition(bad)
        chk(pc_bad["ok"] is False and pc_bad["parses"] is False, "negative-corrupt-output-fails", json.dumps(pc_bad))
        bad.write_bytes(good_bytes)
        chk(postcondition(bad)["ok"] is True, "postcondition-green-again")
        # negative control 2: hiding jsonschema makes validate_policy raise RuntimeError
        chk(REPO.resolve() not in kit.parents, "installed-kit-not-source-tree")
        sys.path.insert(0, str(REPO / "tools" / "plugin"))
        import importlib
        import exec_policy
        importlib.reload(exec_policy)
        raised = ""
        real_jsonschema = exec_policy.jsonschema
        exec_policy.jsonschema = None  # the package does not vendor jsonschema
        try:
            exec_policy.validate_policy({"schema_version": 1})
        except RuntimeError as exc:
            raised = str(exc)
        finally:
            exec_policy.jsonschema = real_jsonschema
        chk("jsonschema is required" in raised, "missing-dep-detector", raised)
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe2 three golden journeys pass against the installed payload with exists+parses+min-bytes postconditions; corrupt-output control fires; hiding jsonschema raises 'jsonschema is required to validate exec policy' (RuntimeError)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
