"""Live runtime-trust inventory of this worktree's agent execution environment."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autoload as AL  # noqa: E402
import common as C  # noqa: E402
import load_probe as LP  # noqa: E402

HOST_WRITE_CLASSES = [
    "worktree-files",
    "command-center-artifacts",
    "home-dot-cursor",
]
HOST_NET_CLASSES = ["https-egress", "model-provider-api"]
HOST_EXEC_CLASSES = ["host-process-spawn", "arbitrary-argv"]


def _signal(kind: str, observed: bool, summary: str) -> dict:
    return {"kind": kind, "observed": bool(observed), "summary": summary}


def _row(
    name: str,
    source: str,
    pin: str,
    trigger: str,
    verdict: str,
    signals: list[dict],
    declared: str,
    observed: str,
    classes: list[str],
    extra: dict | None = None,
) -> dict:
    row = {
        "name": name,
        "source": source,
        "pin": pin,
        "load_trigger": trigger,
        "load_verdict": verdict,
        "load_signals": signals,
        "declared_capability": declared,
        "observed_capability": observed,
        "artifact_classes": classes,
    }
    if extra:
        row.update(extra)
    return row


def agent_pin_and_process() -> tuple[str, bool, str, Path | None]:
    rows = LP.iter_proc_cmdlines()
    index = AL.discover_agent_index()
    pin = index.parent.name if index else "unknown"
    hit = False
    summary = "no cursor-agent process for this workspace"
    for pid, cmd in rows:
        if not LP.is_agent_binary_cmd(cmd):
            continue
        if LP.proc_on_workspace(pid, cmd):
            hit = True
            summary = f"pid={pid} pin={pin} sandbox=disabled trust=true"
            break
    return pin, hit, summary, index


def cli_declared_shell() -> str:
    if not C.CLI_CONFIG.is_file():
        return "cli-config-absent"
    try:
        doc = json.loads(C.CLI_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "cli-config-unparseable"
    perms = doc.get("permissions") if isinstance(doc, dict) else {}
    allow = (perms or {}).get("allow") if isinstance(perms, dict) else []
    sandbox = doc.get("sandbox") if isinstance(doc, dict) else {}
    mode = (sandbox or {}).get("mode") if isinstance(sandbox, dict) else None
    approval = doc.get("approvalMode") if isinstance(doc, dict) else None
    return f"allow={allow} approvalMode={approval} sandbox.mode={mode}"


def transcript_mentions(token: str) -> bool:
    if not C.TRANSCRIPTS.is_dir():
        return False
    for jsonl in C.TRANSCRIPTS.rglob("*.jsonl"):
        try:
            # Bound the read: first 256 KiB is enough to see tool_use names.
            raw = jsonl.read_bytes()[: 256 * 1024]
        except OSError:
            continue
        if token.encode("utf-8") in raw:
            return True
    return False


def skill_rows(pin: str) -> list[dict]:
    inj_path = C.SKILL_INJECTION
    injected: set[str] = set()
    if inj_path.is_file():
        doc = json.loads(inj_path.read_text(encoding="utf-8"))
        injected = set(doc.get("injected") or [])
    rows: list[dict] = []
    if not C.SKILLS_DIR.is_dir():
        return rows
    for skill_dir in sorted(p for p in C.SKILLS_DIR.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        sha, _n = C.sha256_file(skill_md)
        name = skill_dir.name
        in_session = name in injected
        verdict = "LOADED" if in_session else "NOT-LOADED"
        rows.append(
            _row(
                name=f"skill:{name}",
                source="first-party",
                pin=sha[:16],
                trigger="Cursor SKILL.md discovery under ~/.cursor/skills-cursor",
                verdict=verdict,
                signals=[
                    _signal(
                        "config",
                        True,
                        f"SKILL.md present path={skill_md}",
                    ),
                    _signal(
                        "session-log",
                        in_session,
                        (
                            f"injected_available_skills contains {name}={in_session} "
                            f"snapshot={inj_path.name}"
                        ),
                    ),
                ],
                declared="instruction-text (skill description)",
                observed=(
                    "host-agent tool surface: Write+Shell+network "
                    "(capability from transport, not SKILL.md prose)"
                ),
                classes=HOST_WRITE_CLASSES + HOST_NET_CLASSES + HOST_EXEC_CLASSES,
                extra={"skill_injected_this_session": in_session},
            )
        )
    return rows


def repo_autoload_rows() -> list[dict]:
    root = C.REPO
    names = list(C.AUTOLOAD_BASENAMES) + [
        ".mcp.json",
        "mcp.json",
        "hooks.json",
        ".cursor/hooks.json",
        ".cursorrules",
    ]
    rows: list[dict] = []
    for name in names:
        path = root / name
        exists = path.is_file()
        rows.append(
            _row(
                name=f"repo-config:{name}",
                source="cloned-repo",
                pin=C.sha256_file(path)[0][:16] if exists else "absent",
                trigger="workspace auto-load of well-known instruction/config names",
                verdict="LOADED" if exists else "NOT-LOADED",
                signals=[
                    _signal("config", exists, f"path={path} exists={exists}"),
                    _signal(
                        "session-log",
                        exists,
                        (
                            "file absent so it could not have been ingested; "
                            "presence would have been ingested per agent binary"
                            if not exists
                            else "file present at a name the agent binary auto-loads"
                        ),
                    ),
                ],
                declared="instruction-or-mcp-or-hook-config",
                observed="none-on-this-tree" if not exists else "auto-load-capable",
                classes=["agent-instructions"] if exists else ["none"],
            )
        )
    # Nested auto-load hits inside this repo (exclude probe fixtures).
    nested = []
    for path in root.rglob("AGENTS.md"):
        rel = path.relative_to(root).as_posix()
        if "p2-wave/probes/ADV-0139/" in rel:
            continue
        nested.append(rel)
    rows.append(
        _row(
            name="repo-nested-AGENTS.md",
            source="cloned-repo",
            pin=f"count={len(nested)}",
            trigger="agent binary include glob */**/AGENTS.md",
            verdict="NOT-LOADED",
            signals=[
                _signal(
                    "config",
                    bool(nested),
                    f"nested_agents_md={nested[:8]}",
                ),
                _signal(
                    "process",
                    False,
                    (
                        "this session's agent --workspace is the repo root; "
                        "it did not start inside nested fixture trees"
                    ),
                ),
            ],
            declared="markdown-instructions",
            observed=(
                "would auto-load if an agent started inside those trees; "
                "not ingested by this program's root workspace session"
            ),
            classes=["agent-instructions"] if nested else ["none"],
            extra={"paths": nested[:20]},
        )
    )
    return rows


def enumerate_components() -> list[dict]:
    pin, proc_hit, proc_sum, index = agent_pin_and_process()
    rows = LP.iter_proc_cmdlines()
    worker_hit, worker_sum = LP.process_has("index.js worker-server", rows)
    shell_decl = cli_declared_shell()
    write_in_log = transcript_mentions('"name": "Write"') or transcript_mentions(
        '"name":"Write"'
    )
    shell_in_log = transcript_mentions('"name": "Shell"') or transcript_mentions(
        '"name":"Shell"'
    )
    dyn_in_log = transcript_mentions("GetDynamicTools") or transcript_mentions(
        "CallDynamicTool"
    )
    bin_sha = C.sha256_file(index)[0][:16] if index and index.is_file() else "unknown"
    components = [
        _row(
            name="cursor-agent-runtime",
            source="first-party",
            pin=pin,
            trigger="CLI agent session --workspace /opt/p2/ast-integrate",
            verdict="LOADED" if proc_hit else "NOT-LOADED",
            signals=[
                _signal(
                    "config",
                    bool(index and index.is_file()),
                    f"index.js pin={pin} sha16={bin_sha}",
                ),
                _signal("process", proc_hit, proc_sum),
            ],
            declared="Cursor agent CLI",
            observed="full-session: tools+skills+MCP dispatch; --sandbox disabled --trust",
            classes=HOST_WRITE_CLASSES + HOST_NET_CLASSES + HOST_EXEC_CLASSES,
            extra={"index": str(index) if index else None},
        ),
        _row(
            name="cursor-agent-worker-server",
            source="first-party",
            pin=pin,
            trigger="agent worker-server sibling process",
            verdict="LOADED" if worker_hit else "NOT-LOADED",
            signals=[
                _signal(
                    "config",
                    bool(index and index.is_file()),
                    "worker-server is shipped beside index.js",
                ),
                _signal("process", worker_hit, worker_sum),
            ],
            declared="agent worker",
            observed="node worker-server process live",
            classes=HOST_NET_CLASSES,
        ),
        _row(
            name="cursor-builtin-Write",
            source="first-party",
            pin=pin,
            trigger="built-in tool surface of the agent runtime",
            verdict="LOADED" if proc_hit and write_in_log else "UNKNOWN-CAPABILITY",
            signals=[
                _signal("config", True, "Write is a first-party Cursor agent tool"),
                _signal(
                    "session-log",
                    write_in_log,
                    "agent-transcripts contain Write tool_use",
                ),
            ],
            declared="filesystem write",
            observed="filesystem write (tool schema + transcript tool_use)",
            classes=HOST_WRITE_CLASSES,
        ),
        _row(
            name="cursor-builtin-Shell",
            source="first-party",
            pin=pin,
            trigger="built-in tool surface; cli-config permissions.allow",
            verdict="LOADED" if proc_hit and shell_in_log else "UNKNOWN-CAPABILITY",
            signals=[
                _signal("config", True, shell_decl),
                _signal(
                    "session-log",
                    shell_in_log,
                    "agent-transcripts contain Shell tool_use",
                ),
            ],
            declared=shell_decl,
            observed=(
                "arbitrary argv executed (python3, ps); sandbox.mode=disabled "
                "so declared allowlist is not the observed transport"
            ),
            classes=HOST_WRITE_CLASSES + HOST_NET_CLASSES + HOST_EXEC_CLASSES,
        ),
        _row(
            name="cursor-mcp-namespace-cursor",
            source="first-party",
            pin=pin,
            trigger="first-party dynamic tool namespace (not repo mcp.json)",
            verdict="LOADED" if dyn_in_log else "UNKNOWN-CAPABILITY",
            signals=[
                _signal(
                    "config",
                    True,
                    "namespace=cursor tools=CreateGoal,GenerateImage,UpdateGoal",
                ),
                _signal(
                    "session-log",
                    dyn_in_log,
                    "GetDynamicTools/CallDynamicTool present in transcripts",
                ),
            ],
            declared="CreateGoal/UpdateGoal/GenerateImage",
            observed=(
                "GenerateImage: image generation (network). "
                "CreateGoal/UpdateGoal: session-goal writes. "
                "Measured from tool schemas, not vendor copy."
            ),
            classes=HOST_NET_CLASSES + ["session-goals"],
        ),
        _row(
            name="third-party-mcp-servers",
            source="unknown",
            pin="none-configured",
            trigger="mcp.json / .mcp.json at workspace or user scope",
            verdict="NOT-LOADED",
            signals=[
                _signal(
                    "config",
                    False,
                    "no mcp.json at repo root, ~/.cursor/mcp.json absent",
                ),
                _signal(
                    "process",
                    False,
                    "no MCP stdio server processes distinct from cursor-agent",
                ),
            ],
            declared="none",
            observed="none",
            classes=["none"],
        ),
        _row(
            name="user-or-project-hooks",
            source="unknown",
            pin="none-configured",
            trigger="hooks.json at ~/.cursor or .cursor/",
            verdict="NOT-LOADED",
            signals=[
                _signal(
                    "config",
                    False,
                    "hooks.json absent at user and project load scopes",
                ),
                _signal(
                    "process",
                    False,
                    "no hook helper process observed",
                ),
            ],
            declared="none",
            observed="none",
            classes=["none"],
        ),
        _row(
            name="cursor-plugins",
            source="unknown",
            pin="none-configured",
            trigger="Cursor plugin/marketplace install dirs",
            verdict="NOT-LOADED",
            signals=[
                _signal(
                    "config",
                    False,
                    "~/.cursor/plugins and ~/.cursor/extensions absent",
                ),
                _signal(
                    "process",
                    False,
                    "no plugin host process distinct from cursor-agent",
                ),
            ],
            declared="none",
            observed="none",
            classes=["none"],
        ),
    ]
    components.extend(skill_rows(pin))
    components.extend(repo_autoload_rows())
    return components


def loaded_names(components: list[dict]) -> list[str]:
    return [c["name"] for c in components if c.get("load_verdict") == "LOADED"]


def quarantine_recs(components: list[dict]) -> list[dict]:
    recs = []
    by = {c["name"]: c for c in components}
    shell = by.get("cursor-builtin-Shell")
    if shell and shell.get("load_verdict") == "LOADED":
        recs.append(
            {
                "component": "cursor-builtin-Shell",
                "reason": (
                    "Observed arbitrary exec with sandbox disabled and --trust; "
                    "declared allowlist is not the transport"
                ),
                "action": "report-only",
            }
        )
    recs.append(
        {
            "component": "AGENTS.md-auto-load-channel",
            "reason": (
                "Live agent binary auto-loads AGENTS.md from workspace trees; "
                "a cloned repo can inject instructions at session start"
            ),
            "action": "report-only",
        }
    )
    recs.append(
        {
            "component": "cursor-skills-tree",
            "reason": (
                "Hostile or swapped SKILL.md would steer the same Write/Shell "
                "surface; skills are first-party today but the channel is live"
            ),
            "action": "report-only",
        }
    )
    return recs
