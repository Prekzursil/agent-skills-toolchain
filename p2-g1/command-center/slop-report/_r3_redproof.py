"""Both-states proof that the extended twin-parity gate can actually go RED.

125 green tests on a tree that satisfies them is not evidence the new checks
work -- a gate that is silent in the broken state too measures nothing
(single-signal-verification rule 3b). This builds a throwaway git repo laid out
like this one, copies the REAL gate file into it byte-for-byte (not a
reimplementation of its logic), and runs it against a KNOWN-BROKEN surface.

Three checks, each exercised in both states:

  1 `test_no_undeclared_divergence` -- the ratchet. Two fixture twins that are
    identical must pass; the same two made to differ must FAIL.
  2 `test_twin_surface_discovery_is_plausible` -- the fail-closed floor. A repo
    with 1 pair must FAIL it, so the floor is not decorative.
  3 `test_no_stale_declaration` -- must FAIL when the declared paths do not
    exist, so a rotten row cannot sit unnoticed.

Nothing here touches the live working tree.

Run:  python command-center/slop-report/_r3_redproof.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_REL = "ci/tests/test_deployed_hook_twin_parity.py"
OUT = Path(__file__).with_suffix(".out.json")
FIXTURE_ROOT = "rules/_r3_fixture.md"
FIXTURE_MIRROR = "agent-self/config/rules/_r3_fixture.md"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def build_fixture(tmp: Path, *, divergent: bool) -> None:
    for rel in (GATE_REL, FIXTURE_ROOT, FIXTURE_MIRROR):
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / GATE_REL, tmp / GATE_REL)
    (tmp / FIXTURE_ROOT).write_text("shared line\n", encoding="utf-8")
    (tmp / FIXTURE_MIRROR).write_text(
        "shared line\nONLY IN THE MIRROR\n" if divergent else "shared line\n",
        encoding="utf-8",
    )
    run(["git", "add", "-A"], tmp)


def probe(tmp: Path, selector: str) -> dict:
    proc = run(
        [sys.executable, "-m", "pytest", GATE_REL, "-k", selector, "-q", "--no-header"],
        tmp,
    )
    return {"rc": proc.returncode, "tail": (proc.stdout or proc.stderr).strip()[-320:]}


def main() -> int:
    results: dict[str, dict] = {}
    for state in ("clean", "broken"):
        with tempfile.TemporaryDirectory(prefix="r3-redproof-") as raw:
            tmp = Path(raw)
            run(["git", "-c", "init.defaultBranch=main", "init", "-q"], tmp)
            build_fixture(tmp, divergent=(state == "broken"))
            results[f"{state}/ratchet"] = probe(tmp, "no_undeclared_divergence")
            results[f"{state}/floor"] = probe(tmp, "discovery_is_plausible")
            results[f"{state}/stale"] = probe(tmp, "no_stale_declaration")

    # The live tree is the other half of every both-states pair.
    live = {
        name: probe(REPO, sel)
        for name, sel in (
            ("live/ratchet", "no_undeclared_divergence"),
            ("live/floor", "discovery_is_plausible"),
            ("live/stale", "no_stale_declaration"),
            ("live/all", "test_"),
        )
    }
    results.update(live)

    expectations = {
        # the ratchet is the claim under test: silent when clean, red when not
        "clean/ratchet": 0,
        "broken/ratchet": 1,
        # a 1-pair repo is below the floor in BOTH fixture states
        "clean/floor": 1,
        "broken/floor": 1,
        # the fixture repo has none of the declared paths
        "clean/stale": 1,
        "broken/stale": 1,
        # and all three are green on the real surface
        "live/ratchet": 0,
        "live/floor": 0,
        "live/stale": 0,
        "live/all": 0,
    }
    verdicts = {
        name: {
            "expected_rc": want,
            **results[name],
            "pass": results[name]["rc"] == want,
        }
        for name, want in expectations.items()
    }
    ok = all(v["pass"] for v in verdicts.values())
    OUT.write_text(
        json.dumps({"gate": GATE_REL, "verdicts": verdicts, "all_pass": ok}, indent=1),
        encoding="utf-8",
    )

    for name, v in verdicts.items():
        mark = "ok " if v["pass"] else "BAD"
        print(f"{mark} {name:<16} rc={v['rc']} (expected {v['expected_rc']})")
    if not ok:
        print(
            "FAILED:r3-redproof the gate did not behave differently in the two states"
        )
        return 1
    print(f"SUCCESS:r3-redproof -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
