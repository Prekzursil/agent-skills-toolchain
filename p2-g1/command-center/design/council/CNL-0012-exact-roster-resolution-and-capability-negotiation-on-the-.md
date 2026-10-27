{
  "answer": "Exact named seats are REFUSED when unreachable: the resolver emits a LOUD degradation record per unmet seat (action=REFUSE-SEAT) and seats nobody. Silent same-vendor substitution is forbidden and is a detector failure, not a fallback. Live estate on this Linux worktree: anthropic credential ABSENT (unauthenticated GET to api.anthropic.com status=401, TCP443=True); openai credential ABSENT (unauthenticated GET to api.openai.com status=401, TCP443=True); openai-via-codex MCP is NOT mounted (mcp server_names=[]); in-session vendor is cursor model=grok-4.6, not anthropic. Production tools/council/participants/select_explicit.py present=False \u2014 there is no production seating runtime here that could silently swap a model. Catalog-named seats therefore resolve to REFUSED with two LOUD records. SUCCESS:CNL-0012",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0012-exact-roster-resolution-and-capability-negotiation-on-the-.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0012/council-design-note.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "catalog-named-schema-shared-contested"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0012/roster.py",
      "role": "resolver"
    }
  ],
  "catalog_named_transports_today": {
    "anthropic_in_session": false,
    "openai_via_codex_mcp": false
  },
  "cloud_ok": false,
  "completion_sentinel": "SUCCESS:CNL-0012",
  "dependency_cnl_0005": {
    "note": "CNL-0005 is not delivered on this tree. This unit answers reachability for exact vendor+model(+transport) seats without waiting on the nine-dial type note.",
    "output_path": "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md",
    "present": false,
    "reachability_dials_used": [
      "vendor",
      "model",
      "transport"
    ]
  },
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0012/roster.py:11",
      "claim": "Exact unmet seats are refused, not substituted.",
      "kind": "probe-runtime",
      "line": 11,
      "path": "command-center/p2-wave/probes/CNL-0012/roster.py",
      "snippet": "REFUSE_SEAT = \"REFUSE-SEAT\"",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0012/roster.py:184",
      "claim": "Same-vendor model swap is a detector violation even if a record exists.",
      "kind": "probe-runtime",
      "line": 184,
      "path": "command-center/p2-wave/probes/CNL-0012/roster.py",
      "snippet": "violations.append(f\"same-vendor-substitution:{want['id']}\")",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0012/estate.py:142",
      "claim": "Second signal is the mounted-server inventory, independent of env/HTTP.",
      "kind": "live-tree",
      "line": 142,
      "path": "command-center/p2-wave/probes/CNL-0012/estate.py",
      "snippet": "signal\": \"mounted-server-inventory\"",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:34898",
      "claim": "Catalog-named live vendors are anthropic in-session and openai via codex MCP.",
      "kind": "catalog",
      "line": 34898,
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "snippet": "openai via the codex MCP",
      "verdict": "CONFIRMED"
    }
  ],
  "live_estate": {
    "catalog_named_transports": {
      "anthropic_in_session": false,
      "openai_via_codex_mcp": false
    },
    "credential_env_names_present": [
      "CURSOR_API_KEY"
    ],
    "declared_vendors": [
      "anthropic",
      "openai"
    ],
    "mcp_inventory": {
      "codex_mounted": false,
      "config_files": [
        {
          "exists": false,
          "path": "/root/.cursor/mcp.json",
          "server_names": [],
          "size": 0
        },
        {
          "exists": false,
          "path": "/root/.cursor/mcp.json.json",
          "server_names": [],
          "size": 0
        },
        {
          "exists": false,
          "path": "/opt/p2/ast-integrate/.cursor/mcp.json",
          "server_names": [],
          "size": 0
        },
        {
          "exists": false,
          "path": "/opt/p2/ast-integrate/.mcp.json",
          "server_names": [],
          "size": 0
        },
        {
          "exists": false,
          "path": "/root/.claude.json",
          "server_names": [],
          "size": 0
        },
        {
          "exists": false,
          "path": "/root/.claude/settings.json",
          "server_names": [],
          "size": 0
        }
      ],
      "openai_mcp_mounted": false,
      "server_names": [],
      "signal": "mounted-server-inventory"
    },
    "probe": "CNL-0012-live-estate",
    "process_inventory": {
      "codex_process": false,
      "hits": [],
      "mcp_process": false,
      "signal": "process-table-comm-only"
    },
    "production_select_explicit": {
      "path": "tools/council/participants/select_explicit.py",
      "present": false
    },
    "reachable_entries": [
      {
        "model": "grok-4.6",
        "source": "~/.cursor/cli-config.json",
        "transport": "in-session",
        "vendor": "cursor"
      }
    ],
    "session": {
      "auth_fields_read": false,
      "bytes": 1870,
      "display_name": "Cursor Grok 4.6 Extra High",
      "model_id": "grok-4.6",
      "present": true,
      "source": "~/.cursor/cli-config.json",
      "transport": "in-session",
      "vendor": "cursor"
    },
    "signals": [
      "env-credential-presence+http-auth-or-unauth-status",
      "mounted-server-inventory+process-comm"
    ],
    "vendors": {
      "anthropic": {
        "credential": {
          "length": 0,
          "prefix_class": "absent",
          "present": false,
          "ws_only": false
        },
        "credential_env_checked": [
          "ANTHROPIC_API_KEY",
          "ANTHROPIC_AUTH_TOKEN",
          "CLAUDE_API_KEY"
        ],
        "credential_env_hit": null,
        "declared": true,
        "http_authenticated_models": {
          "error": "credential-absent",
          "status": null
        },
        "http_unauthenticated_models": {
          "error": "HTTPError",
          "status": 401
        },
        "network_tcp443": {
          "error": null,
          "ok": true
        },
        "reachable": false,
        "vendor": "anthropic"
      },
      "cursor": {
        "credential": {
          "length": 69,
          "prefix_class": "other",
          "present": true,
          "ws_only": false
        },
        "credential_env_checked": [
          "CURSOR_API_KEY",
          "CURSOR_API_TOKEN"
        ],
        "credential_env_hit": "CURSOR_API_KEY",
        "declared": false,
        "http_authenticated_models": {
          "error": "skipped",
          "status": null
        },
        "http_unauthenticated_models": {
          "error": "no-host",
          "status": null
        },
        "network_tcp443": {
          "error": "no-host",
          "ok": null
        },
        "reachable": true,
        "vendor": "cursor"
      },
      "openai": {
        "credential": {
          "length": 0,
          "prefix_class": "absent",
          "present": false,
          "ws_only": false
        },
        "credential_env_checked": [
          "OPENAI_API_KEY",
          "OPENAI_API_KEY_CODEX",
          "CODEX_API_KEY"
        ],
        "credential_env_hit": null,
        "declared": true,
        "http_authenticated_models": {
          "error": "credential-absent",
          "status": null
        },
        "http_unauthenticated_models": {
          "error": "HTTPError",
          "status": 401
        },
        "network_tcp443": {
          "error": null,
          "ok": true
        },
        "reachable": false,
        "vendor": "openai"
      }
    }
  },
  "live_resolution": {
    "capability_negotiation": {
      "available": [
        {
          "model": "grok-4.6",
          "transport": "in-session",
          "vendor": "cursor"
        }
      ],
      "gaps": [
        {
          "id": "seat.anthropic.opus",
          "model": "claude-opus-4",
          "role": "council-systems-designer",
          "transport": "in-session",
          "vendor": "anthropic"
        },
        {
          "id": "seat.openai.codex",
          "model": "gpt-5-codex",
          "role": "adversarial-reviewer",
          "transport": "mcp:codex",
          "vendor": "openai"
        }
      ],
      "intersection": [],
      "requested": [
        {
          "id": "seat.anthropic.opus",
          "model": "claude-opus-4",
          "role": "council-systems-designer",
          "transport": "in-session",
          "vendor": "anthropic"
        },
        {
          "id": "seat.openai.codex",
          "model": "gpt-5-codex",
          "role": "adversarial-reviewer",
          "transport": "mcp:codex",
          "vendor": "openai"
        }
      ],
      "seated_ids": []
    },
    "decision": "REFUSED",
    "degradations": [
      {
        "action": "REFUSE-SEAT",
        "available_same_vendor": [],
        "class": "LOUD",
        "reason": "in-session-mismatch: session vendor=cursor model=grok-4.6",
        "requested": {
          "id": "seat.anthropic.opus",
          "model": "claude-opus-4",
          "role": "council-systems-designer",
          "transport": "in-session",
          "vendor": "anthropic"
        },
        "seat_id": "seat.anthropic.opus",
        "substituted": false
      },
      {
        "action": "REFUSE-SEAT",
        "available_same_vendor": [],
        "class": "LOUD",
        "reason": "mcp-server-unmounted:codex",
        "requested": {
          "id": "seat.openai.codex",
          "model": "gpt-5-codex",
          "role": "adversarial-reviewer",
          "transport": "mcp:codex",
          "vendor": "openai"
        },
        "seat_id": "seat.openai.codex",
        "substituted": false
      }
    ],
    "roster_mode": "exact",
    "seated": [],
    "silent_substitution": false,
    "would_have_seated": []
  },
  "live_silent_substitution_violations": [],
  "negative_controls": [
    {
      "fires_on_planted_bad": true,
      "id": "silent-same-vendor-substitution",
      "rejects": "a planted result that seats a different same-vendor model with degradations=[]",
      "silent_on_known_good": true,
      "verbatim": "The check rejects a planted silent same-vendor substitution (requested claude-opus-4, seated a sonnet-shaped swap, degradations=[]). It is silent when resolve_exact seats the exact requested vendor+model on the known-good estate."
    },
    {
      "id": "credential-value-leak",
      "rejects": "any serialised measure/probe output containing a live env secret",
      "verbatim": "The leak scanner is proven non-vacuous by detecting a planted synthetic token in a scratch string, then applied to the live measure JSON. A hit names the env var, never the value."
    }
  ],
  "policy": {
    "capability_negotiation": "requested vendor+model+transport intersected with reachable_entries; gaps are unmet exact seats, never filled by a same-vendor neighbour",
    "council_if_any_exact_seat_unmet": "REFUSED",
    "degradation": "LOUD-record-required",
    "exact_roster_unmet_seat": "REFUSE-SEAT",
    "loud_substitution": "forbidden",
    "partial_exact_roster": "forbidden",
    "silent_same_vendor_substitution": "forbidden"
  },
  "question": "When a CouncilSpec names an exact model/vendor seat that is not reachable on this machine, does the runtime substitute, degrade loudly, or refuse - and what does a live probe of the currently mounted vendors (anthropic in-session, openai via the codex MCP) actually report today?",
  "required_fix": null,
  "reviewer": {
    "counterexample": "planted_silent_same_vendor_substitution(spec) is REFUTED by silent_substitution_violations; known-good resolve_exact is silent",
    "independent": true,
    "reviewer_id": "CNL-0012-probe2-silent-substitution-detector",
    "scope_not_agreement": true,
    "verdict": "PASS"
  },
  "schema_note": "Catalog output_schema is command-center/schema/council-design-note.schema.json. On this tree that file was overwritten by CNL-0030 chair/flat fields (declared_metric, size_sweep). This unit does not invent a chair size-sweep and does not rebuild the shared schema. Validation uses the per-unit schema.",
  "sentinel": "SUCCESS:CNL-0012",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0012/probe1_vendor_reachability.py",
      "exit_code": 0,
      "id": "probe1-vendor-reachability",
      "raw_output": "declared=anthropic,openai anthropic_cred=False openai_cred=False anthropic_tcp=True openai_tcp=True anthropic_unauth=401 openai_unauth=401 anthropic_auth_err=credential-absent openai_auth_err=credential-absent mcp_servers=0 codex_mounted=False session_vendor=cursor session_model=grok-4.6 leak_hits=0 signals=env-credential-presence+http-auth-or-unauth-status+mounted-server-inventory+process-comm\nSUCCESS:CNL-0012-probe1 vendor reachability and mounted-server inventory",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0012/probe2_unreachable_seat.py",
      "exit_code": 0,
      "id": "probe2-unreachable-seat",
      "raw_output": "good_decision=SEATED good_violations=0 unreachable_decision=REFUSED loud_records=2 seated_on_unreachable=0 planted_violations=5 both_states_ok=True\nSUCCESS:CNL-0012-probe2 unreachable-seat loud degrade and refuse silent substitution",
      "result": "PASS"
    }
  ],
  "title": "Exact roster resolution and capability negotiation on the live estate",
  "unit_id": "CNL-0012"
}
