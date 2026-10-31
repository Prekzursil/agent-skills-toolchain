"""IMP-0023 transactional-install tests (recreated 2026-10-24 resume).

Covers the receipt's five recorded tests: projection-matching clean install,
kill mid-activate leaving a valid OLD state, corrupt-staged-file refusal with
code verify-digest, already-current no-op idempotency, and MIXED classification
of a half-copied tree.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from plugin.install import (  # noqa: E402
    InstallError,
    classify_live_state,
    install_plugin,
    live_file_census,
    mtime_hash_census,
    predicted_live_paths,
)

import plugin.tests.harness as harness  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


class InstallTransactionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="imp0023-ut-")
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.payload = harness.write_tree(base / "payload", harness.v1_files())
        self.projection = harness.projection_for(self.payload, "demo-plugin")
        self.home = base / "home"

    def _dest(self) -> Path:
        return self.home / "plugins" / "demo-plugin"

    def _payload2(self) -> tuple[Path, dict]:
        base = Path(self.payload).parent
        p2 = harness.write_tree(base / "payload-v2", harness.v2_files())
        return p2, harness.projection_for(p2, "demo-plugin")

    def test_clean_install_matches_projection(self) -> None:
        res = install_plugin(home=self.home, payload=self.payload, projection=self.projection)
        self.assertEqual(res.status, "installed")
        self.assertTrue(res.mutated)
        live = live_file_census(self._dest())
        predicted = predicted_live_paths(self.projection)
        self.assertEqual(set(live), predicted)
        for entry in self.projection["entries"]:
            src = self.payload / entry["source"]
            self.assertEqual(live[entry["live"]], _sha(src.read_bytes()))

    def test_kill_mid_activate_leaves_valid_state(self) -> None:
        install_plugin(home=self.home, payload=self.payload, projection=self.projection)
        dest = self._dest()
        old_census = live_file_census(dest)
        p2, proj2 = self._payload2()
        new_census = {rel: _sha((p2 / rel).read_bytes()) for rel in harness.v2_files()}

        pause = Path(self._tmp.name) / "pause.hold"
        pause.write_text("hold\n", encoding="utf-8")
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": str(REPO / "tools"),
                "HOME_DIR": str(self.home),
                "PAYLOAD_DIR": str(p2),
                "PROJECTION": json.dumps(proj2),
                "IMP0023_PAUSE": str(pause),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        script = (
            "import os, sys, time, json\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, os.environ['PYTHONPATH'])\n"
            "from plugin.install import install_plugin\n"
            "def after_stage(staging):\n"
            "    p = Path(os.environ['IMP0023_PAUSE'])\n"
            "    while p.is_file():\n"
            "        time.sleep(0.02)\n"
            "install_plugin(home=Path(os.environ['HOME_DIR']),\n"
            "               payload=Path(os.environ['PAYLOAD_DIR']),\n"
            "               projection=json.loads(os.environ['PROJECTION']),\n"
            "               after_stage=after_stage)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            env=env,
            cwd=str(REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        staging = self.home / ".staging" / "demo-plugin"
        for _ in range(500):
            if staging.is_dir():
                break
            time.sleep(0.02)
        try:
            proc.send_signal(signal.SIGKILL)
        except Exception:
            proc.kill()
        rc = proc.wait(timeout=15)
        self.assertNotEqual(rc, 0)
        self.assertEqual(classify_live_state(dest, old_census, new_census), "OLD")

    def test_corrupt_staged_file_refuses_activation(self) -> None:
        install_plugin(home=self.home, payload=self.payload, projection=self.projection)
        dest = self._dest()
        old_census = live_file_census(dest)
        p2, proj2 = self._payload2()
        new_census = {rel: _sha((p2 / rel).read_bytes()) for rel in harness.v2_files()}

        def corrupt(staging: Path) -> None:
            victim = staging / "skills" / "alpha" / "SKILL.md"
            victim.write_text("# tampered\n", encoding="utf-8", newline="\n")

        with self.assertRaises(InstallError) as ctx:
            install_plugin(home=self.home, payload=p2, projection=proj2, after_stage=corrupt)
        self.assertEqual(ctx.exception.code, "verify-digest")
        self.assertEqual(classify_live_state(dest, old_census, new_census), "OLD")

    def test_second_install_is_noop_mtime_hash_census(self) -> None:
        install_plugin(home=self.home, payload=self.payload, projection=self.projection)
        before = mtime_hash_census(self._dest())
        second = install_plugin(home=self.home, payload=self.payload, projection=self.projection)
        after = mtime_hash_census(self._dest())
        self.assertEqual(second.status, "already-current")
        self.assertFalse(second.mutated)
        self.assertEqual(before, after)

    def test_mixed_tree_classifies_mixed(self) -> None:
        install_plugin(home=self.home, payload=self.payload, projection=self.projection)
        dest = self._dest()
        old_census = live_file_census(dest)
        p2, _proj2 = self._payload2()
        new_census = {rel: _sha((p2 / rel).read_bytes()) for rel in harness.v2_files()}
        beta = dest / "skills" / "beta"
        beta.mkdir(parents=True, exist_ok=True)
        (beta / "SKILL.md").write_text("# beta\n", encoding="utf-8", newline="\n")
        self.assertEqual(classify_live_state(dest, old_census, new_census), "MIXED")


if __name__ == "__main__":
    unittest.main()
