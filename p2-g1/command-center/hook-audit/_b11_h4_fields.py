"""Which of the three explanations does each H4 row actually support?

A sub-millisecond `run_ms` is an in-process `main()` that returned in ~100us. Three
hypotheses explain that, and they demand different fixes:

  H1 REAL      -- the hook genuinely costs that little.
  H2 FASTPATH  -- a throttle/cache/stamp guard returned early (the git-hygiene shape).
  H3 DECLINED  -- main() exited because the SYNTHETIC PAYLOAD is not the state it
                  reacts to. Then the number times the hook's declination, not the hook.

H3 is separable from the artifact itself: `selected_for_probe_tool` records whether the
row's matcher accepted the probe payload's tool_name. `emitted_bytes` records whether the
hook produced anything. Print the FIELDS, not a sentence about them.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
d = json.loads((HERE / "H4-TIMING-live.json").read_text(encoding="utf-8"))
rows = d["checks"]

# Detector control: these field names must EXIST and must not be uniformly null, or the
# reader is blind and its silence means nothing.
required = ("selected_for_probe_tool", "emitted_bytes", "run_ms", "rc")
missing = [f for f in required if not any(f in r for r in rows)]
if missing:
    raise SystemExit(f"FAILED:h4-fields blind reader, fields absent: {missing}")

head = "{:<13} {:<32} {:>8} {:>6} {:>9} {:>8} {}".format(
    "event", "check", "run_ms", "sel?", "emitted_B", "ctx?", "rc"
)
print(head)
print("-" * (len(head) + 6))
n_sel = n_emit = 0
for x in sorted(rows, key=lambda z: z.get("run_ms") or 0):
    sel = x.get("selected_for_probe_tool")
    em = x.get("emitted_bytes")
    n_sel += 1 if sel else 0
    n_emit += 1 if em else 0
    print(
        "{:<13} {:<32} {:>8} {:>6} {:>9} {:>8} {}".format(
            str(x.get("event")),
            str(x.get("name")),
            str(x.get("run_ms")),
            str(sel),
            str(em),
            str(x.get("emitted_ctx")),
            str(x.get("rc")),
        )
    )

print()
print(f"rows                                  : {len(rows)}")
print(f"selected_for_probe_tool = True        : {n_sel}")
print(f"emitted anything at all (bytes > 0)   : {n_emit}")
print(
    f"run_ms < 1.0 ms (main() did no work)  : {sum(1 for r in rows if (r.get('run_ms') or 0) < 1.0)}"
)
print(
    f"run_ms < 15 ms                        : {sum(1 for r in rows if (r.get('run_ms') or 0) < 15)}"
)
