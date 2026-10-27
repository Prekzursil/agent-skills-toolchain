#!/usr/bin/env python3
"""TST-0193 probe1 -- property test over 300 injection payloads.

Every payload embeds a marker-creating command so that ANY shell evaluation
anywhere in the pipeline would create the marker file. PASS: zero markers and
every payload arrives at the child byte-identical. Exit 0 on pass, 1 on fail.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import param_sink as PS  # noqa: E402

UNIT = "TST-0193"
RUN = HERE / ".run-p1"


def build_payloads(marker: str, rng: random.Random) -> list[str]:
    bases = [
        "$(echo pwned > {m})",
        "`echo pwned > {m}`",
        "%COMSPEC% > {m}",
        "${IFTABLE} && echo pwned > {m}",
        "value; echo pwned > {m}",
        "value | echo pwned > {m}",
        "value && type NUL > {m}",
        "value > {m}",
        "$(cmd /c echo pwned > {m})",
        "a\r\nb > {m}",
        "$(python -c \"open(r'{m}','w').write('x')\")",
        "`{m}`",
        "$(touch {m})",
        "%PATH:~0,1% > {m}",
        "$(echo `echo pwned > {m}`)",
    ]
    payloads = []
    for i in range(300):
        b = bases[i % len(bases)]
        v = rng.choice(["workflow-param", "path/to/thing", "--flag=value", "user text", "id-123"])
        sb = b.replace("{m}", marker)
        payloads.append((v + "|" + sb) if rng.random() < 0.5 else sb + "#" + v)
    return payloads


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    RUN.mkdir(parents=True)
    marker = (RUN / "CANARY-MARKER.txt").as_posix()
    payloads = build_payloads(marker, random.Random(193193))

    mismatches: list[int] = []
    for i, p in enumerate(payloads):
        got = PS.observed([p])
        if got != [p]:
            mismatches.append(i)

    marker_exists = Path(marker).exists()

    payload = {
        "probe": "probe1-canary-property",
        "unit_id": UNIT,
        "pass": not mismatches and not marker_exists,
        "payloads_tested": len(payloads),
        "argv_mismatches": len(mismatches),
        "canary_marker_created": marker_exists,
        "marker_path": marker,
        "sink": "list-argv spawn (shell=False, CreateProcess direct) - zero substitution",
        "payload_families": 15,
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 payloads=300 mismatches=0 marker=absent" % UNIT)
        return 0
    print("FAILED:%s-probe1 mismatches=%d marker=%s" % (UNIT, len(mismatches), marker_exists))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
