"""Run every declared method on every fixture; disagreement + flip sweep."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import fixtures as F
import recount as R
import tabulator as T

HERE = Path(__file__).resolve().parent
REPORT_PATH = HERE / "runtime" / "simulation-report.json"


def demote_first_to_last(ranking: list[str]) -> list[str]:
    """Single-ballot flip: former first becomes last; others shift up."""
    if len(ranking) < 2:
        return list(ranking)
    return list(ranking[1:]) + [ranking[0]]


def flipped_profile(profile: dict, voter: str) -> dict:
    p = deepcopy(profile)
    found = False
    for b in p["ballots"]:
        if b["voter"] == voter:
            b["ranking"] = demote_first_to_last(list(b["ranking"]))
            found = True
            break
    if not found:
        raise KeyError(voter)
    return p


def disagreeing_methods(w: dict[str, str]) -> list[str]:
    vals = set(w.values())
    if len(vals) <= 1:
        return []
    return sorted(w)


def per_fixture(profile: dict, engine) -> dict:
    w = engine.winners(profile)
    wset = sorted(set(w.values()))
    disagree = len(wset) > 1
    n_flips = 0
    changes: dict[str, int] = {m: 0 for m in T.METHODS}
    changing: dict[str, list[str]] = {m: [] for m in T.METHODS}
    for b in profile["ballots"]:
        n_flips += 1
        fp = flipped_profile(profile, b["voter"])
        fw = engine.winners(fp)
        for m in T.METHODS:
            if fw[m] != w[m]:
                changes[m] += 1
                changing[m].append(b["voter"])
    return {
        "id": profile["id"],
        "role": profile["role"],
        "n_ballots": profile["n_ballots"],
        "candidates": list(profile["candidates"]),
        "winners": w,
        "winner_set": wset,
        "methods_disagree": disagree,
        "n_flips": n_flips,
        "flip_changes": changes,
        "flip_changing_voters": changing,
    }


def sensitivity_table(rows: list[dict]) -> list[dict]:
    table = []
    for m in T.METHODS:
        n_flips = sum(r["n_flips"] for r in rows)
        n_changes = sum(r["flip_changes"][m] for r in rows)
        table.append(
            {
                "method": m,
                "n_flips_tried": n_flips,
                "n_winner_changes": n_changes,
                "rate": (n_changes / n_flips) if n_flips else 0.0,
            }
        )
    return table


def most_sensitive(table: list[dict]) -> dict:
    """Max n_winner_changes, then max rate, then lex-smallest method id."""
    ranked = sorted(
        table,
        key=lambda r: (-int(r["n_winner_changes"]), -float(r["rate"]), r["method"]),
    )
    top = ranked[0]
    tied = [
        r["method"]
        for r in table
        if r["n_winner_changes"] == top["n_winner_changes"]
        and abs(float(r["rate"]) - float(top["rate"])) < 1e-15
    ]
    return {
        "method": top["method"],
        "n_winner_changes": top["n_winner_changes"],
        "rate": top["rate"],
        "tied_methods": sorted(tied),
        "rule": "max n_winner_changes, then max rate, then lex-smallest method id",
    }


def report(engine=T) -> dict:
    F.dump()
    profiles = F.load()
    rows = [per_fixture(p, engine) for p in profiles]
    n = len(rows)
    n_dis = sum(1 for r in rows if r["methods_disagree"])
    table = sensitivity_table(rows)
    return {
        "unit_id": "CNL-0119",
        "n_fixtures": n,
        "n_disagree": n_dis,
        "n_agree": n - n_dis,
        "disagreement_rate": n_dis / n if n else 0.0,
        "disagreeing_fixture_ids": [r["id"] for r in rows if r["methods_disagree"]],
        "agreeing_fixture_ids": [r["id"] for r in rows if not r["methods_disagree"]],
        "methods": list(T.METHODS),
        "sensitivity_table": table,
        "most_sensitive": most_sensitive(table),
        "fixtures": rows,
    }


def dump_report(engine=T) -> dict:
    doc = report(engine)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return doc


def engines_match() -> None:
    profiles = F.load()
    for p in profiles:
        a = T.winners(p)
        b = R.winners(p)
        if a != b:
            raise SystemExit(f"tabulator/recount mismatch on {p['id']}: {a} vs {b}")


if __name__ == "__main__":
    F.dump()
    engines_match()
    doc = dump_report()
    print(
        f"n_fixtures={doc['n_fixtures']} n_disagree={doc['n_disagree']} "
        f"rate={doc['disagreement_rate']:.6f} "
        f"most_sensitive={doc['most_sensitive']['method']} "
        f"changes={doc['most_sensitive']['n_winner_changes']}"
    )
    for row in doc["fixtures"]:
        print(f"  {row['id']} disagree={row['methods_disagree']} winners={row['winners']}")
    print("SUCCESS:CNL-0119-simulate")
