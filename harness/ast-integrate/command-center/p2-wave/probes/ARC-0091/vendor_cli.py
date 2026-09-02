#!/usr/bin/env python3
"""Fixture vendor CLI: blocking, prompt-by-file, writes output-last-message JSON.

This is a consumer-side stand-in for a vendor process. It is not a live
Anthropic or OpenAI API. The contract under test is transport, blocking
dispatch, AND-gate, and terminal markers — not billed vendor inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--output-last-message", required=True)
    p.add_argument("--vendor", required=True)
    p.add_argument("--unit-id", required=True)
    p.add_argument("--empty", action="store_true")
    p.add_argument("--bad-json", action="store_true")
    args = p.parse_args()
    prompt_path = Path(args.prompt_file)
    if not prompt_path.is_file():
        print("vendor_cli: prompt file missing", file=sys.stderr)
        return 2
    prompt = prompt_path.read_text(encoding="utf-8")
    if not prompt.strip():
        print("vendor_cli: empty prompt", file=sys.stderr)
        return 2
    out = Path(args.output_last_message)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.empty:
        out.write_text("", encoding="utf-8")
        return 0
    if args.bad_json:
        out.write_text("{not json", encoding="utf-8")
        return 0
    doc = {
        "vendor": args.vendor,
        "unit_id": args.unit_id,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "echo": "fixture-vendor-completed",
        "marker": f"SUCCESS:{args.unit_id}",
    }
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
