#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0063-agent-roster-model-audit.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import audit_agent_roster as R  # noqa: E402

OUT = "command-center/audit/AUD-0063-agent-roster-model-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0063 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which agent definitions exist, what model does each declare, and which "
    "substantive roles are assigned a model below the opus floor for "
    "dispatch-judgement work?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0063/probe1_frontmatter_model.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0063/probe2_dispatcher_classify.py"
)


def unshadow() -> None:
    cwd = Path.cwd().resolve()
    drop = {"", ".", str(cwd), str(Path.cwd())}
    cleaned: list[str] = []
    for p in sys.path:
        if p in drop:
            continue
        if p:
            root = Path(p)
            if (root / "platform" / "__init__.py").is_file() and (
                root / "command-center"
            ).is_dir():
                continue
        cleaned.append(p)
    sys.path[:] = cleaned
    sys.modules.pop("platform", None)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    buf: list[str] = []
    capturing = False
    depth = 0
    for line in text.splitlines():
        if not capturing and line.startswith("{"):
            capturing = True
        if capturing:
            buf.append(line)
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                return json.loads("\n".join(buf))
    raise ValueError("no JSON object in probe output")


def validate(doc: dict) -> list[str]:
    unshadow()
    import jsonschema  # noqa: E402

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{list(e.path)}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


def fp(kind: str, command: str) -> dict:
    return {"tool": kind, "command": command, "engine": "python3-frontmatter-field"}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0063 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:AUD-0063 emit probe payload pass=false")
        return 1

    inv = R.inventory()
    ctl = R.control_checks(inv)
    if not ctl.get("pass"):
        print("FAILED:AUD-0063 emit control_checks failed")
        print(json.dumps(ctl, indent=2, sort_keys=True))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prod_n = inv["production_agent_count"]
    prod_below = inv["production_below_opus_floor_count"]
    trees_present = [t["id"] for t in inv["production_trees"] if t["present"]]
    trees_absent = [t["id"] for t in inv["production_trees"] if not t["present"]]
    ctl_below = [a["name"] for a in inv["control_agents"] if a["below_opus_floor"]]
    prod_rows = [
        {
            "name": a["name"],
            "path": a["path"],
            "model": a["model_frontmatter"],
            "tier": a["model_tier"],
            "dispatching": a["dispatching"],
            "below_opus_floor": a["below_opus_floor"],
            "declared_tools": a["declared_tools"],
        }
        for a in inv["production_agents"]
    ]
    ctl_rows = [
        {
            "name": a["name"],
            "path": a["path"],
            "model": a["model_frontmatter"],
            "tier": a["model_tier"],
            "dispatching": a["dispatching"],
            "below_opus_floor": a["below_opus_floor"],
            "declared_tools": a["declared_tools"],
            "body_mentions_sonnet": a["body_mentions_sonnet"],
            "naive_body_would_assign_sonnet": a["naive_body_would_assign_sonnet"],
        }
        for a in inv["control_agents"]
    ]
    answer = (
        f"On this Linux worktree, production agent trees "
        f"{', '.join(t['path_rel'] for t in inv['production_trees'])} "
        f"yield {prod_n} definition file(s); present={trees_present or ['none']}; "
        f"absent={trees_absent}. Production dispatchers below the opus floor: "
        f"{prod_below}. Control fixtures (n={inv['control_agent_count']}) prove "
        f"the detector: mention-only-lookup is opus despite body 'sonnet'; "
        f"loop-operator (Task + mcp__codex__codex, model sonnet) is below-floor; "
        f"chief-of-staff (Task, opus) is on-floor; docs-lookup (sonnet, Read/Grep) "
        f"is not a floor hit; body-task-mention is not dispatching. "
        f"Control below-floor names={ctl_below}."
    )
    src1 = fp("frontmatter-model-field", P1)
    ver2 = fp("declared-tools-dispatcher", P2)
    src1["field"] = "frontmatter.model"
    ver2["field"] = "frontmatter.tools"

    doc = {
        "unit_id": "AUD-0063",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "audit-finding",
        "kind": "audit-finding",
        "title": "Agent roster inventory and model-assignment audit",
        "question": QUESTION,
        "answer": answer,
        "measured_at": now,
        "schema": SCHEMA,
        "roster": {
            "production_agent_count": prod_n,
            "production_below_opus_floor_count": prod_below,
            "production_trees": [
                {
                    "id": t["id"],
                    "present": t["present"],
                    "md_count": t["md_count"],
                    "path_rel": t["path_rel"],
                }
                for t in inv["production_trees"]
            ],
            "production_agents": prod_rows,
            "control_agents": ctl_rows,
            "opus_floor_rule": (
                "A dispatching agent (declared Task/Agent/spawn tool or "
                "cross-vendor mcp__ prefix) must not be sonnet/haiku/undeclared. "
                "The floor does not apply to non-dispatchers."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "frontmatter-model-field-extraction",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "dispatcher-tool-classification",
                "raw_output": t2,
            },
        ],
        "tests": [
            {
                "id": "use-vs-mention-model",
                "name": (
                    "an agent that merely mentions a model name in its prose "
                    "body must not be classified by that mention"
                ),
                "result": "PASS" if ctl["mention_assigned_opus_not_sonnet"] else "FAIL",
            },
            {
                "id": "naive-grep-goes-red",
                "name": "body grep for sonnet flags the mention-only fixture",
                "result": "PASS"
                if ctl["naive_grep_disagrees_with_frontmatter"]
                else "FAIL",
            },
            {
                "id": "dispatcher-sonnet-below-floor",
                "name": "Task+mcp__codex dispatcher with model sonnet is below floor",
                "result": "PASS" if ctl["dispatcher_sonnet_below_floor"] else "FAIL",
            },
            {
                "id": "dispatcher-opus-on-floor",
                "name": "Task dispatcher with model opus is not below floor",
                "result": "PASS" if ctl["dispatcher_opus_on_floor"] else "FAIL",
            },
            {
                "id": "non-dispatcher-sonnet-exempt",
                "name": "non-dispatching sonnet agent is not a floor violation",
                "result": "PASS" if ctl["non_dispatcher_sonnet_not_floor"] else "FAIL",
            },
            {
                "id": "use-vs-mention-tools",
                "name": "body mention of Task does not classify an agent as dispatching",
                "result": "PASS"
                if ctl["body_task_mention_not_dispatching"]
                else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "use-vs-mention-model",
                "fired_on_bad": True,
                "silent_on_good": True,
                "result": "PASS",
                "good": "mention-only-lookup model_tier=opus body mentions sonnet",
                "bad": "loop-operator model_tier=sonnet via frontmatter field",
            },
            {
                "id": "use-vs-mention-tools",
                "fired_on_bad": True,
                "silent_on_good": True,
                "result": "PASS",
                "good": "body-task-mention dispatching=false",
                "bad": "loop-operator dispatching=true via declared tools",
            },
        ],
        "evidence": [
            {
                "id": "AUD-0063-E1",
                "text": (
                    "mention-only-lookup frontmatter model is opus; a body grep "
                    "for sonnet would mis-assign it."
                ),
                "verdict": "CONFIRMED",
                "source_probe": src1,
                "verifier_probe": ver2,
                "path": "command-center/p2-wave/probes/AUD-0063/fixtures/agents/mention-only.md",
                "kind": "control",
                "note": "use-versus-mention for the model field",
            },
            {
                "id": "AUD-0063-E2",
                "text": (
                    "loop-operator is dispatching from declared Task and "
                    "mcp__codex__codex and is below the opus floor; "
                    "docs-lookup is sonnet but not dispatching so the floor "
                    "does not apply."
                ),
                "verdict": "CONFIRMED",
                "source_probe": ver2,
                "verifier_probe": src1,
                "path": "command-center/p2-wave/probes/AUD-0063/fixtures/agents/dispatcher-sonnet.md",
                "kind": "control",
                "note": "floor applies to dispatchers only",
            },
            {
                "id": "AUD-0063-E3",
                "text": (
                    f"Production agent definition count on this worktree is {prod_n}; "
                    f"production below-floor count is {prod_below}."
                ),
                "verdict": "CONFIRMED",
                "source_probe": src1,
                "verifier_probe": ver2,
                "path": "agents",
                "kind": "live-tree",
                "note": "inventory of declared production trees",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0063-probe2-dispatcher-classify",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 classifies dispatching from declared tools and does "
                "not re-run probe 1's mapping parse. Catalog also names a "
                "fresh-context Claude falsifier; this G-1 records the "
                "mechanical independent probe as reviewer, not that Claude seat."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/AUD-0063/audit_agent_roster.py",
                "exists": True,
                "role": "engine",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0063/probe1_frontmatter_model.py",
                "exists": True,
                "role": "probe1",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0063/probe2_dispatcher_classify.py",
                "exists": True,
                "role": "probe2",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0063/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "AUD-0063",
            "note": "per-unit manifest only; did not run unit_manifest.py --write",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "probe": "live named-probe re-run",
            }
        ],
        "residual_caveat": (
            "Production agents/, .claude/agents, ~/.claude/agents, and "
            ".cursor/agents are measured as present-or-absent on THIS Linux "
            "worktree. A prior Windows harvest of agents/ is not replayed as "
            "if it lived here. Catalog reviewer_requirement still names a "
            "fresh-context Claude count-falsifier; probe2 is a mechanically "
            "different local classifier, not that reviewer."
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-headless",
        },
    }

    if any(t["result"] != "PASS" for t in doc["tests"]):
        print("FAILED:AUD-0063 emit a required test is not PASS")
        return 1

    errs = validate(doc)
    if errs:
        print("FAILED:AUD-0063 emit schema-invalid")
        for e in errs[:20]:
            print(f"  {e}")
        return 1
    garbage_rejected = 0
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        g_errs = validate(garbage)
        if not g_errs:
            print("FAILED:AUD-0063 emit schema accepts garbage", garbage)
            return 1
        garbage_rejected += 1
    doc["schema_garbage_rejected"] = garbage_rejected

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written = json.loads(dest.read_text(encoding="utf-8"))
    errs = validate(written)
    if errs:
        print("FAILED:AUD-0063 emit written schema-invalid")
        for e in errs[:20]:
            print(f"  {e}")
        return 1
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:AUD-0063 emit completion_sentinel absent")
        return 1
    if '"state": "SUCCESS"' not in text and '"state":"SUCCESS"' not in text:
        print("FAILED:AUD-0063 emit state SUCCESS absent")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size} garbage_rejected={garbage_rejected}")
    print("SUCCESS:AUD-0063 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
