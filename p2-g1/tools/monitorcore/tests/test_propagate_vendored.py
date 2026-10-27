from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import _propagate_vendored as propagation


def make_layout(
    tmp_path: Path, names: dict[str, bytes], copies: int = 2
) -> tuple[Path, tuple[Path, ...]]:
    source = tmp_path / "source"
    source.mkdir()
    for name, blob in names.items():
        (source / name).write_bytes(blob)
    destinations = tuple(tmp_path / f"copy-{index}" for index in range(copies))
    for destination in destinations:
        destination.mkdir()
    return source, destinations


def test_propagates_every_discovered_module_to_every_copy(tmp_path: Path) -> None:
    names = {
        "alpha.py": b"a = 1\n",
        "board.py": b"b = 2\n",
        "zeta.py": b"z = 3\n",
    }
    source, copies = make_layout(tmp_path, names)

    result = propagation.propagate(source, copies)

    assert result.exit_code == 0
    assert result.copied == len(names) * len(copies)
    # The old tuple skipped all these names, so this assertion failed before WF-7.
    for copy in copies:
        assert {path.name for path in copy.glob("*.py")} == set(names)
        for name, blob in names.items():
            assert (copy / name).read_bytes() == blob


def test_empty_source_fails_without_writes(tmp_path: Path) -> None:
    source, copies = make_layout(tmp_path, {})

    result = propagation.propagate(source, copies)

    assert result.exit_code != 0
    assert "no top-level Python modules" in result.lines[-1]
    assert all(not list(copy.iterdir()) for copy in copies)


def test_missing_destination_module_is_created(tmp_path: Path) -> None:
    source, copies = make_layout(tmp_path, {"new_module.py": b"NEW = True\n"}, copies=1)

    result = propagation.propagate(source, copies)

    assert result.exit_code == 0
    assert result.created == 1
    assert (copies[0] / "new_module.py").read_bytes() == b"NEW = True\n"
    assert any(" + " in line for line in result.lines)


def test_orphan_fails_and_is_named(tmp_path: Path) -> None:
    source, copies = make_layout(tmp_path, {"kept.py": b"x = 1\n"}, copies=1)
    (copies[0] / "orphan.py").write_bytes(b"orphan = True\n")

    result = propagation.propagate(source, copies)

    assert result.exit_code != 0
    assert any("orphan.py" in line for line in result.lines)
    assert "delete them deliberately" in result.lines[-1]


def test_missing_copy_root_fails(tmp_path: Path) -> None:
    source, _ = make_layout(tmp_path, {"module.py": b"x = 1\n"}, copies=0)
    missing = tmp_path / "missing"

    result = propagation.propagate(source, (missing,))

    assert result.exit_code != 0
    assert missing.as_posix() in result.lines[-1]


def test_copy_is_byte_exact_for_mixed_line_endings(tmp_path: Path) -> None:
    names = {"crlf.py": b"a = 1\r\nb = 2\r\n", "lf.py": b"a = 1\nb = 2\n"}
    source, copies = make_layout(tmp_path, names, copies=1)

    result = propagation.propagate(source, copies)

    assert result.exit_code == 0
    for name, blob in names.items():
        assert (copies[0] / name).read_bytes() == blob


def test_cli_propagates_sandbox_layout(tmp_path: Path) -> None:
    repo = tmp_path / "sandbox"
    script = repo / "tools" / "monitorcore" / "_propagate_vendored.py"
    script.parent.mkdir(parents=True)
    script.write_bytes(Path(propagation.__file__).read_bytes())
    source = script.parent / "monitorcore"
    copies = (
        repo / "skills" / "workflow-monitor" / "monitorcore",
        repo / ".agents" / "skills" / "workflow-monitor" / "monitorcore",
    )
    source.mkdir()
    (source / "board.py").write_bytes(b"BOARD = True\n")
    for copy in copies:
        copy.mkdir(parents=True)

    completed = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, check=False
    )

    assert completed.returncode == 0
    assert "SUCCESS:propagate" in completed.stdout
    assert all((copy / "board.py").read_bytes() == b"BOARD = True\n" for copy in copies)
