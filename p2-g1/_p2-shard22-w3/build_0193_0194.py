#!/usr/bin/env python3
"""Write TST-0193 + TST-0194 probe files."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE.parent / "command-center" / "p2-wave" / "probes"

ECHO = r'''#!/usr/bin/env python3
"""Probe-local child: print the argv it received as JSON (exact strings)."""
from __future__ import annotations

import json
import sys

if __name__ == "__main__":
    sys.stdout.write(json.dumps({"argv": sys.argv[1:]}))
'''

SINK = r'''#!/usr/bin/env python3
"""TST-0193 measured layer: the workflow parameter sink.

sink() forwards parameters to a child through a LIST-ARGV spawn (shell=False,
CreateProcess direct) - the reference no-reparse sink. observe() returns the
exact strings the child received.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sink(params: list[str]) -> tuple[int, str]:
    echo = (HERE / "echo_args.py").as_posix()
    p = subprocess.run(
        [sys.executable, "-B", echo, *params],
        capture_output=True, text=True, timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def observed(params: list[str]) -> list[str]:
    rc, out = sink(params)
    return json.loads(out.strip().splitlines()[-1])["argv"]
'''

P193_1 = r'''#!/usr/bin/env python3
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
        payloads.append((v + "|" + b.format(m=marker)) if rng.random() < 0.5 else b.format(m=marker) + "#" + v)
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
'''

P193_2 = r'''#!/usr/bin/env python3
"""TST-0193 probe2 -- detector control: deliberately eval one payload through a
real shell; the canary marker MUST appear, proving the probe can detect
substitution. The reference sink then runs the same payload and stays clean.
Exit 0 on pass, 1 on fail.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import param_sink as PS  # noqa: E402

UNIT = "TST-0193"
RUN = HERE / ".run-p2"


def git_bash() -> str:
    from pathlib import Path as P

    c = P(r"C:" + chr(92) + "Program Files" + chr(92) + "Git" + chr(92) + "bin" + chr(92) + "bash.exe")
    return str(c) if c.is_file() else "bash"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    RUN.mkdir(parents=True)
    marker = (RUN / "CANARY-MARKER.txt").as_posix()
    evil = "$(echo pwned > '%s')" % marker

    # deliberate eval lane (detector control ONLY): a real shell parses the payload
    subprocess.run([git_bash(), "-c", "eval echo " + "'" + evil + "'"],
                   capture_output=True, text=True, timeout=60)
    detector_can_see_substitution = Path(marker).exists()
    eval_content = Path(marker).read_text(encoding="utf-8", errors="replace") if detector_can_see_substitution else None

    # fresh run dir for the sink lane
    marker2 = (RUN / "second" / "CANARY-MARKER.txt")
    marker2.parent.mkdir(parents=True, exist_ok=True)
    evil2 = "$(echo pwned > '%s')" % marker2.as_posix()
    got = PS.observed([evil2])
    sink_clean = (got == [evil2]) and not marker2.exists()

    payload = {
        "probe": "probe2-detector-control",
        "unit_id": UNIT,
        "pass": detector_can_see_substitution and sink_clean,
        "detector_control": {
            "deliberately_evaled_payload": evil,
            "marker_appeared": detector_can_see_substitution,
            "marker_content_head": (eval_content or "")[:40],
            "note": "proves the canary detects substitution when a shell is in the path",
        },
        "reference_sink": {
            "same_payload_observed": got,
            "literal_passthrough": sink_clean,
            "marker_after_sink": marker2.exists(),
        },
        "payloads_property_tested_in_probe1": 300,
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 detector-fired=%s sink-clean=%s"
              % (UNIT, detector_can_see_substitution, sink_clean))
        return 0
    print("FAILED:%s-probe2 detector=%s sink=%s" % (UNIT, detector_can_see_substitution, sink_clean))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

M194 = r'''#!/usr/bin/env python3
"""TST-0194 measured layer: package packer with a BUILD-TIME case-collision gate,
and an install step that silently loses colliding entries on NTFS (the
case-insensitive filesystem reality the build gate exists for)."""
from __future__ import annotations

import shutil
from pathlib import Path


class PackerBuildError(Exception):
    def __init__(self, message: str, colliding: list[str] | None = None):
        super().__init__(message)
        self.colliding = colliding or []


def find_case_collisions(entries: dict[str, bytes]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for path in entries:
        f = path.casefold()
        if f in seen and seen[f] != path:
            out.append((seen[f], path))
        else:
            seen.setdefault(f, path)
    return out


def build(entries: dict[str, bytes], staging: Path) -> Path:
    """BUILD step: rejects case-only duplicate entries BEFORE anything is written."""
    collisions = find_case_collisions(entries)
    if collisions:
        names = "; ".join("%r collides with %r" % (a, b) for a, b in collisions)
        raise PackerBuildError(
            "build failed: case-only duplicate manifest entries: " + names,
            colliding=[p for c in collisions for p in c],
        )
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for rel, data in entries.items():
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return staging


def install(staging: Path, target: Path) -> int:
    """INSTALL step: naive copy into a case-insensitive NTFS target.
    Returns the number of files ACTUALLY present after install."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for src in staging.rglob("*"):
        if src.is_file():
            dest = target / src.relative_to(staging)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    return sum(1 for f in target.rglob("*") if f.is_file())
'''

P194_1 = r'''#!/usr/bin/env python3
"""TST-0194 probe1 -- case-only duplicate manifest entries are caught at BUILD
time, with both paths named; the case-distinct-but-non-colliding manifest
builds (both-states control). Exit 0 on pass, 1 on fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import packer as PK  # noqa: E402

UNIT = "TST-0194"
RUN = HERE / ".run-p1"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)

    colliding = {
        "Lib/Hooks.py": b"# hooks A\n",
        "lib/hooks.py": b"# hooks B (case-variant)\n",
        "README.md": b"readme\n",
    }
    err = None
    named: list[str] = []
    try:
        PK.build(colliding, RUN / "pack-colliding")
    except PK.PackerBuildError as e:
        err = str(e)
        named = list(e.colliding)
    both_named = set(named) == {"Lib/Hooks.py", "lib/hooks.py"}

    distinct = {
        "Lib/Hooks.py": b"# hooks\n",
        "lib/utils.py": b"# utils (case-distinct prefix, no collision)\n",
        "README.md": b"readme\n",
    }
    built = None
    try:
        built = PK.build(distinct, RUN / "pack-distinct")
    except PK.PackerBuildError as e:
        err = str(e)

    payload = {
        "probe": "probe1-build-rejects",
        "unit_id": UNIT,
        "pass": err is not None and both_named and built is not None,
        "colliding_manifest": {
            "build_failed": err is not None,
            "error_names_both_paths": named,
            "error_text": err,
        },
        "distinct_manifest": {
            "built": built is not None,
            "files": sorted(p.relative_to(built).as_posix() for p in built.rglob("*") if p.is_file()) if built else [],
        },
        "signals": {
            "a_packer_exit_and_message": err,
            "b_casefold_set_vs_raw_set": {
                "raw_distinct": len({p for p in colliding}),
                "casefold_distinct": len({p.casefold() for p in colliding}),
            },
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 build_rejects=True both_named=%s distinct_builds=True"
              % (UNIT, both_named))
        return 0
    print("FAILED:%s-probe1 err=%s named=%s built=%s" % (UNIT, err is not None, named, built is not None))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P194_2 = r'''#!/usr/bin/env python3
"""TST-0194 probe2 -- negative control: deferring the check to INSTALL time must
fail the unit's requirement - on case-insensitive NTFS the colliding pair
installs to FEWER files than manifest entries (silent last-write-wins loss),
which is exactly what the BUILD-time gate prevents. Exit 0 on pass, 1 on fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import packer as PK  # noqa: E402

UNIT = "TST-0194"
RUN = HERE / ".run-p2"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)

    colliding = {
        "Lib/Hooks.py": b"# hooks A (build-gated pair)\n",
        "lib/hooks.py": b"# hooks B (case-variant, would overwrite)\n",
    }
    staging = RUN / "naive-staging"
    staging.mkdir(parents=True)
    for rel, data in colliding.items():  # a packer WITHOUT the build gate
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    staged_files = sum(1 for f in staging.rglob("*") if f.is_file())

    target = RUN / "install-target"
    installed_files = PK.install(staging, target)
    survivor = (target / "Lib" / "Hooks.py")
    survived_content = survivor.read_bytes() if survivor.exists() else None
    lost_variant = b"# hooks A (build-gated pair)" not in (survived_content or b"") or installed_files < staged_files
    data_loss_demonstrated = installed_files < len(colliding)

    payload = {
        "probe": "probe2-install-deferral",
        "unit_id": UNIT,
        "pass": data_loss_demonstrated and lost_variant,
        "negative_control": {
            "deferred_check": "naive packer skips the build gate; collision surfaces at install",
            "manifest_entries": len(colliding),
            "staged_files": staged_files,
            "installed_files_after_ntfs_merge": installed_files,
            "silent_data_loss": data_loss_demonstrated,
            "survivor_content": (survived_content or b"").decode(errors="replace").strip(),
        },
        "casefold_set_comparison": {
            "raw_distinct": len(set(colliding)),
            "casefold_distinct": len(set(p.casefold() for p in colliding)),
            "delta_is_hidden_collision": len(set(colliding)) - len(set(p.casefold() for p in colliding)),
        },
        "conclusion": "deferring to install time fails the requirement; the build-time gate (probe1) is required",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 installed=%d<%d silent-loss-demonstrated=True"
              % (UNIT, installed_files, len(colliding)))
        return 0
    print("FAILED:%s-probe2 installed=%d staged=%d loss=%s"
          % (UNIT, installed_files, staged_files, data_loss_demonstrated))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

D193 = PROBES / "TST-0193"
D194 = PROBES / "TST-0194"
D193.mkdir(parents=True, exist_ok=True)
D194.mkdir(parents=True, exist_ok=True)
(D193 / "echo_args.py").write_text(ECHO, encoding="utf-8", newline="\n")
(D193 / "param_sink.py").write_text(SINK, encoding="utf-8", newline="\n")
(D193 / "probe1_canary_property.py").write_text(P193_1, encoding="utf-8", newline="\n")
(D193 / "probe2_detector_control.py").write_text(P193_2, encoding="utf-8", newline="\n")
(D194 / "packer.py").write_text(M194, encoding="utf-8", newline="\n")
(D194 / "probe1_build_rejects.py").write_text(P194_1, encoding="utf-8", newline="\n")
(D194 / "probe2_install_deferral.py").write_text(P194_2, encoding="utf-8", newline="\n")
import ast

for f in [ECHO, SINK, P193_1, P193_2, M194, P194_1, P194_2]:
    ast.parse(f)
print("TST-0193 + TST-0194 written + syntax OK")
