# The claim ledger

The input `claim_gate.py` reads. One JSON object; one row per atomic claim.

## Schema

```jsonc
{
  "subject": "what the answer was about (free text)",
  "claims": [
    {
      "id": "C1",                         // required, unique
      "text": "one atomic assertion",     // required, stands alone out of order
      "verdict": "CONFIRMED",             // required: CONFIRMED | REFUTED | UNVERIFIED

      // The probe that PRODUCED the claim. Naming it is what makes step 3
      // checkable at all. Free-form values; only these four keys are compared.
      "source_probe": {"tool": "...", "engine": "...", "shell": "...", "field": "..."},

      // The probe that RE-CHECKED it. Must differ on >=1 of the four axes.
      // `command` may be recorded for the reader; it is NOT a discriminating axis.
      "verify_probe":  {"tool": "...", "engine": "...", "shell": "...", "field": "...",
                        "command": "documentation only"},

      "evidence": ["path/to/file.py:42", "https://example.org/page"],  // CONFIRMED needs >=1
      "scope": "the surface actually measured",   // required if the text asserts an absolute
      "band": "likely",                           // required if the text hedges
      "settling_experiment": "...",               // required when UNVERIFIED
      "revised_text": "..."                       // required when REFUTED, must differ from text
    }
  ]
}
```

Enumerated bands: `almost certain` - `very likely` - `likely` - `roughly even` -
`unlikely` - `very unlikely` - `remote` - `almost certainly not`.

## Worked example - the shape the gate is built to catch

```json
{
  "subject": "dedicated CDP profile probe",
  "claims": [
    {
      "id": "C1",
      "text": "Chrome ignores --remote-debugging-port on the default user-data-dir.",
      "verdict": "CONFIRMED",
      "source_probe": {"tool": "playwright", "shell": "powershell", "field": "connect_result"},
      "verify_probe": {"tool": "curl", "shell": "bash", "field": "http_status",
                       "command": "curl -s 127.0.0.1:9222/json/version"},
      "evidence": ["https://developer.chrome.com/blog/remote-debugging-port"],
      "band": "almost certain"
    },
    {
      "id": "C2",
      "text": "Seeding the profile carries every login across.",
      "verdict": "REFUTED",
      "source_probe": {"tool": "file-copy", "shell": "powershell", "field": "exit_code"},
      "verify_probe": {"tool": "chrome-ui", "shell": "gui", "field": "signed_in_state"},
      "evidence": ["tools/mcp/seed_profile.py:88"],
      "revised_text": "Seeding carries Local State, Preferences and Local Storage; Default/Network/Cookies is locked while Chrome runs, so logins do NOT carry.",
      "scope": "one profile, Chrome running during the copy"
    },
    {
      "id": "C3",
      "text": "The 0.10s connect time holds on any host.",
      "verdict": "UNVERIFIED",
      "source_probe": {"tool": "playwright", "shell": "powershell", "field": "wall_clock"},
      "scope": "one host, one run",
      "band": "roughly even",
      "settling_experiment": "Re-time connect_over_cdp on a second host and compare wall_clock across 10 runs."
    }
  ]
}
```

Read the three rows as the three failure modes the gate exists for:

- **C1** would have been rejected had the verify probe been another Playwright
  connect - same tool, same shell, same field is the same query re-run.
- **C2** is the common case: the code was fine, the sentence was wider than the
  evidence. The repair is `revised_text` plus `scope`, not a deletion.
- **C3** is a residual. It is disclosed, scoped and has a named settling
  experiment, so it is reported and does **not** fail the gate.
