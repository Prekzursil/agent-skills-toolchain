#!/usr/bin/env python3
"""BLD-0042 probe1: default-parameter census delivery predicate.

Re-derives the census arithmetic from the receipt's own counts:
  explicit_only(70) + unreferenced(65) + exercised(58) + dynamic_unknown(1)
    + assertionless(0) == public_default_parameters(194)
  function_defaults_reported_unexercised(135) == explicit_only(70)+unreferenced(65)
  reported_findings(137) == 135 + cli_defaults_reported_unexercised(2)
Register semantics (per kind, from the receipt itself):
  function/dataclass/constructor rows (135): a finding only when
    default_exercising_call_site_count == 0
  cli-flag rows (2): classified unexercised-in-shipped-ci only when
    ci_bare_invocations is empty (a local asserting test caller does not
    exercise the default in the SHIPPED CI)
condition_11 records a per-unit manifest route; negative control
BLD-0042-NEG-COVERED-AS-FINDING must be recorded both-states. Absence of
the supporting census.json (production worktree) here is surfaced as a
NOTE, never folded into a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import (  # noqa: E402
    REPO, ProbeFailure, check_receipt_core, require,
)

UID = "BLD-0042"
HERE = Path(__file__).resolve().parent
NON_CLI_KINDS = {"config-dataclass-default", "public-function-default", "constructor-default"}


def main() -> int:
    doc = check_receipt_core(UID)
    c = doc.get("counts") or {}

    pub = int(c.get("public_default_parameters") or 0)
    parts = ("function_defaults_explicit_only", "function_defaults_unreferenced",
             "function_defaults_exercised", "function_defaults_dynamic_unknown",
             "function_defaults_assertionless_only")
    total = sum(int(c.get(k) or 0) for k in parts)
    require(pub == total == 194,
            f"function-default partition {total} != public_default_parameters {pub}")
    eo = int(c.get("function_defaults_explicit_only") or 0)
    ur = int(c.get("function_defaults_unreferenced") or 0)
    require(int(c.get("function_defaults_reported_unexercised") or 0) == eo + ur == 135,
            "reported_unexercised != explicit_only + unreferenced")
    cli_un = int(c.get("cli_defaults_reported_unexercised") or 0)
    require(int(c.get("reported_findings") or 0) == 135 + cli_un == 137,
            "reported_findings != 135 + cli_unexercised")
    require(int(c.get("cli_flag_defaults") or 0) == 108, "cli_flag_defaults drift")
    require(int(c.get("resolved_call_sites") or 0) >= 1, "resolved_call_sites empty")

    fr = doc.get("finding_register") or []
    require(len(fr) == int(c.get("reported_findings") or -1),
            f"finding_register rows {len(fr)} != reported_findings")
    ids = [f.get("census_id") for f in fr]
    require(len(set(ids)) == len(ids), "duplicate census_id in finding_register")

    fn_rows = [f for f in fr if f.get("kind") in NON_CLI_KINDS]
    cli_rows = [f for f in fr if f.get("kind") == "cli-flag-default"]
    require(len(fn_rows) == 135, f"non-cli finding rows {len(fn_rows)} != 135")
    require(len(cli_rows) == 2, f"cli finding rows {len(cli_rows)} != 2")
    def _i(v):
        return -1 if v is None else int(v)

    bad_zero = [
        f.get("census_id") for f in fn_rows
        if _i(f.get("default_exercising_call_site_count")) != 0
    ]
    require(not bad_zero,
            f"function findings with default-exercising callers: {bad_zero[:3]}")
    bad_cli = [
        f.get("census_id") for f in cli_rows
        if f.get("classification") != "unexercised-in-shipped-ci"
        or (f.get("ci_bare_invocations") or None) is not None and f.get("ci_bare_invocations")
    ]
    require(not bad_cli,
            f"cli findings not unexercised-in-shipped-ci / have bare CI invocations: {bad_cli}")
    sites = [f.get("declaration_site") for f in fr]
    require(all(s and ":" in str(s) for s in sites),
            "finding row without declaration_site:line")

    c11 = doc.get("condition_11") or {}
    require(str(c11.get("route", "")).startswith("STRUCTURAL-CONDITION-11"),
            "condition_11 route drift")
    require(c11.get("green") is True, "condition_11 not green")
    require("UNIT-ARTIFACT-MANIFEST.json" in str(c11.get("manifest_path") or ""),
            "condition_11 manifest_path not per-unit")

    ncs = doc.get("negative_controls") or []
    nc = next((x for x in ncs if x.get("id") == "BLD-0042-NEG-COVERED-AS-FINDING"), None)
    require(nc is not None, "BLD-0042-NEG-COVERED-AS-FINDING not recorded")
    require(nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True,
            "NEG control not both-states")

    notes = []
    for a in doc.get("artifacts") or []:
        if a.get("role") == "supporting" and not (REPO / str(a.get("path") or "x")).is_file():
            notes.append(f"supporting-artifact-absent-on-this-worktree: {a.get('path')} "
                         f"(produced on the production worktree; receipt keeps its sha)")

    print(json.dumps({
        "probe": "probe1-census-predicate",
        "unit_id": UID,
        "partition_sum": total,
        "explicit_plus_unreferenced": eo + ur,
        "non_cli_findings": len(fn_rows),
        "cli_findings": len(cli_rows),
        "condition_11_green": True,
        "neg_both_states": True,
        "notes": notes,
        "pass": True,
    }))
    print(f"SUCCESS:{UID}-probe1 70+65+58+1+0=194; 135=70+65; 137=135+2 findings; "
          f"condition_11 green; NEG both-states")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe1 {exc}")
        raise SystemExit(1)
