"""Premature-convergence detector: quotas at convergence, never labels (IMP-0323)."""
from __future__ import annotations

from typing import Any


class Result(dict):
    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def as_dict(self) -> dict[str, Any]:
        return dict(self)


DECISION_BASIS = "quota-at-convergence"
SPEC_ANCHOR = "IMP-0323"


def _ids(items: list | None) -> set[str]:
    out: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("canonical_id") or item.get("id") or "")
        if ident and ident != "None":
            out.add(ident)
    return out


def _fire_decision(converged, ideas_met, objections_met):
    return bool(converged) and not (bool(ideas_met) and bool(objections_met))


def detect(run: Any, *args: Any, **kwargs: Any) -> Result:
    if not isinstance(run, dict):
        return Result(status="NOT-CHECKED", fired=False, decision_basis="not-a-run", quota={})
    divergence = run.get("divergence")
    if not isinstance(divergence, dict) or "min_unique_ideas" not in divergence or "min_objections" not in divergence:
        n_i = len(_ids(run.get("ideas")))
        n_o = len(_ids(run.get("objections")))
        return Result(
            id=run.get("id"),
            status="NOT-CHECKED",
            fired=False,
            decision_basis="undeclared-quotas",
            quota={
                "round_index_recorded": run.get("round_index"),
                "unique_ideas_attained": n_i,
                "min_unique_ideas": (divergence or {}).get("min_unique_ideas") if isinstance(divergence, dict) else None,
                "objections_attained": n_o,
                "min_objections": (divergence or {}).get("min_objections") if isinstance(divergence, dict) else None,
                "quotas_met": False,
            },
        )
    n_i = len(_ids(run.get("ideas")))
    n_o = len(_ids(run.get("objections")))
    min_i = int(divergence["min_unique_ideas"])
    min_o = int(divergence["min_objections"])
    ideas_met = n_i >= min_i
    objections_met = n_o >= min_o
    converged = bool(run.get("converged"))
    if not converged:
        return Result(
            id=run.get("id"),
            status="NOT-CHECKED",
            fired=False,
            decision_basis="not-converged",
            quota={
                "round_index_recorded": run.get("round_index"),
                "unique_ideas_attained": n_i,
                "min_unique_ideas": min_i,
                "objections_attained": n_o,
                "min_objections": min_o,
                "quotas_met": False,
            },
        )
    fired = _fire_decision(converged, ideas_met, objections_met)
    met = ideas_met and objections_met
    return Result(
        id=run.get("id"),
        status="FIRE" if fired else "SILENT",
        fired=fired,
        decision_basis="quota-unmet-at-convergence" if fired else "quotas-met",
        quota={
            "round_index_recorded": run.get("round_index"),
            "unique_ideas_attained": n_i,
            "min_unique_ideas": min_i,
            "objections_attained": n_o,
            "min_objections": min_o,
            "quotas_met": met,
        },
    )


__all__ = ["DECISION_BASIS", "Result", "SPEC_ANCHOR", "detect", "_fire_decision"]
