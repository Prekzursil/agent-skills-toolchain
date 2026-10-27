# gate-sast fails CLOSED on a transient download — it produced a false verdict once

Recorded 2026-08-12 by the orchestrator, from a firing that has already been re-run away.
Without this note the evidence is gone: a re-run overwrites the job result in place, so the
flake leaves no trace in `gh run list` afterwards.

## What happened

Run `31632302523`, job `gate-sast (opengrep)` @ `86dde6c1`, FAILED with:

    curl: (56) Connection died, tried 5 times before giving up
    ##[error]Process completed with exit code 56.

That is the **install step**, not the scan. The step is:

    curl -fsSL -o /usr/local/bin/opengrep \
      https://github.com/opengrep/opengrep/releases/download/v1.23.0/opengrep_manylinux_x86
    chmod +x /usr/local/bin/opengrep
    opengrep scan --config .quality/opengrep --error ...

`curl -f` exits non-zero, `shell: /usr/bin/bash -e` aborts the step, and the job reports
FAILURE. **opengrep never ran and zero files were scanned.** `gh run rerun --failed` on the
same commit returned `gate-sast (opengrep) success`, unchanged tree.

## Why it is worth fixing rather than shrugging at

The failure is INDISTINGUISHABLE from a real finding at the job level -- both render as
`failure  gate-sast (opengrep)` in `gh run list` and in the PR checks UI. The orchestrator read
that verdict and was one sentence from concluding a just-landed `# nosemgrep` waiver had not
worked, which would have sent someone to rewrite a correct fix. The only tell is 40 lines down
in the log.

This is the documented class: *a tool's install/auth/network failure is a DETECTOR failure,
never a verdict.* A security gate SHOULD fail closed on a missing scanner -- that part is
right, and must not be "fixed" by adding `|| true`. What is wrong is that it fails closed
**silently as a finding** instead of loudly as an infrastructure error.

## Suggested remedy (CIGREEN lane's call, not executed here)

1. Split install from scan into two steps so the log line and the failing step name say which
   one broke. One line of YAML, and it makes the class self-diagnosing forever.
2. Make the install genuinely retrying: `curl --retry 5 --retry-all-errors --retry-delay 3`.
   NOTE -- the current `curl: (56) ... tried 5 times` message comes from curl's own internal
   retry of a *connection reset mid-transfer*; `--retry-all-errors` is what covers that case.
3. Consider pinning by digest and caching the binary (`actions/cache`) so a GitHub releases
   blip cannot red the security gate at all.
4. Do NOT add `continue-on-error` or `|| true`. A gate that cannot run must not report success.

## Detector-control note for whoever verifies the fix

To prove the split actually distinguishes the two states, force it: point the URL at a
nonexistent tag and confirm the failure names the INSTALL step, then restore it and confirm a
seeded finding still fails the SCAN step. A fix that is only ever observed in the healthy state
has not been shown to separate them.
