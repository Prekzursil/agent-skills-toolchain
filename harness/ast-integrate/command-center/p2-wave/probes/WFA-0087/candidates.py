"""Fifteen REPAIR-class fixture candidates for WFA-0087.

The Windows 08-WORKFLOW-CANDIDATE-REGISTRY.json (REPAIR n=15) is not on this
Linux worktree, and WFA-0086's intake artifact is also absent. These fifteen
ids are a fixture corpus of the REPAIR class (n=15), not harvested registry
ids. Each candidate has a red intake test, a scoped fix, and a green canary
that must stay green.
"""
from __future__ import annotations

from typing import Any

CANARY_STABLE = "def ping():\n    return 'stable'\n"
CANARY_TEST = """import sys
import stable

got = stable.ping()
if got != "stable":
    print(f"RED: canary ping={got!r} want='stable'")
    sys.exit(1)
print("GREEN: canary")
sys.exit(0)
"""


def _intake(body: str) -> str:
    return body.lstrip("\n") + ("" if body.endswith("\n") else "\n")


def _mod(broken: str, fixed: str, test: str, *, extra_broken: dict[str, str] | None = None,
         extra_fixed: dict[str, str] | None = None, declared: list[str] | None = None) -> dict[str, Any]:
    files_broken = {
        "target/workflow.py": broken if broken.endswith("\n") else broken + "\n",
        "target/test_intake.py": _intake(test),
        "canary/stable.py": CANARY_STABLE,
        "canary/test_canary.py": CANARY_TEST,
    }
    if extra_broken:
        files_broken.update(extra_broken)
    files_fixed = {
        "target/workflow.py": fixed if fixed.endswith("\n") else fixed + "\n",
    }
    if extra_fixed:
        files_fixed.update(extra_fixed)
    return {
        "files_broken": files_broken,
        "files_fixed": files_fixed,
        "declared_scope": declared or ["target/workflow.py"],
        "intake_rel": "target/test_intake.py",
        "intake_cwd": "target",
        "canary_rel": "canary/test_canary.py",
        "canary_cwd": "canary",
    }


CANDIDATES: list[dict[str, Any]] = [
    {
        "id": "wf-repair-01-add-offbyone",
        "title": "add() returns a+b+1",
        "defect_class": "off-by-one",
        **_mod(
            "def add(a, b):\n    return a + b + 1\n",
            "def add(a, b):\n    return a + b\n",
            """
import sys
import workflow
got = workflow.add(2, 2)
if got != 4:
    print(f"RED: add(2,2)={got!r} want=4")
    sys.exit(1)
print("GREEN: add(2,2)==4")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-02-mul-offbyone",
        "title": "mul() returns a*b+1",
        "defect_class": "off-by-one",
        **_mod(
            "def mul(a, b):\n    return a * b + 1\n",
            "def mul(a, b):\n    return a * b\n",
            """
import sys
import workflow
got = workflow.mul(3, 3)
if got != 9:
    print(f"RED: mul(3,3)={got!r} want=9")
    sys.exit(1)
print("GREEN: mul(3,3)==9")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-03-clamp-noop",
        "title": "clamp() ignores bounds",
        "defect_class": "missing-guard",
        **_mod(
            "def clamp(x, lo, hi):\n    return x\n",
            "def clamp(x, lo, hi):\n    return min(max(x, lo), hi)\n",
            """
import sys
import workflow
got = workflow.clamp(11, 0, 10)
if got != 10:
    print(f"RED: clamp(11,0,10)={got!r} want=10")
    sys.exit(1)
print("GREEN: clamp==10")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-04-json-drop-null",
        "title": "serializer drops null fields",
        "defect_class": "lossy-encode",
        **_mod(
            "def pack(row):\n    return {k: v for k, v in row.items() if v is not None}\n",
            "def pack(row):\n    return dict(row)\n",
            """
import sys
import workflow
got = workflow.pack({"a": 1, "b": None})
if "b" not in got or got["b"] is not None:
    print(f"RED: pack={got!r} want key b=None")
    sys.exit(1)
print("GREEN: null retained")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-05-env-path",
        "title": "path assembled from HOME instead of explicit root",
        "defect_class": "env-dependent-path",
        **_mod(
            "import os\nfrom pathlib import Path\n\ndef locate(name, root=None):\n    return str(Path(os.environ.get('HOME', '/')) / name)\n",
            "from pathlib import Path\n\ndef locate(name, root=None):\n    if not root:\n        raise ValueError('explicit root required')\n    return str(Path(root) / name)\n",
            """
import sys
import workflow
got = workflow.locate("k", root="/estate")
if got != "/estate/k":
    print(f"RED: locate={got!r} want='/estate/k'")
    sys.exit(1)
print("GREEN: explicit root")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-06-wall-clock",
        "title": "stamp() reads wall clock, ignoring injected clock",
        "defect_class": "wall-clock-nondeterminism",
        **_mod(
            "import time\n\ndef stamp(clock=None):\n    return {'id': str(time.time())}\n",
            "def stamp(clock=None):\n    if clock is None:\n        raise ValueError('clock required')\n    return {'id': str(clock())}\n",
            """
import sys
import workflow
got = workflow.stamp(clock=lambda: 7)
if got != {"id": "7"}:
    print(f"RED: stamp={got!r} want={{'id': '7'}}")
    sys.exit(1)
print("GREEN: injected clock")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-07-unseeded-rand",
        "title": "pick() ignores seed and always returns last item",
        "defect_class": "unseeded-randomness",
        **_mod(
            "def pick(xs, seed=None):\n    return xs[-1]\n",
            "import random\n\ndef pick(xs, seed=None):\n    return random.Random(seed).choice(xs)\n",
            """
import sys
import random
import workflow
xs = ["x", "y", "z"]
got = workflow.pick(xs, seed=0)
want = random.Random(0).choice(xs)
if got != want:
    print(f"RED: pick={got!r} want={want!r}")
    sys.exit(1)
print("GREEN: seeded pick")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-08-shell-interp",
        "title": "argv built by string interpolation",
        "defect_class": "string-interpolated-args",
        **_mod(
            "def argv(arg):\n    return f'echo {arg}'\n",
            "def argv(arg):\n    return ['echo', arg]\n",
            """
import sys
import workflow
got = workflow.argv("x; rm")
if not isinstance(got, list) or got != ["echo", "x; rm"]:
    print(f"RED: argv={got!r} want=['echo', 'x; rm']")
    sys.exit(1)
print("GREEN: argv list")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-09-fire-forget",
        "title": "dispatch returns a background job receipt",
        "defect_class": "fire-and-forget-dispatch",
        **_mod(
            "def dispatch(job):\n    return {'receipt': 'background-job:1', 'done': False}\n",
            "def dispatch(job):\n    return {'receipt': None, 'done': True, 'result': f'ok:{job}'}\n",
            """
import sys
import workflow
got = workflow.dispatch("unit-a")
if got.get("done") is not True or got.get("receipt"):
    print(f"RED: dispatch={got!r}")
    sys.exit(1)
if got.get("result") != "ok:unit-a":
    print(f"RED: result={got!r}")
    sys.exit(1)
print("GREEN: blocking dispatch")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-10-digest-ghost",
        "title": "accepts a digest for a file that does not exist",
        "defect_class": "digest-for-missing-file",
        **_mod(
            "def accept(path, digest):\n    return {'accepted': True, 'digest': digest}\n",
            "from pathlib import Path\n\ndef accept(path, digest):\n    if not Path(path).is_file():\n        return {'accepted': False, 'reason': 'missing-file'}\n    return {'accepted': True, 'digest': digest}\n",
            """
import sys
import workflow
got = workflow.accept("no-such-file-wfa0087", "abc")
if got.get("accepted") is not False or got.get("reason") != "missing-file":
    print(f"RED: accept={got!r}")
    sys.exit(1)
print("GREEN: missing-file rejected")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-11-drop-null-fanin",
        "title": "fan-in silently drops null rows",
        "defect_class": "null-drop-fanin",
        **_mod(
            "def fanin(rows):\n    return [r for r in rows if r is not None]\n",
            "def fanin(rows):\n    return {'results': list(rows), 'missing': [i for i, r in enumerate(rows) if r is None]}\n",
            """
import sys
import workflow
got = workflow.fanin([1, None, 3])
if not isinstance(got, dict) or got.get("missing") != [1]:
    print(f"RED: fanin={got!r} want missing=[1]")
    sys.exit(1)
print("GREEN: null reported")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-12-phase-deadline",
        "title": "deadline is phase-only, no per-agent timeout",
        "defect_class": "phase-only-deadline",
        **_mod(
            "def deadlines():\n    return {'phase_seconds': 100, 'per_agent_seconds': None}\n",
            "def deadlines():\n    return {'phase_seconds': 100, 'per_agent_seconds': 20}\n",
            """
import sys
import workflow
got = workflow.deadlines()
pa = got.get("per_agent_seconds")
if not isinstance(pa, int) or pa <= 0 or pa > got.get("phase_seconds", 0):
    print(f"RED: deadlines={got!r}")
    sys.exit(1)
print("GREEN: per-agent deadline")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-13-memory-partial",
        "title": "partial results held only in memory",
        "defect_class": "in-memory-partial",
        **_mod(
            "def save(rows, dest):\n    return {'memory': list(rows), 'path': None}\n",
            "import json\nfrom pathlib import Path\n\ndef save(rows, dest):\n    Path(dest).write_text(json.dumps(list(rows)), encoding='utf-8')\n    return {'memory': list(rows), 'path': dest}\n",
            """
import json
import sys
from pathlib import Path
import workflow
dest = Path("partial.json")
got = workflow.save([1, 2], str(dest))
if got.get("path") != str(dest) or not dest.is_file():
    print(f"RED: save={got!r} exists={dest.is_file()}")
    sys.exit(1)
if json.loads(dest.read_text(encoding="utf-8")) != [1, 2]:
    print("RED: durable bytes mismatch")
    sys.exit(1)
print("GREEN: durable partial")
sys.exit(0)
""",
            declared=["target/workflow.py"],
        ),
    },
    {
        "id": "wf-repair-14-broad-add",
        "title": "stage() sweeps sibling paths (shared-index analogue)",
        "defect_class": "broad-add-shared-index",
        **_mod(
            "def stage(changed, declared):\n    return sorted(changed)\n",
            "def stage(changed, declared):\n    return sorted(p for p in changed if p in set(declared))\n",
            """
import sys
import workflow
got = workflow.stage(["a.py", "b.py"], ["a.py"])
if got != ["a.py"]:
    print(f"RED: stage={got!r} want=['a.py']")
    sys.exit(1)
print("GREEN: scoped stage")
sys.exit(0)
""",
        ),
    },
    {
        "id": "wf-repair-15-barrier-timeout",
        "title": "barrier wait has no per-agent timeout",
        "defect_class": "barrier-without-timeout",
        **_mod(
            "def barrier_wait(timeout=None):\n    return {'waited': True, 'timeout': timeout}\n",
            "def barrier_wait(timeout=30):\n    if timeout is None:\n        raise ValueError('per-agent timeout required')\n    return {'waited': True, 'timeout': timeout}\n",
            """
import sys
import workflow
got = workflow.barrier_wait()
if got.get("timeout") is None:
    print(f"RED: barrier_wait={got!r}")
    sys.exit(1)
print("GREEN: timed wait")
sys.exit(0)
""",
        ),
    },
]


def by_id(cid: str) -> dict[str, Any]:
    for row in CANDIDATES:
        if row["id"] == cid:
            return row
    raise KeyError(cid)


def assert_fifteen() -> None:
    ids = [c["id"] for c in CANDIDATES]
    if len(ids) != 15 or len(set(ids)) != 15:
        raise RuntimeError(f"expected 15 unique candidates, got {ids}")
