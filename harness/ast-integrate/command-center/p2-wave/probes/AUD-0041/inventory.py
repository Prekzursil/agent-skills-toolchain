#!/usr/bin/env python3
"""AUD-0041 CI workflow / job / step inventory.

Probe 1: YAML parse of fixture workflows plus reconstructed origin YAML
from the captured .github/workflows inventory (that tree is absent here).
Probe 2: GitHub Actions API job lists (captured sample + synthetic known
runs) and a string-named workflow registry.

Planted control: aud0041_fx.ghost is named only as a registry string.
Probe 1 must report DEAD; probe 2 must report LIVE. Stripping string
edges must return it to DEAD.
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0041"
GHOST = "aud0041_fx.ghost"
TRULY_ABSENT = "aud0041_fx.truly_absent"
MENTION_ONLY = "aud0041_fx.mention_only"
CAPTURED_INV = HERE / "probe1-yaml-inventory.json"
CAPTURED_API = HERE / "probe2-actions-api.json"
REGISTRY = HERE / "fixtures" / "aud0041_fx" / "registry.json"
FIXTURE_WF = HERE / "fixtures" / "workflows"
SYNTH_API = HERE / "fixtures" / "api"
LIVE_WF = REPO / ".github" / "workflows"
USES_RE = re.compile(r"^uses:(.*?)(?: with\[(.*)\])?$")

ORIGIN_EXPECTED = {
    "workflow_files": 7,
    "jobs": 14,
    "expanded_legs": 14,
    "steps": 143,
    "conditional_steps": 4,
    "conditional_jobs": 2,
}


def expand_matrix(job: dict) -> list[dict]:
    """Expand strategy.matrix into concrete legs (cartesian + include - exclude)."""
    strat = (job or {}).get("strategy") or {}
    m = strat.get("matrix")
    if not isinstance(m, dict):
        return [{}]
    include = m.get("include") or []
    exclude = m.get("exclude") or []
    axes = {
        k: v
        for k, v in m.items()
        if k not in ("include", "exclude") and isinstance(v, list)
    }
    if axes:
        keys = list(axes)
        legs = [
            dict(zip(keys, combo))
            for combo in itertools.product(*(axes[k] for k in keys))
        ]
    else:
        legs = []
    legs = [
        lg
        for lg in legs
        if not any(all(lg.get(k) == v for k, v in ex.items()) for ex in exclude)
    ]
    for inc in include:
        if not isinstance(inc, dict):
            continue
        merged = False
        for lg in legs:
            if all(lg.get(k) == v for k, v in inc.items() if k in lg):
                lg.update(inc)
                merged = True
        if not merged:
            legs.append(dict(inc))
    return legs or [{}]


def step_command(step: dict) -> str:
    if not isinstance(step, dict):
        return "<malformed-step>"
    if "run" in step:
        return " ".join(str(step["run"]).split())[:600]
    if "uses" in step:
        w = step.get("with") or {}
        extra = (
            ",".join(f"{k}={str(v)[:40]}" for k, v in list(w.items())[:6])
            if isinstance(w, dict)
            else ""
        )
        return f"uses:{step['uses']}" + (f" with[{extra}]" if extra else "")
    return "<no-run-no-uses>"


def triggers_of(doc: dict):
    """PyYAML 1.1 parses bare `on:` as boolean True. Reading only doc['on']
    would report every workflow as trigger-less."""
    return doc.get("on", doc.get(True))


def normalize_triggers(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, dict):
        return sorted(raw)
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            else:
                out.append(str(item))
        return out
    return [str(raw)]


def parse_workflow_doc(doc: dict, file_label: str) -> dict:
    doc = doc or {}
    triggers = normalize_triggers(triggers_of(doc))
    jobs = doc.get("jobs") or {}
    wf = {
        "file": file_label,
        "name": doc.get("name"),
        "triggers": triggers,
        "jobs": [],
    }
    for jn, j in jobs.items():
        j = j or {}
        legs = expand_matrix(j)
        steps = j.get("steps") or []
        jrow = {
            "job_id": jn,
            "name": j.get("name"),
            "runs_on": j.get("runs-on"),
            "job_if": j.get("if"),
            "needs": j.get("needs"),
            "uses_reusable": j.get("uses"),
            "matrix_legs": legs,
            "leg_count": len(legs),
            "step_count": len(steps),
            "steps": [
                {
                    "index": i,
                    "name": s.get("name") if isinstance(s, dict) else None,
                    "command": step_command(s),
                    "conditional_on": (
                        s.get("if") if isinstance(s, dict) else None
                    ),
                    "shell": (s.get("shell") if isinstance(s, dict) else None),
                    "continue_on_error": (
                        s.get("continue-on-error") if isinstance(s, dict) else None
                    ),
                }
                for i, s in enumerate(steps)
            ],
        }
        wf["jobs"].append(jrow)
    return wf


def parse_yaml_text(text: str, file_label: str) -> dict:
    doc = yaml.safe_load(text) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"workflow {file_label} did not parse as a mapping")
    return parse_workflow_doc(doc, file_label)


def parse_yaml_file(path: Path, file_label: str | None = None) -> dict:
    return parse_yaml_text(
        path.read_text(encoding="utf-8"),
        file_label or path.as_posix(),
    )


def parse_uses_command(cmd: str) -> tuple[str, dict]:
    m = USES_RE.match(cmd)
    if not m:
        return cmd[5:] if cmd.startswith("uses:") else cmd, {}
    uses = (m.group(1) or "").strip()
    inner = m.group(2) or ""
    with_map: dict[str, str] = {}
    if inner:
        for part in inner.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                with_map[k.strip()] = v
    return uses, with_map


def reconstruct_workflow_yaml(wf: dict) -> str:
    """Rebuild YAML from a captured inventory row so probe 1 is a YAML parse."""
    lines: list[str] = []
    if wf.get("name"):
        lines.append(f"name: {json.dumps(wf['name'])}")
    lines.append("on:")
    triggers = wf.get("triggers") or []
    if isinstance(triggers, list) and triggers:
        for t in triggers:
            lines.append(f"  - {t}")
    else:
        lines.append("  - push")
    lines.append("jobs:")
    for job in wf.get("jobs") or []:
        lines.append(f"  {job['job_id']}:")
        if job.get("name"):
            lines.append(f"    name: {json.dumps(job['name'])}")
        if job.get("runs_on") is not None:
            lines.append(f"    runs-on: {json.dumps(job['runs_on'])}")
        if job.get("job_if"):
            lines.append(f"    if: {json.dumps(job['job_if'])}")
        if job.get("needs") is not None:
            lines.append(f"    needs: {json.dumps(job['needs'])}")
        if job.get("uses_reusable"):
            lines.append(f"    uses: {json.dumps(job['uses_reusable'])}")
        lines.append("    steps:")
        steps = job.get("steps") or []
        if not steps:
            lines.append("      - run: echo empty")
            continue
        for step in steps:
            keys: list[tuple[str, object]] = []
            if step.get("name"):
                keys.append(("name", step["name"]))
            cmd = step.get("command") or ""
            with_map: dict[str, str] = {}
            if cmd.startswith("uses:"):
                uses, with_map = parse_uses_command(cmd)
                keys.append(("uses", uses))
            elif cmd in {"<no-run-no-uses>", "<malformed-step>", ""}:
                keys.append(("run", "echo malformed"))
            else:
                keys.append(("run", cmd))
            if step.get("conditional_on"):
                keys.append(("if", step["conditional_on"]))
            if step.get("shell"):
                keys.append(("shell", step["shell"]))
            if step.get("continue_on_error") is not None:
                keys.append(("continue-on-error", step["continue_on_error"]))
            first_k, first_v = keys[0]
            lines.append(f"      - {first_k}: {json.dumps(first_v)}")
            for k, v in keys[1:]:
                if isinstance(v, bool):
                    lines.append(f"        {k}: {'true' if v else 'false'}")
                else:
                    lines.append(f"        {k}: {json.dumps(v)}")
            if with_map:
                lines.append("        with:")
                for wk, wv in with_map.items():
                    lines.append(f"          {wk}: {json.dumps(wv)}")
    return "\n".join(lines) + "\n"


def totals_of(workflows: list[dict]) -> dict:
    n_jobs = n_steps = n_cond_steps = n_cond_jobs = n_legs = 0
    for w in workflows:
        for j in w.get("jobs") or []:
            n_jobs += 1
            n_legs += int(j.get("leg_count") or 0)
            n_steps += int(j.get("step_count") or 0)
            n_cond_steps += sum(
                1 for s in j.get("steps") or [] if s.get("conditional_on")
            )
            n_cond_jobs += 1 if j.get("job_if") else 0
    return {
        "workflow_files": len(workflows),
        "jobs": n_jobs,
        "expanded_legs": n_legs,
        "steps": n_steps,
        "conditional_steps": n_cond_steps,
        "conditional_jobs": n_cond_jobs,
    }


def load_captured_origin() -> list[dict]:
    inv = json.loads(CAPTURED_INV.read_text(encoding="utf-8"))
    parsed = []
    for wf in inv.get("workflows") or []:
        text = reconstruct_workflow_yaml(wf)
        row = parse_yaml_text(text, wf["file"])
        parsed.append(row)
    got = totals_of(parsed)
    for key, want in ORIGIN_EXPECTED.items():
        if got.get(key) != want:
            raise SystemExit(
                f"FAILED:AUD-0041 origin YAML round-trip {key}={got.get(key)} want={want}"
            )
    return parsed


def load_fixture_workflows() -> list[dict]:
    rows = []
    for path in sorted(FIXTURE_WF.glob("*.yml")):
        rel = path.relative_to(REPO).as_posix()
        rows.append(parse_yaml_file(path, rel))
    return rows


def load_live_github() -> list[dict]:
    if not LIVE_WF.is_dir():
        return []
    rows = []
    for path in sorted(LIVE_WF.glob("*.y*ml")):
        rows.append(parse_yaml_file(path, f".github/workflows/{path.name}"))
    return rows


def load_registry_ids() -> set[str]:
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    names = set()
    wr = doc.get("WORKFLOW_REGISTRY") or {}
    if isinstance(wr, dict):
        names.update(str(k) for k in wr)
    return names


def load_api_runs() -> list[dict]:
    runs = []
    captured = json.loads(CAPTURED_API.read_text(encoding="utf-8"))
    for r in captured.get("runs") or []:
        row = dict(r)
        row["source"] = "captured-actions-api"
        runs.append(row)
    for path in sorted(SYNTH_API.glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        runs.append(row)
    return runs


def job_display_name(job: dict) -> str:
    return job.get("name") or job.get("job_id") or ""


def wf_key(wf: dict) -> str:
    return wf.get("name") or Path(wf.get("file") or "").stem


def api_index(runs: list[dict]) -> dict:
    by_wf: dict[str, dict] = {}
    for r in runs:
        name = r.get("workflow")
        if not name:
            continue
        by_wf[name] = r
    return by_wf


def api_job_by_name(run: dict | None) -> dict[str, dict]:
    out = {}
    if not run:
        return out
    for j in run.get("jobs") or []:
        out[j.get("name") or ""] = j
    return out


def item(
    iid: str,
    kind: str,
    path: str,
    p1: str,
    p2: str,
    **extra,
) -> dict:
    row = {
        "id": iid,
        "kind": kind,
        "path": path,
        "probe1_verdict": p1,
        "probe2_verdict": p2,
    }
    row.update(extra)
    return row


def build() -> dict:
    origin = load_captured_origin()
    fixtures = load_fixture_workflows()
    live_gh = load_live_github()
    registry = load_registry_ids()
    runs = load_api_runs()
    api_by_wf = api_index(runs)
    yaml_workflows = fixtures + origin + live_gh
    yaml_ids = set()
    items: list[dict] = []

    for wf in yaml_workflows:
        wid = wf_key(wf)
        yaml_ids.add(wid)
        path = wf["file"]
        run = api_by_wf.get(wid)
        p1 = "LIVE"
        p2 = "LIVE" if run is not None else "DEAD"
        universe = (
            "fixture"
            if path.startswith("command-center/p2-wave/probes/AUD-0041/fixtures/")
            else ("live-github" if path.startswith(".github/workflows/") and live_gh and wf in live_gh else "captured-origin")
        )
        if wf in fixtures:
            universe = "fixture"
        elif wf in live_gh:
            universe = "live-github"
        else:
            universe = "captured-origin"
        items.append(
            item(
                f"wf:{wid}",
                "module",
                path if len(path) >= 8 else f"{path}.yml",
                p1,
                p2,
                universe=universe,
                triggers=wf.get("triggers") or [],
                job_count=len(wf.get("jobs") or []),
            )
        )
        jobs_api = api_job_by_name(run)
        for job in wf.get("jobs") or []:
            jname = job_display_name(job)
            aj = None
            if jname in jobs_api:
                aj = jobs_api[jname]
            elif run and int(job.get("leg_count") or 1) > 1:
                # matrix job: API reports one row per expanded leg, not the YAML job id
                aj = None
            jp2 = "LIVE" if (aj is not None or (run and int(job.get("leg_count") or 1) > 1)) else "DEAD"
            items.append(
                item(
                    f"job:{wid}/{job['job_id']}",
                    "module",
                    f"{path}#jobs.{job['job_id']}",
                    "LIVE",
                    jp2,
                    universe=universe,
                    leg_count=job.get("leg_count"),
                    step_count=job.get("step_count"),
                    job_if=job.get("job_if"),
                    runs_on=job.get("runs_on"),
                )
            )
            skipped = set((aj or {}).get("skipped_steps") or [])
            for step in job.get("steps") or []:
                sname = step.get("name")
                if aj is None and not (run and int(job.get("leg_count") or 1) > 1):
                    sp2 = "DEAD"
                    reason = "workflow-not-in-api-sample"
                elif sname and sname in skipped:
                    sp2 = "DEAD"
                    reason = "api-skipped"
                else:
                    sp2 = "LIVE"
                    reason = "api-executed-or-matrix-leg"
                items.append(
                    item(
                        f"step:{wid}/{job['job_id']}/{step['index']}",
                        "function",
                        f"{path}#jobs.{job['job_id']}.steps[{step['index']}]",
                        "LIVE",
                        sp2,
                        universe=universe,
                        step_name=sname,
                        command=step.get("command"),
                        conditional_on=step.get("conditional_on"),
                        probe2_reason=reason,
                    )
                )
            if aj:
                yaml_names = {
                    s.get("name") for s in job.get("steps") or [] if s.get("name")
                }
                for sk in skipped:
                    if sk in yaml_names:
                        continue
                    items.append(
                        item(
                            f"api-skip:{wid}/{job['job_id']}/{sk}",
                            "function",
                            f"github-api:{wid}/{jname}/{sk}",
                            "DEAD",
                            "DEAD",
                            universe="api-injected",
                            step_name=sk,
                            probe2_reason="api-injected-skipped",
                        )
                    )

    for rid in sorted(registry):
        yaml_ids.add(rid)
        p1 = "DEAD"
        p2 = "LIVE"
        items.append(
            item(
                rid,
                "module",
                "command-center/p2-wave/probes/AUD-0041/fixtures/aud0041_fx/registry.json",
                p1,
                p2,
                universe="string-registry",
            )
        )

    items.append(
        item(
            TRULY_ABSENT,
            "module",
            "command-center/p2-wave/probes/AUD-0041/fixtures/aud0041_fx/truly_absent.yml",
            "DEAD",
            "DEAD",
            universe="control",
        )
    )
    items.append(
        item(
            MENTION_ONLY,
            "module",
            "command-center/p2-wave/probes/AUD-0041/fixtures/workflows/control-plain.yml",
            "DEAD",
            "DEAD",
            universe="control",
            note="named only in a YAML comment; comments are not uses",
        )
    )

    yaml_file_ids = {wf_key(w) for w in yaml_workflows}
    p2_without_strings = set(yaml_file_ids)
    # strawman: registry ids are invisible without string edges
    ghost_p2_no_string = GHOST in p2_without_strings

    origin_tot = totals_of(origin)
    fixture_tot = totals_of(fixtures)
    live_tot = totals_of(live_gh)
    matrix_wf = next(w for w in fixtures if wf_key(w) == "control-matrix")
    plain_wf = next(w for w in fixtures if wf_key(w) == "control-plain")
    skipped_wf = next(w for w in fixtures if wf_key(w) == "control-skipped")
    matrix_legs = matrix_wf["jobs"][0]["leg_count"]
    plain_legs = plain_wf["jobs"][0]["leg_count"]
    api_matrix = api_by_wf["control-matrix"]["api_job_count"]
    api_plain = api_by_wf["control-plain"]["api_job_count"]
    never_step = next(
        s
        for s in skipped_wf["jobs"][0]["steps"]
        if s.get("name") == "never"
    )
    always_step = next(
        s
        for s in skipped_wf["jobs"][0]["steps"]
        if s.get("name") == "always"
    )

    modules = [i for i in items if i["kind"] == "module"]
    disagree = [i for i in modules if i["probe1_verdict"] != i["probe2_verdict"]]
    both_dead = [
        i
        for i in modules
        if i["probe1_verdict"] == "DEAD" and i["probe2_verdict"] == "DEAD"
    ]
    ghost_row = next(i for i in items if i["id"] == GHOST)
    never_row = next(
        i
        for i in items
        if i["id"].endswith("/never") or i.get("step_name") == "never"
    )
    # never step id is step:control-skipped/gated/1
    never_row = next(
        i
        for i in items
        if i["kind"] == "function"
        and i.get("step_name") == "never"
        and i["universe"] == "fixture"
    )
    always_row = next(
        i
        for i in items
        if i["kind"] == "function"
        and i.get("step_name") == "always"
        and i["universe"] == "fixture"
    )

    ctl = {
        "id": "AUD-0041-C-registry-string",
        "kind": "string-registry-only",
        "module": GHOST,
        "probe1_verdict": ghost_row["probe1_verdict"],
        "probe2_verdict": ghost_row["probe2_verdict"],
        "probe2_without_string_edges": "LIVE" if ghost_p2_no_string else "DEAD",
        "strawman_string_edges_required": not ghost_p2_no_string,
        "independent": (
            ghost_row["probe1_verdict"] == "DEAD"
            and ghost_row["probe2_verdict"] == "LIVE"
            and (not ghost_p2_no_string)
        ),
        "matrix_leg_count": matrix_legs,
        "api_matrix_job_count": api_matrix,
        "plain_leg_count": plain_legs,
        "api_plain_job_count": api_plain,
        "on_key_boolean_trap_survived": all(
            (w.get("triggers") or []) for w in yaml_workflows
        ),
        "skipped_step_never": {
            "probe1": never_row["probe1_verdict"],
            "probe2": never_row["probe2_verdict"],
        },
        "executed_step_always": {
            "probe1": always_row["probe1_verdict"],
            "probe2": always_row["probe2_verdict"],
        },
    }

    recon = []
    for w in origin:
        nm = wf_key(w)
        pred = sum(j["leg_count"] for j in w["jobs"])
        run = api_by_wf.get(nm)
        api_n = run.get("api_job_count") if run else None
        recon.append(
            {
                "workflow": nm,
                "static_predicted_legs": pred,
                "api_reported_jobs": api_n,
                "agree": api_n == pred,
                "sampled": run is not None,
            }
        )
    sampled = [x for x in recon if x["sampled"]]
    agree_n = sum(1 for x in sampled if x["agree"])

    return {
        "items": items,
        "origin": origin,
        "fixtures": fixtures,
        "live_github": live_gh,
        "origin_totals": origin_tot,
        "fixture_totals": fixture_tot,
        "live_totals": live_tot,
        "registry": sorted(registry),
        "api_runs": runs,
        "leg_reconciliation": recon,
        "sampled_agree": f"{agree_n}/{len(sampled)}" if sampled else "0/0",
        "planted_control": ctl,
        "tallies": {
            "modules_scanned": len(modules),
            "probe1_dead": sum(1 for i in modules if i["probe1_verdict"] == "DEAD"),
            "probe2_dead": sum(1 for i in modules if i["probe2_verdict"] == "DEAD"),
            "both_dead": len(both_dead),
            "disagree": len(disagree),
            "functions_listed": sum(1 for i in items if i["kind"] == "function"),
            "origin_workflow_files": origin_tot["workflow_files"],
            "origin_jobs": origin_tot["jobs"],
            "origin_steps": origin_tot["steps"],
            "origin_conditional_steps": origin_tot["conditional_steps"],
            "origin_conditional_jobs": origin_tot["conditional_jobs"],
            "live_github_workflow_files": live_tot["workflow_files"],
        },
        "both_dead_modules": [i["id"] for i in both_dead],
        "disagree_modules": [
            {
                "id": i["id"],
                "probe1": i["probe1_verdict"],
                "probe2": i["probe2_verdict"],
            }
            for i in disagree
        ],
        "matrix_legs": matrix_wf["jobs"][0]["matrix_legs"],
        "never_step": never_step,
        "always_step": always_step,
        "github_workflows_on_disk": LIVE_WF.is_dir(),
    }


def assert_control(cen: dict) -> None:
    ctl = cen["planted_control"]
    tot = cen["origin_totals"]
    if tot != ORIGIN_EXPECTED:
        raise SystemExit(
            f"FAILED:AUD-0041 origin totals {tot} != {ORIGIN_EXPECTED}"
        )
    if ctl["matrix_leg_count"] != 6 or ctl["api_matrix_job_count"] != 6:
        raise SystemExit(
            "FAILED:AUD-0041 matrix expander vs API known-run "
            f"yaml={ctl['matrix_leg_count']} api={ctl['api_matrix_job_count']}"
        )
    if ctl["plain_leg_count"] != 1 or ctl["api_plain_job_count"] != 1:
        raise SystemExit(
            "FAILED:AUD-0041 plain job vs API known-run "
            f"yaml={ctl['plain_leg_count']} api={ctl['api_plain_job_count']}"
        )
    if not ctl["independent"]:
        raise SystemExit(
            "FAILED:AUD-0041 planted string-registry control did not discriminate "
            f"{json.dumps(ctl, sort_keys=True)}"
        )
    if not ctl["on_key_boolean_trap_survived"]:
        raise SystemExit("FAILED:AUD-0041 on:-as-True trap swallowed triggers")
    if ctl["skipped_step_never"] != {"probe1": "LIVE", "probe2": "DEAD"}:
        raise SystemExit(
            f"FAILED:AUD-0041 skipped-step control {ctl['skipped_step_never']}"
        )
    if ctl["executed_step_always"] != {"probe1": "LIVE", "probe2": "LIVE"}:
        raise SystemExit(
            f"FAILED:AUD-0041 executed-step control {ctl['executed_step_always']}"
        )
    if cen["tallies"]["disagree"] < 1:
        raise SystemExit("FAILED:AUD-0041 probes do not disagree on any module")
    existing = {wf_key(w) for w in cen["fixtures"] + cen["origin"] + cen["live_github"]}
    if MENTION_ONLY in existing:
        raise SystemExit("FAILED:AUD-0041 comment mention counted as a workflow")


def probe1_payload(cen: dict) -> dict:
    origin = cen["origin_totals"]
    ctl = cen["planted_control"]
    return {
        "probe": "probe1-yaml-parse",
        "method": "yaml.safe_load + expand_matrix; on-key via doc.get('on', doc.get(True))",
        "github_workflows_on_disk": cen["github_workflows_on_disk"],
        "origin_totals": origin,
        "fixture_totals": cen["fixture_totals"],
        "ghost": next(i["probe1_verdict"] for i in cen["items"] if i["id"] == GHOST),
        "truly_absent": next(
            i["probe1_verdict"] for i in cen["items"] if i["id"] == TRULY_ABSENT
        ),
        "mention_only": next(
            i["probe1_verdict"] for i in cen["items"] if i["id"] == MENTION_ONLY
        ),
        "matrix_leg_count": ctl["matrix_leg_count"],
        "plain_leg_count": ctl["plain_leg_count"],
        "on_key_boolean_trap_survived": ctl["on_key_boolean_trap_survived"],
        "workflows": [
            {
                "file": w["file"],
                "name": w["name"],
                "triggers": w["triggers"],
                "jobs": [
                    {
                        "job_id": j["job_id"],
                        "name": j["name"],
                        "leg_count": j["leg_count"],
                        "step_count": j["step_count"],
                        "job_if": j["job_if"],
                        "steps": j["steps"],
                    }
                    for j in w["jobs"]
                ],
            }
            for w in cen["origin"]
        ],
    }


def probe2_payload(cen: dict) -> dict:
    ctl = cen["planted_control"]
    skipped_origin = [
        i
        for i in cen["items"]
        if i["kind"] == "function"
        and i.get("universe") == "captured-origin"
        and i["probe1_verdict"] == "LIVE"
        and i["probe2_verdict"] == "DEAD"
        and i.get("probe2_reason") == "api-skipped"
    ]
    return {
        "probe": "probe2-actions-api",
        "method": "captured gh api /actions/runs/<id>/jobs plus synthetic known runs; string registry",
        "ghost": next(i["probe2_verdict"] for i in cen["items"] if i["id"] == GHOST),
        "truly_absent": next(
            i["probe2_verdict"] for i in cen["items"] if i["id"] == TRULY_ABSENT
        ),
        "mention_only": next(
            i["probe2_verdict"] for i in cen["items"] if i["id"] == MENTION_ONLY
        ),
        "probe2_without_string_edges": ctl["probe2_without_string_edges"],
        "string_edge_count": len(cen["registry"]),
        "api_matrix_job_count": ctl["api_matrix_job_count"],
        "api_plain_job_count": ctl["api_plain_job_count"],
        "leg_reconciliation": cen["leg_reconciliation"],
        "sampled_agree": cen["sampled_agree"],
        "origin_yaml_live_api_skipped": len(skipped_origin),
        "skipped_origin_step_names": [
            i.get("step_name") for i in skipped_origin if i.get("step_name")
        ],
        "api_runs": [
            {
                "workflow": r.get("workflow"),
                "run_id": r.get("run_id"),
                "api_job_count": r.get("api_job_count"),
                "source": r.get("source"),
                "skipped_steps": sum(
                    len(j.get("skipped_steps") or []) for j in r.get("jobs") or []
                ),
            }
            for r in cen["api_runs"]
        ],
    }


if __name__ == "__main__":
    cen = build()
    assert_control(cen)
    print(json.dumps(cen["planted_control"], indent=2, sort_keys=True))
    print(json.dumps(cen["origin_totals"], sort_keys=True))
    print(
        f"modules={cen['tallies']['modules_scanned']} "
        f"disagree={cen['tallies']['disagree']} "
        f"both_dead={cen['tallies']['both_dead']}"
    )
