#!/usr/bin/env python3
"""Probe 2: README-only control plus sample-size / overclaim checks.

Detector control (both-states):
  * planted README mentions sampling/createMessage and is classified readme-only
  * planted server.py without the method is not a code hit
  * injecting the method string into that server.py text flips the class to code
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

ART = REPO / "command-center/research/RES-0043.json"
CTRL_PY = HERE / "fixtures/readme-only-control/server.py"
CTRL_MD = HERE / "fixtures/readme-only-control/README.md"


def main() -> int:
    measured = S.scan()
    ctrl = measured["control"]
    summary = measured["summary"]
    per = summary["per_capability"]

    samp_class = ctrl["capabilities"]["sampling"]["class"]
    print(f"control.sampling class={samp_class}")
    if samp_class != "readme-only":
        print("FAILED:RES-0043-probe2 control was not README-only")
        return 1
    if ctrl["capabilities"]["sampling"]["code_files"]:
        print("FAILED:RES-0043-probe2 control leaked a code hit")
        return 1
    if not ctrl["capabilities"]["sampling"]["doc_files"]:
        print("FAILED:RES-0043-probe2 control README did not fire")
        return 1

    py = CTRL_PY.read_text(encoding="utf-8")
    md = CTRL_MD.read_text(encoding="utf-8")
    silent = S.classify_text(py, "code", "sampling")
    mention = S.classify_text(md, "doc", "sampling")
    mutant = S.classify_text(
        py + '\nhandler = "sampling/createMessage"\n', "code", "sampling"
    )
    print(
        f"control_code_silent={not silent} "
        f"readme_mentions={mention} "
        f"mutant_code_hit={mutant}"
    )
    if silent:
        print("FAILED:RES-0043-probe2 control server.py is a false code hit")
        return 1
    if not mention:
        print("FAILED:RES-0043-probe2 control README mention missed")
        return 1
    if not mutant:
        print("FAILED:RES-0043-probe2 method injection did not go red")
        return 1

    if summary["sample_size_servers"] != 10:
        print("FAILED:RES-0043-probe2 expected 10 servers")
        return 1
    if summary["sample_size_clients"] != 5:
        print("FAILED:RES-0043-probe2 expected 5 clients")
        return 1
    print(
        "sample_size servers="
        f"{summary['sample_size_servers']} "
        f"clients={summary['sample_size_clients']} "
        f"readme_only_sum={summary['readme_only_count_sum']}"
    )

    if not ART.is_file():
        print("FAILED:RES-0043-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0043-probe2 self-declared {doc.get('state')}")
        return 1
    art = doc.get("per_capability_code_level_adoption") or {}
    if art.get("readme_only_count_sum") != summary["readme_only_count_sum"]:
        print("FAILED:RES-0043-probe2 artifact README-only sum mismatch")
        return 1
    if "control.readme-only" in json.dumps(art.get("sampling") or {}):
        print("FAILED:RES-0043-probe2 planted control leaked into product counts")
        return 1

    # Overclaim guard: excluding the reference everything server, sampled
    # production servers have zero sampling/elicitation code hits.
    prod_servers = [
        s
        for s in measured["subjects"]
        if s["kind"] == "server" and s.get("product") and not s.get("reference")
    ]
    samp_prod = [
        s["id"]
        for s in prod_servers
        if s["capabilities"]["sampling"]["class"] == "code"
    ]
    elic_prod = [
        s["id"]
        for s in prod_servers
        if s["capabilities"]["elicitation"]["class"] == "code"
    ]
    print(f"production_servers n={len(prod_servers)} sampling={samp_prod} elicitation={elic_prod}")
    if samp_prod or elic_prod:
        print("FAILED:RES-0043-probe2 unexpected production-server capability")
        return 1
    if len(prod_servers) != 9:
        print("FAILED:RES-0043-probe2 expected 9 non-reference servers")
        return 1
    if not doc.get("everything_server_is_reference") is True:
        print("FAILED:RES-0043-probe2 artifact did not flag everything as reference")
        return 1

    rec = doc.get("recommendation") or {}
    if rec.get("sampling") != "do-not-adopt":
        print("FAILED:RES-0043-probe2 sampling recommendation not do-not-adopt")
        return 1
    if rec.get("roots") != "do-not-adopt":
        print("FAILED:RES-0043-probe2 roots recommendation not do-not-adopt")
        return 1
    if rec.get("elicitation") not in {"optional-not-required", "aspirational"}:
        print("FAILED:RES-0043-probe2 elicitation recommendation missing")
        return 1

    print(
        "SUCCESS:RES-0043-probe2 README-only control fires, "
        "sample size and README-only count restated, overclaim guarded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
