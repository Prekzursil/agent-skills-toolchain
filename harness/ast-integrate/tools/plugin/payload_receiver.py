"""Child used by arg_marshalling: read payload from file or argv and report."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def main() -> int:
    source = "argv"
    data = ""
    env_path = os.environ.get("IMP0018_PAYLOAD_FILE") or os.environ.get(
        "ARG_MARSHALL_PAYLOAD_FILE"
    )
    if env_path:
        raw = Path(env_path).read_bytes()
        data = raw.decode("utf-8")
        source = "file"
    elif len(sys.argv) > 1 and sys.argv[1] == "--file" and len(sys.argv) > 2:
        raw = Path(sys.argv[2]).read_bytes()
        data = raw.decode("utf-8")
        source = "file"
    elif len(sys.argv) > 1:
        data = sys.argv[1]
        source = "argv"
    raw = data.encode("utf-8")
    rec = {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "source": source,
    }
    print(json.dumps(rec, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
