"""Self-demo / integration proof for the TG-2 mutation gate (marked ``demo``).

These tests run the REAL mutation tester (cosmic-ray) and REAL git, so they are
excluded from the fast unit/coverage run (``-m "not demo"``) and executed on their
own with ``-m demo`` under an env that has cosmic-ray + pytest installed, e.g.::

    uv run --python 3.12 --with cosmic-ray==8.4.6 --with pytest --with pytest-cov \\
        python -m pytest -m demo -q

They prove every acceptance criterion end-to-end:
  * RED  : the weak sample leaves surviving mutant(s); the gate exits non-zero and
           names the surviving mutant.
  * GREEN: the strengthened sample kills them; the gate exits zero.
  * SCOPE: driven by a real ``git diff``, the gate mutates ONLY the changed file,
           never the whole tree.
"""

import pathlib
import shutil
import subprocess
import sys

import mutation_gate as mg
import pytest

pytestmark = pytest.mark.demo

SAMPLE_DIR = pathlib.Path(__file__).resolve().parent.parent / "sample"


def _work_copy(tmp_path):
    """Copy the sample tree to a scratch dir (cosmic-ray mutates files in place)."""
    work = tmp_path / "work"
    shutil.copytree(SAMPLE_DIR, work, ignore=shutil.ignore_patterns("__pycache__"))
    return work


def _run_sample_gate(work, test_file, captured):
    return mg.run_gate(
        files=["threshold.py"],
        repo_root=str(work),
        test_command=f"{{python}} -m pytest -x -q {test_file}",
        python_exe=sys.executable,
        log=captured.append,
    )


def test_demo_gate_is_red_on_the_weak_test(tmp_path):
    captured = []
    result = _run_sample_gate(_work_copy(tmp_path), "test_threshold_weak.py", captured)

    assert result.exit_code != 0  # RED
    assert result.survivors, "the weak test must leave a surviving mutant"
    # The boundary scar (>=  ->  >) must survive, in is_large_enough().
    assert any(s.operator.endswith("GtE_Gt") for s in result.survivors)
    assert any(s.function == "is_large_enough" for s in result.survivors)
    # The gate NAMES the surviving mutant + the weak suite.
    report = captured[-1]
    assert "FAILED" in report
    assert "threshold.py" in report and "is_large_enough" in report
    assert "test_threshold_weak.py" in report


def test_demo_gate_is_green_on_the_strong_test(tmp_path):
    captured = []
    result = _run_sample_gate(
        _work_copy(tmp_path), "test_threshold_strong.py", captured
    )

    assert result.exit_code == 0  # GREEN
    assert result.survivors == ()
    assert "SUCCESS" in captured[-1]


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_demo_gate_is_diff_scoped_against_real_git(tmp_path):
    """With a real git history, only the CHANGED file is mutated (not the tree)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "threshold.py").write_text(
        "def f(x):\n    return x > 0\n", encoding="utf-8"
    )
    (repo / "other.py").write_text("def g(y):\n    return y * 2\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tg2@example.com")
    _git(repo, "config", "user.name", "TG2")
    _git(repo, "add", "-A")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "base")

    # Change ONLY threshold.py, then commit.
    (repo / "threshold.py").write_text(
        "def f(x):\n    return x >= 0\n", encoding="utf-8"
    )
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-am", "tweak threshold")

    mutated = []

    def recording_runner(file, repo_root, test_command, timeout, python_exe):
        mutated.append(file)
        return ""  # no survivors; we only care WHICH files get mutated

    result = mg.run_gate(
        base="HEAD~1",
        repo_root=str(repo),
        mutation_runner=recording_runner,
        log=lambda *_: None,
    )

    assert mutated == ["threshold.py"]  # other.py was NOT mutated
    assert result.scoped_files == ("threshold.py",)
