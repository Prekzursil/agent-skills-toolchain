#!/usr/bin/env python3
"""Stand-in Codex CLI for IMP-0421 recorded invocations.

Honors the estate argv contract:
  codex exec --ignore-user-config --output-last-message FILE --prompt-file FILE

Refuses --background. Never treats stdout as the result; the last-message
file is the only payload. Used so probes do not need a live Codex login.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if "--background" in argv or "--detach" in argv or "--detached" in argv:
        print("fake-codex: background refused", file=sys.stderr)
        return 2
    if "exec" not in argv:
        print("fake-codex: missing exec", file=sys.stderr)
        return 2
    if "--ignore-user-config" not in argv:
        print("fake-codex: missing --ignore-user-config", file=sys.stderr)
        return 2

    def after(flag: str) -> str | None:
        if flag not in argv:
            return None
        i = argv.index(flag)
        if i + 1 >= len(argv):
            return None
        return argv[i + 1]

    prompt_path = after("--prompt-file")
    out_path = after("--output-last-message")
    if not prompt_path or not out_path:
        print("fake-codex: need --prompt-file and --output-last-message", file=sys.stderr)
        return 2
    prompt = Path(prompt_path)
    if not prompt.is_file():
        print(f"fake-codex: prompt missing {prompt_path}", file=sys.stderr)
        return 2
    body = prompt.read_text(encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    payload = {
        "ok": True,
        "vendor": "fake-codex",
        "prompt_file": prompt_path,
        "prompt_sha256": digest,
        "prompt_bytes": len(body.encode("utf-8")),
        "echo": body.splitlines()[0] if body.splitlines() else "",
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    # Progress stream on stdout must NOT be treated as the result by the adapter.
    print("[codex] fake progress stream; not a result")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
