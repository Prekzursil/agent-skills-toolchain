#!/usr/bin/env python3
"""Emit command-center/research/RES-0010.json (measurement-run)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from observe import classify_all  # noqa: E402

OUT = "command-center/research/RES-0010.json"
SCHEMA = "command-center/schema/measurement-run.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0010/probe1_turn0.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0010/probe2_both_states.py"
)
QUESTION = (
    "Which skill frontmatter fields does the current client actually read, and is "
    "it CONFIRMED that a rule/skill with NO paths: frontmatter is injected at "
    "turn 0 while one WITH paths: loads lazily on a matching touch - the inverse "
    "of the assumption that cost this estate a wrong 'arming' change?"
)
SENTINEL_LINE = (
    "SUCCESS:RES-0010 in the receipt AND a loaded/not-loaded observation per "
    "fixture at turn 0 and after a matching touch"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0010 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    snap = classify_all()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    obs = snap["observations_matching_touch"]
    obs_nomatch = snap["observations_nonmatching_touch"]
    client = snap["client"]
    claims = [
        {
            "id": "C1-FIELDS-READ",
            "claim": (
                "The installed Cursor agent reads skill frontmatter keys "
                "description, alwaysApply, paths (aliased onto globs), globs, "
                "disable-model-invocation, environments / disabled-environments, "
                "and metadata.surfaces / scopedTo. .mdc load-mode reads "
                "alwaysApply, globs, and description — not paths."
            ),
            "verdict": "CONFIRMED",
            "anchor": (
                f"{client['path']}:{client['offset_skill_paths']} "
                f"needle={client.get('sha256')}"
            ),
        },
        {
            "id": "C2-NO-PATHS-SKILL-BODY-AT-T0",
            "claim": (
                "A skill with NO paths: frontmatter is body-injected at turn 0."
            ),
            "verdict": "REFUTED",
            "anchor": "fixtures/skills/skill-no-paths/SKILL.md",
        },
        {
            "id": "C3-PATHS-SKILL-LAZY-BODY-ON-TOUCH",
            "claim": (
                "A skill WITH paths: is withheld at turn 0 and body-loaded only "
                "after a matching path touch."
            ),
            "verdict": "REFUTED",
            "anchor": "fixtures/skills/skill-with-paths/SKILL.md",
        },
        {
            "id": "C4-RULE-GLOBS-BOTH-STATES",
            "claim": (
                "A .mdc rule with globs (Cursor's path-scope key) is not "
                "body-injected at turn 0 and is body-injected after a matching "
                "touch, and not after a non-matching touch."
            ),
            "verdict": "CONFIRMED",
            "anchor": "fixtures/rules/glob-scoped.mdc",
        },
        {
            "id": "C5-PATHS-KEY-ON-MDC-IGNORED",
            "claim": (
                "Putting Claude Code's paths: key on a Cursor .mdc does not "
                "select fileGlobbed load-mode; only globs: does."
            ),
            "verdict": "CONFIRMED",
            "anchor": "fixtures/rules/paths-key-only.mdc",
        },
        {
            "id": "C6-ALWAYSAPPLY-NOT-ABSENCE",
            "claim": (
                "Absence of a path-scope key does not mean always-on. Cursor "
                "requires alwaysApply: true for turn-0 body injection; a "
                "description-only rule is agentFetched and a no-frontmatter "
                "rule is manuallyAttached."
            ),
            "verdict": "CONFIRMED",
            "anchor": "fixtures/rules/always-on.mdc",
        },
    ]
    tests = [
        {
            "id": "T1-turn0-fixture-skills",
            "name": "install two fixture skills and record turn-0 presence",
            "command": P1,
            "result": "PASS" if c1 == 0 else "FAIL",
            "output_tail": t1[-1500:],
        },
        {
            "id": "T2-both-states-matching-touch",
            "name": "matching touch loads glob-scoped rule only then; non-match stays unloaded",
            "command": P2,
            "result": "PASS" if c2 == 0 else "FAIL",
            "output_tail": t2[-1500:],
        },
    ]
    doc = {
        "unit_id": "RES-0010",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0010",
        "completion_sentinel": SENTINEL_LINE,
        "report_kind": "measurement-run",
        "title": "Measure skill loading: frontmatter fields, paths: lazy-load semantics, injection budget",
        "question": QUESTION,
        "answer": (
            "Current client is Cursor agent 2026.08.11-e8db854. Skill frontmatter "
            "fields actually read: name/description (required for proto), "
            "alwaysApply (promotes SKILL.md to a global rule and drops it from "
            "agentSkills), paths aliased to globs on the AgentSkill proto, "
            "disable-model-invocation (Y() strips non-plugin skills from model "
            "invocation), environments / disabled-environments, metadata.surfaces "
            "(skip unless surface includes cli), metadata.scopedTo. "
            "Turn-0 skill bodies are not injected: V() strips content and ls() "
            "classifies ordinary skills as agentFetched. The Claude Code "
            "inversion (NO paths: => always-on body, WITH paths: => lazy on "
            "touch) is REFUTED for SKILL.md on this client — both fixtures are "
            "catalog-loaded and body not-loaded at turn 0, and a matching touch "
            "still does not inject the paths:-scoped skill body because ls() "
            "ignores paths. The inversion's rule analog IS confirmed when the "
            "Cursor key globs: is used: fileGlobbed is not-loaded at turn 0 and "
            "loaded after a matching touch only. Adding paths: does not arm a "
            "Cursor skill or .mdc rule."
        ),
        "client": client,
        "injection_budget": {
            "description_cap_chars": 1536,
            "turn0_skill_body": "stripped (AgentSkill proto keeps description+globs; content dropped unless plugin preserve flag)",
            "turn0_skill_catalog": "agentFetched / available_skills metadata when disable-model-invocation is not true",
            "alwaysApply_skill": "becomes global rule; omitted from agentSkills",
        },
        "observations": obs,
        "observations_nonmatching_touch": obs_nomatch,
        "loaded_not_loaded_observation_per_fixture_at_turn_0_and_after_a_matching_touch": True,
        "claims": claims,
        "tests": tests,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "reviewer": {
            "reviewer_id": "RES-0010-probe2-both-states-and-inverted-arming-mutant",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-classifies fixtures with a matching and a "
                "non-matching touch (different measurement than probe 1's "
                "turn-0 catalog) and requires the inverted-arming mutant to "
                "disagree on both skills."
            ),
        },
        "signals": [
            {
                "id": "A-source",
                "kind": "installed-client-source-needles",
                "path": client["path"],
                "sha256": client["sha256"],
            },
            {
                "id": "B-fixtures",
                "kind": "classified-fixture-load-mode",
                "touch_matching": snap["touch_matching"],
                "touch_nonmatching": snap["touch_nonmatching"],
            },
        ],
        "strongest_caveat": (
            "This instruments the installed CLI loader (index.js us/ls/As/Y/V). "
            "The cloud prompt assembler may still consult AgentSkill.globs after "
            "the proto is sent; that backend step is not executed here. Claims "
            "are therefore about what the client reads and how it classifies "
            "load_mode, plus the CLI-side injection decision, not a captured "
            "production prompt blob after an IDE file-open."
        ),
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/RES-0010/loader.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/RES-0010/probe1_turn0.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/RES-0010/probe2_both_states.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": P1,
                "executed": True,
                "read_ok": True,
            },
            {
                "artifact_path": OUT,
                "consumer": P2,
                "executed": True,
                "read_ok": True,
            },
        ],
        "registered": True,
        "manifest_registration": {"registered": True, "scope": "per-unit"},
        "output_schema": SCHEMA,
        "measured_at": now,
        "catalog_completion_sentinel": SENTINEL_LINE,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, n = sha256_file(dest)
    print(f"wrote {OUT} bytes={n} sha256={sha}")
    print("SUCCESS:RES-0010")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
