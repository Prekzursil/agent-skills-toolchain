{
  "$schema": "command-center/schema/councilspec.v2.schema.json",
  "unit_id": "CNL-0127",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0127",
  "completion_sentinel": "SUCCESS:CNL-0127",
  "title": "Audit, replay, privacy and persistence contract for council transcripts",
  "question": "What may a persisted council transcript contain, what must be redacted before it is written, and what is the executable scan proving no credential or private datum entered a council artifact?",
  "phase": "2C",
  "produced_by": {
    "role": "council-security-and-privacy-designer",
    "execution_substrate": "linux-headless",
    "worktree": "/opt/p2/ast-integrate"
  },
  "emitted_at": "2026-08-25T00:54:08Z",
  "spec_anchors": [
    {
      "claim": "credentials or decrypted secrets enter an artifact bundle",
      "anchor": "_USER-PROMPTS.md:11345",
      "on_this_worktree": false,
      "catalog_citation": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0127].evidence_requirement",
      "local_corroboration": "command-center/adversarial/ADV-0037-credential-diagnosis-path-leak.json spec_anchor=_USER-PROMPTS.md:11345, 11049"
    },
    {
      "claim": "AGENTS.md 9 READ-ONLY credential diagnosis; never print values",
      "anchor": "agent-self/config/AGENTS.md:111-122",
      "on_this_worktree": true,
      "how_honoured": "findings carry class/path/byte_length/sha256 only; probes print token_sha256 never the fixture value"
    }
  ],
  "inputs_absent_on_worktree": [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/OWNER-DECISIONS.md",
    "command-center/design/council/CNL-0011-replay-state-model-what-must-be-serialised-for-determinist.md",
    "command-center/design/council/CNL-0007-anonymity-levels-and-their-effect-on-attribution.md"
  ],
  "answer": "A persisted council transcript may contain round structure, seat_id and role labels, votes, tallies, stopping_rule_id, dissent text, replay seeds, input hashes, and a declared retain_until. It must not contain credentials, API tokens, private keys, decrypted secrets, env-style secret assignments, JSON/camelCase secret-shaped fields, or base64 envelopes that decode to those classes (spec :11345). The executable scan runs on the in-memory transcript BEFORE any write: findings refuse persist of the original bytes. Retention is a declared retain_until/ttl_seconds; undeclared retention refuses persist (no silent forever). Sweep deletes expired payloads and writes a tombstone (id+sha256+deleted_at) with no payload. Replay of an unexpired payload is byte-identical JSON; replay after expiry raises REPLAY_EXPIRED rather than inventing state. Production calendar TTL is owner-gated and is not guessed; fixtures use explicit timestamps.",
  "may_persist": [
    "round structure and seat_id / role labels",
    "votes, tallies, stopping_rule_id, dissent text after secret-scan",
    "replay seeds (sampling, tool-order) \u2014 seeds are not credentials",
    "input hashes, declared retain_until, payload sha256",
    "tombstones after expiry (id + sha256 + deleted_at, no payload)"
  ],
  "must_redact_before_write": [
    "credentials, API tokens, private keys, decrypted secrets (spec :11345)",
    "env-style KEY=value assignments whose key names a secret class",
    "JSON and camelCase secret-shaped keys (apiKey, accessToken, secretKey)",
    "base64 envelopes that decode to a token-shaped or PEM payload",
    "vendor auth material used to recruit a seat \u2014 never a replay seed"
  ],
  "scan": {
    "when": "before persist, on in-memory transcript plus canonical JSON",
    "encodings": [
      "plain-token",
      "env-assignment",
      "json-embedded",
      "camelCase",
      "base64-envelope"
    ],
    "on_hit": "refuse persist of original bytes; do not write payload",
    "finding_fields": [
      "class",
      "path",
      "byte_length",
      "sha256"
    ],
    "never_print_values": true,
    "synthetic_fixture_sha256": "abb6261c094876197bd62ecaa829e63757053e227f3b533d26b3f04088c66760"
  },
  "retention": {
    "declaration_required": true,
    "undeclared_refuses_persist": true,
    "sweep_deletes_payload": true,
    "tombstone_without_payload": true,
    "production_calendar_ttl": "OWNER-GATED-NOT-GUESSED",
    "fixture_proof": "retain_until in the past is deleted; future is kept"
  },
  "replay": {
    "unexpired": "return persisted JSON (canonical)",
    "expired": "raise ReplayUnavailable code=REPLAY_EXPIRED (loud, not empty)",
    "seeds_are_not_credentials": true
  },
  "owner_gate": {
    "required_by_catalog": true,
    "signoff_path": "command-center/OWNER-DECISIONS.md",
    "signoff_present": false,
    "question": "What production calendar TTL applies to council transcripts?",
    "disposition": "NOT-GUESSED. Spec :11345 already forbids secrets in artifacts; this unit implements that mandate and requires a declared retain_until rather than inventing a calendar. Forging OWNER-DECISIONS.md would be authority laundering. Residual is named.",
    "blocks_executable_contract": false
  },
  "tests": [
    {
      "id": "planted-secret-scan",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0127/probe1_planted_secret.py",
      "result": "PASS",
      "both_states": true,
      "summary": "Five encodings of a synthetic token-shaped fixture are caught and persist is refused; a clean transcript persists; disk has zero synthetic bytes on the refuse path."
    },
    {
      "id": "retention-deletes",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0127/probe2_retention.py",
      "result": "PASS",
      "both_states": true,
      "summary": "Declared retain_until in the past is deleted with a tombstone; unexpired payload is kept; undeclared retention refuses persist; replay after expiry is REPLAY_EXPIRED."
    }
  ],
  "negative_controls": [
    {
      "id": "scanner-off-writes-planted",
      "planted_defect": "persist(..., scan_enabled=False) of a planted transcript",
      "detector_fired": true,
      "silent_on_good": true,
      "verbatim": "What the check does on the state it is meant to reject: with scan_enabled=False the persist writes payload bytes containing the synthetic fixture (detected by disk_contains_synthetic_token). With scan_enabled=True the same payload is refused and the store has zero synthetic bytes. That contrast proves the scanner is load-bearing, not decorative."
    },
    {
      "id": "unexpired-not-deleted",
      "planted_defect": "sweep must not delete retain_until > now",
      "detector_fired": true,
      "silent_on_good": true,
      "verbatim": "What the check does on the state it is meant to reject: a payload whose retain_until is already past is deleted and replaced by a tombstone; a sibling whose retain_until is in the future remains and still replays. A sweeper that deleted everything would fail this control."
    }
  ],
  "live_evidence": {
    "clean_scan_findings": 0,
    "clean_persist_ok": true,
    "clean_disk_contains_synthetic": false,
    "clean_replay_council_id": "cnl-0127-clean",
    "planted": [
      {
        "encoding": "plain",
        "finding_count": 2,
        "finding_classes": [
          "openai-style-token"
        ],
        "persist_ok": false,
        "persist_refused": true,
        "persist_reason": "secret-scan-refused-before-persist",
        "disk_contains_synthetic": false,
        "token_sha256": "abb6261c094876197bd62ecaa829e63757053e227f3b533d26b3f04088c66760",
        "value_printed": false
      },
      {
        "encoding": "env",
        "finding_count": 4,
        "finding_classes": [
          "env-assignment",
          "openai-style-token"
        ],
        "persist_ok": false,
        "persist_refused": true,
        "persist_reason": "secret-scan-refused-before-persist",
        "disk_contains_synthetic": false,
        "token_sha256": "abb6261c094876197bd62ecaa829e63757053e227f3b533d26b3f04088c66760",
        "value_printed": false
      },
      {
        "encoding": "json",
        "finding_count": 4,
        "finding_classes": [
          "json-embedded-secret-key",
          "openai-style-token"
        ],
        "persist_ok": false,
        "persist_refused": true,
        "persist_reason": "secret-scan-refused-before-persist",
        "disk_contains_synthetic": false,
        "token_sha256": "abb6261c094876197bd62ecaa829e63757053e227f3b533d26b3f04088c66760",
        "value_printed": false
      },
      {
        "encoding": "camel",
        "finding_count": 6,
        "finding_classes": [
          "camelCase-secret-key",
          "openai-style-token"
        ],
        "persist_ok": false,
        "persist_refused": true,
        "persist_reason": "secret-scan-refused-before-persist",
        "disk_contains_synthetic": false,
        "token_sha256": "abb6261c094876197bd62ecaa829e63757053e227f3b533d26b3f04088c66760",
        "value_printed": false
      },
      {
        "encoding": "b64",
        "finding_count": 4,
        "finding_classes": [
          "base64-envelope",
          "openai-style-token"
        ],
        "persist_ok": false,
        "persist_refused": true,
        "persist_reason": "secret-scan-refused-before-persist",
        "disk_contains_synthetic": false,
        "token_sha256": "abb6261c094876197bd62ecaa829e63757053e227f3b533d26b3f04088c66760",
        "value_printed": false
      }
    ],
    "undeclared_retention_reason": "retention-undeclared",
    "undeclared_retention_refused": true,
    "sweep_deleted": [
      "expired"
    ],
    "sweep_kept": [
      "clean",
      "unexpired"
    ],
    "expired_payload_deleted": true,
    "unexpired_payload_kept": true,
    "tombstone_without_payload": true,
    "replay_after_expiry_code": "REPLAY_EXPIRED",
    "replay_after_expiry_loud": true,
    "negative_control_scanner_off_wrote_planted": true,
    "token_sha256": "abb6261c094876197bd62ecaa829e63757053e227f3b533d26b3f04088c66760",
    "value_printed": false
  },
  "reviewer": {
    "reviewer_id": "CNL-0127-probe1-scanner-off-adversarial",
    "verdict": "PASS",
    "independent": true,
    "method": "probe1 re-runs the scanner-off persist and requires planted bytes on disk; probe2 independently re-runs sweep/replay. Neither probe trusts this document's prose; both execute contract.py."
  },
  "residual_unknowns": [
    {
      "id": "production-ttl-calendar",
      "status": "OWNER-GATED",
      "note": "retain_until must be declared; the calendar is not guessed"
    },
    {
      "id": "cnl-0007-anonymity-overlay",
      "status": "DEPENDENCY-ABSENT",
      "note": "identity display in audit records follows CNL-0007; this unit does not invent named vs blind defaults. Credentials remain forbidden."
    },
    {
      "id": "cnl-0011-seed-set",
      "status": "DEPENDENCY-ABSENT",
      "note": "which seeds are load-bearing is CNL-0011; this unit requires declared seeds to persist and forbids treating credentials as seeds"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0127-audit-replay-privacy-and-persistence-contract-for-council-.md",
      "role": "primary",
      "exists": true
    },
    {
      "path": "command-center/schema/councilspec.v2.schema.json",
      "role": "schema",
      "exists": true
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0127/contract.py",
      "role": "executable-contract",
      "exists": true
    }
  ],
  "evidence": [
    {
      "claim": "spec :11345 forbids credentials in artifact bundles",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0127.evidence_requirement"
    },
    {
      "claim": "planted synthetic token is refused before persist",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0127/contract.py:persist"
    },
    {
      "claim": "declared retention deletes payload and loud-fails replay",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0127/contract.py:sweep"
    },
    {
      "claim": "scanner-off negative control writes planted bytes",
      "verdict": "CONFIRMED",
      "anchor": "live_evidence.negative_control_scanner_off_wrote_planted"
    }
  ]
}
