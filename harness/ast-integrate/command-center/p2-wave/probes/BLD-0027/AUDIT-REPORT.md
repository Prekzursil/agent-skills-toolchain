# BLD-0027 timeout-and-stillness audit

Instrument reducer: two-signal (CPU delta AND byte growth); mtime never consulted.
Catalog faults: all_pass=True
Planted mtime-only timeout-as-health caught=True
Planted mtime-only 11h-as-stall caught=True
Live required surfaces missing: ['platform/lib/completion_predicate.py', 'rules/common/bash-hud-and-terminal-emit.md']
CodexAdapter timeout state=TIMEOUT
CodexAdapter exit0-missing state=SEVERED
Reviewer: partition kill vs SIGKILL independently both returned SEVERED.
SUCCESS:BLD-0027
