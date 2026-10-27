"""TST-0247 shared field-set parser.

One parser, two surfaces: the ``--plain`` subprocess byte stream and the
in-process production ``frame()`` of every pane. A field is a named
information slot (``<pane>.<element>``) whose structural marker is present
in the rendered line; the same rules run on both surfaces, so a set
difference is a real information difference, not a formatting artifact.

Row anchors tolerate any glyph / cursor-column prefix (``[^[]*``) because
the parser must treat the ``> `` selection column and the pane glyphs as
decoration, not information.
"""
from __future__ import annotations

import re

MID = "\u00b7"  # the board's middle-dot separator
_PANE_BAR = re.compile(r"panes .*\[(\d+):(\w+)\]")
_BADGE = re.compile(r"^  (\S+) \[([a-z]+)\] age=(\S+) (.*)$")
_AGENTS_ROW = re.compile(
    r"^[^[]*\[([A-Z]+)\] (.+?) " + MID + r" (.+?) " + MID + r" (.+?) " + MID
    + r" (.+?) idle " + MID + r" (.*)$"
)
_WF_ROW = re.compile(
    r"^[^[]*(\S+) " + MID + r" (\d+) agents " + MID + r" (\d+) running " + MID
    + r" (\d+) error " + MID + r" done=(\S+) " + MID + r" (.+?) idle$"
)
_DBX_ROW = re.compile(
    r"^[^[]*\[([A-Za-z]+)\] (.+?) " + MID + r" (.+?) " + MID
    + r" idle=(\S+)(?: " + MID + r" (.*))?$"
)
_MCP_ROW = re.compile(
    r"^[^[]*\[([a-z]+)\] (.+?) " + MID + r" (.+?) " + MID + r" tools=(.+?) " + MID
    + r" scopes=(\d+)(?: " + MID + r" err=(.*?))?(?: " + MID + r" note=(.*))?$"
)
_HEALTH_BAND = re.compile(
    r"^[^[]*\[([A-Z]+)\] phys (\d+)% " + MID + r" commit (\d+)% " + MID + r" driver (.*)$"
)
_HEALTH_COUNTS = re.compile(
    r"^\s*procs (\d+) " + MID + r" handles (\d+) " + MID + r" threads (\d+)\s*$"
)
_HEALTH_GDI = re.compile(
    r"^\s*gdi_max (.+?) " + MID + r" usr_max (.+?) " + MID + r" top (.+)$"
)
_ORPHANS = re.compile(r"^\s*orphaned MCP runtimes (\d+)\s*$")
_ORPHAN_TOP = re.compile(r"^\s*orphan " + MID + r" (.+)$")
_CODEX_THREAD = re.compile(
    r"^[^[]*\[([A-Z]+)\] (.+?)  (.*?)  (.+?) elapsed " + MID + r" (.+?) idle\s+(.+)$"
)
_CODEX_EVENT = re.compile(r"^\s*<\d\d:\d\d:\d\d> .*$")


def parse_fields(lines: list[str]) -> set[str]:
    """Extract the exposed-information field set from rendered board lines."""
    fields: set[str] = set()
    pane = ""
    for line in lines:
        if line.lstrip().startswith("panes "):
            m = _PANE_BAR.search(line)
            if m:
                pane = m.group(2)
                fields.add(pane + ".pane_bar")
            continue
        bm = _BADGE.match(line)
        if bm and pane:
            fields |= {
                pane + ".snapshot.source_id",
                pane + ".snapshot.state",
                pane + ".snapshot.age",
                pane + ".snapshot.headline",
            }
            if "[stale]" in line:
                fields.add(pane + ".snapshot.stale")
            if "err=" in line:
                fields.add(pane + ".snapshot.error")
            continue
        if not pane:
            continue
        if pane == "codex":
            tm = _CODEX_THREAD.match(line)
            if tm:
                fields.add("codex.thread.status")
                fields.add("codex.thread.cwd_basename")
                bits = [b for b in tm.group(3).split(" " + MID + " ") if b]
                for name in ("model", "tool_kind", "source")[: len(bits)]:
                    fields.add("codex.thread." + name)
                fields.add("codex.thread.elapsed")
                fields.add("codex.thread.idle")
                fields.add("codex.thread.tokens_total")
                continue
            if _CODEX_EVENT.match(line):
                fields.add("codex.event.label")
                fields.add("codex.event.detail")
                if re.search(r"\(\d", line):
                    fields.add("codex.event.duration")
                continue
        elif pane == "agents":
            if _AGENTS_ROW.match(line):
                fields |= {
                    "agents.row.bucket",
                    "agents.row.name",
                    "agents.row.agent_type",
                    "agents.row.workflow",
                    "agents.row.idle",
                    "agents.row.last",
                }
                continue
        elif pane == "workflows":
            if _WF_ROW.match(line):
                fields |= {
                    "workflows.workflow.id",
                    "workflows.workflow.agent_count",
                    "workflows.workflow.running_count",
                    "workflows.workflow.error_count",
                    "workflows.workflow.done",
                    "workflows.workflow.idle",
                }
                continue
        elif pane == "databricks":
            m = _DBX_ROW.match(line)
            if m:
                fields |= {
                    "databricks.unit.liveness",
                    "databricks.unit.unit_id",
                    "databricks.unit.run_id",
                    "databricks.unit.idle",
                }
                if m.group(5):
                    fields.add("databricks.unit.error")
                continue
        elif pane == "mcp":
            if _MCP_ROW.match(line):
                fields |= {
                    "mcp.server.state",
                    "mcp.server.name",
                    "mcp.server.transport",
                    "mcp.server.tool_count",
                    "mcp.server.scope_count",
                }
                if "err=" in line:
                    fields.add("mcp.server.last_error")
                if "note=" in line:
                    fields.add("mcp.server.note")
                continue
            if "mcp config" in line and "not-measured" in line:
                fields.add("mcp.config.problem")
                continue
        elif pane == "health":
            if "[STALE] retained" in line:
                fields.add("health.feed.stale")
                continue
            if _HEALTH_BAND.match(line):
                fields |= {
                    "health.band",
                    "health.phys_pct",
                    "health.commit_pct",
                    "health.driver",
                }
                continue
            if _HEALTH_COUNTS.match(line):
                fields |= {"health.procs", "health.handles", "health.threads"}
                continue
            if _HEALTH_GDI.match(line):
                fields |= {"health.gdi_max", "health.usr_max", "health.gdi_max_proc"}
                continue
            if _ORPHANS.match(line):
                fields.add("health.orphan_count")
                continue
            if _ORPHAN_TOP.match(line):
                fields.add("health.orphan_top")
                continue
    return fields
