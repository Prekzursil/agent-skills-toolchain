#!/usr/bin/env python3
"""Deterministic M-NN known-case briefing pack plus inverted/reconciled packs.

Original 17-DECISION-LOG.md / 13-ARCHITECTURE-CANDIDATES.md are absent on
this worktree. The pack reconstructs the documented known case so the
check can fire on a stale-open premise and stay silent on a current one
in the SAME pack.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
KNOWN = FIX / "known-case"
INVERTED = FIX / "inverted"
RECONCILED = FIX / "reconciled"

OPTION_IDS = list(range(1, 34))  # 33 option-universe family-M ids
# 38 mechanism cards, historically M-3..M-40; 31-way overlap with options is 3..33.
MECH_IDS = list(range(3, 41))

LOG_NAME = "17-DECISION-LOG.md"
OPTION_NAME = "07-OPTION-UNIVERSE.md"
ARCH_NAME = "13-ARCHITECTURE-CANDIDATES.md"


def _pad_log(collision_line: str, *, mech_ok: bool) -> str:
    rows = [f"- {i:04d} prior decision entry (unrelated scope)." for i in range(1, 175)]
    rows.append(collision_line.rstrip())
    if mech_ok:
        rows.append(
            "- 0176 Re-prefix applied 2026-08-07 18:41; namespace is now MECH-NN."
        )
    body = "\n".join(rows) + "\n"
    if not mech_ok and "MECH" in body:
        raise RuntimeError("stale log must contain zero MECH tokens")
    return body


def option_universe() -> str:
    lines = ["# 07-OPTION-UNIVERSE family M (fixture reconstruction)\n"]
    for n in OPTION_IDS:
        lines.append(f"- M-{n}: option card {n} in family M\n")
    return "".join(lines)


def architecture_reprefixed() -> str:
    lines = [
        "# 13-ARCHITECTURE-CANDIDATES mechanism cards (fixture reconstruction)\n",
        "# Re-prefixed 2026-08-07. Historical metavariable name M-NN is not an id.\n",
    ]
    for n in MECH_IDS:
        lines.append(f"- MECH-{n}: mechanism card {n}\n")
    return "".join(lines)


def architecture_bare() -> str:
    lines = ["# 13-ARCHITECTURE-CANDIDATES mechanism cards (pre-fix fixture)\n"]
    for n in MECH_IDS:
        lines.append(f"- M-{n}: mechanism card {n} (pre-reprefix)\n")
    return "".join(lines)


def stale_log() -> str:
    return _pad_log(
        "The 31-way M-NN option-id collision between 07-OPTION-UNIVERSE family M "
        "and 13-ARCHITECTURE-CANDIDATES mechanism cards is live and Queued as P2-09.",
        mech_ok=False,
    )


def reconciled_log() -> str:
    return _pad_log(
        "The 31-way M-NN option-id collision was re-prefixed to MECH-NN on 2026-08-07. "
        "Literal collision count is 0. P2-09 is closed.",
        mech_ok=True,
    )


def _premises(*, open_expect: bool, reprefix_expect: bool) -> list[dict]:
    return [
        {
            "id": "P-STALE-MNN-OPEN",
            "text": "The 31-way M-NN option-id collision is live and queued as P2-09.",
            "asserted_status": "open-problem",
            "check": "mnn-collision-open",
            "briefing_rel": f"briefing/{LOG_NAME}",
            "artifact_rels": [
                f"artifacts/{OPTION_NAME}",
                f"artifacts/{ARCH_NAME}",
            ],
            "expect_fire": open_expect,
        },
        {
            "id": "P-CURRENT-MECH-REPREFIX",
            "text": (
                "13-ARCHITECTURE-CANDIDATES has used MECH-NN since 2026-08-07 "
                "and carries zero bare M-NN tokens."
            ),
            "asserted_status": "current-fact",
            "check": "mech-reprefix-applied",
            "briefing_rel": f"briefing/{LOG_NAME}",
            "artifact_rels": [f"artifacts/{ARCH_NAME}"],
            "expect_fire": reprefix_expect,
        },
    ]


def pack_doc(kind: str) -> dict:
    expects = {
        "known-case": (True, False),
        "inverted": (False, True),
        "reconciled": (False, False),
    }
    if kind not in expects:
        raise ValueError(kind)
    open_expect, reprefix_expect = expects[kind]
    return {
        "id": f"RES-0188-{kind}",
        "kind": kind,
        "premises": _premises(open_expect=open_expect, reprefix_expect=reprefix_expect),
    }


def write_tree(root: Path, *, log: str, architecture: str, pack_kind: str) -> None:
    (root / "briefing").mkdir(parents=True, exist_ok=True)
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "briefing" / LOG_NAME).write_text(log, encoding="utf-8")
    (root / "artifacts" / OPTION_NAME).write_text(option_universe(), encoding="utf-8")
    (root / "artifacts" / ARCH_NAME).write_text(architecture, encoding="utf-8")
    (root / "pack.json").write_text(
        json.dumps(pack_doc(pack_kind), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ensure_fixtures() -> dict[str, Path]:
    write_tree(
        KNOWN,
        log=stale_log(),
        architecture=architecture_reprefixed(),
        pack_kind="known-case",
    )
    write_tree(
        INVERTED,
        log=stale_log(),
        architecture=architecture_bare(),
        pack_kind="inverted",
    )
    write_tree(
        RECONCILED,
        log=reconciled_log(),
        architecture=architecture_reprefixed(),
        pack_kind="reconciled",
    )
    return {"known-case": KNOWN, "inverted": INVERTED, "reconciled": RECONCILED}


if __name__ == "__main__":
    paths = ensure_fixtures()
    for k, p in paths.items():
        log = (p / "briefing" / LOG_NAME).read_text(encoding="utf-8")
        print(f"{k} dir={p.relative_to(HERE)} log_lines={log.count(chr(10))}")
