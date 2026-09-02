"""Post-processor: declared invariants over one run's own output.

A contradictory output is classified detector-failure. No number from that
run is published. The invariant set is loaded from invariants.json, which is
the document written down before any run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SPEC = json.loads((HERE / "invariants.json").read_text(encoding="utf-8"))
INVARIANTS: list[dict[str, Any]] = list(SPEC["invariants"])

ALL_HIT = "all_hit"
EMPTY_INTERSECTION = "empty_intersection"


@dataclass
class RunOutput:
    counts: dict[str, Any]
    claims: set[str] = field(default_factory=set)
    raw: str = ""
    n_universe: int = 7


@dataclass
class CheckResult:
    ok: bool
    classification: str | None
    violated: list[str]
    message: str
    published_numbers: dict[str, int] | None
    raw_held: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "classification": self.classification,
            "violated_invariants": list(self.violated),
            "message": self.message,
            "published_numbers": self.published_numbers,
        }


def as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if ("\n" in value) or ("\r" in value) or ("\n" in text):
            return None
        if text.startswith("-") and text[1:].isdigit():
            return int(text)
        if text.isdigit():
            return int(text)
        return None
    return None


def check_invariants(
    run: RunOutput, invariants: list[dict[str, Any]] | None = None
) -> CheckResult:
    invs = list(INVARIANTS if invariants is None else invariants)
    violated: list[str] = []
    messages: list[str] = []
    parsed: dict[str, int] = {}
    well_formed = True
    for key, val in (run.counts or {}).items():
        n = as_int(val)
        if n is None:
            well_formed = False
        else:
            parsed[key] = n

    for inv in invs:
        iid = str(inv["id"])
        kind = str(inv["kind"])
        statement = str(inv.get("statement") or iid)
        if kind == "well-formed":
            if not well_formed:
                violated.append(iid)
                messages.append(
                    f"DETECTOR-FAILURE: violated invariant {iid}: {statement}"
                )
        elif kind == "sum":
            if not well_formed:
                continue
            parts = [parsed.get(p) for p in inv["parts"]]
            total = parsed.get(inv["total"])
            if any(p is None for p in parts) or total is None:
                violated.append(iid)
                messages.append(
                    f"DETECTOR-FAILURE: violated invariant {iid}: "
                    f"missing counts for sum. {statement}"
                )
            elif int(sum(int(p) for p in parts if p is not None)) != int(total):
                s = sum(int(p) for p in parts if p is not None)
                violated.append(iid)
                messages.append(
                    f"DETECTOR-FAILURE: violated invariant {iid}: "
                    f"{'+'.join(inv['parts'])}={s} != {inv['total']}={total}. "
                    f"{statement}"
                )
        elif kind == "subset":
            if not well_formed:
                continue
            sub = parsed.get(inv["subset"])
            sup = parsed.get(inv["superset"])
            if sub is None or sup is None:
                violated.append(iid)
                messages.append(
                    f"DETECTOR-FAILURE: violated invariant {iid}: "
                    f"missing subset/superset counts. {statement}"
                )
            elif int(sub) > int(sup):
                violated.append(iid)
                messages.append(
                    f"DETECTOR-FAILURE: violated invariant {iid}: "
                    f"{inv['subset']}={sub} > {inv['superset']}={sup}. "
                    f"{statement}"
                )
        elif kind == "mutex-claims":
            present = [c for c in inv["claims"] if c in run.claims]
            if len(present) >= 2:
                violated.append(iid)
                messages.append(
                    f"DETECTOR-FAILURE: violated invariant {iid}: "
                    f"claims {present} are mutually exclusive. {statement}"
                )

    if violated:
        return CheckResult(
            ok=False,
            classification="detector-failure",
            violated=violated,
            message="; ".join(messages),
            published_numbers=None,
            raw_held=run.raw,
        )
    return CheckResult(
        ok=True,
        classification=None,
        violated=[],
        message="invariants held",
        published_numbers=dict(parsed),
        raw_held=run.raw,
    )
