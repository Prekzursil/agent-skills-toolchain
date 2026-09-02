#!/usr/bin/env python3
"""Isolated fixtures and live measurements for WFA-0056."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard as G  # noqa: E402

LEGIT_PY = (
    "import json\n"
    "import hashlib\n"
    "try:\n"
    "    import pydantic\n"
    "except ImportError:\n"
    "    pydantic = None\n"
    "import urllib.request as _req  # legitimate library, not a control plane\n"
)
LEGIT_REQ = "pydantic>=2.0\nhttpx>=0.27\njsonschema>=4.0\n"
ALLOWLIST_PRECEDENT = {
    "version": 1,
    "entries": [
        {
            "runtime_id": "prefect",
            "approval_id": "OWNER-APPROVAL-WFA-0056-PRECEDENT",
            "approver": "owner",
            "recorded_at": "2026-08-24T00:00:00Z",
            "scope": "expressibility-test-only",
            "rationale": (
                "Owner-approved runtime adoption must be an explicit allowlist "
                "entry with the approval recorded; this precedent exercises that path."
            ),
        }
    ],
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def plant_legit(root: Path) -> Path:
    _write(root / "app.py", LEGIT_PY)
    _write(root / "requirements.txt", LEGIT_REQ)
    _write(root / "lib" / "helpers.py", "import json\nimport pathlib\n")
    return root


def plant_import(root: Path, runtime_id: str, how: str = "from") -> Path:
    rt = G.runtime_by_id(runtime_id)
    prefix = rt["import_prefixes"][0]
    if how == "from":
        src = f"from {prefix}.runtime import Engine  # planted WFA-0056\n"
    elif how == "import":
        src = f"import {prefix}  # planted WFA-0056\n"
    elif how == "importlib":
        src = (
            "import importlib\n"
            f"importlib.import_module({prefix!r})  # planted WFA-0056\n"
        )
    else:
        raise ValueError(how)
    _write(root / "acquired.py", src)
    _write(root / "requirements.txt", LEGIT_REQ)
    return root


def plant_manifest(root: Path, runtime_id: str) -> Path:
    rt = G.runtime_by_id(runtime_id)
    pkg = rt["pypi"][0]
    _write(root / "app.py", LEGIT_PY)
    _write(root / "requirements.txt", LEGIT_REQ + f"{pkg}==0.0.0-plant\n")
    return root


def plant_vendored(root: Path, runtime_id: str) -> Path:
    rt = G.runtime_by_id(runtime_id)
    pkg_dir = root / "vendor" / rt["import_prefixes"][0]
    _write(pkg_dir / "__init__.py", "# vendored torn-down runtime; not declared\n")
    _write(root / "app.py", LEGIT_PY)
    _write(root / "requirements.txt", LEGIT_REQ)
    return root


def plant_spawn_source(root: Path, runtime_id: str) -> Path:
    rt = G.runtime_by_id(runtime_id)
    bin_name = rt["process_names"][0]
    _write(
        root / "launcher.py",
        "import subprocess\n"
        f"subprocess.Popen([{bin_name!r}, 'scheduler'])  # planted spawn\n",
    )
    _write(root / "requirements.txt", LEGIT_REQ)
    return root


class PlantedProcess:
    """Spawn a dummy process whose argv0 basename is a torn-down runtime."""

    def __init__(self, runtime_id: str) -> None:
        self.runtime_id = runtime_id
        self.proc: subprocess.Popen | None = None
        self.tmpdir: tempfile.TemporaryDirectory | None = None
        self.pid: int | None = None

    def __enter__(self) -> "PlantedProcess":
        rt = G.runtime_by_id(self.runtime_id)
        bin_name = rt["process_names"][0]
        self.tmpdir = tempfile.TemporaryDirectory(prefix="wfa-0056-proc-")
        tmp = Path(self.tmpdir.name)
        script = tmp / "sleeper.py"
        script.write_text(
            "import time\n"
            "time.sleep(120)\n",
            encoding="utf-8",
        )
        fake = tmp / bin_name
        payload = (
            "#!/usr/bin/env python3\n"
            + script.read_text(encoding="utf-8")
        )
        fake.write_text(payload, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        # Invoke through the interpreter so /proc cmdline is stable
        # (python3 <script-named-airflow> ...) rather than racing /usr/bin/env.
        self.proc = subprocess.Popen(
            [sys.executable, str(fake), "--wfa-0056-plant", self.runtime_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.pid = self.proc.pid
        deadline = time.time() + 2.0
        while time.time() < deadline:
            cmd_path = Path(f"/proc/{self.pid}/cmdline")
            try:
                raw = cmd_path.read_bytes()
            except OSError:
                time.sleep(0.02)
                continue
            if bin_name.encode("utf-8") in raw:
                break
            time.sleep(0.02)
        return self

    def __exit__(self, *exc: object) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
        if self.tmpdir is not None:
            self.tmpdir.cleanup()


def evidence_a() -> dict:
    """Planted import of each of the seven torn-down runtimes."""
    rows = []
    with tempfile.TemporaryDirectory(prefix="wfa-0056-a-") as raw:
        root = Path(raw)
        legit = plant_legit(root / "legit")
        good = G.evaluate(legit)
        if good.fired:
            return {
                "pass": False,
                "reason": "legit-library-not-silent",
                "good": good.as_dict(),
            }
        hows = ["from", "import", "importlib"]
        for i, runtime_id in enumerate(G.runtime_ids()):
            target = plant_import(root / runtime_id, runtime_id, how=hows[i % 3])
            bad = G.evaluate(target)
            named = bad.named_planes
            rt = G.runtime_by_id(runtime_id)
            ok = (
                bad.fired
                and rt["name"] in named
                and all(f.runtime_id == runtime_id for f in bad.findings if not f.allowlisted)
            )
            rows.append(
                {
                    "runtime_id": runtime_id,
                    "control_plane": rt["name"],
                    "fired": bad.fired,
                    "named_planes": named,
                    "names_which": rt["name"] in named,
                    "pass": ok,
                    "findings": [f.as_dict() for f in bad.findings],
                }
            )
        allow_root = plant_import(root / "allow-prefect", "prefect", how="import")
        denied = G.evaluate(allow_root)
        allowed = G.evaluate(allow_root, allowlist=ALLOWLIST_PRECEDENT)
        allow_ok = (
            denied.fired
            and "Prefect" in denied.named_planes
            and (not allowed.fired)
            and "Prefect" in allowed.named_planes
            and allowed.allowlist_hits
            and allowed.allowlist_hits[0]["approval_id"]
            == "OWNER-APPROVAL-WFA-0056-PRECEDENT"
        )
        all_seven = all(r["pass"] for r in rows) and len(rows) == 7
        return {
            "pass": bool(all_seven and (not good.fired) and allow_ok),
            "legit_silent": (not good.fired),
            "legit_named_planes": good.named_planes,
            "planted": rows,
            "seven_named": all_seven,
            "allowlist": {
                "denied_fired": denied.fired,
                "denied_named": denied.named_planes,
                "allowed_fired": allowed.fired,
                "allowed_named": allowed.named_planes,
                "approval_recorded": allowed.allowlist_hits,
                "pass": allow_ok,
            },
        }


def evidence_b() -> dict:
    """Manifest diff + vendored-without-declare + live process-table observation."""
    with tempfile.TemporaryDirectory(prefix="wfa-0056-b-") as raw:
        root = Path(raw)
        baseline = plant_legit(root / "baseline")
        silent = G.evaluate(root / "empty-app", baseline=baseline)
        # empty missing dir: treat as silent by using legit as target too
        silent = G.evaluate(baseline, baseline=baseline)

        manifest_rows = []
        for runtime_id in G.runtime_ids():
            target = plant_manifest(root / f"man-{runtime_id}", runtime_id)
            result = G.evaluate(target, baseline=baseline)
            rt = G.runtime_by_id(runtime_id)
            channels = {f.channel for f in result.findings}
            ok = result.fired and rt["name"] in result.named_planes and "manifest" in channels
            manifest_rows.append(
                {
                    "runtime_id": runtime_id,
                    "control_plane": rt["name"],
                    "fired": result.fired,
                    "named_planes": result.named_planes,
                    "channels": sorted(channels),
                    "pass": ok,
                }
            )

        vendored = plant_vendored(root / "vendored-langgraph", "langgraph")
        vres = G.evaluate(vendored, baseline=baseline)
        vendor_ok = (
            vres.fired
            and "LangGraph" in vres.named_planes
            and any(f.channel == "vendored" for f in vres.findings)
            and not any(f.channel == "manifest" for f in vres.findings)
        )

        spawned_src = plant_spawn_source(root / "spawn-airflow", "airflow")
        sres = G.evaluate(spawned_src, baseline=baseline)
        spawn_src_ok = (
            sres.fired
            and "Airflow" in sres.named_planes
            and any(f.channel == "subprocess_source" for f in sres.findings)
        )

        with PlantedProcess("airflow") as planted:
            pres = G.evaluate(
                baseline,
                baseline=baseline,
                observe_processes=True,
                restrict_pids={planted.pid} if planted.pid else None,
            )
            process_ok = (
                planted.pid is not None
                and pres.fired
                and "Airflow" in pres.named_planes
                and any(f.channel == "process_table" for f in pres.findings)
            )
            process_detail = pres.as_dict()

        # Control: same tree, no process observation, must stay silent.
        no_proc = G.evaluate(baseline, baseline=baseline, observe_processes=False)

        return {
            "pass": bool(
                silent.silent
                and all(r["pass"] for r in manifest_rows)
                and vendor_ok
                and spawn_src_ok
                and process_ok
                and no_proc.silent
            ),
            "baseline_silent": silent.silent,
            "manifest_diff": manifest_rows,
            "vendored": {
                "fired": vres.fired,
                "named_planes": vres.named_planes,
                "channels": sorted({f.channel for f in vres.findings}),
                "not_in_manifest": not any(f.channel == "manifest" for f in vres.findings),
                "pass": vendor_ok,
            },
            "subprocess_source": {
                "fired": sres.fired,
                "named_planes": sres.named_planes,
                "pass": spawn_src_ok,
            },
            "process_table": {
                "planted_runtime": "airflow",
                "planted_pid": planted.pid,
                "fired": pres.fired,
                "named_planes": pres.named_planes,
                "pass": process_ok,
                "detail": process_detail,
            },
            "observe_off_stays_silent": no_proc.silent,
        }


def both_states() -> dict:
    with tempfile.TemporaryDirectory(prefix="wfa-0056-both-") as raw:
        root = Path(raw)
        good = G.evaluate(plant_legit(root / "good"))
        bad = G.evaluate(plant_import(root / "bad", "crewai"))
        return {
            "silent_on_legitimate_library": (not good.fired),
            "loud_on_runtime_import": bad.fired,
            "named_on_bad": bad.named_planes,
            "names_which": "CrewAI" in bad.named_planes,
            "pass": (not good.fired) and bad.fired and ("CrewAI" in bad.named_planes),
        }


def write_example_allowlist() -> Path:
    path = HERE / "allowlist.example.json"
    path.write_text(
        json.dumps(ALLOWLIST_PRECEDENT, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    write_example_allowlist()
    a = evidence_a()
    b = evidence_b()
    both = both_states()
    print(json.dumps({"A": a["pass"], "B": b["pass"], "both": both["pass"]}, indent=2))
    raise SystemExit(0 if a["pass"] and b["pass"] and both["pass"] else 1)
