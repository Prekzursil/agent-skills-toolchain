"""Both-states control: prove vendordrift FIRES on a real staged drift in THIS repo.

vendordrift's own suite exercises temp repos. That does not prove the gate reads the INDEX of
the live worktree, which is the property this lane relies on when it claims the vendored copies
are in sync. So: mutate one vendored file, STAGE it, and require exit 1; then restore byte-exact
from the source of truth, re-stage, and require exit 0 again.

Restores in a finally block and asserts byte-equality with the pre-run bytes before exiting.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "tools" / "monitorcore" / "monitorcore" / "pane.py"
VICTIM = REPO / ".agents" / "skills" / "workflow-monitor" / "monitorcore" / "pane.py"
GATE = REPO / "tools" / "measure-guard" / "vendordrift.py"


def stage(path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(REPO), "add", "--", str(path.relative_to(REPO).as_posix())],
        check=True,
        capture_output=True,
    )


def gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GATE)], cwd=REPO, capture_output=True, text=True
    )
    return proc.returncode, proc.stdout.strip().splitlines()[-1] if proc.stdout else ""


def main() -> int:
    original = VICTIM.read_bytes()
    failures: list[str] = []
    try:
        clean_code, clean_line = gate()
        print(f"[clean]  exit={clean_code}  {clean_line}")
        if clean_code != 0:
            failures.append("gate was already red before the mutation")

        VICTIM.write_bytes(original + b"\n# injected drift\n")
        stage(VICTIM)
        dirty_code, dirty_line = gate()
        print(f"[drifted] exit={dirty_code}  {dirty_line}")
        if dirty_code == 0:
            failures.append(
                "gate stayed GREEN on a real staged drift (it measures nothing)"
            )
        elif "pane.py" not in dirty_line and "CONTENT" not in dirty_line:
            print("  note: gate failed but did not name pane.py on its last line")
    finally:
        VICTIM.write_bytes(SOURCE.read_bytes())
        stage(VICTIM)

    assert VICTIM.read_bytes() == original, (
        "restore failed: victim differs from pre-run bytes"
    )
    back_code, back_line = gate()
    print(f"[restored] exit={back_code}  {back_line}")
    if back_code != 0:
        failures.append("gate did not return to green after restore")

    if failures:
        print(f"FAILED:vendordrift-control {failures}")
        return 1
    print(
        "SUCCESS:vendordrift-control gate is green-clean, red-on-staged-drift, green-again"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
