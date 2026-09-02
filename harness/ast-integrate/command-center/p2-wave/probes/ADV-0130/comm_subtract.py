"""Independent NOVEL set via POSIX comm(1) over sorted unique TSV triples.

This is the reviewer-shaped re-implementation: it does not import engine.subtract
and does not read a precomputed NOVEL list. It takes two sets of typed triples,
writes LC_ALL=C sorted unique TSV files, and runs `comm -23 filed declared`.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from normalize import encode


def comm_novel(
    filed: set[tuple[str, str, str]],
    declared: set[tuple[str, str, str]],
    *,
    workdir: Path | None = None,
) -> set[tuple[str, str, str]]:
    lines_filed = sorted({encode(t) + "\n" for t in filed})
    lines_decl = sorted({encode(t) + "\n" for t in declared})
    if workdir is None:
        tmp = Path(tempfile.mkdtemp(prefix="adv0130-comm-"))
        cleanup = True
    else:
        tmp = workdir
        tmp.mkdir(parents=True, exist_ok=True)
        cleanup = False
    f_filed = tmp / "filed.tsv"
    f_decl = tmp / "declared.tsv"
    f_filed.write_text("".join(lines_filed), encoding="utf-8", newline="\n")
    f_decl.write_text("".join(lines_decl), encoding="utf-8", newline="\n")
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    proc = subprocess.run(
        ["comm", "-23", str(f_filed), str(f_decl)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"comm -23 failed rc={proc.returncode} stderr={proc.stderr!r}"
        )
    novel: set[tuple[str, str, str]] = set()
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise RuntimeError(f"comm emitted a non-triple line: {line!r}")
        novel.add((parts[0], parts[1], parts[2]))
    if cleanup:
        f_filed.unlink(missing_ok=True)
        f_decl.unlink(missing_ok=True)
        tmp.rmdir()
    return novel
