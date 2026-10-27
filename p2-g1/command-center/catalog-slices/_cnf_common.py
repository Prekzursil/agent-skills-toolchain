"""Shared presets for the CNF (independent confirmation and reproduction) slice.

Field vocabulary is deliberately VARIED per unit: a field that carries one
distinct value across the whole slice is a global default in disguise, which is
the measured P1 defect on WORK-UNIT-CATALOG.json (9 of 19 contract fields exist
only in a global `defaults` block, overridden by 0 of 103 items).
"""

TOOLS = {
    "ro": ["Read", "Grep", "Glob", "Bash"],
    "rw": ["Read", "Grep", "Glob", "Write", "Edit", "Bash"],
    "net": ["Read", "Grep", "Glob", "Bash", "WebFetch",
            "mcp__search-hub__web_search_exa", "mcp__search-hub__tavily_search"],
    "gh": ["Read", "Grep", "Glob", "Bash", "mcp__github__pull_request_read",
           "mcp__github__list_commits", "mcp__github__get_file_contents"],
    "xv": ["Read", "Grep", "Glob", "Bash", "mcp__codex__codex", "mcp__codex__codex-reply"],
    "rwxv": ["Read", "Grep", "Glob", "Write", "Edit", "Bash", "mcp__codex__codex"],
    "sandbox": ["Read", "Grep", "Glob", "Bash", "mcp__cloud-hub__modal_sandbox_create",
                "mcp__cloud-hub__modal_sandbox_exec", "mcp__cloud-hub__modal_sandbox_read_file",
                "mcp__cloud-hub__modal_sandbox_terminate"],
    "mem": ["Read", "Grep", "Glob", "Bash", "mcp__basic-memory__search_notes",
            "mcp__basic-memory__read_note"],
    "arch": ["Read", "Grep", "Glob", "Bash", "WebFetch", "mcp__search-hub__web_url_read"],
    "min": ["Read", "Bash"],
}

REVIEWERS = {
    "xv": ("one fresh-context adversarial reviewer from the OTHER vendor than this unit's "
           "executor (Claude executor -> Codex reviewer, and the reverse); a same-vendor "
           "reviewer inherits the executor's blind spots and does not satisfy this field"),
    "raw": ("one reviewer who is given ONLY the raw source and the recorded probe output and "
            "must re-derive the verdict BEFORE being shown this unit's conclusion; a reviewer "
            "who reads the conclusion first has been anchored and does not count"),
    "impl": ("the original implementer MUST be served the discrepancy record and may contest it "
             "in writing, but has NO authority to close it; closure requires a second confirmer "
             "who authored neither the implementation nor this confirmation"),
    "two": ("two independent reviewers who do not see each other's verdict until both are filed; "
            "a disagreement escalates to raw-source adjudication, never to a majority vote"),
    "owner": ("owner sign-off required in addition to one cross-vendor reviewer, because this "
              "unit's verdict gates an owner-controlled action"),
    "sec": ("one security reviewer who did not author any of the scanned code, plus a mechanical "
            "re-run of the same scan by CI on the identical commit SHA"),
    "det": ("one reviewer whose only job is to re-run the DETECTOR CONTROL and confirm the probe "
            "fires on the known-broken fixture; a reviewer who only re-reads the result has "
            "verified nothing"),
    "stat": ("one reviewer with the sampling frame and the seed who re-draws the sample and "
             "confirms it is identical; plus one reviewer who re-computes the interval arithmetic"),
}

RETRY = {
    "two_strikes": ("two strikes then pivot (AGENTS.md 4b): after the 2nd failure carrying the same "
                    "error fingerprint, enumerate >=2 mechanically different approaches before any "
                    "3rd attempt; a 3rd identical retry is a unit failure, not a retry"),
    "flake": ("no blind retry. Re-runs are permitted ONLY as flake measurement and EVERY run's "
              "outcome is recorded; a green on run 7 of 7 does not overwrite the 6 reds, it is "
              "reported as 1/7"),
    "env_once": ("one retry only when the failure classifies as environment-transient (429, DNS, "
                 "disk, runner eviction); a logic or evidence failure is never retried, it is filed"),
    "zero": ("zero retries. This unit's first observation IS the verdict; a later run that "
             "disagrees is a DISCREPANCY to record (spec 11039), never an error to retry away"),
    "escalate": ("one retry executed by a confirmer from the other vendor; if the two runs "
                 "disagree, escalate to raw-source adjudication rather than a third run"),
    "resume": ("resumable: on interruption, restart from the last durable checkpoint and record "
               "the resume boundary in the receipt; never restart from zero and silently discard "
               "the partial evidence"),
    "bounded3": ("at most 3 attempts, each with a DIFFERENT substrate or interpreter; the receipt "
                 "must name what changed between attempts or the attempt does not count"),
}

SENT_TMPL = ("SUCCESS:{id} emitted only when the artifact at output_path exists, is non-empty, "
             "parses against output_schema, and {post}. Any other terminal state is "
             "FAILED:{id} <classification> with the diagnostic tail attached.")

FIELDS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
          "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
          "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
          "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
          "failure_classification", "owner_approval_required"]
