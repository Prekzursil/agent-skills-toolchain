#!/usr/bin/env python3
"""hardening.py -- D4/D6 owned-hub tool-surface hardening (shadow-default).

Shared by both ``cloud-hub`` and ``social-hub`` (like ``accounts.py``). Two
concerns, one module, stdlib-only and side-effect-free except an optional bounded
shadow log:

* **D6 -- surface enrichment (``enrich_tools``)**: a PURE function that returns a
  NEW, enriched copy of the advertised ``tools/list`` surface. It adds
  ``readOnlyHint``/``destructiveHint``/``idempotentHint`` annotations by lexical
  (token-boundary keyword) classification -- the council anti-overfit bus:
  *lexical only, no trained classifier, no vector store*. It appends schema-derived
  usage **Examples** to the descriptions of confirm-gated and high-arity tools
  (the 72->90% param-accuracy lever), and -- for the hub-native ``*_account_*``
  tools whose schema the hub fully OWNS -- tightens ``additionalProperties:false``
  and attaches an ``outputSchema``. Enrichment is strictly ADDITIVE: it never
  clobbers a hint or schema a backend already declared, so a backend that ships
  better metadata always wins.

* **D4 -- destructive-op confirm gate (``ConfirmGate``)**: an un-bypassable,
  server-side confirmation requirement on the ~30 IRREVERSIBLE first-party tools
  (``modal_sandbox_terminate``, ``ovh_vps_stop``/``reboot``, ``delete-pod``,
  ``dbx_cluster_permanent_delete``, ``dataset_delete``, every ``operations_*``
  delete/purge, ...). It ships **SHADOW by default** per the build charter +
  council C5: it OBSERVES and logs a "would-require-confirm" record to a separate,
  bounded, auto-rotating sink and forwards the call UNCHANGED -- it never blocks
  and never nags. Flip ``HARNESS_HUB_CONFIRM_MODE=enforce`` to make it actually
  require ``confirm``/``_confirm``/``dry_run`` before an irreversible call reaches
  the backend (belt-and-suspenders on top of the native ``destructiveHint`` the
  MCP client already honours). ``off`` disables it entirely.

The two layers are independent: enrichment (declarative metadata; always applied)
is the primary "requiresUserInteraction" delivery -- an honest ``destructiveHint``
lets the MCP CLIENT (Claude Code) prompt the user natively. The confirm gate is
the shadow-first, flip-to-enforce runtime backstop.

Anti-zombie shadow contract (council C5(i)) is recorded in ``SHADOW_CONTRACT`` and
in the shipped ``APPLY.md`` so the gate cannot rot in shadow limbo.
"""

from __future__ import annotations

import copy
import json
import os
import time
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Lexical classification (token-boundary keyword; council "existing bus" only)  #
# --------------------------------------------------------------------------- #
# Matched against tokens after splitting a tool name on ``_`` and ``-``, by
# EQUALITY (plus a small compound set), so substrings never misfire -- e.g.
# ``bm_list_skills`` no longer reads "kill" out of "skills".

_DESTRUCTIVE = frozenset(
    {
        "delete",
        "deletefile",
        "terminate",
        "destroy",
        "purge",
        "teardown",
        "rmdir",
        "rmdirs",
        "rm",
        "wipe",
        "drop",
    }
)
_DISRUPTIVE = frozenset({"stop", "reboot", "restart", "kill", "cancel", "unsend"})
_WRITE = frozenset(
    {
        "send",
        "post",
        "publish",
        "upload",
        "uploadfile",
        "create",
        "reply",
        "comment",
        "react",
        "message",
        "put",
        "write",
        "submit",
        "deploy",
        "copyfile",
        "copyurl",
        "movefile",
        "like",
        "follow",
        "unfollow",
        "block",
        "moderate",
        "forward",
        "add",
    }
)
_READONLY = frozenset(
    {
        "list",
        "get",
        "show",
        "status",
        "info",
        "describe",
        "search",
        "read",
        "ls",
        "current",
        "whoami",
        "cat",
        "stat",
        "detail",
        "details",
        "fetch",
        "catalog",
        "leaderboard",
        "history",
        "tree",
        "output",
        "logs",
        "monitoring",
        "balance",
        "usage",
        "versions",
        "summary",
        "view",
        "find",
        "health",
        "about",
        "providers",
        "paths",
        "pid",
        "download",
        "pull",
        "ips",
        "insights",
        "context",
        "trending",
        "related",
        "recent",
        "liked",
        "saved",
    }
)

# Precedence: DESTRUCTIVE > DISRUPTIVE > READONLY > WRITE > unknown. READONLY
# outranks WRITE so ``get_recent_posts`` / ``fb_page_read_posts`` read as reads,
# while ``fb_page_post`` / ``upload_reel`` stay writes.
_ORDER = (
    ("DESTRUCTIVE", _DESTRUCTIVE),
    ("DISRUPTIVE", _DISRUPTIVE),
    ("READONLY", _READONLY),
    ("WRITE", _WRITE),
)


def _tokens(name: str) -> list[str]:
    return [t for t in name.replace("-", "_").lower().split("_") if t]


def classify(name: str) -> str:
    """Classify a tool by its name tokens (lexical only)."""
    if not isinstance(name, str) or not name:
        return "UNKNOWN"
    toks = set(_tokens(name))
    for label, kws in _ORDER:
        if toks & kws:
            return label
    return "UNKNOWN"


# --------------------------------------------------------------------------- #
# D4 confirm set -- the IRREVERSIBLE first-party tools that require confirmation #
# --------------------------------------------------------------------------- #
# Default-derived from the DESTRUCTIVE classification (so a NEW ``delete-*`` tool
# added to any backend is auto-covered -- drift-resilient), minus low-stakes
# counter resets, plus the spec-named disruptive halts of a running paid resource.
_CONFIRM_EXCLUDE = frozenset({"core_stats_delete", "core_stats_reset"})
_CONFIRM_EXTRA = frozenset({"ovh_vps_stop", "ovh_vps_reboot", "stop-pod"})


def confirm_required(name: str) -> bool:
    """True if a call to ``name`` must be confirmed (D4 gate membership)."""
    if name in _CONFIRM_EXTRA:
        return True
    if name in _CONFIRM_EXCLUDE:
        return False
    return classify(name) == "DESTRUCTIVE"


# --------------------------------------------------------------------------- #
# D6 -- annotations                                                            #
# --------------------------------------------------------------------------- #
def annotations_for(name: str) -> dict:
    """MCP tool ``annotations`` implied by the lexical class (empty if unknown)."""
    c = classify(name)
    if c in ("DESTRUCTIVE", "DISRUPTIVE"):
        return {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False}
    if c == "WRITE":
        return {"readOnlyHint": False, "destructiveHint": False}
    if c == "READONLY":
        return {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
    return {}


# --------------------------------------------------------------------------- #
# D6 -- schema-derived usage examples (param-accuracy lever)                    #
# --------------------------------------------------------------------------- #
# Marquee high-arity workhorses that earn an example even with <2 required args.
_HIGH_ARITY = frozenset(
    {
        "modal_sandbox_exec",
        "modal_sandbox_create",
        "modal_run",
        "modal_deploy",
        "compute_provision",
        "compute_exec",
        "dbx_sql_exec",
        "dbx_run_submit",
        "dbx_exec",
        "ovh_ssh_exec",
        "ovh_api_raw",
        "run_gcloud_command",
        "operations_copyfile",
        "sync_copy",
        "sync_sync",
        # social marquee writes
        "fb_page_post",
        "fb_page_schedule_post",
        "fb_send_message",
        "ig_graph_publish",
        "upload_reel",
        "upload_photo",
        "tiktok_hashtag",
    }
)


def _placeholder(pname: str, pschema: dict):
    """A schema-accurate placeholder value for one property."""
    t = (pschema or {}).get("type")
    if t == "boolean":
        return True
    if t in ("integer", "number"):
        return 1
    if t == "array":
        return []
    if t == "object":
        return {}
    default = (pschema or {}).get("default")
    if isinstance(default, str) and default:
        return default
    return f"<{pname}>"


def _example_for(name: str, tool: dict) -> str | None:
    """A one-line JSON example built from the tool's OWN inputSchema, or None.

    Fires only for tools that materially benefit: confirm-gated (teaches the
    ``confirm`` pattern), curated high-arity workhorses, or any tool with >=2
    required params. The param NAMES come from the schema (never invented), which
    is what actually lifts param accuracy.
    """
    schema = tool.get("inputSchema") or {}
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    required = [r for r in (schema.get("required") or []) if r in props]
    confirm = confirm_required(name)
    curated = name in _HIGH_ARITY
    if not (confirm or curated or len(required) >= 2):
        return None
    keys: list[str] = list(required)
    if curated:
        for k in props:
            if k not in keys:
                keys.append(k)
            if len(keys) >= 5:
                break
    example = {k: _placeholder(k, props.get(k) or {}) for k in keys}
    note = ""
    if confirm:
        if "confirm" in props:
            example["confirm"] = True
        elif "dry_run" in props:
            example.setdefault("dry_run", True)
        else:
            example["_confirm"] = True
        note = "  (DESTRUCTIVE -- set confirm/_confirm=true to proceed)"
    if not example:
        return None  # nothing worth showing (e.g. a curated tool with no schema)
    return json.dumps(example, ensure_ascii=False) + note


# --------------------------------------------------------------------------- #
# D6 -- account-tool schema tightening (hub-OWNED, complete schema)             #
# --------------------------------------------------------------------------- #
_ACCOUNT_OUTPUT_SCHEMA = {
    "type": "object",
    "description": "Account-op result: {ok, ...}. See structuredContent.",
    "additionalProperties": True,
}


def _tighten_account_schema(tool: dict) -> None:
    """In-place (on an already-copied tool): forbid unknown args + add outputSchema.

    Safe because the hub authors the ENTIRE schema for ``*_account_*`` tools, so
    ``additionalProperties:false`` cannot reject a legitimate backend-only param.
    """
    schema = tool.get("inputSchema")
    if isinstance(schema, dict) and schema.get("type") == "object":
        schema.setdefault("additionalProperties", False)
    tool.setdefault("outputSchema", dict(_ACCOUNT_OUTPUT_SCHEMA))


# --------------------------------------------------------------------------- #
# D6 -- public entrypoint                                                       #
# --------------------------------------------------------------------------- #
def _enrich_one(tool: dict) -> dict:
    t = copy.deepcopy(tool)
    name = t.get("name")
    if not isinstance(name, str) or not name:
        return t
    ann = annotations_for(name)
    if ann:
        merged = dict(t.get("annotations") or {})
        for k, v in ann.items():
            merged.setdefault(k, v)  # additive: never clobber a declared hint
        t["annotations"] = merged
    if "_account_" in name:
        _tighten_account_schema(t)
    example = _example_for(name, t)
    if example:
        base = t.get("description") or ""
        if "\nExamples:" not in base:
            t["description"] = base.rstrip() + "\n\nExamples:\n" + example
    return t


def enrich_tools(tools: list[dict]) -> list[dict]:
    """Return a NEW enriched copy of the advertised tool surface (pure)."""
    if not isinstance(tools, list):
        return tools
    return [_enrich_one(t) if isinstance(t, dict) else t for t in tools]


# --------------------------------------------------------------------------- #
# D4 -- the confirm gate (shadow by default)                                    #
# --------------------------------------------------------------------------- #
SHADOW_CONTRACT = {
    "gate": "cloud/social-hub destructive-op confirm gate (D4)",
    "risk_class": "irreversible-resource-destruction (council C5 safety-tier)",
    "default_mode": "shadow",
    "promotion_metric": "false-positive fire rate on non-destructive calls, "
    "measured from the shadow sink vs the owner's --supersedes / "
    "claude-reflect corrections",
    "fire_rate_hypothesis": "destructive calls are <1% of hub traffic; the gate "
    "fires ONLY on genuinely irreversible ops; predict 0 shadow records for any "
    "read-only or plain-write tool",
    "owner": "darias.grama",
    "graduation_deadline_days": 30,
    "at_deadline": "promote to enforce iff 0 false-positives AND owner opts in; "
    "else keep shadow or retire -- never leave in limbo",
}

_MODE_ENV = "HARNESS_HUB_CONFIRM_MODE"
_SINK_ENV = "HARNESS_HUB_SHADOW_SINK"
_VALID_MODES = ("off", "shadow", "enforce")
_SINK_MAX_BYTES = 256 * 1024  # bounded + rotate-once (council C5(iii))
_HUB_CONFIRM_KEY = "_confirm"  # hub-native confirm flag (stripped before forward)


@dataclass(frozen=True)
class Decision:
    """Outcome of a confirm-gate check."""

    blocked: bool
    request: dict  # the (possibly _confirm-stripped) request to forward
    message: str = ""
    shadow_logged: bool = False


def _confirmed(args: dict) -> bool:
    """True if the caller supplied any accepted confirmation token."""
    if not isinstance(args, dict):
        return False
    return bool(
        args.get("confirm") is True
        or args.get(_HUB_CONFIRM_KEY) is True
        or args.get("dry_run") is True
    )


class ConfirmGate:
    """Server-side confirmation requirement for irreversible tools.

    Modes (from ``HARNESS_HUB_CONFIRM_MODE``, default ``shadow``):

    * ``off``     -- no-op; forwards everything, logs nothing.
    * ``shadow``  -- logs a would-require-confirm record to the bounded sink and
      forwards the call UNCHANGED. Never blocks, never nags. (DEFAULT.)
    * ``enforce`` -- if the tool is confirm-gated and no confirmation token was
      supplied, BLOCKS with a clear instruction; otherwise strips the hub-native
      ``_confirm`` flag and forwards.
    """

    def __init__(self, mode: str | None = None, log_dir: str | None = None,
                 sink_path: str | None = None, clock=time.time) -> None:
        env_mode = (mode if mode is not None else os.environ.get(_MODE_ENV) or "shadow")
        self.mode = env_mode.lower() if env_mode.lower() in _VALID_MODES else "shadow"
        if sink_path is not None:
            self.sink_path = sink_path
        else:
            self.sink_path = os.environ.get(_SINK_ENV) or (
                os.path.join(log_dir, "shadow", "confirm-gate.jsonl")
                if log_dir
                else None
            )
        self._clock = clock

    # -- public ----------------------------------------------------------------
    def check(self, original_name: str, request: dict) -> Decision:
        """Evaluate one ``tools/call`` against the gate (fail-open on any error)."""
        try:
            if self.mode == "off" or not confirm_required(original_name):
                return Decision(False, request)
            args = ((request or {}).get("params") or {}).get("arguments") or {}
            if self.mode == "shadow":
                logged = self._log(original_name, args, would_block=not _confirmed(args))
                return Decision(False, request, shadow_logged=logged)
            # enforce
            if _confirmed(args):
                return Decision(False, self._strip_hub_key(request))
            return Decision(
                True,
                request,
                message=(
                    f"[hub-hardening] '{original_name}' is a DESTRUCTIVE, "
                    "irreversible operation. Re-invoke with confirm=true "
                    "(or _confirm=true, or dry_run=true to preview) to proceed."
                ),
            )
        except Exception:  # fail-open: a gate error must never break the hub
            return Decision(False, request)

    # -- internals -------------------------------------------------------------
    @staticmethod
    def _strip_hub_key(request: dict) -> dict:
        """Return a copy with the hub-native ``_confirm`` flag removed.

        ``confirm``/``dry_run`` are BACKEND-native params (e.g. Modal, Databricks)
        and are preserved; only the hub's own ``_confirm`` is stripped so it never
        confuses a backend that does not declare it.
        """
        req = dict(request or {})
        params = dict(req.get("params") or {})
        args = params.get("arguments")
        if isinstance(args, dict) and _HUB_CONFIRM_KEY in args:
            new_args = {k: v for k, v in args.items() if k != _HUB_CONFIRM_KEY}
            params["arguments"] = new_args
            req["params"] = params
        return req

    def _log(self, name: str, args: dict, would_block: bool) -> bool:
        """Append one bounded, VALUE-FREE record to the rotating shadow sink."""
        if not self.sink_path:
            return False
        record = {
            "ts": round(self._clock(), 3),
            "gate": "confirm",
            "tool": name,
            "would_block": bool(would_block),
            "arg_keys": sorted(k for k in args if isinstance(k, str)),
        }
        try:
            os.makedirs(os.path.dirname(self.sink_path), exist_ok=True)
            self._rotate_if_needed()
            with open(self.sink_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            return True
        except OSError:
            return False  # logging must never break a call

    def _rotate_if_needed(self) -> None:
        try:
            if os.path.getsize(self.sink_path) >= _SINK_MAX_BYTES:
                backup = self.sink_path + ".1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.replace(self.sink_path, backup)
        except OSError:
            pass
