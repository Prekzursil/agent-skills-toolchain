#!/usr/bin/env python3
"""AUD-0043 named probe 2: scratch-build both-states packaging control.

Catalog `tests_required`: "both-states control: remove one module from the
package include list in a scratch build and confirm the installed-run turns
RED while the source-tree run stays GREEN."

This probe builds a real scratch fixture -- a minimal two-top-level-package
project (`scratch_pkg` + `helper_mod`) with a `[project.scripts]` console
entry point -- in two states:

  * GOOD state (fixtures/scratch_pkg_good): `[tool.setuptools] packages =
    ["scratch_pkg", "helper_mod"]` -- both modules declared.
  * BAD state  (fixtures/scratch_pkg_bad):  `packages = ["scratch_pkg"]`
    only -- `helper_mod` silently dropped from the include list, exactly the
    catalog's prescribed mutation. The files on disk are otherwise IDENTICAL
    between the two fixture trees (helper_mod/ is still present as source).

For each state it runs BOTH halves of the parity claim:

  1. "source_tree_run": `python -m pytest fixtures/<state>/tests` -- the
     BASELINE runner command, executed directly against the checked-out
     source tree with no packaging/build step at all.
  2. "installed_run": `pip install fixtures/<state>` into a FRESH, disposable
     virtualenv, then invoke the INSTALLED console script
     (`<venv>/bin/scratch-cli`) -- the CI-realistic route that only sees
     whatever the wheel's manifest actually shipped.

Expected (and asserted) result matrix:

    state   source_tree_run   installed_run
    good    PASS              PASS  (exit 0)
    bad     PASS              FAIL  (ModuleNotFoundError: helper_mod)

If the source-tree run for the BAD state fails, or the installed run for the
BAD state passes, the packaging/import-path exposure this unit measures does
not exist as claimed and the probe reports ok=False rather than silently
declaring success.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
FIXTURES = PROBE / "fixtures"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except OSError as e:  # pragma: no cover - environment-dependent
        return 127, f"{type(e).__name__}: {e}"


def source_tree_run(state_dir: Path) -> dict:
    """Baseline runner command: python -m pytest against the SOURCE TREE."""
    rc, out = run([sys.executable, "-m", "pytest", str(state_dir / "tests"), "-q"])
    return {"exit_code": rc, "passed": rc == 0, "output_tail": out[-2000:]}


def installed_run(state_dir: Path, tmp_root: Path, label: str) -> dict:
    """CI-realistic route: build+install into a FRESH venv, run the installed
    console script. Builds from a DISPOSABLE COPY of the fixture under tmp_root
    so pip's build artifacts (build/, *.egg-info, __pycache__) never land back
    in the committed fixture tree -- the committed tree stays pristine and the
    two fixture states stay byte-identical outside pyproject.toml."""
    src_copy = tmp_root / f"src_{label}"
    shutil.copytree(state_dir, src_copy)
    venv_dir = tmp_root / f"venv_{label}"
    rc_venv, out_venv = run([sys.executable, "-m", "virtualenv", "-q", str(venv_dir)])
    if rc_venv != 0:
        return {
            "venv_created": False,
            "exit_code": rc_venv,
            "passed": False,
            "output_tail": out_venv[-2000:],
        }
    pip = str(venv_dir / "bin" / "pip")
    console_script = str(venv_dir / "bin" / "scratch-cli")
    rc_install, out_install = run([pip, "install", "--quiet", str(src_copy)], timeout=300)
    if rc_install != 0:
        return {
            "venv_created": True,
            "installed": False,
            "exit_code": rc_install,
            "passed": False,
            "output_tail": out_install[-2000:],
        }
    rc_run, out_run = run([console_script])
    return {
        "venv_created": True,
        "installed": True,
        "exit_code": rc_run,
        "passed": rc_run == 0,
        "output_tail": out_run[-2000:],
    }


def main() -> int:
    good_dir = FIXTURES / "scratch_pkg_good"
    bad_dir = FIXTURES / "scratch_pkg_bad"
    for d in (good_dir, bad_dir):
        if not (d / "pyproject.toml").is_file():
            print(f"FAILED:AUD-0043-probe2 missing fixture {d}")
            return 1

    # Sanity: the two fixture trees differ ONLY in pyproject.toml's packages list and
    # project name -- the mutation is exactly "remove one module from the package
    # include list", nothing else. helper_mod/ source is present on disk in BOTH.
    good_py = (good_dir / "pyproject.toml").read_text(encoding="utf-8")
    bad_py = (bad_dir / "pyproject.toml").read_text(encoding="utf-8")
    def _tracked_files(root: Path) -> list[str]:
        skip_dirs = {"__pycache__", ".pytest_cache", "build"}
        return sorted(
            p.relative_to(root).as_posix()
            for p in root.rglob("*")
            if p.is_file()
            and p.name != "pyproject.toml"
            and not p.suffix == ".pyc"
            and not (set(p.relative_to(root).parts[:-1]) & skip_dirs)
            and ".egg-info" not in p.parts
        )

    fixture_files_match = _tracked_files(good_dir) == _tracked_files(bad_dir)
    manifest_mutation_ok = (
        'packages = ["scratch_pkg", "helper_mod"]' in good_py
        and 'packages = ["scratch_pkg"]' in bad_py
        and 'packages = ["scratch_pkg", "helper_mod"]' not in bad_py
    )

    with tempfile.TemporaryDirectory(prefix="aud0043-") as tmp:
        tmp_root = Path(tmp)
        results = {
            "good": {
                "source_tree_run": source_tree_run(good_dir),
                "installed_run": installed_run(good_dir, tmp_root, "good"),
            },
            "bad": {
                "source_tree_run": source_tree_run(bad_dir),
                "installed_run": installed_run(bad_dir, tmp_root, "bad"),
            },
        }

    good_src_pass = results["good"]["source_tree_run"]["passed"]
    good_inst_pass = results["good"]["installed_run"]["passed"]
    bad_src_pass = results["bad"]["source_tree_run"]["passed"]
    bad_inst_pass = results["bad"]["installed_run"]["passed"]

    # The claim under test: installed-run turns RED (bad_inst_pass=False) while the
    # source-tree run stays GREEN (bad_src_pass=True) for the SAME mutated tree, and
    # both halves stay GREEN for the unmutated tree (negative control: the harness
    # itself is not just always-red).
    both_states_ok = (
        good_src_pass
        and good_inst_pass
        and bad_src_pass
        and (not bad_inst_pass)
    )
    control_ok = fixture_files_match and manifest_mutation_ok
    ok = both_states_ok and control_ok

    doc = {
        "unit": "AUD-0043",
        "probe": 2,
        "fixture_root": str(PROBE.relative_to(REPO) / "fixtures"),
        "results": results,
        "good_source_tree_pass": good_src_pass,
        "good_installed_pass": good_inst_pass,
        "bad_source_tree_pass": bad_src_pass,
        "bad_installed_pass": bad_inst_pass,
        "both_states": both_states_ok,
        "control": {
            "fixture_files_match": fixture_files_match,
            "manifest_mutation_ok": manifest_mutation_ok,
            "ok": control_ok,
        },
        "ok": ok,
    }

    print("AUD-0043 NAMED PROBE 2: scratch-build both-states packaging control")
    print("unit=AUD-0043")
    print(f"fixture_root={doc['fixture_root']}")
    print(
        "GOOD state: source_tree_pass="
        f"{good_src_pass} installed_pass={good_inst_pass} "
        f"(exit={results['good']['installed_run']['exit_code']})"
    )
    print(
        "BAD  state: source_tree_pass="
        f"{bad_src_pass} installed_pass={bad_inst_pass} "
        f"(exit={results['bad']['installed_run']['exit_code']})"
    )
    print(f"both_states={both_states_ok}")
    print(
        f"CONTROL fixture_files_match={fixture_files_match} "
        f"manifest_mutation_ok={manifest_mutation_ok} ok={control_ok}"
    )
    print("--- installed_run BAD state tail ---")
    print(results["bad"]["installed_run"]["output_tail"].strip()[-800:])
    print("SUCCESS:AUD-0043-probe2" if ok else "FAILED:AUD-0043-probe2")

    out = PROBE / "probe2-scratch-both-states.json"
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
