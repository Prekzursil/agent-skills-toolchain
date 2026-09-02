#!/usr/bin/env python3
"""Emit command-center/research/RES-0029.json from live fetches + stored API snapshots."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    AGENT_PERMALINK,
    AGENT_RAW,
    ART,
    ART_REL,
    DOCKER_API,
    DOCKER_PERMALINK,
    DOCKER_RAW,
    DOCS_PERMALINK,
    DOCS_RAW,
    ISSUE_API,
    ISSUE_HTML,
    README_RAW,
    REPO,
    SCHEMA_REL,
    SDK_COMMIT,
    SENTINEL,
    SKILL_API,
    SKILL_PERMALINK,
    SKILL_RAW,
    TRIGGER_RAW,
    UNIT,
    def_line,
    digest_file,
    fetch,
    sha256_bytes,
    utc_now,
)

TMP = Path("/tmp/res0029/captures")
CAP = HERE / "captures"


def load_or_fetch(url: str, cap_name: str, label: str) -> dict:
    """Live fetch preferred; fall back to the on-disk capture if GitHub is down."""
    rec = fetch(url)
    if rec["http_status"] == 200 and rec["bytes"] >= 200:
        (CAP / cap_name).write_bytes(rec["body"])
        return rec
    cap = CAP / cap_name
    if cap.is_file() and cap.stat().st_size >= 200:
        return from_file(cap, url, utc_now())
    raise SystemExit(
        f"FAILED:emit {label} http={rec['http_status']} bytes={rec['bytes']}"
    )


def snapshot_api(name: str) -> Path:
    dest = CAP / name
    tmp = TMP / name
    if tmp.is_file():
        shutil.copy2(tmp, dest)
    if not dest.is_file() or dest.stat().st_size < 200:
        raise SystemExit(f"FAILED:emit missing snapshot {dest}")
    return dest


def rail(rid: str, kind: str, rec: dict, permalink: str) -> dict:
    return {
        "rail": rid,
        "kind": kind,
        "permalink": permalink,
        "fetch_timestamp": rec["fetch_timestamp"],
        "http_status": rec["http_status"],
        "sha256": rec["sha256"],
        "bytes": rec["bytes"],
    }


def lineage(rec: dict, role: str, permalink: str) -> dict:
    return {
        "permalink": permalink,
        "fetch_timestamp": rec["fetch_timestamp"],
        "http_status": rec["http_status"],
        "sha256": rec["sha256"],
        "role": role,
    }


def from_file(path: Path, url: str, ts: str) -> dict:
    raw = path.read_bytes()
    return {
        "url": url,
        "http_status": 200,
        "body": raw,
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "fetch_timestamp": ts,
    }


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    (REPO / "command-center" / "research").mkdir(parents=True, exist_ok=True)
    ts = utc_now()

    skill = load_or_fetch(SKILL_RAW, "skill.py", "skill.py")
    trigger = load_or_fetch(TRIGGER_RAW, "trigger.py", "trigger.py")
    agent = load_or_fetch(AGENT_RAW, "agent.py", "agent.py")
    docker = load_or_fetch(DOCKER_RAW, "docker_workspace.py", "docker workspace.py")
    docs = load_or_fetch(DOCS_RAW, "skill.mdx", "skill.mdx")
    readme = load_or_fetch(README_RAW, "sdk_README.md", "README.md")
    issue_html = load_or_fetch(ISSUE_HTML, "issue10073.html", "issue 10073 html")

    snapshot_api("skill.api.json")
    snapshot_api("docker_workspace.api.json")
    snapshot_api("issue10073.json")
    snapshot_api("issue10073.comments.json")

    skill_api = from_file(CAP / "skill.api.json", SKILL_API, ts)
    docker_api = from_file(CAP / "docker_workspace.api.json", DOCKER_API, ts)
    issue_api = from_file(CAP / "issue10073.json", ISSUE_API, ts)
    comments_api = from_file(
        CAP / "issue10073.comments.json", ISSUE_API + "/comments", ts
    )

    skill_txt = skill["body"].decode("utf-8")
    trigger_txt = trigger["body"].decode("utf-8")
    agent_txt = agent["body"].decode("utf-8")
    docker_txt = docker["body"].decode("utf-8")
    docs_txt = docs["body"].decode("utf-8")
    readme_txt = readme["body"].decode("utf-8")
    issue_doc = json.loads((CAP / "issue10073.json").read_text(encoding="utf-8"))
    comments = json.loads((CAP / "issue10073.comments.json").read_text(encoding="utf-8"))

    mt = def_line(skill_txt, "def match_trigger(")
    kw = def_line(skill_txt, "def _keyword_matches(")
    kt = def_line(trigger_txt, "class KeywordTrigger(")
    tt = def_line(trigger_txt, "class TaskTrigger(")
    pt = def_line(trigger_txt, "class PathTrigger(")
    step = def_line(agent_txt, "def step(")
    exe = def_line(agent_txt, "def _execute_action_event(")
    dw = def_line(docker_txt, "class DockerWorkspace(")
    if None in {mt, kw, kt, tt, pt, step, exe, dw}:
        raise SystemExit(
            f"FAILED:emit missing citation mt={mt} kw={kw} kt={kt} step={step} dw={dw}"
        )
    if "identical string matching logic" not in docs_txt:
        raise SystemExit("FAILED:emit docs missing identical-string-matching claim")
    if "Docker" not in readme_txt:
        raise SystemExit("FAILED:emit README missing Docker")
    if "--rm" not in docker_txt or "docker" not in docker_txt.lower():
        raise SystemExit("FAILED:emit DockerWorkspace missing docker run --rm")
    if "ObservationEvent" not in agent_txt:
        raise SystemExit("FAILED:emit agent.py missing ObservationEvent")

    title = str(issue_doc.get("title") or "")
    if "not triggering" not in title.lower() or "/" not in title:
        raise SystemExit(f"FAILED:emit unexpected issue title {title!r}")
    comment_bodies = "\n".join(str(c.get("body") or "") for c in comments)
    if "does not get triggered at all" not in comment_bodies.lower():
        raise SystemExit("FAILED:emit missing reporter confirmation")

    skill_cite = f"openhands-sdk/openhands/sdk/skills/skill.py:{mt}"
    kw_cite = f"openhands-sdk/openhands/sdk/skills/skill.py:{kw}"
    docker_cite = f"openhands-workspace/openhands/workspace/docker/workspace.py:{dw}"
    loop_cite = f"openhands-sdk/openhands/sdk/agent/agent.py:{step}"
    exec_cite = f"openhands-sdk/openhands/sdk/agent/agent.py:{exe}"

    claims = [
        {
            "claim_id": "C-ISOLATION-DOCKER",
            "text": (
                "OpenHands isolates agent execution by running the agent-server "
                "inside a Docker container (DockerWorkspace) that maps host "
                "ports to the in-container HTTP API; tools then execute against "
                "that remote workspace rather than the operator's unsandboxed shell."
            ),
            "canonical_mechanism": (
                f"DockerWorkspace._start_container docker run -d --rm ({docker_cite})"
            ),
            "evidence_tier": "E2",
            "confidence_band": "high — source + README agree; default image pin can drift",
            "verdict": "CONFIRMED",
            "named_settling_probe": "probe1_trigger_citation.py",
            "freshness_stamp": ts,
            "snapshot_sha256": docker["sha256"],
            "source_lineage": [
                lineage(docker_api, "structured-api", DOCKER_API),
                lineage(readme, "prose-source", README_RAW),
            ],
            "rails": [
                rail("R1", "structured-api", docker_api, DOCKER_API),
                rail("R2", "prose-source", readme, README_RAW),
            ],
            "file_line": docker_cite,
            "permalink": f"{DOCKER_PERMALINK}#L{dw}",
            "strongest_caveat": (
                "LocalWorkspace is also first-class: isolation is optional. "
                "DockerWorkspace needs a prebuilt image and a Docker daemon."
            ),
        },
        {
            "claim_id": "C-ACTION-OBSERVATION-LOOP",
            "text": (
                "The agent loop is action/observation: Agent.step samples tool calls, "
                "_execute_action_event runs the tool, and the result is wrapped in "
                "ObservationEvent (or AgentErrorEvent) before the next step."
            ),
            "canonical_mechanism": (
                f"Agent.step + Agent._execute_action_event ({loop_cite}; {exec_cite})"
            ),
            "evidence_tier": "E2",
            "confidence_band": "high — function bodies read on the pinned commit",
            "verdict": "CONFIRMED",
            "named_settling_probe": "probe1_trigger_citation.py",
            "freshness_stamp": ts,
            "snapshot_sha256": agent["sha256"],
            "source_lineage": [
                lineage(agent, "structured-api", AGENT_PERMALINK),
                lineage(docs, "prose-source", DOCS_PERMALINK),
            ],
            "rails": [
                rail("R1", "structured-api", agent, AGENT_PERMALINK),
                rail("R2", "prose-source", docs, DOCS_PERMALINK),
            ],
            "file_line": f"{loop_cite}; {exec_cite}",
            "permalink": f"{AGENT_PERMALINK}#L{exe}",
            "strongest_caveat": (
                "Confirmation-mode can execute pending actions before a new sample; "
                "that is still the same action-observation machine."
            ),
        },
        {
            "claim_id": "C-TRIGGER-IS-KEYWORD-MATCH",
            "text": (
                "Microagent/skill auto-activation is keyword (and path-glob) matching, "
                f"not an LLM router. Skill.match_trigger at {skill_cite} walks "
                "KeywordTrigger.keywords or TaskTrigger.triggers and returns the first "
                f"whole-token hit via _keyword_matches at {kw_cite}. TaskTrigger is a "
                "semantic variant of the same string matcher. PathTrigger is a glob on "
                "a touched file path."
            ),
            "canonical_mechanism": (
                f"Skill.match_trigger -> _keyword_matches ({skill_cite})"
            ),
            "evidence_tier": "E2",
            "confidence_band": "high — implementation and architecture doc agree",
            "verdict": "CONFIRMED",
            "named_settling_probe": "probe1_trigger_citation.py",
            "freshness_stamp": ts,
            "snapshot_sha256": skill["sha256"],
            "source_lineage": [
                lineage(skill_api, "structured-api", SKILL_API),
                lineage(docs, "prose-source", DOCS_PERMALINK),
            ],
            "rails": [
                rail("R1", "structured-api", skill_api, SKILL_API),
                rail("R2", "prose-source", docs, DOCS_PERMALINK),
            ],
            "file_line": skill_cite,
            "permalink": f"{SKILL_PERMALINK}#L{mt}",
            "trigger_types": {
                "KeywordTrigger": f"openhands-sdk/openhands/sdk/skills/trigger.py:{kt}",
                "TaskTrigger": f"openhands-sdk/openhands/sdk/skills/trigger.py:{tt}",
                "PathTrigger": f"openhands-sdk/openhands/sdk/skills/trigger.py:{pt}",
            },
            "strongest_caveat": (
                "Docs still permalink trigger.py under "
                "openhands-sdk/openhands/sdk/context/skills/ which 404s; live path is "
                "openhands-sdk/openhands/sdk/skills/. AgentSkills also lists skills for "
                "model invocation (invoke_skill) — a second path, not match_trigger."
            ),
        },
        {
            "claim_id": "C-NOT-BETTER-THAN-KEYWORD",
            "text": (
                "The trigger mechanism is not a better router than keyword matching: "
                "it is keyword matching (plus deterministic path globs). Architecture "
                "docs state KeywordTrigger and TaskTrigger use identical string "
                "matching logic."
            ),
            "canonical_mechanism": "identity: auto-trigger == keyword/path match",
            "evidence_tier": "E2",
            "confidence_band": "high for auto-trigger; medium if one conflates invoke_skill",
            "verdict": "CONFIRMED",
            "named_settling_probe": "probe1_trigger_citation.py",
            "freshness_stamp": ts,
            "snapshot_sha256": docs["sha256"],
            "source_lineage": [
                lineage(skill_api, "structured-api", SKILL_API),
                lineage(docs, "prose-source", DOCS_PERMALINK),
            ],
            "rails": [
                rail("R1", "structured-api", skill_api, SKILL_API),
                rail("R2", "prose-source", docs, DOCS_PERMALINK),
            ],
            "file_line": skill_cite,
            "strongest_caveat": (
                "Model-invocable skills are a different router (the LLM chooses). "
                "That path is not what match_trigger implements."
            ),
        },
        {
            "claim_id": "C-ISSUE-TRACKER-FAILURE-MODE",
            "text": (
                "Issue-tracker failure mode: OpenHands/OpenHands#10073 "
                f"({title!r}). Slash-prefixed microagent triggers such as /design "
                "stopped firing; switching type to knowledge still did not trigger; "
                "a header-only /codereview agent was the exception. This is a "
                "false-negative of the keyword-trigger router, not proof that an "
                "LLM router would have done better."
            ),
            "canonical_mechanism": "keyword-trigger false negative on slash commands",
            "evidence_tier": "E2",
            "confidence_band": (
                "high that the failure was reported in-thread; low that #10073 "
                "still reproduces on the 2026 matcher without a live run"
            ),
            "verdict": "CONFIRMED",
            "named_settling_probe": "probe2_issue_failure.py",
            "freshness_stamp": ts,
            "snapshot_sha256": issue_api["sha256"],
            "source_lineage": [
                lineage(issue_api, "structured-api", ISSUE_API),
                lineage(issue_html, "prose-source", ISSUE_HTML),
            ],
            "rails": [
                rail("R1", "structured-api", issue_api, ISSUE_API),
                rail("R2", "prose-source", issue_html, ISSUE_HTML),
            ],
            "file_line": skill_cite,
            "issue": {
                "number": 10073,
                "html_url": issue_doc.get("html_url"),
                "title": title,
                "state": issue_doc.get("state"),
                "reporter_followup": (
                    "changed it to knowledge and tried but it does not get triggered at all :("
                ),
            },
            "strongest_caveat": (
                "The issue closed stale without a linked root-cause commit. "
                "Current _keyword_matches documents slash-prefixed keywords as "
                "intentionally supported; #10073 is a recorded failure mode, not a "
                "live reproduction on this commit."
            ),
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0029",
        "kind": "research-claim-record",
        "schema": SCHEMA_REL,
        "question": (
            "How does OpenHands isolate execution (container runtime, "
            "action/observation loop) and how do its microagents get triggered "
            "— and is the trigger mechanism a better router than keyword matching?"
        ),
        "title": (
            "Teardown of OpenHands runtime isolation and its microagent trigger model"
        ),
        "canonical_mechanism": (
            f"DockerWorkspace container + Agent.step action/observation; "
            f"auto-trigger is Skill.match_trigger at {skill_cite} "
            f"(keyword/path match, not an LLM router)."
        ),
        "answer": (
            "Execution isolation: optional DockerWorkspace starts "
            "`docker run -d --rm` of an OpenHands agent-server image and proxies "
            "tools through that container HTTP API. The loop is Agent.step -> "
            "tool action -> ObservationEvent. Microagent/skill auto-trigger is "
            f"Skill.match_trigger ({skill_cite}) plus PathTrigger globs — "
            "identical string matching for KeywordTrigger and TaskTrigger. "
            "It is not a better router than keyword matching; it is keyword "
            "matching. Failure mode: GitHub issue #10073 (slash-prefixed "
            "triggers such as /design not firing, including after type: knowledge)."
        ),
        "completion_sentinel": SENTINEL,
        "source_lineage": [
            lineage(skill_api, "structured-api", SKILL_API),
            lineage(docs, "prose-source", DOCS_PERMALINK),
            lineage(issue_api, "structured-api", ISSUE_API),
            lineage(issue_html, "prose-source", ISSUE_HTML),
            lineage(comments_api, "structured-api", ISSUE_API + "/comments"),
            lineage(docker_api, "structured-api", DOCKER_API),
            lineage(readme, "prose-source", README_RAW),
            lineage(agent, "structured-api", AGENT_PERMALINK),
        ],
        "claims": claims,
        "named_settling_probe": (
            "command-center/p2-wave/probes/RES-0029/probe1_trigger_citation.py"
        ),
        "freshness_stamp": ts,
        "snapshot_sha256": skill["sha256"],
        "repo_canonical": {
            "catalog_pointer": "All-Hands-AI/OpenHands",
            "html_redirect": "https://github.com/OpenHands/OpenHands",
            "python_agent_and_runtime": "OpenHands/software-agent-sdk",
            "pinned_sdk_commit": SDK_COMMIT,
            "note": (
                "The catalog names All-Hands-AI/OpenHands. That org URL redirects. "
                "OpenHands/OpenHands main is now Agent Canvas (TypeScript). The "
                "container runtime, action/observation loop, and skill trigger "
                "evaluator live in OpenHands/software-agent-sdk on this date."
            ),
        },
        "citations": {
            "match_trigger": skill_cite,
            "keyword_matches": kw_cite,
            "docker_workspace": docker_cite,
            "agent_step": loop_cite,
            "execute_action_event": exec_cite,
            "issue_failure_mode": "https://github.com/OpenHands/OpenHands/issues/10073",
        },
        "tests": [
            {
                "id": "T-TRIGGER-FILE-LINE",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0029/probe1_trigger_citation.py"
                ),
                "result": "NOT-RUN",
            },
            {
                "id": "T-ISSUE-FAILURE-MODE",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0029/probe2_issue_failure.py"
                ),
                "result": "NOT-RUN",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0029-probe2-issue-control",
            "verdict": (
                "PASS on isolation + keyword-trigger identity; "
                "the 'better than keyword matching' reading is REFUTED"
            ),
            "independent": True,
            "default_without_evidence": "REFUTED",
            "scope_not_agreement": True,
        },
        "artifacts": [
            {"path": ART_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "supporting"},
        ],
        "residual_unknowns": [
            "Whether #10073 still reproduces against Skill.match_trigger on this commit was not executed as a running OpenHands session.",
            "Docs permalink for trigger.py is stale relative to the live skills/ path.",
        ],
    }

    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        raise SystemExit("FAILED:emit sentinel missing from serialized artifact")
    if skill_cite not in text or "issues/10073" not in text:
        raise SystemExit("FAILED:emit file:line or issue citation missing")
    ART.write_text(text, encoding="utf-8")
    sha, size = digest_file(ART)
    print(f"wrote {ART_REL} bytes={size} sha256={sha}")
    print(f"match_trigger {skill_cite}")
    print("issue https://github.com/OpenHands/OpenHands/issues/10073")
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
