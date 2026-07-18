#!/usr/bin/env python3
r"""compute-confidence-gate/gate.py — PreToolUse hook: pre-flight assumption ledger
for long-compute launches (jaguar / desmond / glide / binding_pose_metadynamics /
multisim / fep(_plus) / longrun) run over Bash or PowerShell (typically an ssh
command reaching a remote compute box).

WHY THIS EXISTS (ground-truth incident, verified live 2026-07-13)
  The deployed /compute-monitor reported "IE 5/6, BPMD 4/4 done" while the box's OWN
  /root/n1_qm/_qm_results.log showed 3 cluster SCFs FAILED (exit_3 = SCF
  non-convergence) — only 3/6 IEs were actually valid — AND the monitor was
  structurally BLIND to a second, untracked program (Program B GABA-B BPMD,
  /root/jobs/bpmd_gb_*) that had all 4 GPUs at 88% busy. Separately, charged QM
  clusters (molchg != 0) launched at iacscf=2 wasted ~3.7h each before failing
  exit_3 — the fix (iacscf=4) was predictable A PRIORI, before spending any compute.
  This hook cannot see remote box state or remote input-file content (a Windows-side
  PreToolUse hook has no live SSH round-trip budget — see "Design constraints"
  below) — so instead of trying to BE the oracle, it forces the AGENT to produce
  one: an explicit, falsifiable assumption ledger (AGENTS.md S1b) before the
  command executes, naming the exact log line that will prove success and
  confirming the parameters against the one KNOWN a-priori-predictable bad
  pattern (charged cluster + iacscf=2).

THREE STRICTNESS TIERS, ONE SCRIPT (argv-mode, mirrors this repo's own
loop-recovery/handler.py --mode / mcp-liveness/liveness.py pretool convention):

  argv[0] == "inject" (default)  -> Tier 1: additionalContext checklist. NEVER
      blocks. Wire through _dispatch/manifest.json (dispatcher-compatible: this
      mode ONLY ever emits additionalContext, exit 0 — see "Wiring" below).

  argv[0] == "ask"               -> Tier 2: hookSpecificOutput.permissionDecision
      = "ask" (native Claude Code confirm-gate) with the checklist as
      permissionDecisionReason. MUST be a standalone settings.json entry — the
      dispatcher (_dispatch/dispatch.py) only ever extracts additionalContext
      from a check's stdout (see dispatch.py _extract_ctx) and always exits 0
      itself, so a manifest-routed "ask"/"deny" decision would be SILENTLY
      DROPPED. Caveat: this workspace's settings.json sets
      defaultMode=bypassPermissions + skipDangerousModePermissionPrompt=true;
      whether a hook-level "ask" still forces an interactive prompt under that
      mode is NOT verified here (medium confidence, ~60-70%) — smoke-test before
      relying on it.

  argv[0] == "block"             -> Tier 3: hard exit-2 block, but ONLY for the
      one evidenced, deterministic bad pattern (charged cluster + iacscf=2 —
      _CHARGED_SCF_BAD_RE, kept in sync with the recommended
      contraindication/contraindications.json PARA-CHARGED-SCF row). Any OTHER
      long-compute launch (no known-bad pattern matched) falls through to the
      SAME Tier-1 checklist behaviour — it is never hard-blocked merely for being
      expensive. This is the AGENTS.md S6 reconciliation: "block only
      dangerous/predictably-wasteful; inject for everything else". MUST also be
      a standalone settings.json entry (exit 2 is likewise invisible to the
      dispatcher — see dispatch.py: _worker() swallows BaseException, and
      main()'s own process always `return 0`).

SCOPE / DESIGN CONSTRAINTS (read before relying on this)
  - Only inspects tool_name in {Bash, PowerShell} and tool_input.command — this
    is a LOCAL, Windows-side, sub-second check (regex + a small per-session JSON
    state file). It does NOT ssh into the box itself: a live network round-trip
    inside a PreToolUse hook risks hanging past the hook's timeout budget, and a
    timed-out check is DROPPED SILENTLY by the dispatcher (fail-open) — exactly
    the wrong failure mode for a confidence gate (silently absent right when the
    box is slow/loaded, i.e. right when it matters most). So it is a FORCING
    FUNCTION (make the agent go verify), not a live oracle.
  - The charged+iacscf=2 pattern can only be seen if it is TEXTUALLY present in
    the gated Bash/PowerShell command (e.g. an inline heredoc that both writes
    the .in file and launches jaguar in one command). A `.in` file authored via a
    separate local Write/Edit call, or edited in an earlier turn, is invisible to
    this script (tool_name filter excludes Edit/Write). The companion
    contraindications.json row (advisory-only, via the EXISTING
    contraindication/check.py, whose matcher already includes Edit|Write|Bash|
    PowerShell) is the wider-coverage complement for that gap — see the
    recommended row in this hook's design write-up.
  - Never touches ssh output, credentials, or the box. Read-only w.r.t. the
    pending command; state files store a SHA-1 signature + timestamp only, never
    the raw command text (the "never echo secrets" rule extends to not
    persisting the literal payload either).

FAIL-OPEN (AGENTS.md S6/S9): any exception, malformed stdin, missing state dir,
or disabled sentinel -> exit 0 (allow), for ALL THREE modes, including "block".
The exit-2 return is a single, narrow, un-nested statement on the one confirmed
positive branch (mirrors no-force-push/hook.py) so a crash can never masquerade
as a block.

Opt-out: COMPUTE_CONFIDENCE_GATE=off in env, or a `.disabled` file in this dir.

WIRING (exact — see the accompanying design write-up for full diffs):
  Tier 1 ("inject"): one new object appended to
    C:/Users/Prekzursil/.claude/hooks/_dispatch/manifest.json
    -> events.PreToolUse.checks, e.g.:
      {"name": "compute-confidence-gate", "script":
       "compute-confidence-gate/gate.py", "args": ["inject"], "timeout": 8,
       "matcher": "Bash|PowerShell", "isolate": null, "side_effect":
       "seen-state", "emits": true}
    No settings.json change needed: the existing PreToolUse entry that invokes
    `_dispatch/dispatch.py pretooluse` already matches
    "Task|Bash|PowerShell|Edit|Write|MultiEdit|mcp__basic-memory__.*|
    mcp__schrodinger__glide_dock|mcp__schrodinger__prime_mmgbsa|
    mcp__cheatengine__.*|mcp__frida-mcp__.*" — Bash and PowerShell are already
    in that matcher today.

  Tier 2 ("ask") / Tier 3 ("block"): a NEW standalone group in
    C:/Users/Prekzursil/.claude/settings.json -> hooks.PreToolUse (own matcher
    "Bash|PowerShell", own `command` invoking this file with the trailing "ask"
    or "block" argv), analogous to the existing no-force-push / deny-credential-
    reads standalone entries. Must NOT also be added to manifest.json (the
    dispatcher would silently discard the permissionDecision / exit code —
    exactly the failure mode hooks/_dispatch/test_wiring.py's
    test_incompatible_gates_and_transformers_remain_standalone guards against
    for the pre-existing gates).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"

STATE_DIR = Path(
    os.environ.get("COMPUTE_CONFIDENCE_GATE_DIR", str(Path.home() / ".claude" / "compute-confidence-gate"))
)
TTL_HOURS = float(os.environ.get("COMPUTE_CONFIDENCE_GATE_TTL_HOURS", "12"))

# ---------------------------------------------------------------------------
# Detection: named long-compute engines/binaries + the generic longrun wrapper.
# Tunable — verify/extend against your own box's real invocation strings.
# Grounded against this repo's actual usage (compute/modal_scripts/
# schrodinger_modal.py): "fep_plus -RESTART ... -JOBNAME ... -WAIT",
# "run -FROM psp binding_pose_metadynamics.py <complex> -ligand_asl ... -WAIT",
# "*multisim.log" / "*multisim_checkpoint*", "jaguar-v13.2" (QM custom-charge
# stage). Word-boundary matching deliberately does NOT fire on filenames that
# merely CONTAIN these tokens with a trailing underscore/suffix (e.g.
# fep_sar.py, fep_monitor.ps1, fep_edge_monitor.ps1, glide_dock) — those are
# analysis/monitor scripts, not launches.
# ---------------------------------------------------------------------------
_BINARY_RE = re.compile(
    r"\b(jaguar|desmond|glide|binding_pose_metadynamics(?:\.py)?|multisim)\b"
    r"|\bfep(?:_plus|_absolute|mapper|_analysis)?\b"
    r"|(?:^|[\\/\s\"'])longrun(?:\.ps1|\.sh)?\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# The ONE evidenced, deterministic, a-priori-predictable bad pattern this repo
# has actually hit: a charged QM cluster (molchg != 0) launched at iacscf=2
# wasted ~3.7h before failing exit_3 (SCF non-convergence); iacscf=4 was the
# known fix. Lookaheads so the two keywords can appear in either order /
# anywhere in the command (e.g. an inline heredoc authoring the .in file).
# Keep in sync with contraindication/contraindications.json row PARA-CHARGED-SCF
# (that row is advisory-only via the existing check.py and has WIDER coverage —
# it also matches Edit/Write of the .in file; this regex is narrower: Bash/
# PowerShell command text only, but is the one used for the actual exit-2
# decision in --block mode).
# ---------------------------------------------------------------------------
_CHARGED_SCF_BAD_RE = re.compile(
    r"(?=.*\bmolchg\s*[:=]\s*-?[1-9]\d*\b)(?=.*\biacscf\s*[:=]\s*2\b)",
    re.IGNORECASE | re.DOTALL,
)

_BLOCK_REASON = (
    "[compute-confidence-gate] BLOCKED: this command sets molchg != 0 (charged system) "
    "together with iacscf=2. This exact combination has already been run and failed "
    "non-convergent (exit_3) after ~3.7h of GPU time — it is a KNOWN, a-priori-predictable "
    "failure, not a hypothesis. Use iacscf=4 (or another convergence algorithm suited to "
    "charged clusters) before relaunching. If you believe this match is wrong (e.g. molchg is "
    "intentionally 0 for this specific cluster and the digit matched is unrelated), inspect the "
    "command text and, if genuinely a false positive, rerun after fixing the input or ask the "
    "user to override.\n"
)


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("COMPUTE_CONFIDENCE_GATE", "").strip().lower() in (
        "off",
        "0",
        "false",
    )


def _emit_inject(msg: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )


def _emit_ask(msg: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": msg,
                }
            }
        )
    )


def _checklist(tool_name: str, matched: str) -> str:
    return (
        "**[compute-confidence gate]** Long-compute launch detected "
        f"(`{tool_name}`, matched `{matched}`). Per the standing rule — don't start long "
        "compute without ~100% confidence — fill this pre-flight assumption ledger "
        "(AGENTS.md S1b: rate each item, a LOW/MEDIUM item is a STOP, not a guess) before "
        "this command runs:\n"
        "1. REGISTRY: which /compute-monitor registry id will this land under? If none, say "
        "so explicitly — an untracked job is a monitoring blind spot (precedent: an entire "
        "second program ran on all 4 GPUs at 88% busy, invisible to the monitor).\n"
        "2. LIVE STATE: have you read the box's raw state THIS TURN (log tail, `ls` of the "
        "job/results dirs, GPU busy%) rather than trusting a prior monitor summary or your own "
        "memory of it? A monitor's derived summary ('5/6 done') is not the ground truth — the "
        "raw per-job exit codes are.\n"
        "3. PARAMETERS: state the exact launch parameters (charge, multiplicity, "
        "convergence/algorithm flags, ligand identity, host/subhost, trial count). For a charged "
        "QM cluster, iacscf=2 is the recommended first-line convergence aid; a LARGE salt-bridge "
        "cluster that still oscillates needs iacscf=4 + maxit>=300 (the a-priori-predictable case "
        "— ~3.7h to fail exit_3 if under-provisioned). Keep EVERY leg of an interaction-energy "
        "difference set at the SAME iacscf (2 and 4 give non-comparable energies). Is there another "
        "parameter here with a similarly predictable failure mode you already know about?\n"
        "4. COST OF WRONG: best-guess wall-clock/GPU-hours for this launch, and what a wrong "
        "configuration costs before you would notice.\n"
        "5. SUCCESS CRITERION: the literal log line / exit code you will check to confirm THIS "
        "specific launch (e.g. `DONE_<job>_exit_0`) — not \"the monitor will say done\".\n"
        "6. CONFIDENCE: high / medium / low, honestly. Anything below high — clarify, dry-run, "
        "or re-derive the risky parameter in a fresh check first; do not launch on a guess.\n"
        "(Fires once per distinct launch signature per session — a retry of the exact same "
        "command will not re-nag; a materially different command will.)"
    )


def _sig(tool_name: str, cmd: str) -> str:
    raw = f"{tool_name}\x00{cmd}"
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- non-cryptographic launch-signature fingerprint for session dedup, not a security control
    return hashlib.sha1(raw.encode("utf-8", "replace"), usedforsecurity=False).hexdigest()[:20]


def _state_path(session_id: str) -> Path:
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- non-cryptographic session-id slug for a state-file name, not a security control
    h = hashlib.sha1(str(session_id).encode("utf-8", "replace"), usedforsecurity=False).hexdigest()[:24]
    return STATE_DIR / f"{h}.json"


def _load_seen(session_id: str) -> dict:
    p = _state_path(session_id)
    try:
        if not p.exists():
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        if time.time() - float(data.get("_ts", 0)) > TTL_HOURS * 3600:
            return {}  # stale -> treat every signature as new again
        return data
    except Exception:
        return {}


def _save_seen(session_id: str, seen: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        seen["_ts"] = time.time()
        # NOTE: only the signature hash + timestamp are ever persisted — never the raw
        # command text (never echo secrets, and ssh/launch commands can carry sensitive
        # paths/params even without literal credentials in them).
        _state_path(session_id).write_text(json.dumps(seen), encoding="utf-8")
    except Exception:
        pass


def main(argv=None) -> int:
    argv = list(argv or sys.argv[1:])
    mode = (argv[0].strip().lower() if argv else "inject") or "inject"
    try:
        if _disabled():
            return 0

        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0  # malformed stdin -> fail-open

        tool_name = str(data.get("tool_name") or "")
        if tool_name not in ("Bash", "PowerShell"):
            return 0

        ti = data.get("tool_input") or {}
        cmd = str(ti.get("command") or "")
        if not cmd:
            return 0

        m = _BINARY_RE.search(cmd)
        if not m:
            return 0

        # Tier 3: hard-block ONLY the one evidenced, deterministic bad pattern.
        # This branch runs before the once-per-signature gate below on purpose —
        # a known-bad relaunch must be blocked every single time, never deduped.
        if mode == "block" and _CHARGED_SCF_BAD_RE.search(cmd):
            sys.stderr.write(_BLOCK_REASON)
            sys.stderr.flush()
            return 2

        session_id = str(data.get("session_id") or data.get("cwd") or "default")
        sig = _sig(tool_name, cmd)
        seen = _load_seen(session_id)
        if sig in seen:
            return 0  # already surfaced this exact launch signature this session

        seen[sig] = int(time.time())
        _save_seen(session_id, seen)

        msg = _checklist(tool_name, m.group(0).strip())
        if mode == "ask":
            _emit_ask(msg)
        else:  # "inject" (Tier 1), and the "block" fallthrough (no known-bad match)
            _emit_inject(msg)

    except Exception:
        return 0  # fail-open: never let this gate crash or wedge a tool call
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
