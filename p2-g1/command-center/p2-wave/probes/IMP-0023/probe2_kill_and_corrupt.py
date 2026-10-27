#!/usr/bin/env python3
"""IMP-0023 probe2: independent reviewer probe (kill mid-activate + corrupt stage).

Reviewer obligations (receipt reviewer block):
  * SIGKILL of the installer subprocess after verify and before the live swap
    leaves the live tree byte-identical to the previous generation (OLD).
  * A corrupted staged file makes verify refuse with code verify-digest and the
    live tree stays on the old generation (negative control, must fire).
  * Completing the upgrade reaches NEW; a half-copied tree classifies MIXED.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.install import (  # noqa: E402
    InstallError,
    classify_live_state,
    install_plugin,
    live_file_census,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write_tree(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
    return root


def projection_for(payload: Path, plugin_id: str = "demo-plugin") -> dict:
    entries = []
    for path in sorted(payload.rglob("*")):
        if path.is_file():
            rel = path.relative_to(payload).as_posix()
            entries.append({"source": rel, "live": rel, "sha256": sha(path)})
    return {"plugin_id": plugin_id, "entries": entries}


V1 = {
    "skills/alpha/SKILL.md": "# alpha v1\nbody-one\n",
    "hooks/post.py": "print('v1')\n",
}
V2 = {
    "skills/alpha/SKILL.md": "# alpha v2\nbody-two\n",
    "hooks/post.py": "print('v2')\n",
    "skills/beta/SKILL.md": "# beta\n",
}


def child_script() -> str:
    return (
        "import os, sys, time\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, os.environ['TOOLS'])\n"
        "from plugin.install import install_plugin\n"
        "def after_stage(staging):\n"
        "    p = Path(os.environ['IMP0023_PAUSE'])\n"
        "    while p.is_file():\n"
        "        time.sleep(0.02)\n"
        "home = Path(os.environ['HOME_DIR'])\n"
        "payload = Path(os.environ['PAYLOAD_DIR'])\n"
        "import json\n"
        "projection = json.loads(os.environ['PROJECTION'])\n"
        "install_plugin(home=home, payload=payload, projection=projection, "
        "after_stage=after_stage)\n"
        "print('child-installed')\n"
    )


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0023-p2-"))
    try:
        home = tmp / "home"
        payload1 = write_tree(tmp / "p1", V1)
        payload2 = write_tree(tmp / "p2", V2)
        proj1 = projection_for(payload1)
        proj2 = projection_for(payload2)

        # Generation 1 is live.
        res1 = install_plugin(home=home, payload=payload1, projection=proj1)
        assert res1.status == "installed"
        dest = home / "plugins" / "demo-plugin"
        old_census = live_file_census(dest)
        new_census = {rel: sha(payload2 / rel) for rel in V2}

        # Kill mid-activate: child blocks in after_stage (post-verify, pre-swap).
        pause = tmp / "pause.hold"
        pause.write_text("hold\n", encoding="utf-8")
        env = os.environ.copy()
        env.update(
            {
                "TOOLS": str(REPO / "tools"),
                "HOME_DIR": str(home),
                "PAYLOAD_DIR": str(payload2),
                "PROJECTION": json.dumps(proj2),
                "IMP0023_PAUSE": str(pause),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", child_script()],
            env=env,
            cwd=str(REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait until the staging generation exists, proving the child is past
        # stage/verify and parked exactly before the live swap.
        staging = home / ".staging" / "demo-plugin"
        for _ in range(500):
            if staging.is_dir():
                break
            time.sleep(0.02)
        try:
            proc.send_signal(signal.SIGKILL)
        except Exception:
            proc.kill()
        rc = proc.wait(timeout=15)
        state_after_kill = classify_live_state(dest, old_census, new_census)

        # Corrupt-stage negative control: after_stage mutates a staged file;
        # verify must refuse and the live tree must stay on generation 1.
        def corrupt(staging_dir: Path) -> None:
            victim = staging_dir / "skills" / "alpha" / "SKILL.md"
            victim.write_text("# tampered\n", encoding="utf-8", newline="\n")

        corrupt_refused = False
        corrupt_code = ""
        try:
            install_plugin(home=home, payload=payload2, projection=proj2, after_stage=corrupt)
        except InstallError as exc:
            corrupt_refused = True
            corrupt_code = getattr(exc, "code", "") or "install-error"
        corrupt_live_intact = classify_live_state(dest, old_census, new_census) == "OLD"

        # Completing the upgrade reaches NEW.
        res3 = install_plugin(home=home, payload=payload2, projection=proj2)
        completed_state = classify_live_state(dest, old_census, new_census)
        completed_ok = res3.status == "installed" and completed_state == "NEW"

        # MIXED inspector: v1 files plus the v2-only beta file is neither OLD nor NEW.
        mixed_home = tmp / "mixed-home"
        mixed_dest = mixed_home / "plugins" / "demo-plugin"
        install_plugin(home=mixed_home, payload=payload1, projection=proj1)
        (mixed_dest / "skills" / "beta").mkdir(parents=True, exist_ok=True)
        (mixed_dest / "skills" / "beta" / "SKILL.md").write_text(
            "# beta\n", encoding="utf-8", newline="\n"
        )
        inspector_mixed = classify_live_state(mixed_dest, old_census, new_census)

        passed = bool(
            rc != 0
            and state_after_kill == "OLD"
            and corrupt_refused
            and corrupt_code == "verify-digest"
            and corrupt_live_intact
            and completed_ok
            and inspector_mixed == "MIXED"
        )
        out = {
            "unit_id": "IMP-0023",
            "probe": "probe2-kill-and-corrupt",
            "kill_returncode": rc,
            "state_after_kill": state_after_kill,
            "corrupt_refused": corrupt_refused,
            "corrupt_code": corrupt_code,
            "corrupt_live_intact": corrupt_live_intact,
            "completed_state": completed_state,
            "inspector_mixed": inspector_mixed,
            "pass": passed,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"kill_state={state_after_kill} corrupt_refused={corrupt_refused} "
            f"mixed={inspector_mixed} completed={completed_state}"
        )
        if not passed:
            print("FAILED:IMP-0023-probe2 kill/corrupt contract violation")
            return 1
        print("SUCCESS:IMP-0023-probe2 kill mid-activate and corrupt-stage refuse")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
