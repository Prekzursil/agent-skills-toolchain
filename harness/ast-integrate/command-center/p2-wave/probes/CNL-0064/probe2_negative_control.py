#!/usr/bin/env python3
"""Probe 2: independent recount + both-states publication check."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import publication as P  # noqa: E402
import recount as R  # noqa: E402
import tabulate as T  # noqa: E402
from fixtures_lib import councils, load_all  # noqa: E402

ART_REL = (
    "command-center/design/council/"
    "CNL-0064-weighted-voting-weight-provenance-and-post-hoc-audit.md"
)
SCHEMA_REL = "command-center/p2-wave/probes/CNL-0064/note.schema.json"
DEP_PATHS = {
    "CNL-0023": (
        "command-center/design/council/"
        "CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md"
    ),
    "CNL-0058": (
        "command-center/design/council/"
        "CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md"
    ),
}
CATALOG_INPUTS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]


def resolve_anchor(repo: Path, rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = repo / rel
    if not path.is_file():
        return False, f"missing:{rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"line-oob:{rel}:{line}:n={len(lines)}"
    if snippet not in lines[line - 1]:
        return False, f"snippet-miss:{rel}:{line}"
    return True, f"{rel}:{line}"


def _excess(delta: dict) -> str:
    return str(
        delta.get("excess_weight_on_weighted_winner")
        or delta.get("excess_weight_on_weighted_winner")
        or ""
    )


def main() -> int:
    disagreements = []
    for fid, fixture in councils().items():
        author = T.decide(fixture)
        review = R.recount(fixture)
        if bool(author.get("rejected")) != bool(review.get("rejected")):
            disagreements.append(
                {"id": fid, "why": "reject-mismatch", "author": author, "review": review}
            )
            continue
        if author.get("rejected"):
            continue
        if review.get("weighted_winner") != author["weighted_result"]["winner"]:
            disagreements.append({"id": fid, "why": "weighted-winner"})
        if review.get("equal_winner") != author["equal_weight_counterfactual"]["winner"]:
            disagreements.append({"id": fid, "why": "equal-winner"})
        if bool(review.get("weighting_flip")) != bool(author.get("weighting_flip")):
            disagreements.append({"id": fid, "why": "flip"})
    if disagreements:
        print("FAILED:CNL-0064-probe2 recount disagrees with tabulate")
        print(json.dumps(disagreements, sort_keys=True)[:2000])
        return 1
    print("recount_agrees=True")

    unpublished = load_all()["unpublished-delta"]
    fired_bad = P.fires(unpublished)
    print(f"unpublished_fires={fired_bad} defects={P.defects(unpublished)}")
    if not fired_bad:
        print("FAILED:CNL-0064-probe2 unpublished-delta did not fire")
        return 1

    stable_live = T.decide(councils()["weighted-stable"])
    fired_good = P.fires(stable_live, stable_live)
    print(
        f"complete_audit_fires={fired_good} defects={P.defects(stable_live, stable_live)}"
    )
    if fired_good:
        print("FAILED:CNL-0064-probe2 complete audit was not silent")
        return 1

    equal_live = T.decide(councils()["equal-weight"])
    excess = _excess(equal_live["weighting_delta"])
    print(
        "negative-control target=equal-weight "
        f"weighting_flip={equal_live.get('weighting_flip')} "
        f"excess={excess} rejected={equal_live.get('rejected')}"
    )
    if equal_live.get("weighting_flip") or equal_live.get("rejected"):
        print("FAILED:CNL-0064-probe2 equal-weight was flagged (enumerator wrong)")
        return 1
    if excess not in {"0/1", "0"}:
        print(f"FAILED:CNL-0064-probe2 equal-weight excess was not zero ({excess})")
        return 1

    missing = T.decide(councils()["missing-provenance"])
    print(
        "negative-control target=missing-provenance "
        f"rejected={missing.get('rejected')} code={missing.get('reject_code')}"
    )
    if not missing.get("rejected") or missing.get("reject_code") != "MISSING_PROVENANCE":
        print("FAILED:CNL-0064-probe2 missing provenance was not rejected")
        return 1

    art = REPO / ART_REL
    if not art.is_file():
        print("FAILED:CNL-0064-probe2 design note missing")
        return 1
    text = art.read_text(encoding="utf-8")
    note = json.loads(text)
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(note)
    if "SUCCESS:CNL-0064" not in text:
        print("FAILED:CNL-0064-probe2 sentinel-absent")
        return 1
    if str(note.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CNL-0064-probe2 self-declared {note.get('state')}")
        return 1

    rev = note.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:CNL-0064-probe2 reviewer not independent")
        return 1
    if rev.get("scope_not_agreement") is not True:
        print("FAILED:CNL-0064-probe2 reviewer missing scope_not_agreement")
        return 1
    if rev.get("re_ran_both_states") is not True:
        print("FAILED:CNL-0064-probe2 reviewer did not re-run both-states")
        return 1

    deps = note.get("dependency_status") or {}
    for uid, rel in DEP_PATHS.items():
        live = (REPO / rel).is_file()
        claimed = bool((deps.get(uid) or {}).get("artifact_present"))
        if claimed != live:
            print(
                f"FAILED:CNL-0064-probe2 dependency honesty {uid} "
                f"claimed={claimed} live={live}"
            )
            return 1
        print(f"dep {uid} present={live} claimed={claimed}")

    inputs = note.get("catalog_inputs_on_tree") or {}
    for path in CATALOG_INPUTS:
        if inputs.get(path) is True:
            print(
                f"FAILED:CNL-0064-probe2 overclaim: catalog input marked present {path}"
            )
            return 1

    evidence = note.get("evidence") or []
    if len(evidence) < 2:
        print("FAILED:CNL-0064-probe2 evidence < 2")
        return 1
    kinds = {str(row.get("kind") or "") for row in evidence}
    if len(kinds) < 2:
        print(f"FAILED:CNL-0064-probe2 evidence kinds not independent: {kinds}")
        return 1
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        ok, why = resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            print("FAILED:CNL-0064-probe2 unresolved anchor")
            return 1

    mutant = copy.deepcopy(note)
    mutant.pop("negative_controls", None)
    try:
        jsonschema.Draft7Validator(schema).validate(mutant)
        print("FAILED:CNL-0064-probe2 schema accepted missing negative_controls")
        return 1
    except jsonschema.ValidationError:
        print("schema_mutant_rejected=True")

    print(
        "both-states unpublished_fires=True complete_silent=True "
        "recount_independent=True"
    )
    print("SUCCESS:CNL-0064-probe2 recount both-states negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
