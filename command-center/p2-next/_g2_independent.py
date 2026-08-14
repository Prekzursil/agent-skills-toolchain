"""Grounding round 2: an INDEPENDENT third derivation of the blocked/split counts.

Deliberately does NOT import vendor_satisfiability.py or split_review_gate.py. Reads the
committed blobs itself, discovers the population itself, and classifies with its own predicate,
so agreement with the two shipped instruments is a real second signal and not an echo.

Shape is asserted before anything is counted. The first version of this probe read cat["units"],
which does not exist, and silently reported "10 units" -- the catalog's top-level key count.
Every collection is now size-asserted so a wrong collection is loud instead of plausible.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SHIPPED_REL = "command-center/p2-next/VENDOR-SATISFIABILITY.json"


def blob(rev: str, rel: str) -> str | None:
    r = subprocess.run(
        ["git", "show", f"{rev}:{rel}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return r.stdout if r.returncode == 0 else None


def batch_blobs(rev: str, rels: list[str]) -> dict[str, str]:
    """Read many blobs in ONE git process. 2007 `git show` calls did not finish in 600s."""
    tracked = set(
        subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", rev],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
    )
    want = [r for r in rels if r in tracked]
    if not want:
        return {}
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=REPO,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    stdin = "".join(f"{rev}:{r}\n" for r in want).encode()
    raw, _ = proc.communicate(stdin)
    res, pos = {}, 0
    for rel in want:
        nl = raw.index(b"\n", pos)
        header = raw[pos:nl].decode()
        if header.endswith("missing"):
            pos = nl + 1
            continue
        size = int(header.split()[2])
        body = raw[nl + 1 : nl + 1 + size]
        res[rel] = body.decode("utf-8", "replace")
        pos = nl + 1 + size + 1
    return res


def main() -> None:
    out: dict = {}
    cat = json.loads(blob("HEAD", CATALOG_REL) or "{}")
    if "work_units" not in cat:
        raise SystemExit("FAILED:g2 catalog has no work_units key -- shape changed")
    units = cat["work_units"]
    if not isinstance(units, list) or len(units) < 100:
        raise SystemExit(f"FAILED:g2 work_units implausible: len={len(units)}")
    print(f"catalog work_units = {len(units)}")
    out["catalog_units"] = len(units)

    # ---- discover the population from RECEIPTS at each declared output_path ----
    cand = [u for u in units if str(u.get("output_path", "")).lower().endswith(".json")]
    print(f"units with a .json output_path = {len(cand)}")
    out["json_output_paths"] = len(cand)

    XV = re.compile(
        r"cross[-_ ]?vendor|cross[-_ ]?model|different vendor|other vendor|another vendor"
        r"|separate vendor|non[-_ ]?anthropic|non[-_ ]?openai",
        re.I,
    )
    OPENAI = re.compile(r"\bopenai\b|\bcodex\b|\bgpt-?5\b", re.I)
    ANTHROPIC = re.compile(r"\banthropic\b|\bclaude\b|\bopus\b", re.I)

    blobs = batch_blobs("HEAD", [u["output_path"] for u in cand])
    print(f"receipt blobs read in one batch = {len(blobs)}")

    states = Counter()
    rows, present = [], 0
    for u in cand:
        txt = blobs.get(u["output_path"])
        if txt is None:
            continue
        present += 1
        try:
            rec = json.loads(txt)
        except json.JSONDecodeError:
            continue
        st = str(rec.get("state", "")).upper()
        states[st] += 1
        if st not in ("BLOCKED", "FAILED"):
            continue

        uid = u.get("id")
        # Producer: read the `vendor` FIELD, never the serialized object.
        # v1 of this probe regexed json.dumps(produced_by) and matched the ROLE prose
        # ("catalog assigns openai/gpt-5-codex; executed by anthropic/opus"), flipping four
        # anthropic-produced units to openai and moving the headline 42 -> 38. That is
        # use-vs-mention: the receipt NAMES the other vendor, it was not produced by it.
        pb = rec.get("produced_by")
        if isinstance(pb, dict):
            prod_v = str(pb.get("vendor", "")).strip().lower() or "anthropic"
        else:
            prod_v = "anthropic"  # 2 receipts carry no produced_by; shipped instrument assumes same
        if prod_v not in ("anthropic", "openai"):
            raise SystemExit(f"FAILED:g2 {uid} unknown produced_by.vendor={prod_v!r}")

        # demand text: every field that can carry a review constraint
        demand = " ".join(
            [
                json.dumps(u.get("reviewer_requirement", "")),
                json.dumps(rec.get("failure", "")),
                json.dumps(rec.get("classification_tags", "")),
                json.dumps(rec.get("review_gate", "")),
            ]
        )
        has_xv = bool(XV.search(demand))
        n_o, n_a = bool(OPENAI.search(demand)), bool(ANTHROPIC.search(demand))

        if has_xv:
            need = "openai" if prod_v == "anthropic" else "anthropic"
        elif n_o and not n_a:
            need = "openai"
        elif n_a and not n_o:
            need = "anthropic"
        else:
            need = "any"

        v = "RAIL_BLOCKED" if need == "openai" else "SATISFIABLE_NOW"
        rows.append(
            {
                "id": uid,
                "state": st,
                "producer": prod_v,
                "need": need,
                "verdict": v,
                "xv_clause": has_xv,
            }
        )

    print(f"receipts present at HEAD = {present}")
    print(f"RECEIPT STATE CENSUS: {dict(states)}")
    print(f"BLOCKED/FAILED population = {len(rows)}")
    out["receipts_present"] = present
    out["state_census"] = dict(states)
    out["population"] = len(rows)

    verdict = Counter(r["verdict"] for r in rows)
    print(f"\nMY  VERDICT: {dict(verdict)}")
    out["independent_verdict"] = dict(verdict)
    out["rows"] = rows

    shipped = json.loads(blob("HEAD", SHIPPED_REL) or "{}")
    print(
        f"SHIPPED VERDICT: {shipped['verdict_counts']}  (blocked_units={shipped['blocked_units']})"
    )
    out["shipped_verdict"] = shipped["verdict_counts"]

    mine = {r["id"]: r["verdict"] for r in rows}
    theirs = {u["id"]: u["verdict"] for u in shipped["units"]}
    only_mine = sorted(set(mine) - set(theirs))
    only_theirs = sorted(set(theirs) - set(mine))
    disagree = sorted(i for i in set(mine) & set(theirs) if mine[i] != theirs[i])
    print(f"\nonly in MY population : {only_mine}")
    print(f"only in SHIPPED       : {only_theirs}")
    print(f"per-unit DISAGREEMENTS: {len(disagree)}")
    for i in disagree:
        r = next(x for x in rows if x["id"] == i)
        print(
            f"   {i}: mine={mine[i]} theirs={theirs[i]} need={r['need']} xv={r['xv_clause']}"
        )
    out.update(only_mine=only_mine, only_theirs=only_theirs, disagreements=disagree)

    Path(REPO / "command-center/p2-next/G2-INDEPENDENT.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8", newline="\n"
    )
    print("\nwrote command-center/p2-next/G2-INDEPENDENT.json")


if __name__ == "__main__":
    main()
