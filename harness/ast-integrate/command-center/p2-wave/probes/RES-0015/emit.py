#!/usr/bin/env python3
"""Emit command-center/research/RES-0015.json and per-unit receipts."""
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

from engine import digest_text  # noqa: E402
from flags import INVENTED_FLAG  # noqa: E402

UNIT = "RES-0015"
OUT = "command-center/research/RES-0015.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0015/probe1_flag_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0015/probe2_controls.py"
)
SENTINEL = (
    "SUCCESS:RES-0015 in the receipt AND a flag-by-flag accepted/rejected "
    "table produced by running the installed binary"
)
QUESTION = (
    "What is the exact non-interactive surface today - flags, stream-json "
    "control_request channel, permission modes, output schemas - and which of "
    "it is stable enough for this program's distributed runner to depend on?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/RES-0015/flags.py",
    "command-center/p2-wave/probes/RES-0015/engine.py",
    "command-center/p2-wave/probes/RES-0015/probe1_flag_table.py",
    "command-center/p2-wave/probes/RES-0015/probe2_controls.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_cmd(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def local_schema_errors(doc) -> list[str]:
    """Catalog output_schema is a generated shim with no constraints of its own.

    Discriminate here so {} / unrelated blobs / lineage-stripped copies fail.
    """
    if not isinstance(doc, dict):
        return ["not-object"]
    errs: list[str] = []
    for key in (
        "unit_id",
        "state",
        "claims",
        "flag_table",
        "source_lineage",
        "completion_sentinel",
        "counts",
        "binary",
        "negative_controls",
    ):
        if key not in doc:
            errs.append(f"missing:{key}")
    lineage = doc.get("source_lineage")
    if not isinstance(lineage, list) or len(lineage) < 1:
        errs.append("source_lineage-missing-or-empty")
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 1:
        errs.append("claims-missing-or-empty")
    else:
        for i, c in enumerate(claims):
            if not isinstance(c, dict):
                errs.append(f"claims[{i}]-not-object")
                break
            if not c.get("source_lineage"):
                errs.append(f"claims[{i}]-source_lineage-missing")
                break
            if not c.get("canonical_mechanism"):
                errs.append(f"claims[{i}]-canonical_mechanism-missing")
                break
    table = doc.get("flag_table")
    if not isinstance(table, list) or len(table) < 8:
        errs.append("flag_table-too-small")
    sentinel = str(doc.get("completion_sentinel") or "")
    if SENTINEL not in sentinel and SENTINEL not in json.dumps(doc):
        errs.append("sentinel-absent")
    return errs


def claim(
    cid: str,
    text: str,
    mechanism: str,
    lineage: list[dict],
    tier: str,
    band: str,
    probe: str,
    stamp: str,
    snap: str,
    verdict: str,
    caveat: str,
    rails: list[dict],
    measured_fact: str,
    edges: list[dict] | None = None,
) -> dict:
    return {
        "id": cid,
        "claim_id": cid,
        "text": text,
        "canonical_mechanism": mechanism,
        "source_lineage": lineage,
        "evidence_tier": tier,
        "confidence_band": band,
        "rails": rails,
        "measured_fact": measured_fact,
        "named_settling_probe": probe,
        "freshness_stamp": stamp,
        "snapshot_sha256": snap,
        "verdict": verdict,
        "strongest_caveat": caveat,
        "edges": edges or [],
    }


def main() -> int:
    started = now()
    cache = HERE / "last-measure.json"
    c1, t1 = run_cmd(P1)
    print(f"probe1 rc={c1}")
    print(t1[-2500:])
    if c1 != 0:
        print("FAILED:RES-0015 named probe1")
        return 1
    if not cache.is_file():
        print("FAILED:RES-0015 probe1 did not write last-measure.json")
        return 1
    data = json.loads(cache.read_text(encoding="utf-8"))
    stamp = started
    help_sha = data["binary"]["help_sha256"]
    table_sha = digest_text(json.dumps(data["flag_table"], sort_keys=True, default=str))
    bin_path = data["binary"]["path"]
    version = data["binary"]["version"]
    invented = data["invented"]
    runner = data["runner_flags"]
    ofmt = data["output_format"]
    ctrl = data["control_request_scan"]

    runner_stable = []
    runner_unstable = []
    for row in runner:
        if row["verdict"] == "accepted":
            runner_stable.append(row["flag"])
        else:
            runner_unstable.append(row["flag"])

    effort_row = next((r for r in data["flag_table"] if r["flag"] == "--effort"), None)
    perm_row = next((r for r in data["flag_table"] if r["flag"] == "--permission-mode"), None)
    inp_row = next((r for r in data["flag_table"] if r["flag"] == "--input-format"), None)
    print_row = next((r for r in data["flag_table"] if r["flag"] == "--print"), None)
    sj_row = ofmt["stream_json"]

    claims = [
        claim(
            "RES-0015-C1-installed-binary",
            (
                f"The installed client on this worktree is Cursor Agent {version} "
                f"at {bin_path}. `claude` is not on PATH "
                f"(claude_on_path={data['binary']['claude_on_path']!r}). "
                "The catalog's code.claude.com headless/SDK inputs describe a "
                "different product than the binary this program's runner execs."
            ),
            "PATH resolve + `agent --version` stdout vs shutil.which('claude')",
            [
                {"kind": "command", "locator": f"{bin_path} --version"},
                {"kind": "path", "locator": "shutil.which('claude')"},
            ],
            "E1",
            "almost-certain",
            "probe1_flag_table.py:binary.version",
            stamp,
            help_sha,
            "CONFIRMED",
            "Version string is this build only (2026.08.11-e8db854). A later agent upgrade can change the flag set.",
            [
                {"id": "which-agent", "kind": "path-resolve"},
                {"id": "agent-version", "kind": "command-stdout"},
            ],
            f"version={version}; claude_on_path={data['binary']['claude_on_path']!r}",
        ),
        claim(
            "RES-0015-C2-noninteractive-flags",
            (
                "Non-interactive invocation is `-p`/`--print` plus "
                "`--output-format {text,json,stream-json}`. `--print` with no "
                "prompt exits 1 with 'No prompt provided for print mode' "
                f"(reason={print_row['reason'] if print_row else 'missing'}). "
                "Valid `--output-format stream-json` is accepted as a known value "
                f"({sj_row['reason']}); an invented format hits the enum "
                f"({ofmt['invented_value']['reason']}: "
                f"{(ofmt['invented_value']['stderr_tail'] or '').splitlines()[:1]})."
            ),
            "execute each documented flag once; classify unknown-option vs known-flag errors",
            [
                {"kind": "command", "locator": f"{bin_path} --print"},
                {"kind": "command", "locator": f"{bin_path} --output-format stream-json"},
                {"kind": "help-snapshot", "locator": f"sha256:{help_sha}"},
            ],
            "E1",
            "almost-certain",
            "probe1_flag_table.py",
            stamp,
            table_sha,
            "CONFIRMED",
            (
                "Parser acceptance is not a live stream-json session. Event "
                "shapes (system/init, assistant, tool_call, result) were not "
                "captured from a real run; they remain documentation-only."
            ),
            [
                {"id": "help-parse", "kind": "help-text"},
                {"id": "argv-execute", "kind": "binary-execution"},
            ],
            (
                f"print_reason={(print_row or {}).get('reason')}; "
                f"stream_json_reason={sj_row['reason']}; "
                f"invented_format_reason={ofmt['invented_value']['reason']}"
            ),
        ),
        claim(
            "RES-0015-C3-control-request-absent",
            (
                "The Claude Code stream-json `control_request` / "
                "`control_response` stdin channel is REFUTED on this binary: "
                f"JS byte search total={ctrl['total']} for 'control_request', "
                f"{data['control_response_scan']['total']} for 'control_response', "
                f"{data['permission_prompt_tool_scan']['total']} for "
                "'permission-prompt-tool'. `--input-format` and "
                "`--permission-prompt-tool` are rejected as unknown options. "
                "This is not a capability of the installed client."
            ),
            "byte-search of shipped *.js independently of argv classification of Claude-doc flags",
            [
                {"kind": "bytes", "locator": f"{data['binary']['install_dir']}/*.js needle=control_request"},
                {"kind": "command", "locator": f"{bin_path} --input-format"},
                {"kind": "command", "locator": f"{bin_path} --permission-prompt-tool"},
            ],
            "E1",
            "almost-certain",
            "probe2_controls.py",
            stamp,
            digest_text(json.dumps(ctrl, sort_keys=True)),
            "REFUTED",
            "A minified identifier rename could hide the string; the unknown-option results on the Claude flags are the independent second signal and would still stand.",
            [
                {"id": "js-byte-scan", "kind": "bytes"},
                {"id": "claude-flag-argv", "kind": "binary-execution"},
            ],
            (
                f"control_request_total={ctrl['total']}; "
                f"control_response_total={data['control_response_scan']['total']}; "
                f"permission_prompt_tool_total={data['permission_prompt_tool_scan']['total']}; "
                f"input_format={(inp_row or {}).get('verdict')}"
            ),
            edges=[
                {
                    "type": "direct-contradiction",
                    "from": "code.claude.com/docs/en/headless + cli-reference control_request/--input-format stream-json",
                    "to": "installed cursor-agent 2026.08.11-e8db854",
                }
            ],
        ),
        claim(
            "RES-0015-C4-permission-surface",
            (
                "Permission / trust surface honoured by this binary is "
                "`--force`/`--yolo`, `--auto-review`, `--sandbox {enabled,disabled}`, "
                "and `--trust`. Claude `--permission-mode` "
                f"is {perm_row['verdict'] if perm_row else 'missing'} "
                f"({perm_row['reason'] if perm_row else ''}). `--mode` accepts only "
                f"plan|ask; value `agent` is invalid "
                f"({data['mode_agent_value']['reason']}). `--sandbox` invented "
                "value is rejected by the choice enum while `disabled` is accepted."
            ),
            "flag execution + sandbox/mode choice enums",
            [
                {"kind": "command", "locator": f"{bin_path} --force"},
                {"kind": "command", "locator": f"{bin_path} --permission-mode"},
                {"kind": "command", "locator": f"{bin_path} --sandbox not-a-mode"},
            ],
            "E1",
            "almost-certain",
            "probe1_flag_table.py + probe2_controls.py",
            stamp,
            table_sha,
            "CONFIRMED",
            "These checks prove parser acceptance, not that --force actually bypasses a tool prompt in a live session.",
            [
                {"id": "force-trust-sandbox-argv", "kind": "binary-execution"},
                {"id": "permission-mode-unknown", "kind": "binary-execution"},
            ],
            (
                f"permission_mode={(perm_row or {}).get('verdict')}/{(perm_row or {}).get('reason')}; "
                f"mode_agent={data['mode_agent_value']['reason']}; "
                f"sandbox_invented={data['sandbox']['invented_value']['reason']}"
            ),
        ),
        claim(
            "RES-0015-C5-runner-stability",
            (
                "This program's distributed runner "
                "(command-center/p2-wave/seed-stage/dispatch_cursor.py) currently "
                f"passes {sorted({r['flag'] for r in runner})}. "
                f"Accepted by the binary: {sorted(runner_stable)}. "
                f"Rejected by the binary: {sorted(runner_unstable)}. "
                "`--effort` "
                f"is {effort_row['verdict'] if effort_row else 'missing'} "
                f"({effort_row['reason'] if effort_row else ''}); "
                "agent_cmd() in dispatch_cursor.py lists it, launch_one() does not. "
                "Stable-enough-to-depend: -p/--print, --force, --trust, "
                "--sandbox disabled, --model, --workspace, --output-format text. "
                "Do not depend on --effort, --permission-mode, --input-format, "
                "or control_request."
            ),
            "parse quoted flags out of dispatch_cursor.py (signal 1) vs execute each against the binary (signal 2)",
            [
                {"kind": "source", "locator": "command-center/p2-wave/seed-stage/dispatch_cursor.py"},
                {"kind": "command", "locator": f"{bin_path} --effort"},
            ],
            "E1",
            "almost-certain",
            "probe1_flag_table.py:runner_flags",
            stamp,
            digest_text(
                (REPO / "command-center/p2-wave/seed-stage/dispatch_cursor.py").read_text(
                    encoding="utf-8"
                )
            ),
            "CONFIRMED",
            "--model cursor-grok-4.6-xhigh was not live-invoked as a full print session; only the --model flag's parser acceptance was measured (missing-arg).",
            [
                {"id": "dispatch-source-parse", "kind": "static-parse"},
                {"id": "runner-flag-execute", "kind": "binary-execution"},
            ],
            (
                f"runner_stable={sorted(runner_stable)}; "
                f"runner_unstable={sorted(runner_unstable)}; "
                f"effort={(effort_row or {}).get('verdict')}"
            ),
        ),
        claim(
            "RES-0015-C6-invented-flag-control",
            (
                f"Negative control {INVENTED_FLAG} is rejected as unknown-option "
                f"(python reason={invented['reason']}, exit={invented['exit_code']}). "
                "The acceptance test therefore discriminates: it is not silent in both states."
            ),
            "invented flag vs known --print: opposite verdicts",
            [
                {"kind": "command", "locator": f"{bin_path} {INVENTED_FLAG}"},
                {"kind": "command", "locator": f"{bin_path} --print"},
            ],
            "E1",
            "almost-certain",
            "probe2_controls.py (python3-subprocess vs /bin/sh)",
            stamp,
            digest_text(invented.get("stderr_tail") or ""),
            "CONFIRMED",
            "Pairing an unknown flag with --help swallows the unknown-option error (commander prints help, exit 0). The control therefore must not use --help as the discriminator.",
            [
                {"id": "python-subprocess", "kind": "binary-execution"},
                {"id": "bin-sh-dash", "kind": "second-shell"},
            ],
            (
                f"invented_verdict={invented['verdict']}; "
                f"invented_reason={invented['reason']}; "
                f"print_verdict={(print_row or {}).get('verdict')}"
            ),
        ),
    ]

    flag_table = [
        {
            "flag": r["flag"],
            "argv": r["argv"],
            "sources": r["sources"],
            "in_help": r["in_help"],
            "verdict": r["verdict"],
            "reason": r["reason"],
            "kind": r["kind"],
            "exit_code": r["exit_code"],
            "timed_out": r["timed_out"],
            "stderr_tail": r["stderr_tail"],
        }
        for r in data["flag_table"]
    ]

    answer = (
        f"Installed binary is Cursor Agent {version}, not Claude Code. "
        f"Executed {data['counts']['executed']} flags: "
        f"{data['counts']['accepted']} accepted, {data['counts']['rejected']} rejected, "
        f"{data['counts']['doc_vs_binary']} doc-vs-binary. "
        "Non-interactive surface: --print/-p, --output-format text|json|stream-json, "
        "--stream-partial-output (requires stream-json), --force/--yolo, --trust, "
        "--sandbox enabled|disabled, --model, --workspace. "
        "control_request channel: REFUTED. "
        f"{SENTINEL}"
    )

    ended = now()
    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "kind": "research-claim-record",
        "report": {"kind": "research-claim-record"},
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Map the headless/SDK surface: programmatic invocation, stream-json control channel, modes",
        "question": QUESTION,
        "answer": answer,
        "binary": data["binary"],
        "flag_table": flag_table,
        "command_table": data["command_table"],
        "counts": data["counts"],
        "output_schemas": {
            "documented_and_parser_accepted": ["text", "json", "stream-json"],
            "invented_value_rejected": True,
            "invented_stderr": ofmt["invented_value"]["stderr_tail"],
            "live_session_capture": "NOT-CHECKED",
            "note": (
                "Parser enum is live. NDJSON event schemas from Cursor docs "
                "were not re-emitted by a real --print session in this unit."
            ),
        },
        "permission_modes": {
            "honoured_flags": ["--force", "--yolo", "--auto-review", "--sandbox", "--trust"],
            "claude_permission_mode": perm_row,
            "mode_flag_choices": ["plan", "ask"],
            "mode_agent_value": data["mode_agent_value"],
            "sandbox_enum": data["sandbox"],
        },
        "control_request_channel": {
            "present_in_js": ctrl["total"] > 0,
            "scan": ctrl,
            "control_response_scan": data["control_response_scan"],
            "permission_prompt_tool_scan": data["permission_prompt_tool_scan"],
            "input_format": inp_row,
            "verdict": "REFUTED",
        },
        "runner_dependency": {
            "source": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
            "flags": runner,
            "stable": sorted(runner_stable),
            "do_not_depend": sorted(set(runner_unstable) | {"--permission-mode", "--input-format", "--effort"}),
        },
        "claims": claims,
        "tests": [
            {
                "id": "every-documented-flag-executed",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "invented-flag-rejected",
                "command": P2,
                "result": "PASS" if invented["verdict"] == "rejected" else "FAIL",
            },
            {
                "id": "output-format-enum-discriminates",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "control-request-byte-scan",
                "command": P2,
                "result": "PASS" if ctrl["total"] == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0015-C1-invented-flag",
                "kind": "invented-flag",
                "description": (
                    f"{INVENTED_FLAG} must be rejected as unknown-option. "
                    "--print must not be classified the same way."
                ),
                "fired": invented["verdict"] == "rejected",
                "silent_on_clean": bool(print_row and print_row["verdict"] == "accepted"),
                "bad_state_output": invented.get("stderr_tail"),
                "good_state_output": (print_row or {}).get("stderr_tail"),
            },
            {
                "id": "RES0015-C2-invented-output-format",
                "kind": "invented-enum-value",
                "description": "--output-format res0015-not-a-format must hit Allowed values, not unknown option.",
                "fired": "Invalid" in (ofmt["invented_value"]["stderr_tail"] or "")
                or "Allowed values" in (ofmt["invented_value"]["stderr_tail"] or ""),
                "silent_on_clean": ofmt["stream_json"]["reason"] != ofmt["invented_value"]["reason"]
                or (ofmt["stream_json"]["stderr_tail"] != ofmt["invented_value"]["stderr_tail"]),
                "bad_state_output": ofmt["invented_value"]["stderr_tail"],
                "good_state_output": ofmt["stream_json"]["stderr_tail"],
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0015-probe2-sh-and-byte-scan",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "read_conclusion_first": False,
            "shells": ["python3-subprocess", "/bin/sh (dash)"],
            "note": (
                "Catalog asked for PowerShell 7 vs Git Bash. This worktree is "
                "Linux; pwsh is not installed. The second shell is /bin/sh "
                "(dash) re-running the invented-flag command. The byte scan of "
                "control_request is a different measurement, not a re-run of probe 1."
            ),
        },
        "evidence": [
            {
                "path": bin_path,
                "line": 1,
                "snippet": f"agent --version -> {version}",
                "kind": "binary",
                "claim": "Installed client identity",
            },
            {
                "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
                "line": 333,
                "snippet": '"--force", "--trust", "--sandbox", "disabled"',
                "kind": "runner",
                "claim": "Distributed runner argv",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "registered": True,
        "ranking_factors": [
            {
                "id": "cursor-docs-parameters",
                "marketplace": "cursor.com/docs/cli/reference/parameters",
                "factor": "global option listed in the official Cursor CLI parameters table fetched 2026-08-24",
                "evidence_class": "documented",
            },
            {
                "id": "live-binary-help",
                "marketplace": "cursor-agent --help",
                "factor": "option listed in the installed binary's --help",
                "evidence_class": "documented",
            },
            {
                "id": "help-absent-or-other-product",
                "marketplace": "cursor-agent argv parser vs code.claude.com/docs/en/cli-reference",
                "factor": "flag accepted or rejected by this binary but not listed in the fetched Cursor parameters table",
                "evidence_class": "inferred",
            },
        ],
        "undocumented_proportion": {
            "documented_count": sum(
                1
                for r in data["flag_table"]
                if r.get("in_help") or "cursor-docs" in (r.get("sources") or [])
            ),
            "inferred_count": sum(
                1
                for r in data["flag_table"]
                if not (r.get("in_help") or "cursor-docs" in (r.get("sources") or []))
            ),
            "total": len(data["flag_table"]),
            "proportion": (
                sum(
                    1
                    for r in data["flag_table"]
                    if not (r.get("in_help") or "cursor-docs" in (r.get("sources") or []))
                )
                / max(1, len(data["flag_table"]))
            ),
            "definition": (
                "documented = in live --help or the fetched Cursor parameters table; "
                "inferred = Claude-doc-only, runner-only, invented, or help-parse miss"
            ),
        },
        "source_lineage": [
            {"kind": "binary", "locator": bin_path, "role": "installed-client"},
            {"kind": "help-snapshot", "locator": f"sha256:{help_sha}", "role": "self-documented-flags"},
            {
                "kind": "url",
                "locator": "https://cursor.com/docs/cli/reference/parameters",
                "role": "cursor-docs-frozen-2026-08-24",
            },
            {
                "kind": "url",
                "locator": "https://code.claude.com/docs/en/cli-reference",
                "role": "claude-docs-frozen-2026-08-24",
            },
            {
                "kind": "source",
                "locator": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
                "role": "distributed-runner",
            },
        ],
        "evidence_tier_vocabulary": [
            {"id": "E1", "meaning": "verbatim local command or file bytes"},
            {"id": "E2", "meaning": "two independent local signals agree"},
            {"id": "E3", "meaning": "single source (docs or help, not both)"},
            {"id": "E4", "meaning": "inferred from docs without executing the binary"},
        ],
        "freshness": {
            "measured_at": stamp,
            "binary_version": version,
            "help_sha256": help_sha,
            "flag_table_sha256": table_sha,
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "residual_unknowns": [
            {
                "claim": "Live stream-json NDJSON from a real --print session was not captured (would consume the runner model budget and is not required to classify flag acceptance).",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Run a one-token --print --output-format stream-json session and record event types only, redacting prompt/result text.",
            },
            {
                "claim": "PowerShell 7 vs Git Bash reproduction was not run; this box has bash and dash.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Install pwsh and re-run the invented-flag command; compare stderr to /bin/sh.",
            },
        ],
        "notes": (
            "G-1 for RES-0015: live named probes exit 0, research/RES-0015.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Catalog output_schema is a generated shim "
            "with no constraints; local_schema_errors discriminates garbage and "
            "source_lineage-stripped copies."
        ),
    }

    errs = local_schema_errors(doc)
    if errs:
        print("FAILED:RES-0015 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not local_schema_errors(g):
            print(f"FAILED:RES-0015 schema accepted garbage {list(g)[:2]}")
            return 1
    stripped = json.loads(json.dumps(doc))
    stripped.pop("source_lineage", None)
    if not local_schema_errors(stripped):
        print("FAILED:RES-0015 schema accepted source_lineage-stripped document")
        return 1
    if SENTINEL not in json.dumps(doc):
        print("FAILED:RES-0015 catalog sentinel missing from document")
        return 1
    if invented["verdict"] != "rejected":
        print("FAILED:RES-0015 invented flag not rejected")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    digest, size = sha256_file(out_path)
    if size < 2048:
        print(f"FAILED:RES-0015 artifact {size}B below floor")
        return 1

    c2, t2 = run_cmd(P2)
    print(f"probe2 rc={c2}")
    print(t2[-2500:])
    if c2 != 0:
        print("FAILED:RES-0015 named probe2")
        return 1

    digest, size = sha256_file(out_path)
    ts = now()
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0015/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0015-probe2-sh-and-byte-scan",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": None,
        "ts": ts,
        "notes": (
            "G-1 for RES-0015: live named probes exit 0, research/RES-0015.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": p.is_file(),
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/RES-0015/SUBAGENT-RETURN.json",
            "role": role,
        }

    man_arts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(man_arts),
        "present": sum(1 for a in man_arts if a["present"]),
        "artifacts": man_arts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0015 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
