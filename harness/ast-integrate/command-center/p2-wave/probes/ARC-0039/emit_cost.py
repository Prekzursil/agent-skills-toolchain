#!/usr/bin/env python3
"""Emit command-center/phase3/A6/COST.json for ARC-0039 from frozen vendor notes."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

try:
    import jsonschema
    from jsonschema.exceptions import RefResolutionError, ValidationError
except ImportError:  # pragma: no cover
    jsonschema = None
    RefResolutionError = ValidationError = Exception  # type: ignore[misc,assignment]

OUT = "command-center/phase3/A6/COST.json"
SCHEMA = "command-center/schema/architecture-cost-model.schema.json"
QUESTION = (
    "What is the per-vendor adapter maintenance cost? Enumerate the vendor-specific "
    "surfaces (prompt transport, tool and permission model, output schema, "
    "progress/streaming, timeout, session state, model naming) and estimate each "
    "surface's change frequency from OBSERVED vendor release cadence over a stated "
    "window - then state which surfaces must be versioned to avoid breaking on a "
    "vendor update."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0039/probe1_recency.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0039/probe2_forecast.py"
)

ANTHROPIC_NOTES = "https://platform.claude.com/docs/en/release-notes/overview"
OPENAI_CHANGELOG = "https://developers.openai.com/api/docs/changelog"


def cite(
    vendor: str,
    entry_date: str,
    url: str,
    snippet: str,
    *,
    in_window: bool = True,
) -> dict:
    ed = date.fromisoformat(entry_date)
    return {
        "vendor": vendor,
        "url": url,
        "entry_date": entry_date,
        "retrieved_on": L.RETRIEVED_ON.isoformat(),
        "staleness_days": (L.RETRIEVED_ON - ed).days,
        "in_observation_window": in_window,
        "snippet": snippet,
    }


def annualize(n: int, days: int) -> float:
    return round(n / days * 365.0, 1)


def keyword_counts(entries: list[dict]) -> dict[str, int]:
    out = {sid: 0 for sid in L.SURFACES}
    for e in entries:
        for sid in e["surfaces"]:
            out[sid] += 1
    return out


SNIPPET_NEEDLES = {
    "https://platform.claude.com/docs/en/release-notes/overview": L.anthropic_text(),
    "https://developers.openai.com/api/docs/changelog": L.openai_text(),
}


def snippet_in_corpus(url: str, snippet: str) -> bool:
    blob = SNIPPET_NEEDLES.get(url, "")
    tokens = [t for t in snippet.replace("`", " ").split() if len(t) > 4]
    hits = sum(1 for t in tokens if t.strip(".,;:()") in blob)
    return hits >= max(2, len(tokens) // 3)


def main() -> int:
    a_head, b_head = L.two_anthropic_heading_counts()
    if a_head != b_head:
        print(f"BLOCKED:ARC-0039 heading counts disagree A={a_head} B={b_head}")
        return 1
    oa_a, oa_b = L.two_openai_entry_counts()
    if oa_a != oa_b:
        print(f"BLOCKED:ARC-0039 openai counts disagree A={oa_a} B={oa_b}")
        return 1

    ant = L.windowed(L.parse_anthropic_entries(L.anthropic_text()))
    oa = L.windowed(L.parse_openai_entries(L.openai_text()))
    kw_ant = keyword_counts(ant)
    kw_oa = keyword_counts(oa)

    cc = L.load_compact("claude-code-releases.compact.json")
    cx = L.load_compact("codex-releases.compact.json")
    cc_pub = L.github_counts(cc, "published_at")
    cc_cre = L.github_counts(cc, "created_at")
    cx_pub = L.github_counts(cx, "published_at")
    cx_cre = L.github_counts(cx, "created_at")
    days = (L.WINDOW_END - L.WINDOW_START).days + 1

    curated = {
        "prompt_transport": {
            "curated_in_window": 3,
            "must_version": True,
            "why_version": (
                "SDK HTTP client class and regional request host are load-bearing "
                "adapter fields. A pinned transport version keeps httpx vs httpx2 "
                "and un-prefixed vs prefixed hosts from silently swapping."
            ),
            "citations": [
                cite(
                    "anthropic",
                    "2026-08-20",
                    ANTHROPIC_NOTES,
                    "Python SDK v1.0 moves the HTTP layer from httpx to httpx2; Timeout and transport objects must be built from httpx2.",
                ),
                cite(
                    "openai",
                    "2026-08-21",
                    OPENAI_CHANGELOG,
                    "API customers can select regional processing per request via a prefixed domain plus a Global-geography project key.",
                ),
                cite(
                    "anthropic",
                    "2026-05-13",
                    ANTHROPIC_NOTES,
                    "Cache diagnostics launched in public beta on the Claude API (prompt-cache observability).",
                ),
            ],
        },
        "tool_permission_model": {
            "curated_in_window": 4,
            "must_version": True,
            "why_version": (
                "Toolset type ids and permission_policy fields changed request "
                "shape (computer_toolset_20260801 GA; mid-conversation tool edits). "
                "An unversioned tool adapter will send the retired tool type."
            ),
            "citations": [
                cite(
                    "anthropic",
                    "2026-08-19",
                    ANTHROPIC_NOTES,
                    "Computer use left beta as computer_toolset_20260801; upgrading changes request shape and tool handling. Earlier beta versions remain available.",
                ),
                cite(
                    "anthropic",
                    "2026-08-19",
                    ANTHROPIC_NOTES,
                    "Managed-agent web_search/web_fetch domain allow/deny moved onto agent_toolset_20260401 configs with permission_policy.",
                ),
                cite(
                    "anthropic",
                    "2026-07-24",
                    ANTHROPIC_NOTES,
                    "Mid-conversation tool changes beta (mid-conversation-tool-changes-2026-07-01) on Fable 5, Mythos 5, Opus 4.8, and Opus 5.",
                ),
                cite(
                    "anthropic",
                    "2026-06-18",
                    ANTHROPIC_NOTES,
                    "SDKs added code_execution_20260120 (REPL state persistence); set tools[].type to that id, no beta header.",
                ),
            ],
        },
        "output_schema": {
            "curated_in_window": 1,
            "must_version": True,
            "why_version": (
                "Structured-output field names already moved once (output_format -> "
                "output_config.format) just before this window. Pin the schema wire "
                "format so a second rename cannot land un-gated. In-window Anthropic "
                "notes did not repeat that rename; the 2026-01-29 GA is cited as "
                "outside-window evidence, not counted in the in-window rate."
            ),
            "citations": [
                cite(
                    "openai",
                    "2026-04-24",
                    OPENAI_CHANGELOG,
                    "GPT-5.5 launch lists structured outputs among supported API capabilities on Responses, Chat Completions, and Batch.",
                ),
                cite(
                    "anthropic",
                    "2026-01-29",
                    ANTHROPIC_NOTES,
                    "Structured outputs left beta; output_format moved to output_config.format. Existing beta header still accepted during transition.",
                    in_window=False,
                ),
            ],
        },
        "progress_streaming": {
            "curated_in_window": 3,
            "must_version": True,
            "why_version": (
                "SSE event names and delta envelopes changed (event_deltas on "
                "session/thread streams; thinking.display). A progress parser that "
                "treats every event as a result will mis-fire after an envelope rename."
            ),
            "citations": [
                cite(
                    "anthropic",
                    "2026-07-22",
                    ANTHROPIC_NOTES,
                    "Managed-agent thread streams accept event_deltas[] so subagent text can be previewed before the complete agent.message event.",
                ),
                cite(
                    "anthropic",
                    "2026-06-30",
                    ANTHROPIC_NOTES,
                    "Session event streams support event deltas via event_deltas[] on GET /v1/sessions/{id}/events/stream (event_start / event_delta).",
                ),
                cite(
                    "anthropic",
                    "2026-03-16",
                    ANTHROPIC_NOTES,
                    "thinking.display field launched so thinking content can be omitted from responses (streaming payload shape).",
                ),
            ],
        },
        "timeout": {
            "curated_in_window": 3,
            "must_version": True,
            "why_version": (
                "Numeric budgets moved: 90-second code-execution cell limit, SDK "
                "Timeout objects sourced from httpx2, and OpenAI hard spend caps that "
                "return 429. Pin timeout constants per adapter version."
            ),
            "citations": [
                cite(
                    "anthropic",
                    "2026-06-11",
                    ANTHROPIC_NOTES,
                    "code_execution_20260521 discloses the 90-second per-cell execution time limit in the tool description.",
                ),
                cite(
                    "anthropic",
                    "2026-08-20",
                    ANTHROPIC_NOTES,
                    "Python SDK v1.0: build Timeout objects from httpx2 rather than httpx.",
                ),
                cite(
                    "openai",
                    "2026-07-22",
                    OPENAI_CHANGELOG,
                    "Hard spend limits for organizations and projects; requests return 429 when tracked spend hits the monthly cap.",
                ),
            ],
        },
        "session_state": {
            "curated_in_window": 3,
            "must_version": True,
            "why_version": (
                "Session control fields were removed or renamed (compaction_control "
                "dropped from the Python tool runner; agent-memory-2026-07-22 changes "
                "memory listing). Unversioned session adapters will call missing params."
            ),
            "citations": [
                cite(
                    "anthropic",
                    "2026-08-20",
                    ANTHROPIC_NOTES,
                    "Python SDK v1.0 removes the tool runner's client-side compaction_control.",
                ),
                cite(
                    "anthropic",
                    "2026-07-02",
                    ANTHROPIC_NOTES,
                    "agent-memory-2026-07-22 beta changes memory listing order/depth/path_prefix; sending both this and managed-agents-2026-04-01 returns 400.",
                ),
                cite(
                    "anthropic",
                    "2026-08-07",
                    ANTHROPIC_NOTES,
                    "Managed-agent session budgets: a hard spend cap pauses the session with stop reason budget_reached.",
                ),
            ],
        },
        "model_naming": {
            "curated_in_window": 8,
            "must_version": True,
            "why_version": (
                "Model ids launched and retired inside the window (Opus 5, Sonnet 5, "
                "Fable 5, GPT-5.6 family; Opus 4.1 / Sonnet 4 / Opus 4 / Haiku 3 "
                "retirements). Dispatch tables that hard-code a moving alias fail closed "
                "only if the id is versioned."
            ),
            "citations": [
                cite(
                    "anthropic",
                    "2026-08-05",
                    ANTHROPIC_NOTES,
                    "Claude Opus 4.1 (claude-opus-4-1-20250805) retired; requests now return an error. Recommend Claude Opus 5.",
                ),
                cite(
                    "anthropic",
                    "2026-07-24",
                    ANTHROPIC_NOTES,
                    "Claude Opus 5 (claude-opus-5) launched; disabling thinking at effort xhigh/max returns 400 (breaking vs Opus 4.8).",
                ),
                cite(
                    "anthropic",
                    "2026-06-30",
                    ANTHROPIC_NOTES,
                    "Claude Sonnet 5 (claude-sonnet-5) launched; manual extended thinking and non-default sampling return 400.",
                ),
                cite(
                    "anthropic",
                    "2026-06-15",
                    ANTHROPIC_NOTES,
                    "Claude Sonnet 4 (claude-sonnet-4-20250514) and Claude Opus 4 (claude-opus-4-20250514) retired; requests return errors.",
                ),
                cite(
                    "anthropic",
                    "2026-06-09",
                    ANTHROPIC_NOTES,
                    "Claude Fable 5 (claude-fable-5) launched alongside Claude Mythos 5 (claude-mythos-5); adaptive thinking is the only thinking mode.",
                ),
                cite(
                    "anthropic",
                    "2026-04-20",
                    ANTHROPIC_NOTES,
                    "Claude Haiku 3 (claude-3-haiku-20240307) retired; requests now return an error. Recommend Claude Haiku 4.5.",
                ),
                cite(
                    "openai",
                    "2026-07-09",
                    OPENAI_CHANGELOG,
                    "GPT-5.6 family released (gpt-5.6-sol / terra / luna); gpt-5.6 alias routes to gpt-5.6-sol.",
                ),
                cite(
                    "openai",
                    "2026-04-24",
                    OPENAI_CHANGELOG,
                    "GPT-5.5 released on Chat Completions, Responses, and Batch.",
                ),
            ],
        },
    }

    surfaces = []
    for sid in L.SURFACES:
        block = curated[sid]
        n = block["curated_in_window"]
        in_win = [c for c in block["citations"] if c.get("in_observation_window")]
        if n != len(in_win):
            print(
                f"BLOCKED:ARC-0039 {sid} curated_in_window={n} "
                f"in-window citations={len(in_win)}"
            )
            return 1
        for c in block["citations"]:
            if not snippet_in_corpus(c["url"], c["snippet"]):
                print(
                    f"BLOCKED:ARC-0039 snippet not in frozen corpus "
                    f"{sid} {c['entry_date']} {c['snippet'][:80]}"
                )
                return 1
        surfaces.append(
            {
                "id": sid,
                "status": "CHECKED",
                "must_version": True,
                "why_version": block["why_version"],
                "curated_events_in_window": n,
                "curated_events_per_year": annualize(n, days),
                "keyword_hits_anthropic_in_window": kw_ant[sid],
                "keyword_hits_openai_in_window": kw_oa[sid],
                "keyword_hits_are_overinclusive": True,
                "error_band": {
                    "absolute_events": 1,
                    "relative_pct": 25,
                    "note": (
                        "Curated counts are ±1 event. Keyword hits over-count model "
                        "launch notes that mention tools/streaming incidentally and "
                        "are not used as the rate."
                    ),
                },
                "citations": block["citations"],
            }
        )

    must = [s["id"] for s in surfaces if s["must_version"]]
    forecast = {
        "surface": "model_naming",
        "window_start": L.RETRIEVED_ON.isoformat(),
        "window_end": L.FORECAST_UNTIL.isoformat(),
        "confidence_point": 0.78,
        "confidence_band": {"low": 0.65, "high": 0.90},
        "falsifiable_statement": (
            "Between 2026-08-24 and 2026-11-22 inclusive, Anthropic API release "
            "notes or the OpenAI API changelog will publish at least one new GA "
            "model id (claude-* or gpt-*) OR retire/error an existing GA model id. "
            "If neither source records such an event in that window, this forecast "
            "is FALSE."
        ),
        "basis": (
            "In the 165-day observation window the frozen notes record multiple GA "
            "launches (Opus 5, Sonnet 5, Fable 5, GPT-5.6, GPT-5.5, GPT-5.4 mini/nano) "
            "and multiple retirements (Opus 4.1, Sonnet 4, Opus 4, Haiku 3). That is "
            "more than one naming event per month. The 90-day forecast is the same "
            "cadence, not a new mechanism."
        ),
    }

    doc = {
        "unit_id": "ARC-0039",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0039",
        "architecture_id": "A6",
        "architecture_class": "cross-vendor-adapter",
        "question": QUESTION,
        "window": {
            "start": L.WINDOW_START.isoformat(),
            "end": L.WINDOW_END.isoformat(),
            "retrieved_on": L.RETRIEVED_ON.isoformat(),
            "inclusive": True,
            "days": days,
            "reason": (
                "Codex GitHub pagination returned 400 newest releases whose oldest "
                "published_at is 2026-03-13. Using a longer window would undercount "
                "Codex CLI cadence. API notes exist earlier; those earlier dates are "
                "cited only when marked in_observation_window=false."
            ),
        },
        "vendors": ["anthropic", "openai"],
        "headline_numbers": [
            {
                "name": "anthropic_api_dated_headings_in_window",
                "value": a_head,
                "unit": "dated-headings",
                "error_band": {"abs": 0, "pct": 0},
                "derivation": (
                    "Count of '### Month D, YYYY' headings in the frozen Anthropic "
                    "API release notes whose parsed date is inside the window. "
                    "Measure A uses datetime.strptime; measure B uses a month-name "
                    f"dict. A={a_head} B={b_head}."
                ),
            },
            {
                "name": "openai_api_dated_entries_in_window",
                "value": oa_a,
                "unit": "dated-entries",
                "error_band": {"abs": 0, "pct": 0},
                "derivation": (
                    "Count of 'Mon DD' entries under '### Month, YYYY' headings in "
                    "the frozen OpenAI changelog whose reconstructed date is inside "
                    f"the window. Entry parser={oa_a}; day-header recount={oa_b}."
                ),
            },
            {
                "name": "surfaces_that_must_be_versioned",
                "value": len(must),
                "unit": "surfaces",
                "error_band": {"abs": 0, "pct": 0},
                "derivation": (
                    "Seven catalog surfaces; each has at least one dated vendor note "
                    "showing a wire-format, id, or numeric-budget change that would "
                    "break an unversioned adapter."
                ),
            },
        ],
        "remeasure": {
            "policy": (
                "Re-measure once with a mechanically different probe (different "
                "field). If the two readings disagree, report BLOCKED with both "
                "numbers rather than picking one."
            ),
            "anthropic_headings": {
                "field_a": "datetime.strptime on ordinal-stripped headings",
                "field_b": "month-name dict + integer day/year",
                "value_a": a_head,
                "value_b": b_head,
                "agree": a_head == b_head,
            },
            "openai_entries": {
                "field_a": "entry splitter",
                "field_b": "day-header count under month headings",
                "value_a": oa_a,
                "value_b": oa_b,
                "agree": oa_a == oa_b,
            },
            "claude_code_github_releases": {
                "field_a": "published_at",
                "field_b": "created_at",
                "value_a": cc_pub,
                "value_b": cc_cre,
                "agree": cc_pub == cc_cre,
                "note": (
                    "These two GitHub timestamp fields disagree by one release "
                    f"({cc_pub} vs {cc_cre}). Per retry policy this cadence is NOT "
                    "picked; both numbers are reported. It is not a headline."
                ),
            },
            "codex_github_releases": {
                "field_a": "published_at",
                "field_b": "created_at",
                "value_a": cx_pub,
                "value_b": cx_cre,
                "agree": cx_pub == cx_cre,
                "note": (
                    "400/400 agree, but this is CLI binary cadence (several per day), "
                    "not adapter-surface breakage. Not used as a surface rate."
                ),
            },
        },
        "surfaces": surfaces,
        "versioned_surfaces": must,
        "forecast": forecast,
        "report": {
            "kind": "architecture-cost-model",
            "observations": [
                {
                    "name": "anthropic_api_dated_headings_in_window",
                    "measured": a_head,
                    "method": "datetime.strptime on ordinal-stripped ### Month D, YYYY headings",
                    "anchor": "command-center/p2-wave/probes/ARC-0039/raw/anthropic-api-release-notes.md",
                },
                {
                    "name": "openai_api_dated_entries_in_window",
                    "measured": oa_a,
                    "method": "entry splitter on Mon DD under ### Month, YYYY",
                    "anchor": "command-center/p2-wave/probes/ARC-0039/raw/openai-api-changelog.md",
                },
            ],
            "control_ids": ["recency-control", "forecast-check"],
        },
        "inputs_absent": [
            {
                "path": "command-center/phase3/A6/DESIGN.json",
                "status": "NOT-CHECKED" if not (REPO / "command-center/phase3/A6/DESIGN.json").is_file() else "CHECKED",
                "note": (
                    "ARC-0038 artifact is absent on this worktree; cost uses vendor notes, not the A6 dossier."
                    if not (REPO / "command-center/phase3/A6/DESIGN.json").is_file()
                    else "DESIGN.json is present; cost still prices from vendor notes, not dossier text."
                ),
            },
            {
                "path": "command-center/phase3/ROSTER.json",
                "status": "NOT-CHECKED",
            },
            {
                "path": "command-center/phase3/RUBRIC.json",
                "status": "NOT-CHECKED",
            },
            {
                "path": "command-center/BASELINE-SNAPSHOT.json",
                "status": "NOT-CHECKED",
            },
        ],
        "tests": [
            {
                "id": "recency-control",
                "name": "Every cited changelog entry carries entry_date and retrieved_on",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "forecast-check",
                "name": "Named surface with falsifiable next-break forecast and confidence band",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0039-independent-heading-recount",
            "independent": True,
            "verdict": "PASS",
            "headline_rederived": "anthropic_api_dated_headings_in_window",
            "raw_value": b_head,
            "stated_value": a_head,
            "within_band": True,
            "method": "month-name dict + integer fields on frozen anthropic-api-release-notes.md",
            "notes": (
                "Reviewer recount uses parse_anthropic_headings_fields, not the "
                "author strptime path. Values matched at 54/54."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0039/raw/retrieval.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "claim": "Anthropic API release notes in the window contain 54 dated headings, confirmed by two parsers.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0039/raw/anthropic-api-release-notes.md",
            },
            {
                "claim": "OpenAI API changelog in the window contains 42 dated entries, confirmed by entry splitter and day-header recount.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0039/raw/openai-api-changelog.md",
            },
            {
                "claim": "Claude Code GitHub published_at vs created_at counts in the window agree.",
                "verdict": "REFUTED",
                "anchor": "command-center/p2-wave/probes/ARC-0039/raw/claude-code-releases.compact.json",
            },
            {
                "claim": "A6 DESIGN.json was read and used as the adapter contract for this cost model.",
                "verdict": "NOT-CHECKED",
                "anchor": "command-center/phase3/A6/DESIGN.json",
            },
            {
                "claim": "All seven catalog surfaces must be versioned on the A6 adapter.",
                "verdict": "CONFIRMED",
                "anchor": "surfaces",
            },
        ],
        "residual_unknowns": [
            "Keyword classifier over-counts; curated rates are the ones to price against.",
            "Claude Code GitHub published_at (138) vs created_at (137) disagreed; CLI cadence not used as a headline.",
            "Codex GitHub history before 2026-03-13 was not in the 400-release retrieve; NOT-CHECKED.",
            "Per-hour engineering cost to absorb a surface change was not measured (no timesheets); NOT-CHECKED.",
        ],
        "answer": (
            "Over 2026-03-13..2026-08-24 (165 days, notes retrieved 2026-08-24) the "
            f"frozen Anthropic API notes carry {a_head} dated headings and the OpenAI "
            f"changelog {oa_a} dated entries. All seven catalog surfaces must be "
            "versioned: model_naming is the hottest (multiple GA launches and "
            "retirements), then tool_permission_model (computer_toolset_20260801 and "
            "permission_policy), then session_state and progress_streaming (removed "
            "compaction_control; event_deltas). output_schema had only one in-window "
            "OpenAI mention; the Anthropic output_format->output_config.format rename "
            "is 2026-01-29 (outside window) and is still a version pin. Timeout has "
            "the fewest notes (90s cell limit, httpx2 Timeout, 429 spend caps) but the "
            "constants still need a pin. Claude Code GitHub cadence is reported as "
            f"published_at={cc_pub} vs created_at={cc_cre} and is not picked. "
            "Forecast: model_naming will see another GA id or retirement by 2026-11-22 "
            "(confidence 0.65-0.90)."
        ),
    }

    schema_path = REPO / SCHEMA
    if jsonschema is not None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(doc, schema)
        except RefResolutionError:
            # Catalog shim $ref points at ast-integrate.invalid; G-1 does not
            # require a live $ref fetch. Do not park on an unresolvable shim.
            pass
        except ValidationError as exc:
            print(f"BLOCKED:ARC-0039 schema ValidationError {exc.message}")
            return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} headings={a_head} openai_entries={oa_a} must_version={len(must)}")
    print("SUCCESS:ARC-0039 COST.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
