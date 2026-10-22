#!/usr/bin/env python3
"""roster.py -- credential-forge capability (2): key-farm roster.

Enumerates HKCU + HKLM environment-variable NAMES only (the proven safe form).
Unifies the estate's naming forms to the ONE canonical form <BASE>__<account>
(references/naming-spec.md) and emits:

  state/roster.json            -- per key: env name, provider, account tag,
                                  status(active|retired|unknown), vault_ref,
                                  vault_sync, last_seen. NAMES ONLY.
  state/rotation-manifest.json -- EXACTLY audit_secret_artifacts.py's schema
                                  (providers[].environmentVariables; verified
                                  at .agents/scripts/audit_secret_artifacts.py:195-198)
                                  -- closes the estate gap that no manifest
                                  covered the secret-ish env names.

Rotation semantics are carried verbatim from searchhub rotation.py:225-294:
402 -> cool until UTC billing reset + rotate-retry-once; 429 -> never cool,
honor Retry-After; ambiguous -> probe usage API; manual switch overrides
cooldown; NEVER flip a global active pointer. Seeding stores ${ENV} REFERENCES,
never the literal secret (rotation.py:252-253), idempotent (:253) -- the same
doctrine as op:// URIs (1password-ops/SKILL.md).

Examples:
  python roster.py sync
  python roster.py sync --dry
  python roster.py status
  python roster.py retire FIRECRAWL_API_KEY_old1 --reason "superseded"
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _common as C  # noqa: E402

ROSTER = C.STATE_DIR / "roster.json"
MANIFEST = C.STATE_DIR / "rotation-manifest.json"
LEDGER = C.STATE_DIR / "ledger.json"

SECRETISH = re.compile(r"(?i)(token|secret|password|passwd|credential|api[_-]?key|apikey|"
                       r"_key$|^key_|_pat$|^pat_|private_key|webhook)")
CANONICAL = re.compile(r"^(?P<base>[A-Z][A-Z0-9_]*?)__(?P<acct>[A-Za-z0-9][A-Za-z0-9_-]*)$")
ALIAS_LOWER = re.compile(r"^(?P<base>[A-Z][A-Z0-9_]*?)_(?P<acct>[a-z][a-z0-9_-]{2,})$")
ALIAS_NUMBER = re.compile(r"^(?P<base>[A-Z][A-Z0-9_]*?)_(?P<n>[2-9][0-9]*)$")
ALIAS_HASH = re.compile(r"^(?P<base>[A-Z][A-Z0-9_]*)_(?P<h>[a-f0-9]{6,})$")
ALIAS_META = re.compile(r"^(?P<base>.+)_META$")
RETIRED = re.compile(r"(?i)(?:_old\d*|_real_not_used|_not_used|_unused|_potential_?[1-9]|_retired)$")

PROVIDER_ALIASES = {
    "gh": "github", "hf": "huggingface", "huggingface": "huggingface",
    "scw": "scaleway", "gcloud": "gcloud", "aws": "aws", "az": "azure",
    "azure": "azure", "openai": "openai", "anthropic": "anthropic",
    "gemini": "gemini", "grok": "grok", "exa": "exa", "tavily": "tavily",
    "firecrawl": "firecrawl", "github": "github", "do": "digitalocean",
    "digitalocean": "digitalocean", "sentry": "sentry",
}

ROTATION_POLICY = {
    "402": "cool key until UTC billing reset + rotate-retry-once",
    "429": "never cool; honor Retry-After",
    "ambiguous": "probe the provider usage API before switching",
    "manual": "manual switch overrides any cooldown",
    "invariant": "never flip a global active pointer",
    "seeding": "accounts store ${ENV} REFERENCES, never the literal secret (idempotent)",
}


def classify(name: str) -> dict:
    base, tag, form = name, None, "flat"
    m = CANONICAL.match(name)
    if m:
        base, tag, form = m.group("base"), m.group("acct"), "canonical"
    else:
        m = ALIAS_NUMBER.match(name)
        if m:
            # naming-spec.md: numbered _2.._N folds to __backupN (offline-VM only)
            base, tag, form = m.group("base"), "backup" + m.group("n"), "numbered-alias(offline-VM only)"
        else:
            m = ALIAS_HASH.match(name)
            if m:
                base, tag, form = m.group("base"), m.group("h"), "hash-alias"
            else:
                m = ALIAS_LOWER.match(name)
                if m and not RETIRED.search(name):
                    base, tag, form = m.group("base"), m.group("acct"), "account-alias"
    status = "retired" if RETIRED.search(name) else ("active" if tag else "unknown")
    head = base.split("_", 1)[0].lower()
    provider = PROVIDER_ALIASES.get(head, head or "misc")
    canonical = "%s__%s" % (base, tag) if tag else None
    password_shaped = bool(re.search(r"(?i)password|passwd", name))
    vault_sync = "candidate-manual" if password_shaped else "blocked"
    return {"env_name": name, "provider": provider, "base": base,
            "account_tag": tag, "canonical_name": canonical, "form": form,
            "status": status, "vault_sync": vault_sync}


def previous() -> dict:
    data = C.load_json(ROSTER, {}) or {}
    data.setdefault("keys", [])
    return data


def merge_keys(current: list[dict], prev_keys: list[dict]) -> list[dict]:
    prev_by_name = {k.get("env_name"): k for k in prev_keys if isinstance(k, dict)}
    for entry in current:
        old = prev_by_name.get(entry["env_name"])
        if old:
            if old.get("status") == "retired" and entry["status"] == "unknown":
                entry["status"] = "retired"
            if old.get("retired_reason"):
                entry["retired_reason"] = old["retired_reason"]
            if old.get("vault_sync") == "synced":
                entry["vault_sync"] = "synced"
    return current


def store_entries_from_ledger() -> list[dict]:
    ledger = C.load_json(LEDGER) or {}
    out = []
    for e in ledger.get("entries", []):
        out.append({"store": e.get("store"), "account": e.get("account"),
                    "kind": e.get("kind"), "expires_at": e.get("expires_at"),
                    "env_name": None, "status": "active"})
    return out


def build_roster() -> dict:
    names, scopes = C.env_names_both_scopes()
    secretish = [n for n in names if SECRETISH.search(n)]
    keys = []
    sidecars = []
    for name in sorted(secretish):
        if ALIAS_META.match(name):
            sidecars.append({"env_name": name, "base": ALIAS_META.match(name).group("base")})
            continue
        entry = classify(name)
        entry["scopes"] = scopes.get(name, [])
        entry["vault_ref"] = None
        keys.append(entry)
    prev = previous()
    keys = merge_keys(keys, prev.get("keys", []))
    return {
        "schema_version": 1,
        "generated_at": C.now_iso(),
        "rotation_policy": ROTATION_POLICY,
        "counts": {"env_names_total": len(names), "secretish": len(keys),
                   "sidecars": len(sidecars), "retired": sum(1 for k in keys if k["status"] == "retired")},
        "keys": keys,
        "sidecars": sidecars,
        "store_entries": store_entries_from_ledger(),
    }


def build_manifest(roster: dict) -> dict:
    providers: dict[str, list[str]] = {}
    for key in roster["keys"]:
        if key["status"] == "retired":
            continue  # retired lanes stay out of the active manifest
        providers.setdefault(key["provider"], []).append(key["env_name"])
    return {"schema_version": 1, "generated_at": roster["generated_at"],
            "providers": [{"name": p, "provider": p, "environmentVariables": sorted(v)}
                          for p, v in sorted(providers.items())]}


def cmd_sync(args) -> int:
    roster = build_roster()
    manifest = build_manifest(roster)
    counts = roster["counts"]
    print("env names scanned (both scopes, NAMES ONLY): %d" % counts["env_names_total"])
    print("secret-ish keys: %d (retired=%d, sidecars=%d)" %
          (counts["secretish"], counts["retired"], counts["sidecars"]))
    sample = [k["env_name"] for k in roster["keys"]][:10]
    print("sample names: %s" % (", ".join(sample) if sample else "-"))
    print("manifest providers: %d, env vars listed: %d" %
          (len(manifest["providers"]), sum(len(p["environmentVariables"]) for p in manifest["providers"])))
    if args.dry:
        print("DRY: roster.json + rotation-manifest.json NOT written")
        return 0
    C.atomic_json_write(ROSTER, roster)
    C.atomic_json_write(MANIFEST, manifest)
    print("wrote: %s" % ROSTER)
    print("wrote: %s" % MANIFEST)
    return 0


def cmd_status(args) -> int:
    roster = C.load_json(ROSTER)
    if not roster:
        print("no roster yet -- run: python roster.py sync")
        return 1
    by_status: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    for key in roster.get("keys", []):
        by_status[key["status"]] = by_status.get(key["status"], 0) + 1
        by_provider[key["provider"]] = by_provider.get(key["provider"], 0) + 1
    print("roster generated_at=%s" % roster.get("generated_at"))
    print("keys by status: %s" % json.dumps(by_status, sort_keys=True))
    print("keys by provider(top): %s" % json.dumps(
        dict(sorted(by_provider.items(), key=lambda kv: -kv[1])[:12]), sort_keys=True))
    print("store_entries: %d (from ledger)" % len(roster.get("store_entries", [])))
    retired_sample = [k["env_name"] for k in roster.get("keys", []) if k["status"] == "retired"][:4]
    print("retired sample: %s" % (", ".join(retired_sample) or "-"))
    return 0


def cmd_retire(args) -> int:
    roster = C.load_json(ROSTER)
    if not roster:
        print("no roster yet -- run: python roster.py sync first")
        return 1
    hit = None
    for key in roster.get("keys", []):
        if key["env_name"] == args.name:
            hit = key
            break
    if hit is None:
        print("FAIL: %r not in roster (names-only roster; run sync first)" % args.name)
        return 2
    if args.dry:
        print("DRY: would mark %s status retired (reason=%r)" % (args.name, args.reason))
        return 0
    if hit["status"] == "retired":
        print("idempotent: %s already retired" % args.name)
        return 0
    hit["status"] = "retired"
    hit["retired_reason"] = args.reason
    C.atomic_json_write(ROSTER, roster)
    manifest = build_manifest(roster)
    C.atomic_json_write(MANIFEST, manifest)
    print("retired: %s (reason=%r); manifest regenerated" % (args.name, args.reason))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="roster.py",
        description="key-farm roster: names-only env scan -> roster.json + rotation-manifest.json",
        epilog="NAMES ONLY are ever read or written. Values are never queried.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_sync = sub.add_parser("sync", help="scan env names (HKCU+HKLM) and write roster + manifest")
    p_sync.add_argument("--dry", action="store_true", help="print the plan, write nothing")
    p_status = sub.add_parser("status", help="summarize the current roster (names/counts only)")
    p_status.add_argument("--dry", action="store_true", help="no-op for symmetry; status never writes")
    p_retire = sub.add_parser("retire", help="mark an env-name lane retired (idempotent)")
    p_retire.add_argument("name", help="exact env var NAME (never a value)")
    p_retire.add_argument("--reason", default="manual retire", help="short reason (names/words only)")
    p_retire.add_argument("--dry", action="store_true", help="print the plan, write nothing")
    args = ap.parse_args(argv)
    if args.cmd == "sync":
        return cmd_sync(args)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "retire":
        return cmd_retire(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
