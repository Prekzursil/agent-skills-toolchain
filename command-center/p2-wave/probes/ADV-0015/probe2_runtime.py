"""ADV-0015 Probe 2 (mechanically different, 2026-10-21): runtime behaviour test of
the cost estimator on (a) table-supported ids, (b) a RETIRED id (gpt-5-codex,
API shutdown 2026-07-23), (c) a never-existed id.

Execution note (substrate-honest): `bash <script>` spawned from Windows python hangs on
this box (same measured msys-spawn defect recorded in ADV-0019 D3), so the four runs
were executed in the operator's real Git Bash with exit codes and stdout/stderr
captured verbatim under raws/ (capture commands in extensions); this classifier reads
the raws and derives loud-vs-silent mechanically."""

from __future__ import annotations

import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
RAW = DIR / "raws"
CASES = [
    ("supported:gpt-5.3-codex", "gpt-5.3-codex"),
    ("supported:gemini-pro", "gemini-pro"),
    ("retired:gpt-5-codex", "gpt-5-codex"),
    ("never-existed:zzz-fake-model", "zzz-fake-model"),
]


def main() -> int:
    exits = json.loads((RAW / "exits.json").read_text(encoding="utf-8"))
    rows = []
    for label, model in CASES:
        out = (RAW / f"{model}.out").read_text(encoding="utf-8", errors="replace").strip()
        err = (RAW / f"{model}.err").read_text(encoding="utf-8", errors="replace").strip()
        code = exits[model]
        if code == 0 and '"estimated_usd"' in out:
            behaviour = "estimates (exit 0)"
        elif code != 0 and "unknown model" in err.lower():
            behaviour = f"LOUD-FAIL (exit {code}, 'Unknown model' on stderr)"
        elif code != 0:
            behaviour = f"LOUD-FAIL (exit {code})"
        else:
            behaviour = "SILENT (exit 0 without JSON)"
        rows.append({"case": label, "model": model, "exit": code,
                     "stdout": out[:300], "stderr": err[:300], "behaviour": behaviour})

    supported_ok = all(r["exit"] == 0 for r in rows if r["case"].startswith("supported"))
    retired_loud = all(r["exit"] != 0 for r in rows if not r["case"].startswith("supported"))
    silent_substitution = any(r["behaviour"].startswith("SILENT") for r in rows)
    codex_row = next(r for r in rows if r["model"] == "gpt-5.3-codex")
    stale_price_at_runtime = '"estimated_usd":7.5' in codex_row["stdout"].replace(" ", "").replace("\n", "")

    payload = {
        "probe": "probe2-runtime",
        "rows": rows,
        "silent_substitution_detected": silent_substitution,
        "stale_price_at_runtime": stale_price_at_runtime,
        "vendor_price_today_per_m": {"input": 1.75, "output": 14.00,
                                     "source": "platform.openai.com/docs/pricing fetched in probe1"},
        "controls": {
            "CTRL-BOTH-STATES": supported_ok and retired_loud,
            "CTRL-NO-SILENT-SUBSTITUTION": not silent_substitution,
        },
    }
    out = [f"SUCCESS:adv0015-probe2 estimator runtime behaviour on {len(CASES)} cases"]
    for r in rows:
        out.append(f"  {r['case']}: exit={r['exit']} -> {r['behaviour']}")
    out.append(f"  stale price at runtime: {stale_price_at_runtime} "
               f"(estimator 1M+1M = 7.50 USD vs vendor 15.75 USD today)")
    for k, v in payload["controls"].items():
        out.append(f"  {k}: {'PASS' if v else 'FAIL'}")
    text_out = "\n".join(out) + "\n"
    print(text_out, end="")
    (DIR / "probe2-runtime.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    (DIR / "probe2-runtime.raw.txt").write_text(text_out, encoding="utf-8")
    return 0 if all(payload["controls"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
