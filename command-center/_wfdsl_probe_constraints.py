#!/usr/bin/env python3
"""Measure how many of the 2,007 catalog units would satisfy each CANDIDATE constraint.

Read-only. This runs BEFORE the schema is authored so the schema's value domains are
measured, not guessed. Emits JSON to stdout.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "WORK-UNIT-CATALOG.json"

ID_RE = re.compile(r"^[A-Z]{2,4}-[0-9]{4}$")
BUCKET_RE = re.compile(r"^B[0-9]{2}$")
PHASE_RE = re.compile(r"^(?:[0-9]|1[0-9]|2[0-9])[A-Z]?$")
TOOL_RE = re.compile(
    r"^(?:[A-Z][A-Za-z0-9]*(?:\([^)]*\))?|[A-Z][A-Za-z0-9]*:[A-Za-z0-9_.\-]+|mcp__[A-Za-z0-9_.\-]+__[A-Za-z0-9_]+)$"
)
REL_PATH_RE = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._\-/]*$")
SCHEMA_REF_RE = re.compile(r"^(?:https?://[^\s]+|[A-Za-z0-9._][A-Za-z0-9._\-/]*\.json(?:#[^\s]*)?|https://json-schema\.org/[^\s]+)$")
AMVR_STR_RE = re.compile(r"^[^/]+/[^/]+/[^/]+$")


def main() -> int:
    d = json.loads(CATALOG.read_text(encoding="utf-8"))
    wu = d["work_units"]
    n = len(wu)
    ids = {u["id"] for u in wu}
    buckets = {u.get("bucket") for u in wu if u.get("bucket")}
    res: dict[str, object] = {"n": n, "known_bucket_tokens": sorted(x for x in buckets if x)}

    def tally(name: str, pred, why=None) -> None:
        ok = 0
        bad: list[str] = []
        reasons: Counter = Counter()
        for u in wu:
            try:
                good = pred(u)
            except Exception as e:  # noqa: BLE001
                good = False
                reasons["exception:" + type(e).__name__] += 1
            if good:
                ok += 1
            else:
                if len(bad) < 25:
                    bad.append(u["id"])
                if why:
                    reasons[why(u)] += 1
        res[name] = {"pass": ok, "fail": n - ok, "sample_fail": bad, "fail_reasons": dict(reasons.most_common(15))}

    tally("id_pattern", lambda u: bool(ID_RE.match(u["id"])))
    tally("phase_pattern", lambda u: bool(PHASE_RE.match(u["phase"])), lambda u: "phase=" + str(u["phase"]))
    tally("title_min3", lambda u: isinstance(u["title"], str) and len(u["title"]) >= 3)
    tally("question_min10", lambda u: isinstance(u["question_or_target"], str) and len(u["question_or_target"]) >= 10)
    tally("inputs_array_min1", lambda u: isinstance(u["inputs"], list) and len(u["inputs"]) >= 1 and all(isinstance(x, str) and x.strip() for x in u["inputs"]))
    tally("deps_array_of_str", lambda u: isinstance(u["dependencies"], list) and all(isinstance(x, str) and x.strip() for x in u["dependencies"]))
    tally(
        "deps_token_form",
        lambda u: all(ID_RE.match(t) or BUCKET_RE.match(t) for t in u["dependencies"]),
        lambda u: "bad_tokens=" + ",".join(sorted({t for t in u["dependencies"] if not (ID_RE.match(t) or BUCKET_RE.match(t))})),
    )
    tally(
        "deps_resolvable",
        lambda u: all((t in ids) or BUCKET_RE.match(t) for t in u["dependencies"]),
        lambda u: "unresolvable=" + ",".join(sorted({t for t in u["dependencies"] if not ((t in ids) or BUCKET_RE.match(t))})),
    )
    tally("amvr_object", lambda u: isinstance(u["assigned_model_vendor_role"], dict) and {"model", "vendor", "role"} <= set(u["assigned_model_vendor_role"]))
    tally(
        "amvr_object_or_triple_string",
        lambda u: (isinstance(u["assigned_model_vendor_role"], dict) and {"model", "vendor", "role"} <= set(u["assigned_model_vendor_role"]))
        or (isinstance(u["assigned_model_vendor_role"], str) and bool(AMVR_STR_RE.match(u["assigned_model_vendor_role"]))),
    )
    tally("tools_array_min1", lambda u: isinstance(u["tool_permissions"], list) and len(u["tool_permissions"]) >= 1)
    tally(
        "tools_token_form",
        lambda u: all(isinstance(t, str) and TOOL_RE.match(t) for t in u["tool_permissions"]),
        lambda u: "bad=" + ",".join(sorted({t for t in u["tool_permissions"] if not TOOL_RE.match(t)}))[:120],
    )
    SUBSTRATES = {"local-parallel", "local-serialized", "worktree-isolated", "cloud-batch", "local-windows-pwsh7", "databricks-job", "modal-sandbox", "container", "cloud-worker"}
    tally("substrate_enum", lambda u: u["execution_substrate"] in SUBSTRATES, lambda u: "sub=" + str(u["execution_substrate"]))
    tally("timeout_int_60_86400", lambda u: isinstance(u["timeout_seconds"], int) and not isinstance(u["timeout_seconds"], bool) and 60 <= u["timeout_seconds"] <= 86400)
    tally("output_path_relative_posix", lambda u: isinstance(u["output_path"], str) and bool(REL_PATH_RE.match(u["output_path"])) and ".." not in u["output_path"], lambda u: "path=" + str(u["output_path"])[:90])
    tally("output_schema_ref_resolvable_form", lambda u: isinstance(u["output_schema"], str) and bool(SCHEMA_REF_RE.match(u["output_schema"])), lambda u: "oschema=" + str(u["output_schema"])[:90])
    tally("output_schema_no_space", lambda u: isinstance(u["output_schema"], str) and " " not in u["output_schema"])
    tally("evidence_min20", lambda u: isinstance(u["evidence_requirement"], str) and len(u["evidence_requirement"]) >= 20)
    tally("tests_array_min1", lambda u: isinstance(u["tests_required"], list) and len(u["tests_required"]) >= 1)
    tally("tests_array_or_string", lambda u: (isinstance(u["tests_required"], list) and len(u["tests_required"]) >= 1) or (isinstance(u["tests_required"], str) and len(u["tests_required"]) >= 10))
    tally("reviewer_min10", lambda u: isinstance(u["reviewer_requirement"], str) and len(u["reviewer_requirement"]) >= 10)
    tally("sentinel_contains_success_id", lambda u: isinstance(u["completion_sentinel"], str) and ("SUCCESS:" + u["id"]) in u["completion_sentinel"])
    tally("sentinel_startswith_success_id", lambda u: isinstance(u["completion_sentinel"], str) and u["completion_sentinel"].startswith("SUCCESS:" + u["id"]))
    tally("retry_min10", lambda u: isinstance(u["retry_policy"], str) and len(u["retry_policy"]) >= 10)
    tally("failcls_array_min1", lambda u: isinstance(u["failure_classification"], list) and len(u["failure_classification"]) >= 1)
    tally("failcls_array_or_string", lambda u: (isinstance(u["failure_classification"], list) and len(u["failure_classification"]) >= 1) or (isinstance(u["failure_classification"], str) and len(u["failure_classification"]) >= 3))
    tally("owner_approval_bool", lambda u: isinstance(u["owner_approval_required"], bool))
    FAILCLS_RE = re.compile(r"^[a-z0-9]+(?:[-<>][a-z0-9]+)*$")
    tally(
        "failcls_token_form",
        lambda u: all(FAILCLS_RE.match(t) for t in (u["failure_classification"] if isinstance(u["failure_classification"], list) else [u["failure_classification"]])),
        lambda u: "bad=" + ",".join(sorted(t for t in (u["failure_classification"] if isinstance(u["failure_classification"], list) else [u["failure_classification"]]) if not FAILCLS_RE.match(t)))[:120],
    )

    # distributions for a few fields
    res["output_path_prefixes"] = dict(Counter(u["output_path"].split("/")[0] for u in wu if isinstance(u["output_path"], str)).most_common(20))
    res["output_path_backslash"] = sum(1 for u in wu if "\\" in str(u["output_path"]))
    res["output_path_absolute"] = sum(1 for u in wu if re.match(r"^(?:[A-Za-z]:|/)", str(u["output_path"])))
    res["inputs_len"] = dict(Counter(len(u["inputs"]) for u in wu).most_common(20))
    res["deps_len"] = dict(Counter(len(u["dependencies"]) for u in wu).most_common(20))
    res["failcls_str_examples"] = [u["failure_classification"] for u in wu if isinstance(u["failure_classification"], str)][:5]
    res["tests_str_examples"] = [str(u["tests_required"])[:160] for u in wu if isinstance(u["tests_required"], str)][:5]
    res["amvr_str_examples"] = [u["assigned_model_vendor_role"] for u in wu if isinstance(u["assigned_model_vendor_role"], str)][:5]
    json.dump(res, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
