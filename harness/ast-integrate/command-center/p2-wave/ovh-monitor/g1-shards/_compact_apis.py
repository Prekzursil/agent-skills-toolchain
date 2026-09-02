#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

SHARDS = Path(__file__).resolve().parent
data = json.loads((SHARDS / "_remaining40_api.json").read_text(encoding="utf-8"))
SKIP = {
    "__future__", "hashlib", "json", "subprocess", "sys", "datetime", "pathlib",
    "os", "re", "ast", "inspect", "tempfile", "shutil", "copy", "unittest",
    "typing", "dataclasses", "enum", "collections", "itertools", "functools",
    "textwrap", "io", "csv", "math", "time", "uuid", "base64", "hmac",
    "argparse", "traceback", "contextlib", "struct", "stat", "fnmatch",
    "glob", "platform", "string", "decimal", "random", "operator",
}


def main() -> None:
    for rec in data:
        mods = set()
        for f in rec["files"]:
            for imp in f.get("imports") or []:
                if ":" in imp:
                    mod, name = imp.split(":", 1)
                else:
                    mod, name = imp, ""
                root = mod.split(".")[0]
                if root in SKIP or not mod:
                    continue
                mods.add(imp)
        print(rec["id"])
        for m in sorted(mods):
            print(" ", m)


if __name__ == "__main__":
    main()
