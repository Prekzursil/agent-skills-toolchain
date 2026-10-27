#!/usr/bin/env python3
"""Catalog test module for IMP-0013 launch adapter."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from launch_adapter import LaunchAdapterError, get_command, launch, write_cmd_shim  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0013-test-") as tmp:
        d = Path(tmp)
        shim = write_cmd_shim(d, "catalog-tool")
        hit = get_command("catalog-tool", path_dirs=[str(d)])
        if hit is None or Path(hit).resolve() != shim.resolve():
            print("FAILED:IMP-0013-test_launch_adapter resolve")
            return 1
        _res, proc = launch("catalog-tool", ["--catalog"], path_dirs=[str(d)])
        if proc.returncode != 0 or "IMP-0013-SHIM-LAUNCHED" not in (proc.stdout or ""):
            print("FAILED:IMP-0013-test_launch_adapter launch")
            return 1
        try:
            launch("missing-catalog-tool", path_dirs=[str(d)])
            print("FAILED:IMP-0013-test_launch_adapter missing did not raise")
            return 1
        except LaunchAdapterError as err:
            if err.code != "TOOL_NOT_FOUND":
                print("FAILED:IMP-0013-test_launch_adapter code")
                return 1
    print("SUCCESS:IMP-0013-test_launch_adapter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
