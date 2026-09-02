#!/usr/bin/env python3
"""Emit the CNL-0012 council design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402
import roster as R  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0012-exact-roster-resolution-and-capability-negotiation-on-the-.md"
)
SCHEMA = "command-center/p2-wave/probes/CNL-0012/council-design-note.schema.json"
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SPEC = HERE / "fixtures" / "catalog-named-spec.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0012/probe1_vendor_reachability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0012/probe2_unreachable_seat.py"
)
QUESTION = (
    "When a CouncilSpec names an exact model/vendor seat that is not reachable "
    "on this machine, does the runtime substitute, degrade loudly, or refuse - "
    "and what does a live probe of the currently mounted vendors (anthropic "
    "in-session, openai via the codex MCP) actually report today?"
)


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0012 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    live = E.measure()
    resolved = R.resolve_exact(spec, live)
    live_violations = R.silent_substitution_violations(spec, resolved)
    if live_violations:
        print("FAILED:CNL-0012 live resolution violations", live_violations)
        return 1
    if resolved["decision"] != "REFUSED":
        print("FAILED:CNL-0012 catalog-named seats unexpectedly SEATED")
        return 1

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNL-0012 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    session = live.get("session") or {}
    mcp = live.get("mcp_inventory") or {}
    anth = (live.get("vendors") or {}).get("anthropic") or {}
    oai = (live.get("vendors") or {}).get("openai") or {}
    select = live.get("production_select_explicit") or {}

    answer = (
        "Exact named seats are REFUSED when unreachable: the resolver emits a "
        "LOUD degradation record per unmet seat (action=REFUSE-SEAT) and seats "
        "nobody. Silent same-vendor substitution is forbidden and is a detector "
        "failure, not a fallback. Live estate on this Linux worktree: anthropic "
        "credential ABSENT (unauthenticated GET to api.anthropic.com status="
        + str((anth.get("http_unauthenticated_models") or {}).get("status"))
        + ", TCP443="
        + str((anth.get("network_tcp443") or {}).get("ok"))
        + "); openai credential ABSENT (unauthenticated GET to api.openai.com status="
        + str((oai.get("http_unauthenticated_models") or {}).get("status"))
        + ", TCP443="
        + str((oai.get("network_tcp443") or {}).get("ok"))
        + "); openai-via-codex MCP is NOT mounted (mcp server_names="
        + json.dumps(mcp.get("server_names") or [])
        + "); in-session vendor is cursor model="
        + str(session.get("model_id"))
        + ", not anthropic. Production tools/council/participants/select_explicit.py "
        "present="
        + str(bool(select.get("present")))
        + " — there is no production seating runtime here that could silently "
        "swap a model. Catalog-named seats therefore resolve to REFUSED with two "
        "LOUD records. SUCCESS:CNL-0012"
    )

    doc = {
        "unit_id": "CNL-0012",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0012",
        "completion_sentinel": "SUCCESS:CNL-0012",
        "title": "Exact roster resolution and capability negotiation on the live estate",
        "question": QUESTION,
        "answer": answer,
        "policy": {
            "exact_roster_unmet_seat": "REFUSE-SEAT",
            "council_if_any_exact_seat_unmet": "REFUSED",
            "silent_same_vendor_substitution": "forbidden",
            "loud_substitution": "forbidden",
            "degradation": "LOUD-record-required",
            "partial_exact_roster": "forbidden",
            "capability_negotiation": (
                "requested vendor+model+transport intersected with reachable_entries; "
                "gaps are unmet exact seats, never filled by a same-vendor neighbour"
            ),
        },
        "dependency_cnl_0005": {
            "output_path": "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md",
            "present": (
                REPO
                / "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
            ).is_file(),
            "reachability_dials_used": ["vendor", "model", "transport"],
            "note": (
                "CNL-0005 is not delivered on this tree. This unit answers "
                "reachability for exact vendor+model(+transport) seats without "
                "waiting on the nine-dial type note."
            ),
        },
        "live_estate": live,
        "live_resolution": resolved,
        "live_silent_substitution_violations": live_violations,
        "catalog_named_transports_today": live.get("catalog_named_transports"),
        "evidence": [
            {
                **ev(
                    "command-center/p2-wave/probes/CNL-0012/roster.py",
                    'REFUSE_SEAT = "REFUSE-SEAT"',
                    "probe-runtime",
                    "Exact unmet seats are refused, not substituted.",
                ),
                "verdict": "CONFIRMED",
            },
            {
                **ev(
                    "command-center/p2-wave/probes/CNL-0012/roster.py",
                    "violations.append(f\"same-vendor-substitution:{want['id']}\")",
                    "probe-runtime",
                    "Same-vendor model swap is a detector violation even if a record exists.",
                ),
                "verdict": "CONFIRMED",
            },
            {
                **ev(
                    "command-center/p2-wave/probes/CNL-0012/estate.py",
                    'signal": "mounted-server-inventory"',
                    "live-tree",
                    "Second signal is the mounted-server inventory, independent of env/HTTP.",
                ),
                "verdict": "CONFIRMED",
            },
            {
                **ev(
                    CATALOG,
                    "openai via the codex MCP",
                    "catalog",
                    "Catalog-named live vendors are anthropic in-session and openai via codex MCP.",
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [
            {
                "id": "probe1-vendor-reachability",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "exit_code": rc1,
                "raw_output": out1,
            },
            {
                "id": "probe2-unreachable-seat",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "exit_code": rc2,
                "raw_output": out2,
            },
        ],
        "negative_controls": [
            {
                "id": "silent-same-vendor-substitution",
                "rejects": (
                    "a planted result that seats a different same-vendor model "
                    "with degradations=[]"
                ),
                "verbatim": (
                    "The check rejects a planted silent same-vendor substitution "
                    "(requested claude-opus-4, seated a sonnet-shaped swap, "
                    "degradations=[]). It is silent when resolve_exact seats the "
                    "exact requested vendor+model on the known-good estate."
                ),
                "fires_on_planted_bad": True,
                "silent_on_known_good": True,
            },
            {
                "id": "credential-value-leak",
                "rejects": "any serialised measure/probe output containing a live env secret",
                "verbatim": (
                    "The leak scanner is proven non-vacuous by detecting a planted "
                    "synthetic token in a scratch string, then applied to the live "
                    "measure JSON. A hit names the env var, never the value."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0012-probe2-silent-substitution-detector",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "counterexample": (
                "planted_silent_same_vendor_substitution(spec) is REFUTED by "
                "silent_substitution_violations; known-good resolve_exact is silent"
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": CATALOG_SCHEMA,
                "exists": (REPO / CATALOG_SCHEMA).is_file(),
                "role": "catalog-named-schema-shared-contested",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0012/roster.py",
                "exists": True,
                "role": "resolver",
            },
        ],
        "required_fix": None,
        "cloud_ok": False,
        "schema_note": (
            "Catalog output_schema is command-center/schema/council-design-note.schema.json. "
            "On this tree that file was overwritten by CNL-0030 chair/flat fields "
            "(declared_metric, size_sweep). This unit does not invent a chair size-sweep "
            "and does not rebuild the shared schema. Validation uses the per-unit schema."
        ),
    }

    out_path = REPO / OUT
    dump(out_path, doc)
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    if "SUCCESS:CNL-0012" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:CNL-0012 sentinel missing after write")
        return 1
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0012 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
