#!/usr/bin/env python3
"""IMP-0051 probe2: runtime sweep - a sample of real failures emits the
declared code and the declared exit code.

Six failure samples are raised, rendered through emit_failure (to a capture
stream) and checked against the taxonomy: emitted code == declared code,
exit code == declared exit code, and the rendered block carries the
cause / impact / next-command contract.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "platform"))

from plugin.errors import BY_CODE, PluginError, emit_failure  # noqa: E402

SAMPLES = [
    ("E_USAGE", "runtime sweep: missing --prefix"),
    ("E_MANIFEST", "runtime sweep: manifest missing required field"),
    ("E_PAYLOAD", "runtime sweep: allowlist refusal"),
    ("E_SECRET", "runtime sweep: credential-shaped content"),
    ("E_TXN", "runtime sweep: nothing installed in prefix"),
    ("E_HEALTH", "runtime sweep: health gate failed"),
]


def main() -> int:
    checks: dict[str, bool] = {}
    rows: list[dict[str, object]] = []
    for code, detail in SAMPLES:
        declared = BY_CODE[code]
        err = PluginError(code, detail)
        buf = io.StringIO()
        rc = emit_failure(err, "runtime-sweep", stream=buf)
        text = buf.getvalue()
        emitted_code = text.split(" ", 2)[1] if text.startswith("FAILED:") else ""
        ok = (
            err.code == declared.code
            and emitted_code == code
            and rc == declared.exit_code
            and declared.cause in text
            and declared.impact in text
            and declared.next_command in text
            and f"exit code     : {declared.exit_code}" in text
        )
        rows.append({
            "code": code,
            "emitted": emitted_code,
            "exit_code": rc,
            "declared_exit": declared.exit_code,
            "render_ok": ok,
        })
        checks[f"sample_{code}"] = ok
    out = {
        "probe": "probe2-runtime-sweep",
        "unit_id": "IMP-0051",
        "samples": rows,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    bad = [k for k, v in checks.items() if not v]
    print(f"samples={len(rows)} failed={bad if bad else 'none'}")
    if bad:
        print(f"FAILED:IMP-0051-probe2 {bad}")
        return 1
    print("SUCCESS:IMP-0051-probe2 runtime sweep: emitted codes and exit codes match the taxonomy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
