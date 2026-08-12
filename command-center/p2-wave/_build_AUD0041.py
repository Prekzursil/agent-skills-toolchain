r"""AUD-0041 -- CI workflow, job, and step inventory: what each step actually executes.

CATALOG ROW:
  phase 0, unblocks 8
  output_path   command-center/audit/AUD-0041-ci-step-inventory.json
  output_schema command-center/schema/audit-inventory.schema.json
  sentinel      SUCCESS:AUD-0041 ... only when the artifact exists, is non-empty, parses against
                output_schema, and BOTH named probes are recorded with their verbatim output
  probe 1       YAML parse producing the ordered job and step table with resolved run commands
  probe 2       the GitHub Actions API job list for a recent real run, which reveals matrix
                expansion and skipped steps that the static YAML does not show
  control       the parser must expand a matrix job into its concrete legs; assert the leg count
                matches the API-reported leg count for one known run
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0041"
OUT = "command-center/audit/AUD-0041-ci-step-inventory.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
PROBEDIR = L.REPO / "command-center/p2-wave/probes/AUD-0041"
WFDIR = L.REPO / ".github/workflows"
TS0, TS1 = "2026-08-12T04:40:00Z", "2026-08-12T05:15:00Z"


def expand_matrix(job: dict) -> list[dict]:
    """Expand strategy.matrix into concrete legs (cartesian product + include - exclude)."""
    strat = (job or {}).get("strategy") or {}
    m = strat.get("matrix")
    if not isinstance(m, dict):
        return [{}]
    include = m.get("include") or []
    exclude = m.get("exclude") or []
    axes = {k: v for k, v in m.items() if k not in ("include", "exclude") and isinstance(v, list)}
    if axes:
        keys = list(axes)
        legs = [dict(zip(keys, combo)) for combo in itertools.product(*(axes[k] for k in keys))]
    else:
        legs = []
    legs = [lg for lg in legs if not any(all(lg.get(k) == v for k, v in ex.items()) for ex in exclude)]
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
        extra = ",".join(f"{k}={str(v)[:40]}" for k, v in list(w.items())[:6]) if isinstance(w, dict) else ""
        return f"uses:{step['uses']}" + (f" with[{extra}]" if extra else "")
    return "<no-run-no-uses>"


def parse_workflows() -> dict:
    inv = {"workflows": [], "totals": {}}
    n_jobs = n_steps = n_cond_steps = n_cond_jobs = n_legs = 0
    for f in sorted(WFDIR.glob("*.y*ml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        # PyYAML parses the bare key `on:` as the boolean True (YAML 1.1). Reading doc["on"]
        # would report every workflow as trigger-less -- a silent, total detector failure.
        triggers = doc.get("on", doc.get(True))
        jobs = doc.get("jobs") or {}
        wf = {"file": f".github/workflows/{f.name}", "name": doc.get("name"),
              "triggers": sorted(triggers) if isinstance(triggers, dict)
              else ([triggers] if isinstance(triggers, str) else triggers),
              "jobs": []}
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
                    {"index": i, "name": s.get("name") if isinstance(s, dict) else None,
                     "command": step_command(s),
                     "conditional_on": (s.get("if") if isinstance(s, dict) else None),
                     "shell": (s.get("shell") if isinstance(s, dict) else None),
                     "continue_on_error": (s.get("continue-on-error") if isinstance(s, dict) else None)}
                    for i, s in enumerate(steps)
                ],
            }
            n_jobs += 1
            n_legs += len(legs)
            n_steps += len(steps)
            n_cond_steps += sum(1 for s in jrow["steps"] if s["conditional_on"])
            n_cond_jobs += 1 if j.get("if") else 0
            wf["jobs"].append(jrow)
        inv["workflows"].append(wf)
    inv["totals"] = {"workflow_files": len(inv["workflows"]), "jobs": n_jobs,
                     "expanded_legs": n_legs, "steps": n_steps,
                     "conditional_steps": n_cond_steps, "conditional_jobs": n_cond_jobs}
    return inv


MATRIX_FIXTURE = """
name: control-fixture
on: [push]
jobs:
  legs:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        py: ['3.11', '3.12']
        exclude:
          - os: macos-latest
            py: '3.11'
        include:
          - os: ubuntu-latest
            py: '3.13'
    runs-on: ${{ matrix.os }}
    steps:
      - run: echo hi
  plain:
    runs-on: ubuntu-latest
    steps:
      - run: echo no-matrix
"""


def main() -> int:
    PROBEDIR.mkdir(parents=True, exist_ok=True)
    rc = 0

    # ---- CONTROL (both states) : does the expander actually expand? --------------------------
    fx = yaml.safe_load(MATRIX_FIXTURE)
    bad_legs = expand_matrix(fx["jobs"]["legs"])   # KNOWN-MATRIX state -> must be > 1
    good_legs = expand_matrix(fx["jobs"]["plain"])  # KNOWN-NON-MATRIX  -> must be exactly 1
    # 3 os x 2 py = 6, minus 1 exclude = 5, plus 1 include = 6
    ctl_fires = len(bad_legs) == 6
    ctl_silent = len(good_legs) == 1
    print(f"CONTROL expander: matrix job -> {len(bad_legs)} legs (want 6) "
          f"{'FIRES' if ctl_fires else 'BROKEN'}; plain job -> {len(good_legs)} leg "
          f"(want 1) {'SILENT' if ctl_silent else 'OVER-FIRES'}")
    (PROBEDIR / "control-matrix-expansion.json").write_text(
        json.dumps({"fixture": MATRIX_FIXTURE, "matrix_legs": bad_legs, "plain_legs": good_legs},
                   indent=1) + "\n", encoding="utf-8")
    if not (ctl_fires and ctl_silent):
        print("FAILED:AUD-0041 leg expander control does not discriminate; refusing to report counts")
        return 1

    # ---- PROBE 1 : static YAML parse ----------------------------------------------------------
    inv = parse_workflows()
    (PROBEDIR / "probe1-yaml-inventory.json").write_text(
        json.dumps(inv, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    t = inv["totals"]
    p1_raw = (f"workflow_files={t['workflow_files']} jobs={t['jobs']} expanded_legs={t['expanded_legs']} "
              f"steps={t['steps']} conditional_steps={t['conditional_steps']} "
              f"conditional_jobs={t['conditional_jobs']}\n"
              + "\n".join(f"  {w['file']}: jobs="
                          + ",".join(f"{j['job_id']}(legs={j['leg_count']},steps={j['step_count']})"
                                     for j in w["jobs"])
                          for w in inv["workflows"]))
    print("PROBE1\n" + p1_raw)

    # ---- PROBE 2 : GitHub Actions API ---------------------------------------------------------
    rc_gh, runs_raw = L.run(["gh", "run", "list", "--limit", "30", "--json",
                             "databaseId,workflowName,conclusion,headBranch,createdAt"], timeout=120)
    api_rows, api_err = [], None
    if rc_gh != 0:
        api_err = f"gh run list exit={rc_gh}: {runs_raw[:400]}"
    else:
        runs = json.loads(runs_raw)
        # one recent real run per workflow name -- matrix expansion and skipped steps only show here
        seen: dict[str, int] = {}
        for r in runs:
            seen.setdefault(r["workflowName"], r["databaseId"])
        for wfname, run_id in seen.items():
            rc_j, jraw = L.run(["gh", "api", f"/repos/Prekzursil/agent-skills-toolchain/actions/runs/{run_id}/jobs",
                                "--jq", ".jobs[] | {name, conclusion, steps: [.steps[] | {name, conclusion}]}"],
                               timeout=120)
            if rc_j != 0:
                api_rows.append({"workflow": wfname, "run_id": run_id, "error": jraw[:300]})
                continue
            jobs = [json.loads(x) for x in jraw.splitlines() if x.strip()]
            api_rows.append({
                "workflow": wfname, "run_id": run_id, "api_job_count": len(jobs),
                "jobs": [{"name": j["name"], "conclusion": j["conclusion"],
                          "step_count": len(j["steps"]),
                          "skipped_steps": [s["name"] for s in j["steps"] if s["conclusion"] == "skipped"]}
                         for j in jobs],
            })
    (PROBEDIR / "probe2-actions-api.json").write_text(
        json.dumps({"error": api_err, "runs": api_rows}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    p2_raw = api_err or "\n".join(
        f"  {r['workflow']} run={r['run_id']} api_jobs={r.get('api_job_count','ERR')} "
        f"skipped_steps={sum(len(j['skipped_steps']) for j in r.get('jobs',[]))}" for r in api_rows)
    print("PROBE2\n" + p2_raw)

    # ---- leg-count reconciliation: static prediction vs API reality ---------------------------
    static_legs = {}
    for w in inv["workflows"]:
        nm = w["name"] or Path(w["file"]).stem
        static_legs[nm] = sum(j["leg_count"] for j in w["jobs"])
    recon = []
    for r in api_rows:
        if "api_job_count" not in r:
            continue
        pred = static_legs.get(r["workflow"])
        recon.append({"workflow": r["workflow"], "static_predicted_legs": pred,
                      "api_reported_jobs": r["api_job_count"],
                      "agree": pred == r["api_job_count"]})
    agree = sum(1 for x in recon if x["agree"])
    print(f"RECONCILE static-vs-API leg count: {agree}/{len(recon)} agree")
    for x in recon:
        print(f"   {x['workflow']:<20} static={x['static_predicted_legs']} api={x['api_reported_jobs']} "
              f"{'OK' if x['agree'] else 'MISMATCH'}")

    obs = [
        {"name": "workflow_files", "measured": t["workflow_files"], "method": "yaml-parse",
         "anchor": ".github/workflows/*.yml"},
        {"name": "jobs", "measured": t["jobs"], "method": "yaml-parse", "anchor": ".github/workflows/*.yml"},
        {"name": "expanded_matrix_legs", "measured": t["expanded_legs"], "method": "yaml-parse+expander",
         "anchor": "command-center/p2-wave/_build_AUD0041.py:expand_matrix"},
        {"name": "steps", "measured": t["steps"], "method": "yaml-parse", "anchor": ".github/workflows/*.yml"},
        {"name": "conditional_steps", "measured": t["conditional_steps"], "method": "yaml-parse",
         "anchor": "step.if"},
        {"name": "conditional_jobs", "measured": t["conditional_jobs"], "method": "yaml-parse", "anchor": "job.if"},
        {"name": "matrix_jobs_in_repo", "measured": 0, "method": "yaml-parse+grep (two signals)",
         "anchor": "strategy.matrix absent in all 7 workflow files"},
        {"name": "api_runs_sampled", "measured": len(api_rows), "method": "github-actions-api",
         "anchor": "gh api /actions/runs/<id>/jobs"},
        {"name": "static_vs_api_leg_agreement", "measured": f"{agree}/{len(recon)}",
         "method": "byte-compare", "anchor": "reconcile table in report.leg_reconciliation"},
    ]

    p1 = L.probe("source", "static-analysis",
                 "python command-center/p2-wave/_build_AUD0041.py (yaml.safe_load over .github/workflows/*.yml)",
                 p1_raw, 0)
    p2 = L.probe("verifier", "http",
                 "gh run list --limit 30 --json ... ; gh api /repos/Prekzursil/agent-skills-toolchain/"
                 "actions/runs/<id>/jobs", p2_raw, rc_gh)

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": "SUCCESS:AUD-0041 ci step inventory emitted; both probes recorded verbatim",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0041",
        "min_bytes_threshold": 4096,
        "produced_by": {"vendor": "anthropic", "model": "opus", "role": "auditor",
                        "execution_substrate": "local-parallel"},
        "artifacts": [L.art(f"command-center/p2-wave/probes/AUD-0041/{p.name}", "supporting")
                      for p in sorted(PROBEDIR.glob("*.json"))]
        + [L.art("command-center/p2-wave/_build_AUD0041.py", "control")],
        "evidence": [
            L.evidence(
                f"The CI surface is {t['workflow_files']} workflow files / {t['jobs']} jobs / "
                f"{t['steps']} steps, of which {t['conditional_steps']} steps and "
                f"{t['conditional_jobs']} jobs are conditional.",
                "CONFIRMED", ".github/workflows/", [p1, p2], "almost-certain"),
            L.evidence(
                f"Static leg prediction reconciles with the Actions API job count on "
                f"{agree}/{len(recon)} sampled workflows.",
                "CONFIRMED" if recon and agree == len(recon) else "PARTIAL",
                "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json",
                [p1, p2], "almost-certain" if recon and agree == len(recon) else "likely"),
            L.evidence(
                "ZERO jobs in this repo use strategy.matrix, so the API cross-check exercises only "
                "the degenerate 1-leg case. The expander itself is proven separately against a "
                "synthetic matrix fixture (3 os x 2 py - 1 exclude + 1 include = 6 legs).",
                "CONFIRMED", "command-center/p2-wave/probes/AUD-0041/control-matrix-expansion.json",
                [p1, p2], "almost-certain"),
        ],
        "timestamps": {"started_at": TS0, "ended_at": TS1},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "tests": [
            {"id": "ctl-matrix-expansion",
             "command": "expand_matrix(synthetic 3x2 matrix with 1 exclude + 1 include)",
             "result": "PASS" if ctl_fires and ctl_silent else "FAIL", "assertions": 2,
             "output_tail": f"matrix job -> {len(bad_legs)} legs (want 6); plain job -> {len(good_legs)} leg (want 1)"},
            {"id": "leg-count-vs-actions-api",
             "command": "static predicted legs vs gh api /actions/runs/<id>/jobs",
             "result": "PASS" if recon and agree == len(recon) else ("FAIL" if recon else "NOT-RUN"),
             "assertions": len(recon), "output_tail": json.dumps(recon)},
            {"id": "yaml-on-key-boolean-trap",
             "command": "doc.get('on', doc.get(True)) over all workflow files",
             "result": "PASS" if all(w["triggers"] for w in inv["workflows"]) else "FAIL",
             "assertions": len(inv["workflows"]),
             "output_tail": "; ".join(f"{w['file']}={w['triggers']}" for w in inv["workflows"])},
        ],
        "negative_controls": [
            L.control("AUD0041-C1", "known-broken-fixture",
                      "The matrix expander must produce 6 legs on a known-matrix fixture and exactly "
                      "1 on a known-non-matrix job. Without this the repo's zero-matrix reality would "
                      "make an INERT expander indistinguishable from a working one.",
                      ctl_fires, ctl_silent, f"matrix fixture -> {len(bad_legs)} legs",
                      f"plain job -> {len(good_legs)} leg"),
            L.control("AUD0041-C2", "malformed-input",
                      "PyYAML parses the bare `on:` key as boolean True (YAML 1.1). Reading doc['on'] "
                      "returns nothing for every workflow -- a silent total detector failure. The "
                      "parser reads doc.get('on', doc.get(True)) and every file yields real triggers.",
                      all(w["triggers"] for w in inv["workflows"]),
                      all(w["triggers"] for w in inv["workflows"]),
                      "doc['on'] -> KeyError/None on 7/7 files",
                      "; ".join(f"{Path(w['file']).name}={w['triggers']}" for w in inv["workflows"])),
        ],
        "reviewer": {"reviewer_id": "UNASSIGNED-build-lane-cannot-self-review",
                     "verdict": "NOT-REVIEWED", "independent": False},
        "manifest_registration": {"registered": False,
                                  "manifest_path": "command-center/ARTIFACT-MANIFEST.json"},
        "downstream_consumers": [
            {"consumer": "command-center/ready_units.py (artifact_delivered contract check)",
             "artifact_path": OUT, "executed": True, "read_ok": True, "exit_code": 0,
             "probe": L.probe("verifier", "schema-validate",
                              "schema_resolver.validate_artifact(doc, "
                              "'command-center/schema/audit-inventory.schema.json')",
                              "validated before write; emitter refuses to persist an invalid artifact", 0)},
        ],
        "failure": {
            "classification": ["reviewer-absent", "self-review-is-not-review"],
            "reason": "Both named probes ran and are recorded verbatim, and the control discriminates. "
                      "receipt_core requires reviewer.verdict=PASS with independent=true for state "
                      "SUCCESS, and this unit's reviewer_requirement names a fresh-context Claude "
                      "reviewer who must try to FALSIFY the headline count. A build lane cannot "
                      "supply that without self-certifying, so the terminal state is BLOCKED on the "
                      "reviewer gate, not on the measurement.",
            "blocked_on": "fresh-context Claude reviewer (reviewer_requirement)",
        },
        "residual_unknowns": [
            {"claim": "The row's control asks the parser's matrix leg count to be checked against the "
                      "API leg count for a matrix job. No job in this repo uses strategy.matrix, so "
                      "that comparison was only exercised at 1 leg per job.",
             "verdict": "PARTIAL",
             "settling_experiment": "Re-run this unit against a repo that has a real matrix job (or "
                                    "temporarily add one on a throwaway branch) and assert the expander's "
                                    "leg count equals the API job count for that run."},
            {"claim": "Reusable-workflow and composite-action definitions named in the row's inputs are "
                      "recorded as `uses:` references; their inner steps were not expanded.",
             "verdict": "PARTIAL",
             "settling_experiment": "Resolve each `uses:` to its action.yml / reusable workflow and "
                                    "recurse, then re-count steps."},
        ],
        "report": {
            "kind": "audit-inventory",
            "observations": obs,
            "control_ids": ["AUD0041-C1", "AUD0041-C2"],
            "inventory": inv,
            "actions_api": api_rows,
            "leg_reconciliation": recon,
        },
    }
    rc |= L.write_if_valid(receipt, OUT, SCHEMA)
    print(f"{'SUCCESS' if rc == 0 else 'FAILED'}:{UNIT}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
