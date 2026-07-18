#!/usr/bin/env python3
"""
mine.py -- distil ~12 GB of Claude Code history into a structured corpus agents can reason over.

WHY THIS EXISTS
  The owner asked for agents to "read all sessions and our workflows and logs". Measured:
  1,964 session transcripts + 9,669 subagent transcripts + 677 workflow runs = ~12 GB, with a
  single 4.4 GB session. That is not an agent task -- 800 agents each reading 15 MB would spend
  the entire budget on reading and return mush. So: distil first (deterministic, no judgement),
  then let Codex reason over signal.

WHAT IT EXTRACTS (all bounded -- this never accumulates raw transcript)
  1. tool usage      -- per-tool call counts, error counts, error rate, p50/p95 duration
  2. error fingerprints -- normalised error strings ranked by frequency (the recurring pain)
  3. retry loops     -- same tool + same input hash fired >=3x in a row (the grind signal)
  4. user corrections-- owner messages that correct/redirect the agent. HIGHEST SIGNAL in the
                        corpus: these are ground truth about where the harness fails its owner.
  5. hook fires      -- which hooks fired, how often, and whether they blocked (exit 2)
  6. capability use  -- which skills / agents / MCP tools were ACTUALLY invoked, vs merely
                        installed. Feeds the prune-vs-keep decision with data instead of guesses.
  7. session outcomes-- completed vs died mid-task; where the long gaps are
  8. workflow runs   -- agents spawned, phases, completion

DESIGN CONSTRAINTS
  - STREAMING ONLY. Never json.load() a whole file; the largest is 4.4 GB.
  - BOUNDED MEMORY. Counters and capped sample lists only; no unbounded text accumulation.
  - FAIL-SOFT. A malformed line, an encoding error, or a locked file skips that record and is
    counted -- it never aborts the run. A 12 GB corpus WILL contain corrupt lines.
  - REPRODUCIBLE. No wall-clock in the output body; the timestamp is passed in or omitted, so
    two runs over the same corpus diff cleanly.
  - READ-ONLY on the corpus. Opens every file 'r'. Writes only to --out.

USAGE
  python mine.py --out C:/Users/Prekzursil/.claude/harness-sota-2026-07-18/corpus
  python mine.py --out ... --max-mb 500     # skip pathological files while smoke-testing
  python mine.py --out ... --limit 50       # first 50 transcripts only (fast dry run)
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys

# A single JSONL record above this is pathological (a huge base64 blob or an embedded file dump).
# We still count it, but we do not parse it -- that is where the memory blowups live.
MAX_LINE_BYTES = 4 * 1024 * 1024
# Cap every sample list so a hot key cannot grow without bound.
SAMPLE_CAP = 12
# A tool firing this many times consecutively with identical input is a grind loop.
RETRY_RUN_THRESHOLD = 3

# ---- HOOK TELEMETRY -------------------------------------------------------------------
# Hook fires are NOT recorded at the top level of a transcript record. They arrive as
# records of `type: "attachment"` whose payload sits one level down, under
# rec["attachment"], shaped:
#
#   {"type": "hook_success", "hookName": "PreToolUse:Bash", "hookEvent": "PreToolUse",
#    "toolUseID": "...", "stdout": "...", "stderr": "", "exitCode": 0,
#    "command": "Shared harness: PreToolUse", "durationMs": 469}
#
# The ORIGINAL detector read rec["hookName"] at the ROOT and therefore saw zero fires
# across 10.62 GB, which the corpus then published as `DETECTOR_STATUS: BROKEN`. The key
# name was already right; only the nesting level was wrong. Verified 2026-07-18 against a
# known-positive control: 32,211 hook records in a 1,201-file sample.
#
# Match on the semantic role (the payload carries hookName/hookEvent), never on the
# `type: "attachment"` envelope alone -- skill_listing, task_reminder, deferred_tools_delta
# and file records share that envelope and are not hooks.
HOOK_ATTACHMENT_TYPES = frozenset({
    "hook_success",             # completed; carries exitCode + durationMs + stdout
    "async_hook_response",      # completed out of band
    "hook_additional_context",  # the injected context itself
    "hook_cancelled",           # abandoned (timeout / interrupt); carries durationMs
    "hook_non_blocking_error",  # ran and failed, session continued
    "hook_blocking_error",      # ran and failed, and BLOCKED the action
    "hook_system_message",      # hook-authored system message
})
# Types meaning the hook did not complete normally. `hook_cancelled` is deliberately NOT
# here: cancellation is usually an interrupt, not a hook defect. It is still counted in
# hook_types, so it stays visible without inflating the error rate.
HOOK_ERROR_TYPES = frozenset({"hook_blocking_error", "hook_non_blocking_error"})
# Cap per-hook sample lists so a hot key cannot grow without bound.
HOOK_CMD_CAP = 8

# Owner messages matching these are CORRECTIONS -- the highest-signal records in the corpus.
# Deliberately broad: a false positive costs one sample slot, a false negative loses ground truth.
CORRECTION_PAT = re.compile(
    r"\b(no|nope|wrong|incorrect|actually|instead|don'?t|do not|stop|revert|undo|"
    r"that'?s not|not what|i said|i meant|again|redo|fix that|you (?:missed|forgot|broke)|"
    r"why did you|shouldn'?t|mistake|misread|you'?re wrong)\b",
    re.IGNORECASE,
)
# Harness-generated turns that WEAR the user role but were never typed by the owner:
# slash-command envelopes, local-command output, and hook/system injections. Verified present
# in the control corpus, where they were the entire residual false-positive class after
# sidechain filtering. Matched at the START only -- a genuine owner message that merely quotes
# one of these tags mid-body is still a real turn and must be kept.
SYNTHETIC_TURN = re.compile(
    r"<(?:local-command-caveat|local-command-stdout|command-name|command-message|"
    r"command-args|system-reminder|user-prompt-submit-hook)\b"
)
# Strip volatile substrings so "file X not found" and "file Y not found" share a fingerprint.
NORMALISE = [
    (re.compile(r"[A-Za-z]:\\\\[^\s\"']+"), "<winpath>"),
    (re.compile(r"/(?:[\w.@-]+/)+[\w.@-]+"), "<path>"),
    (re.compile(r"\b[0-9a-f]{7,40}\b", re.I), "<hash>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*"), "<ts>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"\s+"), " "),
]


def normalise(text: str, cap: int = 240) -> str:
    """Collapse a message to a comparable fingerprint."""
    s = text[:2000]
    for pat, rep in NORMALISE:
        s = pat.sub(rep, s)
    return s.strip()[:cap]


def as_text(v) -> str:
    """Flatten Claude Code's several content shapes (str | list[block] | dict) to plain text."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        out = []
        for b in v:
            if isinstance(b, str):
                out.append(b)
            elif isinstance(b, dict):
                if isinstance(b.get("text"), str):
                    out.append(b["text"])
                elif isinstance(b.get("content"), (str, list)):
                    out.append(as_text(b["content"]))
        return "\n".join(out)
    if isinstance(v, dict):
        return as_text(v.get("content") or v.get("text"))
    return ""


class Stats:
    """All accumulators. Every container is either a counter or a capped list."""

    def __init__(self) -> None:
        self.files_seen = 0
        self.files_failed = 0
        self.lines = 0
        self.lines_bad = 0
        self.lines_oversized = 0
        self.bytes = 0

        self.tool_calls = collections.Counter()
        self.tool_errors = collections.Counter()
        self.tool_durations: dict[str, list[int]] = collections.defaultdict(list)

        self.errors = collections.Counter()
        self.error_samples: dict[str, list[str]] = collections.defaultdict(list)
        self.error_by_tool: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

        self.retry_loops = collections.Counter()
        self.retry_samples: dict[str, list[str]] = collections.defaultdict(list)

        self.corrections = collections.Counter()
        self.correction_samples: list[dict] = []
        self.user_msgs = 0

        # Hook telemetry. `hooks` is keyed by the per-tool hookName ("PreToolUse:Bash");
        # `hook_events` rolls the same fires up by bare lifecycle event ("PreToolUse"),
        # which is what answers "how much does PreToolUse cost me".
        self.hooks = collections.Counter()
        self.hook_events = collections.Counter()
        self.hook_types = collections.Counter()
        self.hook_blocks = collections.Counter()
        self.hook_errors = collections.Counter()
        self.hook_exit_codes = collections.Counter()
        self.hook_durations: dict[str, list[int]] = collections.defaultdict(list)
        # The command string of a FAILING hook. Counting a failure is useless without it:
        # this is the field that identifies an unexpanded ${CLAUDE_PLUGIN_ROOT} placeholder.
        self.hook_failure_commands: dict[str, list[str]] = collections.defaultdict(list)
        # WHY a block happened. A bare block count cannot distinguish a true positive from
        # the known use-vs-mention false-positive class; the check's own message can.
        self.hook_block_reasons: dict[str, list[str]] = collections.defaultdict(list)

        self.skills = collections.Counter()
        self.agents = collections.Counter()
        self.mcp_tools = collections.Counter()
        self.mcp_servers = collections.Counter()

        self.sessions: list[dict] = []

    # -- helpers ---------------------------------------------------------
    def sample(self, bucket: dict, key: str, value: str) -> None:
        lst = bucket[key]
        if len(lst) < SAMPLE_CAP and value not in lst:
            lst.append(value)


def record_tool(st: Stats, name: str, inp, is_error: bool, dur: int | None) -> str:
    st.tool_calls[name] += 1
    if is_error:
        st.tool_errors[name] += 1
    if isinstance(dur, int) and 0 <= dur < 86_400_000:
        d = st.tool_durations[name]
        if len(d) < 5000:          # p95 is stable well before this; bound the memory
            d.append(dur)

    # Capability attribution -- what was ACTUALLY used, not what is installed.
    if name.startswith("mcp__"):
        parts = name.split("__")
        if len(parts) >= 2:
            st.mcp_servers[parts[1]] += 1
        st.mcp_tools[name] += 1
    elif name == "Skill" and isinstance(inp, dict):
        s = inp.get("skill")
        if isinstance(s, str):
            st.skills[s] += 1
    elif name in ("Agent", "Task") and isinstance(inp, dict):
        a = inp.get("subagent_type") or inp.get("agentType") or "(default)"
        if isinstance(a, str):
            st.agents[a] += 1

    try:
        blob = json.dumps(inp, sort_keys=True, default=str)[:4000]
    except Exception:
        blob = repr(inp)[:4000]
    return name + ":" + hashlib.sha1(blob.encode("utf-8", "replace")).hexdigest()[:12]


def record_hook(st: Stats, att: dict) -> bool:
    """Record one hook fire from an `attachment` payload. Returns True if it was a hook.

    Tolerant by design: a 10 GB corpus contains malformed records, and mine.py's FAIL-SOFT
    constraint means a junk payload must be skipped, never raised.
    """
    if not isinstance(att, dict):
        return False
    name = att.get("hookName")
    event = att.get("hookEvent")
    atype = att.get("type")
    # A hook is identified by carrying a hook identity -- not by the attachment envelope.
    if not isinstance(name, str) and not isinstance(event, str):
        return False
    if atype is not None and atype not in HOOK_ATTACHMENT_TYPES:
        return False

    key = name if isinstance(name, str) else event
    st.hooks[key] += 1
    if isinstance(event, str):
        st.hook_events[event] += 1
    if isinstance(atype, str):
        st.hook_types[atype] += 1

    code = att.get("exitCode")
    if isinstance(code, int) and not isinstance(code, bool):
        st.hook_exit_codes[code] += 1

    failed = atype in HOOK_ERROR_TYPES or (
        isinstance(code, int) and not isinstance(code, bool) and code != 0
    )
    if failed:
        st.hook_errors[key] += 1
        cmd = att.get("command")
        if isinstance(cmd, str) and cmd.strip():
            lst = st.hook_failure_commands[key]
            if len(lst) < HOOK_CMD_CAP and cmd not in lst:
                lst.append(cmd)

    # exit 2 is Claude Code's block signal; hook_blocking_error is the recorded outcome.
    if atype == "hook_blocking_error" or code == 2 or att.get("blocked") is True:
        st.hook_blocks[key] += 1
        # `blockingError` is observed as a dict wrapping its own "blockingError" string;
        # tolerate a bare string too rather than assume one shape.
        be = att.get("blockingError")
        if isinstance(be, dict):
            be = be.get("blockingError")
        if isinstance(be, str) and be.strip():
            lst = st.hook_block_reasons[key]
            reason = normalise(be, cap=300)
            if len(lst) < HOOK_CMD_CAP and reason not in lst:
                lst.append(reason)

    dur = att.get("durationMs")
    if isinstance(dur, int) and not isinstance(dur, bool) and 0 <= dur < 86_400_000:
        d = st.hook_durations[key]
        if len(d) < 5000:          # p95 is stable well before this; bound the memory
            d.append(dur)
    return True


def scan(path: str, st: Stats, kind: str, max_bytes: int) -> None:
    try:
        size = os.path.getsize(path)
    except OSError:
        st.files_failed += 1
        return
    if max_bytes and size > max_bytes:
        return

    st.files_seen += 1
    st.bytes += size

    first_ts = last_ts = None
    n_lines = 0
    last_assistant_had_tool = False
    run_key = None
    run_len = 0
    # tool_use_id -> tool name. REQUIRED for error attribution: an errored tool_result names
    # only its tool_use_id, never the tool. Without this map every per-tool error rate reads
    # 0.0% while thousands of error fingerprints exist -- an incoherence caught on the first
    # full 10.62 GB run (5,692 fingerprints vs 0% on every tool). Bounded to the last 4,000
    # ids: a result always follows its call closely, so older ids are dead weight.
    pending: collections.OrderedDict[str, str] = collections.OrderedDict()

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                n_lines += 1
                st.lines += 1
                if len(raw) > MAX_LINE_BYTES:
                    st.lines_oversized += 1
                    continue
                try:
                    rec = json.loads(raw)
                except Exception:
                    st.lines_bad += 1
                    continue
                if not isinstance(rec, dict):
                    continue

                ts = rec.get("timestamp")
                if isinstance(ts, str):
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts

                rtype = rec.get("type")
                msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
                # A record authored by a SUBAGENT prompt, not the human. Verified present in
                # real transcripts (isSidechain:false x3353 in the control session), so this is
                # a real discriminator, not a guess. Without it the correction detector counts
                # agent-to-agent prompts as owner corrections -- measured on the smoke sample,
                # where 41/41 "corrections" were actually probe prompts I had written myself.
                sidechain = rec.get("isSidechain") is True

                # ---- assistant tool_use ------------------------------------
                if rtype == "assistant":
                    content = msg.get("content")
                    saw_tool = False
                    if isinstance(content, list):
                        for blk in content:
                            if isinstance(blk, dict) and blk.get("type") == "tool_use":
                                saw_tool = True
                                tname = str(blk.get("name", "?"))
                                tuid = blk.get("id")
                                if isinstance(tuid, str):
                                    pending[tuid] = tname
                                    while len(pending) > 4000:
                                        pending.popitem(last=False)
                                key = record_tool(
                                    st, tname, blk.get("input"), False, None,
                                )
                                if key == run_key:
                                    run_len += 1
                                    if run_len == RETRY_RUN_THRESHOLD:
                                        tool = key.split(":", 1)[0]
                                        st.retry_loops[tool] += 1
                                        st.sample(st.retry_samples, tool, os.path.basename(path))
                                else:
                                    run_key, run_len = key, 1
                    last_assistant_had_tool = saw_tool

                # ---- tool results / errors ---------------------------------
                elif rtype == "user":
                    content = msg.get("content")
                    if isinstance(content, list):
                        for blk in content:
                            if isinstance(blk, dict) and blk.get("type") == "tool_result":
                                if blk.get("is_error"):
                                    owner = pending.get(blk.get("tool_use_id") or "", "?")
                                    st.tool_errors[owner] += 1
                                    txt = as_text(blk.get("content"))
                                    fp = normalise(txt)
                                    if fp:
                                        st.errors[fp] += 1
                                        st.sample(st.error_samples, fp, os.path.basename(path))
                                        # Which tool produces which failure -- the join that
                                        # turns "1,631 quoting errors somewhere" into
                                        # "Bash has a quoting problem".
                                        st.error_by_tool[owner][fp] += 1
                    # A real owner turn requires ALL THREE: string content (not a tool_result
                    # envelope), not a subagent sidechain, and a top-level session transcript.
                    # Any one alone is insufficient -- the smoke sample proved it (41/41 false
                    # positives came from agent-authored prompts that pass the string test).
                    elif (isinstance(content, str) and content.strip()
                            and not sidechain and kind == "session"
                            and not SYNTHETIC_TURN.match(content.lstrip())):
                        st.user_msgs += 1
                        body = content.strip()
                        if CORRECTION_PAT.search(body) and len(body) < 4000:
                            fp = normalise(body, cap=160)
                            st.corrections[fp] += 1
                            if len(st.correction_samples) < 400:
                                st.correction_samples.append({
                                    "text": body[:600],
                                    "file": os.path.basename(path),
                                    "ts": ts,
                                    "after_tool_use": last_assistant_had_tool,
                                })

                # ---- hooks --------------------------------------------------
                # Primary path: `type: "attachment"` records carrying a nested hook
                # payload. This is where 100% of observed hook telemetry lives.
                if rtype == "attachment":
                    record_hook(st, rec.get("attachment"))

                # Legacy path: a top-level hookName/hook_event_name. Zero records matched
                # this across 10.62 GB, but it is kept so any other/future record shape
                # that really does carry the field at the root is not newly dropped.
                hook = rec.get("hookName") or rec.get("hook_event_name")
                if isinstance(hook, str):
                    st.hooks[hook] += 1
                    if rec.get("exitCode") == 2 or rec.get("blocked") is True:
                        st.hook_blocks[hook] += 1

                # toolUseResult carries duration + error on some record shapes
                tur = rec.get("toolUseResult")
                if isinstance(tur, dict):
                    nm = tur.get("toolName") or tur.get("tool")
                    if isinstance(nm, str):
                        if tur.get("isError") or tur.get("is_error"):
                            st.tool_errors[nm] += 1
                        d = tur.get("durationMs") or tur.get("duration_ms")
                        if isinstance(d, int) and 0 <= d < 86_400_000:
                            lst = st.tool_durations[nm]
                            if len(lst) < 5000:
                                lst.append(d)
    except (OSError, MemoryError):
        st.files_failed += 1
        return

    if len(st.sessions) < 4000:
        st.sessions.append({
            "file": os.path.basename(path),
            "kind": kind,
            "lines": n_lines,
            "mb": round(size / 1048576, 2),
            "first_ts": first_ts,
            "last_ts": last_ts,
        })


def pct(vals: list[int], q: float) -> int:
    if not vals:
        return 0
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * q))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-mb", type=int, default=0, help="skip files larger than this (0 = no cap)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N transcripts (dry run)")
    ap.add_argument("--stamp", default="", help="timestamp to embed; omitted keeps output diffable")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    st = Stats()
    max_bytes = args.max_mb * 1048576

    targets: list[tuple[str, str]] = []
    for dirpath, _dirs, files in os.walk(args.root):
        kind = "subagent" if os.sep + "subagents" + os.sep in dirpath + os.sep else "session"
        for f in files:
            if f.endswith(".jsonl"):
                targets.append((os.path.join(dirpath, f), kind))
    targets.sort()
    if args.limit:
        targets = targets[: args.limit]

    total = len(targets)
    print(f"mining {total} transcripts from {args.root}", flush=True)
    for i, (p, kind) in enumerate(targets, 1):
        scan(p, st, kind, max_bytes)
        if i % 200 == 0 or i == total:
            print(f"  {i}/{total}  {st.bytes/1073741824:.2f} GB  "
                  f"{st.lines:,} lines  {st.lines_bad:,} bad", flush=True)

    tools = []
    for name, calls in st.tool_calls.most_common():
        errs = st.tool_errors.get(name, 0)
        durs = st.tool_durations.get(name, [])
        tools.append({
            "tool": name, "calls": calls, "errors": errs,
            "error_rate": round(errs / calls, 4) if calls else 0.0,
            "p50_ms": pct(durs, 0.50), "p95_ms": pct(durs, 0.95),
        })

    corpus = {
        "_meta": {
            "root": args.root, "stamp": args.stamp,
            "files_seen": st.files_seen, "files_failed": st.files_failed,
            "gb": round(st.bytes / 1073741824, 2), "lines": st.lines,
            "lines_bad": st.lines_bad, "lines_oversized": st.lines_oversized,
            "note": "Distilled from raw transcripts. Counts are exact; samples are capped "
                    f"at {SAMPLE_CAP}. Absence here means absence in the corpus ONLY IF "
                    "files_failed and lines_bad are near zero -- check them before concluding.",
        },
        "tool_usage": tools,
        "error_fingerprints": [
            {"fingerprint": k, "count": v, "seen_in": st.error_samples.get(k, [])}
            for k, v in st.errors.most_common(400)
        ],
        # The join that makes the corpus actionable: per tool, its own top failure modes.
        # "Bash fails 1,631x on quoting" is a fixable finding; "1,631 quoting errors exist"
        # is trivia. Only tools with >=5 errors are listed.
        "failures_by_tool": {
            tool: {
                "errors": st.tool_errors.get(tool, 0),
                "calls": st.tool_calls.get(tool, 0),
                "error_rate": round(st.tool_errors.get(tool, 0) / st.tool_calls[tool], 4)
                               if st.tool_calls.get(tool) else None,
                "top_failures": [{"fingerprint": f, "count": n} for f, n in fps.most_common(6)],
            }
            for tool, fps in sorted(st.error_by_tool.items(),
                                    key=lambda kv: -sum(kv[1].values()))
            if sum(fps.values()) >= 5
        },
        "retry_loops": [
            {"tool": k, "runs": v, "seen_in": st.retry_samples.get(k, [])}
            for k, v in st.retry_loops.most_common(80)
        ],
        # Named "candidates", not "corrections", deliberately. The regex favours RECALL: it
        # matches any of ~20 objection markers anywhere in the message, so it over-collects
        # (e.g. a message merely containing the word "again"). Triage is the consuming agent's
        # job. Filtered to non-sidechain records in top-level session transcripts only.
        "owner_correction_candidates": {
            "total_owner_messages": st.user_msgs,
            "candidate_count": sum(st.corrections.values()),
            "precision_warning": "RECALL-BIASED. Verify each sample before treating it as a "
                                 "correction; on an unfiltered smoke sample 41/41 were false "
                                 "positives (agent-authored prompts).",
            "top_patterns": [{"pattern": k, "count": v} for k, v in st.corrections.most_common(120)],
            "samples": st.correction_samples,
        },
        # FIXED 2026-07-18 (was DETECTOR_STATUS: BROKEN). Root cause was a NESTING error,
        # not missing telemetry: hook fires live in `type: "attachment"` records under
        # rec["attachment"]["hookName"], and the old probe read rec["hookName"] at the root.
        # Regression-guarded by tools/harness-corpus/test_hook_telemetry.py, which includes
        # a MECHANICAL known-positive control against the live corpus.
        "hooks": {
            "DETECTOR_STATUS": (
                "OK -- extracts type=='attachment' -> attachment.hookName/hookEvent. "
                "Verified against a known-positive control on the live corpus. "
                "If `fires` is empty, suspect the DETECTOR before concluding hooks are idle."
            ),
            "fires": dict(st.hooks.most_common(200)),
            "by_event": dict(st.hook_events.most_common()),
            "by_outcome": dict(st.hook_types.most_common()),
            "blocks": dict(st.hook_blocks.most_common()),
            # Triage input: a block is only actionable once you can read why it fired.
            "block_reasons": {
                k: v for k, v in sorted(
                    st.hook_block_reasons.items(),
                    key=lambda kv: -st.hook_blocks.get(kv[0], 0),
                )[:40]
            },
            # A hook that exits non-zero did not do its job. exit 127 = command not found
            # (an unexpanded ${VAR} in the hook command) = a guard that never ran at all.
            "errors": dict(st.hook_errors.most_common(100)),
            "exit_codes": {str(k): v for k, v in st.hook_exit_codes.most_common()},
            "failing_commands": {
                k: v for k, v in sorted(
                    st.hook_failure_commands.items(),
                    key=lambda kv: -st.hook_errors.get(kv[0], 0),
                )[:60]
            },
            # Hooks sit on the critical path of every tool call, so their latency is a
            # first-class harness cost, not a curiosity.
            "latency_ms": {
                name: {
                    "fires": len(d),
                    "p50": pct(d, 0.50),
                    "p95": pct(d, 0.95),
                    "max": max(d) if d else 0,
                }
                for name, d in sorted(
                    st.hook_durations.items(), key=lambda kv: -pct(kv[1], 0.95)
                )[:60]
            },
        },
        "capability_use": {
            "skills_invoked": dict(st.skills.most_common(200)),
            "agents_invoked": dict(st.agents.most_common(120)),
            "mcp_servers_used": dict(st.mcp_servers.most_common(120)),
            "mcp_tools_used": dict(st.mcp_tools.most_common(400)),
        },
        "sessions": st.sessions,
    }

    out = os.path.join(args.out, "corpus.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(corpus, fh, indent=1, ensure_ascii=False)

    print(f"\nwrote {out}  ({os.path.getsize(out)/1048576:.1f} MB)")
    print(f"  {st.files_seen} files / {st.bytes/1073741824:.2f} GB / {st.lines:,} lines")
    print(f"  {st.lines_bad:,} unparseable lines, {st.lines_oversized:,} oversized, "
          f"{st.files_failed} unreadable files")
    print(f"  {len(tools)} distinct tools, {len(st.errors)} error fingerprints, "
          f"{sum(st.corrections.values())} owner corrections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
