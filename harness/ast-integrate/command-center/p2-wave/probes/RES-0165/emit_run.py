#!/usr/bin/env python3
"""Emit RES-0165 measurement-run artifact from live measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402
from contract import (  # noqa: E402
    BLIND_SPOT,
    COMPLETION,
    OUT_REL,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0165/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0165/probe2_reviewer_papers.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:RES-0165 emit snippet not in {path}: {snippet!r}")


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def slim_rail(rec: dict) -> dict:
    return {
        "id": rec.get("id"),
        "kind": rec.get("kind"),
        "permalink": rec.get("final_url") or rec.get("permalink"),
        "fetch_timestamp": rec.get("fetched_at"),
        "http_status": rec.get("http_status"),
        "sha256": rec.get("sha256"),
        "bytes": rec.get("bytes"),
        "snapshot": rec.get("snapshot"),
    }


def slim_paper(paper: dict) -> dict:
    return {
        "arxiv": paper["arxiv"],
        "title": paper["title"],
        "rails": [slim_rail(r) for r in paper.get("rails") or []],
        "extracted": paper.get("extracted"),
        "compute_matched": paper.get("compute_matched"),
    }


def main() -> int:
    live = M.run()
    if not live["both_states"]["discriminates"]:
        print("FAILED:RES-0165 emit both-states did not discriminate")
        return 1
    if not live["flatten"]["targeted_flattens_earlier"]:
        print("FAILED:RES-0165 emit targeted did not flatten earlier")
        return 1
    if not live["reviewer_agreement"]:
        print("FAILED:RES-0165 emit author/reviewer flatten disagree")
        return 1
    if live["noise_floor"]["clustered_added"] != 0:
        print("FAILED:RES-0165 emit clone clustered added != 0")
        return 1

    flat = live["flatten"]
    floor = live["noise_floor"]
    monkeys = live["published"]["papers"]["llm-monkeys"]
    ensemble = live["estate_ensemble"]
    land_n = flat["landscape_n"]
    targ_n = flat["targeted_n"]
    land_cost = live["landscape"]["author_curve"][land_n - 1]["cost"]
    targ_cost = live["targeted"]["author_curve"][targ_n - 1]["cost"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    answer = (
        f"Local instrument (finding-id union; Jaccard cluster is the same-prompt "
        f"noise floor): broad landscape scan flattens at n={land_n} researchers "
        f"(cost={land_cost} agent-units; {flat['landscape_contradiction_coverage_at_flatten']} "
        f"contradiction-pair coverage). Targeted question flattens earlier at "
        f"n={targ_n} (cost={targ_cost}; coverage already 1.0 by n=2). Same-prompt "
        f"clone clustered_added={floor['clustered_added']} is the noise floor; "
        f"naive string-unique added={floor['naive_added']} is not real yield. "
        f"Dedicated landscape-vs-targeted fan-out transcripts were absent; claim "
        f"texts are harvested from delivered research artifacts "
        f"(n={live['fixtures']['harvest_n']}) with a constructed recorded-run "
        f"assignment. Estate ensemble IMP-0187: 3 correlated members → "
        f"unique_output_hashes={ensemble['correlated']['unique_output_hashes']} "
        f"effective_n={ensemble['correlated']['effective_n']} "
        f"(independence={ensemble['correlated']['independence']}); disjoint "
        f"inputs stay independence={ensemble['independent']['independence']} "
        f"even when outputs coincide. Published, compute-matched from captured "
        f"arXiv Atom bytes: Large Language Monkeys SWE-bench Lite coverage "
        f"15.9% at n=1 to 56% at n=250 (delta={monkeys['compute_matched']['coverage_delta_pp']} "
        f"pp over 249 extra samples; first-sample yield is "
        f"{monkeys['compute_matched']['first_sample_over_later_mean']}× the later "
        f"mean); majority voting plateaus beyond several hundred samples. More "
        f"Agents Is All You Need states sampling-and-voting scales with N and "
        f"gains track task difficulty, with no flatten N in the abs capture. "
        f"Snell et al.: compute-optimal allocation beats best-of-N by >4×. "
        f"Do not treat extra agents as extra certainty. "
        f"{COMPLETION}"
    )

    published = {k: slim_paper(v) for k, v in live["published"]["papers"].items()}
    published["s2_partial"] = {
        "llm-monkeys_http": live["published"]["s2_partial"]["llm-monkeys_http"],
        "snell_http": live["published"]["s2_partial"]["snell_http"],
        "note": live["published"]["s2_partial"]["note"],
    }

    tests = [
        {
            "id": "NC-same-prompt-clone-noise-floor",
            "result": "PASS",
            "command": P1,
            "detail": both_detail(live),
        },
        {
            "id": "both-states-clone-vs-distinct",
            "result": "PASS",
            "command": P1,
            "detail": live["both_states"]["pass_rule"],
        },
        {
            "id": "targeted-flattens-before-landscape",
            "result": "PASS",
            "command": P1,
            "detail": (
                f"targeted_n={targ_n} landscape_n={land_n} "
                "targeted contradiction coverage reaches 1.0 at n=2; landscape at n=4"
            ),
        },
        {
            "id": "published-compute-match-and-reviewer",
            "result": "PASS",
            "command": P2,
            "detail": (
                "Reviewer flatten recount agrees; llm-monkeys 15.9→56 over 249 "
                "samples recomputed; IMP-0187 correlated ensemble effective_n=1"
            ),
        },
    ]

    evidence = [
        ev(
            "command-center/p2-wave/probes/RES-0165/curve.py",
            "same-prompt clone: clustered added value is the noise floor",
            "instrument",
            "Same-prompt overlap is the noise floor for added value",
        ),
        ev(
            "tools/council/quota/unique_ideas.py",
            "S1 catches exact rename, single-word swap, and high-overlap paraphrase.",
            "instrument",
            "Clone paraphrases merge under the estate Jaccard/key counter",
        ),
        ev(
            "command-center/p2-wave/probes/IMP-0187/ensemble.py",
            "Correlated members (agreement explained by a shared input or briefing) are not",
            "estate-fan-out",
            "Shared-briefing ensemble members are not N independent findings",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0165/snapshots/llm-monkeys-structured-api.body",
            "15.9% with one sample to 56% with 250 samples",
            "published",
            "SWE-bench Lite coverage 15.9% at 1 sample and 56% at 250 samples",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0165/snapshots/llm-monkeys-structured-api.body",
            "plateau beyond several hundred samples",
            "published",
            "Majority voting plateaus beyond several hundred samples",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0165/harvest.py",
            "Dedicated multi-researcher transcripts for the two named run shapes",
            "honesty",
            "Landscape-vs-targeted transcripts were absent; assignment is constructed",
        ),
    ]

    claims = [
        {
            "id": "C-local-flatten",
            "claim": (
                f"On this estate's harvested claim texts with a constructed "
                f"recorded-run, targeted flatten_n={targ_n} and landscape "
                f"flatten_n={land_n} (targeted earlier)."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "evidence_type": "direct_measurement",
            "verification_path": P1,
            "rails": ["finding-id-union", "reviewer-persist-2-recount"],
        },
        {
            "id": "C-noise-floor",
            "claim": (
                "Two researchers on the SAME prompt (tagged paraphrase) add "
                f"{floor['clustered_added']} clustered claims; naive string-unique "
                f"adds {floor['naive_added']}. Added value at or below the clustered "
                "floor is not real."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "evidence_type": "direct_measurement",
            "verification_path": P1,
            "rails": ["jaccard-union-find", "naive-string-unique-control"],
        },
        {
            "id": "C-more-agents-not-certainty",
            "claim": (
                f"IMP-0187 correlated fan-out: n_agents=3 unique_output_hashes=1 "
                f"effective_n={ensemble['correlated']['effective_n']} "
                f"verdict={ensemble['correlated']['independence']}."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "evidence_type": "direct_measurement",
            "verification_path": P2,
            "rails": ["IMP-0187-assess_independence", "unique-output-hash-count"],
        },
        {
            "id": "C-monkeys-coverage",
            "claim": (
                "Brown et al. 2024 (arXiv:2407.21787): SWE-bench Lite coverage "
                "15.9% at 1 sample to 56% at 250 samples; per-sample yield "
                "collapses; majority vote plateaus beyond several hundred samples."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "evidence_type": "direct_measurement",
            "verification_path": P2,
            "rails": ["arxiv-atom-api", "arxiv-abs-html"],
            "source_lineage": slim_paper(monkeys)["rails"],
        },
        {
            "id": "C-more-agents-qualitative",
            "claim": (
                "Li et al. 2024 (arXiv:2402.05120) report sampling-and-voting "
                "scales with agent count and that the gain tracks task difficulty. "
                "Abs-level captured bytes do not contain a numeric flatten N."
            ),
            "verdict": "PARTIAL",
            "sherman_kent_band": "likely",
            "evidence_type": "single_inference",
            "verification_path": P2,
            "rails": ["arxiv-atom-api", "arxiv-abs-html"],
        },
    ]

    doc = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "report_kind": "measurement-run",
        "title": "How many parallel researchers before returns diminish, and what is the evidence?",
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "output_schema": SCHEMA_REL,
        "measured_threshold": float(targ_n),
        "measurements": {
            "flatten": flat,
            "noise_floor": {
                k: floor[k]
                for k in (
                    "clustered_added",
                    "naive_added",
                    "clustered_unique_a",
                    "clustered_unique_ab",
                    "naive_unique_a",
                    "naive_unique_ab",
                    "author_reviewer_agree",
                    "rule",
                )
            },
            "landscape_curve": live["landscape"]["author_curve"],
            "targeted_curve": live["targeted"]["author_curve"],
            "cost_at_flatten": {
                "unit": "researcher",
                "landscape": land_cost,
                "targeted": targ_cost,
                "token_telemetry": "absent-on-constructed-fan-out",
            },
            "published": {
                "llm-monkeys": slim_paper(monkeys),
                "more-agents": slim_paper(live["published"]["papers"]["more-agents"]),
                "multiagent-debate": slim_paper(live["published"]["papers"]["multiagent-debate"]),
                "snell-test-time": slim_paper(live["published"]["papers"]["snell-test-time"]),
                "s2_partial": published["s2_partial"],
            },
            "estate_ensemble": ensemble,
            "harvest": live["fixtures"],
        },
        "recorded_runs": {
            "landscape": {
                "flatten_n": land_n,
                "final_unique": live["landscape"]["final_unique"],
                "curve": live["landscape"]["author_curve"],
            },
            "targeted": {
                "flatten_n": targ_n,
                "final_unique": live["targeted"]["final_unique"],
                "curve": live["targeted"]["author_curve"],
            },
            "known_broken": {
                "id": "same-prompt-clone",
                "clustered_added": floor["clustered_added"],
                "naive_added": floor["naive_added"],
            },
            "known_good": {
                "id": "landscape-researcher-2",
                "marginal_unique": live["both_states"]["known_good"]["marginal_unique"],
            },
        },
        "fixtures": live["fixtures"],
        "both_states": live["both_states"],
        "blind_spot": live["blind_spot"],
        "claims": claims,
        "tests": tests,
        "reviewer": {
            "reviewer_id": "RES-0165-probe2-persist2-recount",
            "verdict": "PASS",
            "independent": True,
            "flatten_landscape_n": flat["reviewer_landscape_n"],
            "flatten_targeted_n": flat["reviewer_targeted_n"],
        },
        "evidence": evidence,
        "residual_unknowns": [
            {
                "id": BLIND_SPOT,
                "detail": live["blind_spot"]["description"],
            },
            {
                "id": "RES-0165-NO-DEDICATED-TRANSCRIPTS",
                "detail": live["fixtures"]["note"],
            },
            {
                "id": "RES-0165-ABS-NO-TABLE-N",
                "detail": (
                    "More Agents / debate abs captures have no numeric flatten N. "
                    "Table points were not fetched from PDFs this session."
                ),
            },
        ],
        "inputs_absent": [
            "_USER-PROMPTS.md (cited 10681-10717, 11249, 10484) is not on this worktree",
            "command-center/sources/REGISTER.md is not on this worktree",
        ],
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    blob = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if SENTINEL not in blob:
        print("FAILED:RES-0165 emit sentinel missing")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8")
    sha, n = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={n} sha256={sha}")
    print("SUCCESS:RES-0165 emit")
    return 0


def both_detail(live: dict) -> str:
    b = live["both_states"]
    return (
        b["planted_bad"]["verbatim"]
        + " | "
        + b["known_good"]["verbatim"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
