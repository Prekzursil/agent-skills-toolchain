# Frozen snapshot: CLI hooks reference (RES-0009, rebuilt 2026-10-25)

Rebuilt VERBATIM from the closing receipt research/RES-0009.json (cli_events,
exit2_table) after the original snapshot files were lost with the probes dir.
Provenance: the receipt itself; recorded 2026-09-02T00:37:17Z

## Events (31)

- SessionStart
- Setup
- InstructionsLoaded
- UserPromptSubmit
- UserPromptExpansion
- MessageDisplay
- PreToolUse
- PermissionRequest
- PostToolUse
- PostToolUseFailure
- PostToolBatch
- PermissionDenied
- Notification
- SubagentStart
- SubagentStop
- TaskCreated
- TaskCompleted
- Stop
- StopFailure
- TeammateIdle
- ConfigChange
- CwdChanged
- DirectoryAdded
- FileChanged
- WorktreeCreate
- WorktreeRemove
- PreCompact
- PostCompact
- SessionEnd
- Elicitation
- ElicitationResult

## Exit-code semantics (published table rows recorded in the receipt)

- PreToolUse: can_block=True - Blocks the tool call
- PermissionRequest: can_block=False - Exit code 2 isn't honored for this event and the permission flow proceeds unchanged. Deny through the [`decision` object](#permissionrequest-decision-control) instead
- UserPromptSubmit: can_block=True - Blocks prompt processing and erases the prompt
- UserPromptExpansion: can_block=True - Blocks the expansion
- Stop: can_block=True - Prevents Claude from stopping, continues the conversation
- SubagentStop: can_block=True - Prevents the subagent from stopping
- TeammateIdle: can_block=True - Prevents the teammate from going idle, so it continues working
- TaskCreated: can_block=True - Rolls back the task creation
- TaskCompleted: can_block=True - Prevents the task from being marked as completed
- ConfigChange: can_block=True - Blocks the configuration change from taking effect (except `policy_settings`)
- StopFailure: can_block=False - Output and exit code are ignored, except `terminalSequence`
- PostToolUse: can_block=False - Shows stderr to Claude; the tool already ran
- PostToolUseFailure: can_block=False - Shows stderr to Claude; the tool already failed
- PostToolBatch: can_block=True - Stops the agentic loop before the next model call
- PermissionDenied: can_block=False - Exit code and stderr are ignored because the denial already occurred. Use JSON `hookSpecificOutput.retry: true` to tell the model it may retry; Claude Code ignores `retry: true` for [no-verdict denials](#permissiondenied-decision-control)
- Notification: can_block=False - Exit code and stderr are ignored
- SubagentStart: can_block=False - Shows stderr to user only
- SessionStart: can_block=False - Shows stderr to user only
- Setup: can_block=False - Shows stderr to user only
- SessionEnd: can_block=False - Shows stderr to user only
- CwdChanged: can_block=False - Shows stderr to user only
- DirectoryAdded: can_block=False - Stderr goes to the debug log; the directory is already added
- FileChanged: can_block=False - Shows stderr to user only
- PreCompact: can_block=True - Blocks compaction
- PostCompact: can_block=False - Shows stderr to user only
- Elicitation: can_block=True - Denies the elicitation
- ElicitationResult: can_block=True - Blocks the response (action becomes decline)
- WorktreeCreate: can_block=True - Any non-zero exit code causes worktree creation to fail
- WorktreeRemove: can_block=False - Failures are logged in debug mode only
- InstructionsLoaded: can_block=False - Exit code is ignored
- MessageDisplay: can_block=False - The original text is displayed
