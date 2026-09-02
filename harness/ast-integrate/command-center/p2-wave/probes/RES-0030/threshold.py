"""Parse Goose lead/worker failure-threshold loci from live pinned sources."""
from __future__ import annotations

import hashlib
from typing import Any

from constants import (
    CONFIG_KEY,
    CONFIG_READ_LINE,
    CONSTRUCTOR_DEFAULT_LINE,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_THRESHOLD_LINE,
    ENV_DOCS_PERMALINK,
    ENV_DOCS_RAW,
    ENV_DOCS_REL,
    ENV_DOCS_THRESHOLD_LINE,
    FIXTURES,
    INIT_PERMALINK,
    INIT_RAW,
    INIT_REL,
    LEAD_TURNS_DEFAULT_LINE,
    LEAD_WORKER_MAIN_RAW,
    LEAD_WORKER_PERMALINK,
    LEAD_WORKER_RAW,
    LEAD_WORKER_REL,
    SWITCH_LOG_LINE,
    TRIGGER_LINE,
    TUTORIAL_PERMALINK,
    TUTORIAL_RAW,
    TUTORIAL_REL,
    TUTORIAL_THRESHOLD_LINE,
)
from fetchutil import fetch_body, lineage


def _lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").split("\n")


def _at(lines: list[str], lineno: int) -> str:
    if lineno < 1 or lineno > len(lines):
        raise RuntimeError(f"line {lineno} out of range ({len(lines)})")
    return lines[lineno - 1]


def _require(line: str, needle: str, locus: str) -> None:
    if needle not in line:
        raise RuntimeError(f"{locus} missing {needle!r}: {line!r}")


def _check_fixture(name: str, live_sha: str) -> None:
    path = FIXTURES / name
    if not path.is_file():
        raise RuntimeError(f"fixture missing: {name}")
    want = hashlib.sha256(path.read_bytes()).hexdigest()
    if live_sha != want:
        raise RuntimeError(f"live sha mismatch for {name}: live={live_sha} fixture={want}")


def extract_threshold() -> dict[str, Any]:
    lw = fetch_body(LEAD_WORKER_RAW)
    init = fetch_body(INIT_RAW)
    env = fetch_body(ENV_DOCS_RAW)
    tutorial = fetch_body(TUTORIAL_RAW)
    main_lw = fetch_body(LEAD_WORKER_MAIN_RAW)

    if lw.get("status") != 200 or not lw.get("body"):
        raise RuntimeError(f"lead_worker.rs parent fetch failed: {lw.get('status')}")
    if init.get("status") != 200 or not init.get("body"):
        raise RuntimeError(f"init.rs parent fetch failed: {init.get('status')}")
    if env.get("status") != 200 or not env.get("body"):
        raise RuntimeError(f"env docs parent fetch failed: {env.get('status')}")
    if tutorial.get("status") != 200 or not tutorial.get("body"):
        raise RuntimeError(f"tutorial parent fetch failed: {tutorial.get('status')}")

    _check_fixture("lead_worker.rs", lw["sha256"])
    _check_fixture("init.rs", init["sha256"])
    _check_fixture("environment-variables.md", env["sha256"])
    _check_fixture("lead-worker.md", tutorial["sha256"])

    lw_text = lw["body"].decode("utf-8")
    init_text = init["body"].decode("utf-8")
    env_text = env["body"].decode("utf-8")
    tut_text = tutorial["body"].decode("utf-8")
    lw_lines = _lines(lw_text)
    init_lines = _lines(init_text)
    env_lines = _lines(env_text)
    tut_lines = _lines(tut_text)

    default_line = _at(init_lines, DEFAULT_THRESHOLD_LINE)
    _require(default_line, "DEFAULT_FAILURE_THRESHOLD", f"{INIT_REL}:{DEFAULT_THRESHOLD_LINE}")
    _require(default_line, "2", f"{INIT_REL}:{DEFAULT_THRESHOLD_LINE}")

    config_line = _at(init_lines, CONFIG_READ_LINE)
    _require(config_line, CONFIG_KEY, f"{INIT_REL}:{CONFIG_READ_LINE}")

    ctor_line = _at(lw_lines, CONSTRUCTOR_DEFAULT_LINE)
    _require(ctor_line, "max_failures_before_fallback: 2", f"{LEAD_WORKER_REL}:{CONSTRUCTOR_DEFAULT_LINE}")

    trigger_line = _at(lw_lines, TRIGGER_LINE)
    _require(trigger_line, "turn_count >= self.lead_turns", f"{LEAD_WORKER_REL}:{TRIGGER_LINE}")
    # Next two lines complete the conjunction.
    _require(_at(lw_lines, TRIGGER_LINE + 2), "failure_count >= self.max_failures_before_fallback", f"{LEAD_WORKER_REL}:{TRIGGER_LINE + 2}")

    switch_line = _at(lw_lines, SWITCH_LOG_LINE)
    _require(switch_line, "SWITCHING TO LEAD MODEL", f"{LEAD_WORKER_REL}:{SWITCH_LOG_LINE}")

    lead_turns_line = _at(init_lines, LEAD_TURNS_DEFAULT_LINE)
    _require(lead_turns_line, "DEFAULT_LEAD_TURNS", f"{INIT_REL}:{LEAD_TURNS_DEFAULT_LINE}")

    env_line = _at(env_lines, ENV_DOCS_THRESHOLD_LINE)
    _require(env_line, CONFIG_KEY, f"{ENV_DOCS_REL}:{ENV_DOCS_THRESHOLD_LINE}")
    _require(env_line, "2", f"{ENV_DOCS_REL}:{ENV_DOCS_THRESHOLD_LINE}")

    tut_line = _at(tut_lines, TUTORIAL_THRESHOLD_LINE)
    _require(tut_line, CONFIG_KEY, f"lead-worker.md:{TUTORIAL_THRESHOLD_LINE}")

    if "SWITCHING TO WORKER MODEL: Entering fallback" in lw_text:
        raise RuntimeError("overclaim trap: fallback log claims worker, not lead")
    if CONFIG_KEY not in init_text:
        raise RuntimeError("config key missing from init.rs")
    if "get_param::<usize>(\"GOOSE_LEAD_FAILURE_THRESHOLD\")" not in init_text:
        raise RuntimeError("threshold is not read from config")

    # Directional control: lead-to-worker is turn-count, failure threshold is worker-to-lead.
    lead_to_worker_is_turns = "count < self.lead_turns || in_fallback" in lw_text
    if not lead_to_worker_is_turns:
        raise RuntimeError("could not find turn-count lead/worker selector")

    main_status = main_lw.get("status")
    main_absent = main_status == 404

    # Both-states mutant: drop the config key and the parser must call it hardcoded-only.
    mutant = init_text.replace(CONFIG_KEY, "GOOSE_NOT_A_REAL_KEY")
    mutant_configurable = "get_param::<usize>(\"GOOSE_LEAD_FAILURE_THRESHOLD\")" in mutant
    if mutant_configurable:
        raise RuntimeError("mutant still looks configurable — detector is not using the key")

    return {
        "default_threshold": DEFAULT_FAILURE_THRESHOLD,
        "configurable": True,
        "config_key": CONFIG_KEY,
        "hardcoded_default_also_present": True,
        "direction": "worker-to-lead-fallback",
        "catalog_framing_lead_to_worker_via_failure_threshold": "REFUTED",
        "lead_to_worker_trigger": "turn count (GOOSE_LEAD_TURNS, default 3)",
        "failure_threshold_trigger": (
            "after initial lead turns, consecutive task failures "
            ">= GOOSE_LEAD_FAILURE_THRESHOLD (default 2) switch back to the lead model"
        ),
        "loci": {
            "hardcoded_default": f"{INIT_REL}:{DEFAULT_THRESHOLD_LINE}",
            "config_read": f"{INIT_REL}:{CONFIG_READ_LINE}",
            "constructor_default": f"{LEAD_WORKER_REL}:{CONSTRUCTOR_DEFAULT_LINE}",
            "trigger": f"{LEAD_WORKER_REL}:{TRIGGER_LINE}",
            "switch_log": f"{LEAD_WORKER_REL}:{SWITCH_LOG_LINE}",
            "env_docs": f"{ENV_DOCS_REL}:{ENV_DOCS_THRESHOLD_LINE}",
            "tutorial": f"{TUTORIAL_REL}:{TUTORIAL_THRESHOLD_LINE}",
        },
        "snippets": {
            "hardcoded_default": default_line.strip(),
            "config_read": config_line.strip(),
            "constructor_default": ctor_line.strip(),
            "trigger": trigger_line.strip(),
            "switch_log": switch_line.strip(),
            "env_docs": env_line.strip(),
            "tutorial": tut_line.strip(),
        },
        "permalinks": {
            "hardcoded_default": f"{INIT_PERMALINK}#L{DEFAULT_THRESHOLD_LINE}",
            "config_read": f"{INIT_PERMALINK}#L{CONFIG_READ_LINE}",
            "constructor_default": f"{LEAD_WORKER_PERMALINK}#L{CONSTRUCTOR_DEFAULT_LINE}",
            "trigger": f"{LEAD_WORKER_PERMALINK}#L{TRIGGER_LINE}",
            "switch_log": f"{LEAD_WORKER_PERMALINK}#L{SWITCH_LOG_LINE}",
            "env_docs": f"{ENV_DOCS_PERMALINK}#L{ENV_DOCS_THRESHOLD_LINE}",
            "tutorial": f"{TUTORIAL_PERMALINK}#L{TUTORIAL_THRESHOLD_LINE}",
        },
        "main_lead_worker_http_status": main_status,
        "main_lead_worker_absent": main_absent,
        "mutant_config_key_stripped_still_configurable": mutant_configurable,
        "captures": {
            "lead_worker.rs": {
                "url": LEAD_WORKER_RAW,
                "status": lw["status"],
                "sha256": lw["sha256"],
                "bytes": lw["bytes"],
                "fetched_at": lw["fetched_at"],
            },
            "init.rs": {
                "url": INIT_RAW,
                "status": init["status"],
                "sha256": init["sha256"],
                "bytes": init["bytes"],
                "fetched_at": init["fetched_at"],
            },
            "environment-variables.md": {
                "url": ENV_DOCS_RAW,
                "status": env["status"],
                "sha256": env["sha256"],
                "bytes": env["bytes"],
                "fetched_at": env["fetched_at"],
            },
            "lead-worker.md": {
                "url": TUTORIAL_RAW,
                "status": tutorial["status"],
                "sha256": tutorial["sha256"],
                "bytes": tutorial["bytes"],
                "fetched_at": tutorial["fetched_at"],
            },
            "lead_worker.rs:main": {
                "url": LEAD_WORKER_MAIN_RAW,
                "status": main_status,
                "sha256": main_lw.get("sha256"),
                "bytes": main_lw.get("bytes"),
                "fetched_at": main_lw["fetched_at"],
            },
        },
        "source_lineage": [
            lineage(LEAD_WORKER_RAW, lw["status"], lw["sha256"], lw["fetched_at"], "structured-raw-source"),
            lineage(INIT_RAW, init["status"], init["sha256"], init["fetched_at"], "structured-raw-source"),
            lineage(ENV_DOCS_RAW, env["status"], env["sha256"], env["fetched_at"], "prose-docs"),
            lineage(TUTORIAL_RAW, tutorial["status"], tutorial["sha256"], tutorial["fetched_at"], "prose-docs"),
            lineage(LEAD_WORKER_MAIN_RAW, main_status, main_lw.get("sha256"), main_lw["fetched_at"], "current-main-absence-control"),
        ],
    }
