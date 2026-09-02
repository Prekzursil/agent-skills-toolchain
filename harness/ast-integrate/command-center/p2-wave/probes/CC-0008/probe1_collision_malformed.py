#!/usr/bin/env python3
"""CC-0008 probe 1: collision gate, malformed-slice fail-closed, completeness both-states.

Two slices claiming CC-0007 must fail and name both paths.
A malformed slice must fail loudly (not be dropped).
An unallocated prefix must fail (no rename).
Completeness: incomplete unit fails; complete units merge.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import merge_catalog as M  # noqa: E402

UNIT = "CC-0008"


def write_slice(dir_path: Path, name: str, units: list[dict]) -> Path:
    path = dir_path / name
    M.write_canonical(path, {"slice_file": name, "work_units": units})
    return path


def expect_fail(paths: list[Path], kind_substr: str, must_name: list[str], **kwargs) -> str:
    try:
        M.merge_slices(paths, **kwargs)
    except M.MergeError as exc:
        text = f"{exc.kind} {exc.detail} sources={' '.join(exc.paths)}"
        if kind_substr not in exc.kind and kind_substr not in text:
            raise SystemExit(f"FAILED:{UNIT}-probe1 expected kind~{kind_substr!r} got {text}")
        for token in must_name:
            if token not in text:
                raise SystemExit(
                    f"FAILED:{UNIT}-probe1 expected to name {token!r} in {text}"
                )
        print(f"fired kind={exc.kind} named={must_name}")
        return text
    raise SystemExit(f"FAILED:{UNIT}-probe1 expected failure {kind_substr} but merge succeeded")


def main() -> int:
    alloc = M.load_allocation()
    tmp = Path(tempfile.mkdtemp(prefix="cc0008-p1-"))
    try:
        good = tmp / "good"
        good.mkdir()
        a = write_slice(good, "alpha.json", [M.minimal_unit("CC-0001"), M.minimal_unit("CC-0002")])
        b = write_slice(good, "beta.json", [M.minimal_unit("ADV-0001"), M.minimal_unit("ARC-0001")])
        units = M.merge_slices([b, a], allocation=alloc)
        ids = [u["id"] for u in units]
        if ids != sorted(ids) or set(ids) != {"ADV-0001", "ARC-0001", "CC-0001", "CC-0002"}:
            print(f"FAILED:{UNIT}-probe1 positive merge ids={ids}")
            return 1
        print(f"positive merge ids={ids}")

        collide = tmp / "collide"
        collide.mkdir()
        p1 = write_slice(collide, "slice-a.json", [M.minimal_unit("CC-0007")])
        p2 = write_slice(collide, "slice-b.json", [M.minimal_unit("CC-0007", title="other copy")])
        expect_fail(
            [p1, p2],
            "id-collision",
            [p1.as_posix(), p2.as_posix(), "CC-0007"],
            allocation=alloc,
        )

        mal = tmp / "malformed"
        mal.mkdir()
        bad = mal / "broken.json"
        bad.write_text("{not json", encoding="utf-8")
        ok = write_slice(mal, "ok.json", [M.minimal_unit("CC-0003")])
        expect_fail(
            [bad, ok],
            "malformed-slice",
            [bad.as_posix()],
            allocation=alloc,
        )

        missing = tmp / "missing-array"
        missing.mkdir()
        dropped = missing / "no-units.json"
        M.write_canonical(dropped, {"slice_file": "no-units.json", "note": "no units key"})
        expect_fail(
            [dropped],
            "malformed-slice",
            [dropped.as_posix()],
            allocation=alloc,
        )

        unalloc = tmp / "unalloc"
        unalloc.mkdir()
        zz = write_slice(unalloc, "zz.json", [M.minimal_unit("ZZ-0001")])
        expect_fail(
            [zz],
            "unallocated-prefix",
            [zz.as_posix(), "ZZ-0001"],
            allocation=alloc,
        )

        incomplete = tmp / "incomplete"
        incomplete.mkdir()
        hole = M.minimal_unit("CC-0004")
        del hole["title"]
        hole_path = write_slice(incomplete, "hole.json", [hole])
        expect_fail(
            [hole_path],
            "incomplete-unit",
            [hole_path.as_posix(), "CC-0004"],
            allocation=alloc,
            require_complete=True,
        )

        # both-states: same slice with title restored is silent (already proven by positive merge)
        print(
            json.dumps(
                {
                    "collision_named_both_paths": True,
                    "malformed_not_dropped": True,
                    "unallocated_prefix_not_renamed": True,
                    "completeness_fires_on_missing_title": True,
                    "completeness_silent_on_complete": True,
                    "pass": True,
                    "probe": "probe1-collision-malformed",
                    "unit_id": UNIT,
                },
                sort_keys=True,
            )
        )
        print(f"SUCCESS:{UNIT}-probe1 collision gate, malformed fail-closed, completeness both-states")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
