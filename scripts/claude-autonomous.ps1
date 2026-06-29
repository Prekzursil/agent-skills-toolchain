<#
.SYNOPSIS
  Launch Claude Code for long, unattended runs (Ralph loops, autoresearch,
  benchmark sweeps) with automatic model fallback so a single model-availability
  blip does not kill a multi-hour loop.

.DESCRIPTION
  Modus-operandi upgrade item #3 (2026-06-15 research scan).

  --fallback-model is a LAUNCH flag (CC 2.1.166+), not a settings.json key, and
  the ralph-loop plugin replays the prompt IN-SESSION rather than spawning a
  fresh `claude` — so the only place fallback can be set is the command that
  STARTS the autonomous session. Use this wrapper for those sessions.

  Primary model resolves from your settings/session (Opus 4.8). On a primary
  outage mid-loop, CC auto-switches to the fallback (Sonnet 4.6) and keeps going
  at lower capability instead of dying.

.PARAMETER Fallback
  Model id to fall back to. Default: claude-sonnet-4-6.

.EXAMPLE
  ./claude-autonomous.ps1                      # interactive, with fallback armed
  ./claude-autonomous.ps1 -- /ralph-loop ...   # start a Ralph loop with fallback

.NOTES
  Diagnostic sibling: when a misbehavior is ambiguous (model vs your large
  hook+plugin stack), relaunch once with  `claude --safe-mode`  to start with
  ALL customizations disabled (clean room), then re-enable to bisect.
#>
[CmdletBinding()]
param(
  [string]$Fallback = 'claude-sonnet-4-6',
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Rest
)
$ErrorActionPreference = 'Stop'
& claude --fallback-model $Fallback @Rest
