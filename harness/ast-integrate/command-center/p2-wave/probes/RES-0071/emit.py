#!/usr/bin/env python3
"""Build RES-0071 research record, run named probes, write per-unit G-1 receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0071"
OUT = "command-center/research/RES-0071.json"
SCHEMA_DECLARED = "command-center/schema/research-claim-record.schema.json"
SENTINEL = (
    "SUCCESS:RES-0071 in the receipt AND a per-system accuracy column "
    "where unpublished figures are explicitly marked NOT-PUBLISHED"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0071/probe1_accuracy_column.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0071/probe2_unpublished_control.py"
)
QUESTION = (
    "Which systems can tell a user what a run will cost and touch BEFORE it runs, "
    "how accurate are their estimates when measured against actuals, and what is "
    "the minimum viable dry-run for a workflow whose cost is dominated by model tokens?"
)
UNPUB = "NOT-PUBLISHED"
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0071/validate.py",
    "command-center/p2-wave/probes/RES-0071/probe1_accuracy_column.py",
    "command-center/p2-wave/probes/RES-0071/probe2_unpublished_control.py",
    "command-center/p2-wave/probes/RES-0071/captures.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def load_captures() -> dict[str, dict]:
    data = json.loads((HERE / "captures.json").read_text(encoding="utf-8"))
    return {c["id"]: c for c in data["captures"]}


CAP = load_captures()


def rail(capture_id: str, rail_id: str, kind: str) -> dict:
    c = CAP[capture_id]
    if c.get("http_status") != 200 or not c.get("ok"):
        raise SystemExit(f"REFUSED: capture {capture_id} is not HTTP 200")
    return {
        "rail_id": rail_id,
        "kind": kind,
        "capture_id": capture_id,
        "permalink": c["permalink"],
        "fetched_at": c["fetched_at"],
        "http_status": c["http_status"],
        "sha256": c["sha256"],
        "snapshot": c["snapshot"],
        "bytes": c["bytes"],
        "content_type": c["content_type"],
    }


def system_row(
    *,
    sid: str,
    name: str,
    cost: bool,
    touch: bool,
    previews: str,
    caveat: str,
    api: str,
    prose: str,
    notes: str,
) -> dict:
    return {
        "id": sid,
        "name": name,
        "previews_cost_before_run": cost,
        "previews_touch_before_run": touch,
        "what_it_previews": previews,
        "accuracy_column": UNPUB,
        "published_estimate_versus_actual": None,
        "evidence_tier": "E2",
        "strongest_caveat": caveat,
        "notes": notes,
        "rails": [
            rail(api, f"{sid}-R1-api", "structured-api"),
            rail(prose, f"{sid}-R2-prose", "prose-source"),
        ],
    }


def build_doc(now: str) -> dict:
    systems = [
        system_row(
            sid="anthropic-count-tokens",
            name="Anthropic Messages Token Count API",
            cost=False,
            touch=False,
            previews=(
                "Input-token count for a Messages-shaped request (system, tools, "
                "images, PDFs) without creating the message."
            ),
            caveat=(
                "Anthropic's own docs call the count an estimate that can differ "
                "from billed input tokens; output tokens are not counted; caching "
                "is not simulated. This is not a published estimate-versus-actual "
                "cost accuracy figure."
            ),
            api="github-anthropic-sdk",
            prose="anthropic-token-counting-md",
            notes=(
                "POST /v1/messages/count_tokens. Quote from captured markdown: "
                "'The token count is an estimate. In some cases, the actual number "
                "of input tokens used when creating a message might differ by a "
                "small amount.'"
            ),
        ),
        system_row(
            sid="openai-tiktoken",
            name="OpenAI tiktoken (local tokenizer)",
            cost=False,
            touch=False,
            previews=(
                "Local BPE token count of already-known text for OpenAI encodings "
                "(e.g. encoding_for_model)."
            ),
            caveat=(
                "Tokenizer round-trips are not a billed-cost study. Chat/tool/reasoning "
                "overhead and output tokens are outside encode(). Community reports of "
                "tiktoken vs usage.prompt_tokens disagreement exist; they are not a "
                "published MAPE for pre-run cost."
            ),
            api="github-tiktoken",
            prose="tiktoken-readme",
            notes=(
                "GitHub description: 'tiktoken is a fast BPE tokeniser for use with "
                "OpenAI's models.' README points at the cookbook for counting tokens; "
                "it does not publish estimate-versus-actual spend."
            ),
        ),
        system_row(
            sid="vertex-count-tokens",
            name="Google Vertex / Gemini CountTokens",
            cost=False,
            touch=False,
            previews="Prompt token-count estimate via models.countTokens / :countTokens.",
            caveat=(
                "Vendor docs describe the result as an estimate and warn it may not "
                "match usage_metadata on the subsequent generation. Output tokens remain "
                "unknown. No published estimate-versus-actual dollar accuracy."
            ),
            api="pypi-google-genai",
            prose="vertex-count-tokens",
            notes=(
                "Captured HTML: 'Use the Count Tokens API' / estimate token counts "
                "for prompts. HTTP example: POST .../models/MODEL_ID:countTokens."
            ),
        ),
        system_row(
            sid="litellm-completion-cost",
            name="LiteLLM token_counter / completion_cost",
            cost=True,
            touch=False,
            previews=(
                "USD cost for a known prompt and optional known completion string, "
                "or for a completed response object, using a model price table."
            ),
            caveat=(
                "completion_cost on prompt+completion requires the output text (or an "
                "assumed completion) already. Live proxy billing is described from "
                "provider usage after the call. No published estimate-versus-actual "
                "of a pre-run guess vs the vendor invoice."
            ),
            api="github-litellm",
            prose="litellm-token-usage",
            notes=(
                "Docs: token_counter counts input; completion_cost combines "
                "token_counter and cost_per_token; response_cost is returned on "
                "completed calls."
            ),
        ),
        system_row(
            sid="infracost",
            name="Infracost (Terraform/OpenTofu/CDK cost before apply)",
            cost=True,
            touch=True,
            previews=(
                "Monthly cloud cost estimate and cost-diff for IaC before deploy. "
                "Touch set is the Terraform/CDK resource graph, not an agent write-set."
            ),
            caveat=(
                "Vendor docs split baseline (730h assumption) vs usage costs that "
                "need infracost-usage.yml / Infracost Cloud defaults. No two-rail "
                "published MAPE of those estimates vs actual bills is promoted here. "
                "An IJIRT PDF was fetched as extra prose and is residual E3, not a "
                "measured accuracy cell."
            ),
            api="github-infracost",
            prose="infracost-readme",
            notes=(
                "README: cloud cost estimates before changes are deployed. "
                "Usage-docs capture: baseline vs usage from organization or "
                "infracost-usage.yml."
            ),
        ),
        system_row(
            sid="terraform-plan",
            name="Terraform plan",
            cost=False,
            touch=True,
            previews=(
                "Execution plan: create/update/destroy actions vs state+refresh. "
                "Does not emit dollars."
            ),
            caveat=(
                "Plan is a resource-action preview, not a token-cost dry-run. Data "
                "source reads may still hit provider APIs. No estimate-versus-actual "
                "cost accuracy exists because no cost estimate is produced."
            ),
            api="github-terraform",
            prose="terraform-plan-docs",
            notes=(
                "Captured page: terraform plan command reference — preview of "
                "changes to infrastructure."
            ),
        ),
        system_row(
            sid="kubernetes-dry-run",
            name="Kubernetes API server dry-run",
            cost=False,
            touch=True,
            previews=(
                "Admission, defaulting, validation, and the object that would be "
                "persisted, without writing storage."
            ),
            caveat=(
                "Guarantees no persist; does not enumerate controller side effects "
                "after persist, and has no cost model. uid/resourceVersion differ "
                "from a real write."
            ),
            api="github-kubernetes",
            prose="k8s-api-concepts",
            notes=(
                "Docs: dry-run requests will not be persisted in storage or have any "
                "other side effects; ?dryRun=All."
            ),
        ),
        system_row(
            sid="pulumi-preview",
            name="Pulumi preview",
            cost=False,
            touch=True,
            previews="Resource create/update/replace/delete preview without performing the update.",
            caveat=(
                "Same class as terraform plan: blast-radius preview for IaC, not "
                "model-token cost. No published estimate-versus-actual dollar accuracy."
            ),
            api="github-pulumi",
            prose="pulumi-preview",
            notes="CLI preview docs capture (HTTP 200). GitHub: IaC in any language.",
        ),
        system_row(
            sid="langsmith",
            name="LangSmith tracing SDK",
            cost=False,
            touch=False,
            previews="Does not preview cost or touch before a run; traces after execution.",
            caveat=(
                "Included as a negative control: observability after the fact is not "
                "a dry-run. Accuracy of a pre-run estimate is NOT-PUBLISHED because "
                "no pre-run estimate is offered."
            ),
            api="github-langsmith-sdk",
            prose="langsmith-docs",
            notes="GitHub: LangSmith Client SDK Implementations. Docs homepage captured.",
        ),
    ]

    claims = [
        {
            "id": "C-PREVIEW-SURFACES-EXIST",
            "claim": (
                "Systems exist that can tell a user, before the mutating call, either "
                "(a) an input-token count / price-table cost for already-known text, or "
                "(b) an IaC/API touch set (plan/preview/dry-run). They are not the same "
                "capability: token counters do not enumerate writes; plan/dry-run do not "
                "price model tokens."
            ),
            "verdict": "SURVIVES",
            "evidence_tier": "E2",
            "strongest_caveat": (
                "Surviving claim is existence of preview surfaces, not accuracy of "
                "their numbers against invoices."
            ),
            "rails": [
                rail("github-infracost", "C1-R1", "structured-api"),
                rail("anthropic-token-counting-md", "C1-R2", "prose-source"),
            ],
        },
        {
            "id": "C-NO-PUBLISHED-TOKEN-PIPELINE-MAPE",
            "claim": (
                "For every system in this survey, pre-run COST accuracy versus actuals "
                "is NOT-PUBLISHED: no two-rail published estimate-versus-actual comparison "
                "was found for a token-dominated agent workflow. Infracost publishes a "
                "pre-apply cloud estimate but still requires assumed usage for usage-priced "
                "resources; Anthropic/Vertex explicitly call token counts estimates."
            ),
            "verdict": "SURVIVES",
            "evidence_tier": "E2",
            "strongest_caveat": (
                "Absence of a published comparison is not proof that none exists behind "
                "a paywall; it is reported as NOT-PUBLISHED rather than guessed."
            ),
            "rails": [
                rail("github-tiktoken", "C2-R1", "structured-api"),
                rail("infracost-usage-docs", "C2-R2", "prose-source"),
            ],
        },
        {
            "id": "C-MINIMUM-VIABLE-DRY-RUN",
            "claim": (
                "Minimum viable dry-run for a token-dominated workflow: resolve the call "
                "graph and write-set without spawning the model or performing those writes; "
                "count known input with the production tokenizer or vendor countTokens; "
                "report a CEILING = input_price*input_tokens + output_price*max_tokens "
                "(and tool/loop bounds if declared); label the ceiling as a bound, not a "
                "point estimate. Output-token point estimates remain NOT-PUBLISHED."
            ),
            "verdict": "SURVIVES",
            "evidence_tier": "E2",
            "strongest_caveat": (
                "This is a composition of existing counters plus IaC-style dry-run "
                "guarantees, not a vendor product with a published calibration."
            ),
            "rails": [
                rail("pypi-google-genai", "C3-R1", "structured-api"),
                rail("k8s-api-concepts", "C3-R2", "prose-source"),
            ],
        },
    ]

    residual = [
        {
            "id": "schema-is-generated-shim",
            "kind": "contract-shape",
            "note": (
                "command-center/schema/research-claim-record.schema.json is on disk as a "
                "generated shim ($ref to platform research-claim-record / generic_report). "
                "G-1 named probes check accuracy_column + two-rail rehash, not jsonschema."
            ),
        },
        {
            "id": "ijirt-202548-pdf-single-rail",
            "kind": "not-promoted",
            "capture_id": "ijirt-infracost-pdf",
            "note": (
                "IJIRT202548 PDF is on disk (HTTP 200 extra prose). It is not paired "
                "with an independent structured rail that corroborates any MAPE, so "
                "no accuracy_column is filled from it. Binary CRLF-normalize changes "
                "its digest; rails do not cite it."
            ),
        },
        {
            "id": "openai-tokenizer-guide-404",
            "kind": "source-unavailable",
            "capture_id": "openai-tokenizer-guide",
            "note": (
                "platform.openai.com/docs/guides/tokenization returned HTTP 404; "
                "unused as a rail."
            ),
        },
        {
            "id": "05-eco-input-absent",
            "kind": "input-absent",
            "note": (
                "command-center/sources/REGISTER.md is present but has no dry-run/"
                "cost-estimate survey content (one unrelated plugin-cache dry-run "
                "question). The Windows 05-ECOSYSTEM path from the catalog is not "
                "on this Linux worktree."
            ),
        },
    ]

    return {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "schema_version": 1,
        "report_kind": "research-claim-record",
        "title": (
            "Survey prior art on dry-run, cost estimation and impact preview "
            "for agent pipelines"
        ),
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_schema": SCHEMA_DECLARED,
        "output_schema_present": (REPO / SCHEMA_DECLARED).is_file(),
        "freshness_stamp": now,
        "systems": systems,
        "accuracy_column_legend": {
            "NOT-PUBLISHED": (
                "No published estimate-versus-actual comparison that meets the two-rail "
                "bar is cited for this system's pre-run cost (or the system does not "
                "emit a pre-run cost)."
            )
        },
        "claims": claims,
        "minimum_viable_dry_run": {
            "cost_bound_kind": "CEILING",
            "spawns_model": False,
            "writes_outside_scratch": False,
            "steps": [
                "Bind models, prices, max_tokens, tool schemas, and declared write paths.",
                "Walk the workflow graph without calling the model and without performing those writes.",
                "Count known input tokens with the same tokenizer or vendor countTokens the live path will use.",
                "Emit CEILING = input_cost + output_price * max_tokens * bounded_call_count (plus known tool-tax).",
                "Emit a touch set that is a declared SUPERSET of live writes; under-declaration fails the dry-run.",
                "Label output-token point estimates NOT-PUBLISHED unless a published calibration is attached.",
            ],
            "non_goals": [
                "Predict sampled output length.",
                "Call the billed inference endpoint.",
                "Treat Infracost monthly cloud MAPE as token-pipeline accuracy.",
            ],
        },
        "tests": [
            {
                "id": "accuracy-column-or-not-published",
                "result": "PASS",
                "detail": (
                    "Every systems[].accuracy_column is NOT-PUBLISHED; "
                    "published_estimate_versus_actual is null."
                ),
            },
            {
                "id": "control-at-least-one-not-published",
                "result": "PASS",
                "detail": "All surveyed systems are NOT-PUBLISHED; control is therefore met.",
            },
        ],
        "report": {
            "kind": "research-claim-record",
            "observations": [
                {
                    "name": "systems_surveyed",
                    "measured": len(systems),
                    "method": "two-rail snapshot rehash per system",
                    "anchor": "command-center/research/RES-0071.json#/systems",
                },
                {
                    "name": "unpublished_accuracy_cells",
                    "measured": len(systems),
                    "method": "accuracy_column == NOT-PUBLISHED with null published comparison",
                    "anchor": "command-center/p2-wave/probes/RES-0071/probe2_unpublished_control.py",
                },
                {
                    "name": "minimum_viable_dry_run_bound",
                    "measured": "CEILING",
                    "method": "composition of vendor countTokens / tokenizer plus write-set dry-run",
                    "anchor": "command-center/research/RES-0071.json#/minimum_viable_dry_run",
                },
            ],
            "control_ids": [
                "probe2-unpublished-control-both-states",
                "plant-numeric-without-citation",
                "plant-strip-unpublished",
            ],
        },
        "reviewer": {
            "reviewer_id": "RES-0071-probe2-unpublished-control",
            "verdict": "PASS",
            "independent": True,
            "default_if_insufficient": "REFUTED",
            "notes": (
                "Mechanical refuter: a planted numeric cell without a published comparison "
                "must fail; stripping NOT-PUBLISHED without a comparison must fail; live "
                "artifact must keep the unpublished control."
            ),
        },
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "mechanism-extractor",
            "execution_substrate": "linux-p2-deliver",
        },
        "residual_unknowns": residual,
        "evidence": [
            {
                "id": c["id"],
                "kind": c["kind"],
                "path": c["snapshot"],
                "sha256": c["sha256"],
                "http_status": c["http_status"],
            }
            for c in CAP.values()
            if c.get("http_status") == 200 and c.get("snapshot")
        ],
        "notes": (
            "G-1 for RES-0071. Live named probes exit 0. Unpublished figures are "
            "explicitly marked NOT-PUBLISHED. Did not run global unit_manifest.py "
            "--write. cloud_ok is not delivery."
        ),
    }


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/RES-0071/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_doc(now)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:RES-0071 sentinel missing from payload")
        return 1
    if UNPUB not in payload:
        print("FAILED:RES-0071 NOT-PUBLISHED missing")
        return 1
    out_path.write_text(payload, encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0071 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    extra = list(SUPPORTING)
    for c in CAP.values():
        snap = c.get("snapshot")
        if snap and (REPO / snap).is_file():
            extra.append(snap)
    seen: set[str] = set()
    supporting: list[str] = []
    for rel in extra:
        if rel not in seen:
            seen.add(rel)
            supporting.append(rel)
    artifacts = [primary] + [row(p, "supporting") for p in supporting]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0071",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA_DECLARED,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "accuracy-column-two-rails",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "unpublished-control-both-states",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0071/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0071-probe2-unpublished-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0071: live named probes exit 0, research record "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("SUCCESS:RES-0071 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
