#!/usr/bin/env python3
"""Fixture vendor: report which transport delivered the payload and its digest.

Not a live Codex/Anthropic API. The child proves the payload arrived intact
whether it travelled inline on argv or via --prompt-file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    args = p.parse_args()
    if args.prompt is not None:
        body = args.prompt
        transport = "inline"
    else:
        path = Path(args.prompt_file)
        if not path.is_file():
            print("vendor_cli: prompt file missing", file=sys.stderr)
            return 2
        body = path.read_text(encoding="utf-8")
        transport = "prompt-file"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    body_on_argv = any(a == body for a in sys.argv[1:])
    doc = {
        "ok": True,
        "transport": transport,
        "payload_len": len(body),
        "payload_sha256": digest,
        "prompt_body_on_argv": body_on_argv,
        "argv_len": len(sys.argv),
    }
    print(json.dumps(doc, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
