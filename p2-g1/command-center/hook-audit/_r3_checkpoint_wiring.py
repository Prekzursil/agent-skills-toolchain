#!/usr/bin/env python3
r"""_r3_checkpoint_wiring.py -- settle the one dark-hook disagreement both lanes left open.

Round 1 called `hooks/checkpoint/` DARK; the grounding lane recorded it as wired on the
P3 (`~/.agents/harness`) plane. Round 1 declined to pick a side and excluded it from the
inert set, naming the settling experiment: read the P3 dispatcher's module registry.

Run here. `HarnessDispatcher.__init__` builds `self.modules` from
`build_default_modules(...)`, and those modules are CLASSES declared inside
`~/.agents/harness/modules.py` carrying a `name = "<snake_case>"` attribute -- in-process
Python objects, not `hooks/<dir>/<script>.py` subprocesses. So a bare `checkpoint` on that
plane can be a module NAME that has nothing to do with the `hooks/checkpoint/` directory.
That is a use-vs-mention question and it needs the two shapes counted separately:

  PATH-SHAPED    `hooks/<dir>/...` -- an actual reference to the directory's script
  NAME-SHAPED    the bare token `<dir>` (or its snake_case form) anywhere else

A dir with 0 path-shaped hits and >0 name-shaped hits is NOT evidence of wiring; it is
evidence of a name collision, which is exactly what "the grounding lane says P3-wired"
would look like if it were wrong.

CONTROLS, both required or the run publishes nothing:
  * POSITIVE  `wire-check` is known path-wired -> must show path-shaped hits.
  * NEGATIVE  a synthetic dir name that exists nowhere -> must show zero of both.

Read-only. Reads only the `hooks` key of the live settings.json (it holds credentials
elsewhere and is never serialized whole). Writes R3-CHECKPOINT-WIRING.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "R3-CHECKPOINT-WIRING.json"
HOME = Path.home()

TARGETS = ["checkpoint", "edit-checkpoints", "wire-check", "zzz-no-such-hook-dir"]
POSITIVE_CONTROL = "wire-check"
NEGATIVE_CONTROL = "zzz-no-such-hook-dir"


def surfaces() -> dict[str, str]:
    """Every place a hook can be wired, as text. Missing surface -> empty string, and the
    byte size is reported so a failed read is not mistaken for a surface that mentions
    nothing."""
    out: dict[str, str] = {}

    live_settings = HOME / ".claude" / "settings.json"
    try:
        blob = json.loads(live_settings.read_text(encoding="utf-8"))
        out["live-settings.hooks"] = json.dumps(blob.get("hooks", {}), indent=1)
    except (OSError, ValueError):
        out["live-settings.hooks"] = ""

    for label, p in (
        ("live-manifest", HOME / ".claude" / "hooks" / "_dispatch" / "manifest.json"),
        ("repo-manifest", REPO / "hooks" / "_dispatch" / "manifest.json"),
        ("repo-hooks.json", REPO / "hooks" / "hooks.json"),
        (
            "repo-agent-self-settings",
            REPO / "agent-self" / "config" / "settings.json",
        ),
    ):
        try:
            out[label] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            out[label] = ""

    p3 = HOME / ".agents" / "harness"
    text = []
    for f in sorted(p3.glob("*.py")):
        try:
            text.append(
                f"### {f.name}\n" + f.read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            continue
    out["P3-agents-harness"] = "\n".join(text)
    return out


def scan(name: str, surf: dict[str, str]) -> dict:
    # `<dir>/<file>.<ext>`, with or without a `hooks/` prefix. The first version of this
    # regex REQUIRED the prefix and scored the known-path-wired positive control at 0,
    # because a manifest `script` field is relative (`wire-check/check.py`). The control
    # failed closed and the run published nothing -- which is the only reason the bug is
    # in this comment instead of in the verdict.
    esc = re.escape(name).replace(r"\-", "[-_]")
    path_re = re.compile(
        r"(?<![\w-])" + esc + r"[\\/][\w.-]+\.(?:py|ps1|js|mjs|sh)\b", re.IGNORECASE
    )
    name_re = re.compile(
        r"(?<![\w-])" + re.escape(name).replace(r"\-", "[-_]") + r"(?![\w-])",
        re.IGNORECASE,
    )
    res: dict = {"path_shaped": {}, "name_shaped": {}, "name_shaped_samples": []}
    for label, text in surf.items():
        if not text:
            continue
        ph = path_re.findall(text)
        nh = [
            ln.strip()[:150]
            for ln in text.splitlines()
            if name_re.search(ln) and not path_re.search(ln)
        ]
        if ph:
            res["path_shaped"][label] = len(ph)
        if nh:
            res["name_shaped"][label] = len(nh)
            res["name_shaped_samples"].extend(f"[{label}] {x}" for x in nh[:3])
    res["path_total"] = sum(res["path_shaped"].values())
    res["name_total"] = sum(res["name_shaped"].values())
    res["verdict"] = (
        "PATH-WIRED"
        if res["path_total"]
        else ("NAME-ONLY (collision, not wiring)" if res["name_total"] else "ABSENT")
    )
    return res


def main() -> int:
    surf = surfaces()
    sizes = {k: len(v) for k, v in surf.items()}
    if sum(sizes.values()) == 0:
        print("FAILED:r3-checkpoint-wiring every wiring surface read as empty")
        return 1

    ckdir = REPO / "hooks" / "checkpoint"
    scripts = sorted(p.name for p in ckdir.glob("*.py")) if ckdir.is_dir() else []

    results = {t: scan(t, surf) for t in TARGETS}
    res = {
        "surface_bytes": sizes,
        "hooks_checkpoint_dir_exists": ckdir.is_dir(),
        "hooks_checkpoint_scripts": scripts,
        "targets": results,
        "control_positive_is_path_wired": results[POSITIVE_CONTROL]["path_total"] > 0,
        "control_negative_is_absent": results[NEGATIVE_CONTROL]["verdict"] == "ABSENT",
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")

    for k, v in sizes.items():
        print(f"   surface {k:28s} {v:>8d} B")
    print(f"   hooks/checkpoint/ exists={ckdir.is_dir()} scripts={scripts}")
    for t in TARGETS:
        r = results[t]
        print(
            f"== {t:24s} path={r['path_total']:>3d} name={r['name_total']:>4d}  {r['verdict']}"
        )
        for s in r["name_shaped_samples"][:3]:
            print(f"      {s[:120]}")
    print(
        f"   CONTROL positive({POSITIVE_CONTROL}) path-wired="
        f"{res['control_positive_is_path_wired']} (must be True)  "
        f"negative absent={res['control_negative_is_absent']} (must be True)"
    )
    if not (
        res["control_positive_is_path_wired"] and res["control_negative_is_absent"]
    ):
        print(
            "FAILED:r3-checkpoint-wiring a control misbehaved -- no verdict is readable"
        )
        return 1
    print("SUCCESS:r3-checkpoint-wiring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
