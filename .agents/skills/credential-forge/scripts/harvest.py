#!/usr/bin/env python3
"""harvest.py -- credential-forge capability (1): store harvester.

Generalizes the proven grok 8-step (estate grokPattern) to any store in
references/store-map.md. Pipeline per store:
  detect (path probe + mtime) -> shape (names/types/lengths, never values)
  -> classify (oauth-pair | api-key | jwt-access | password-shaped)
  -> normalize in memory ({provider, account, kind, access_len, refresh_len,
     expires_at, issuer})
  -> sink (bridge admin import | winreg env-persist | 1P vault write).

TOKEN HYGIINE: every print is a status/count/length/mtime. Values live in
process memory and go straight to the sink's native API. Idempotent: re-run
reveals rather than re-mints (grok precedent).

Examples:
  python harvest.py --list
  python harvest.py --store gemini --dry-shape
  python harvest.py --store gemini --sink env --dry-run
  python harvest.py --store grok  --sink bridge --apply
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sqlite3
import sys
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _common as C  # noqa: E402

DEFAULT_BRIDGE = "http://127.0.0.1:8182"
BRIDGE_CFG = pathlib.Path(r"D:\opt\grok-lane\runtime\config.yaml")

# env-lane bases for the env sink (naming spec: <BASE>__<account>)
PROVIDER_ENV_BASE = {
    "grok": "GROK_OAUTH",
    "gemini": "GEMINI_OAUTH",
    "claude": "CLAUDE_DESIGN_OAUTH",
    "codex": "CODEX_OAUTH",
    "zcode": "ZCODE_CRED",
    "cursor": "CURSOR_DESKTOP",
    "cursor-agent": "CURSOR_AGENT",
    "opencode": "OPENCODE_AUTH",
    "gcloud": "GCLOUD_ADC",
    "aws": "AWS_SSO",
}


def sanitize_tag(text: str) -> str:
    tag = re.sub(r"[^A-Za-z0-9_-]+", "-", (text or "").strip()).strip("-")
    return tag[:32] if tag else "default"


# ---------------------------------------------------------------------------
# parsers -- return (meta_entries, raw_entries); raw values NEVER printed

def _grok_entries(data):
    meta, raw = [], []
    for issuer, d in data.items():
        if not isinstance(d, dict):
            continue
        access = d.get("key") or d.get("access_token") or ""
        refresh = d.get("refresh_token") or ""
        exp = None
        if isinstance(d.get("expires_at"), str):
            iso = C.parse_iso(d["expires_at"])
            exp = iso.astimezone(C._dt.timezone.utc).isoformat(timespec="seconds") if iso else None
        account = d.get("email") or (issuer.rsplit("/", 1)[-1] if isinstance(issuer, str) else "issuer")
        meta.append({"provider": "grok", "account": account,
                     "kind": "oauth-pair" if refresh else "api-key",
                     "access_len": len(access), "refresh_len": len(refresh),
                     "expires_at": exp, "issuer": issuer if isinstance(issuer, str) else None})
        raw.append({"account": account, "access": access, "refresh": refresh,
                    "extra": {k: d.get(k) for k in ("user_id", "team_id", "expires_at", "oidc_client_id")}})
    return meta, raw


def _gemini_entries(data, sibling: pathlib.Path | None):
    access = data.get("access_token") or ""
    refresh = data.get("refresh_token") or ""
    id_token = data.get("id_token") or ""
    exp = C.iso_from_unix_ms(data.get("expiry_date"))
    jwt_exp = C.jwt_exp_iso(id_token) or C.jwt_exp_iso(access)
    account = "default"
    if sibling and sibling.exists():
        try:
            acct = json.loads(sibling.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            acct = None
        if isinstance(acct, dict):
            # google_accounts.json shape: {"active": string, "old": []}
            email = acct.get("email") or acct.get("active") or ""
        elif isinstance(acct, list) and acct and isinstance(acct[0], dict):
            email = acct[0].get("email") or acct[0].get("active") or ""
        else:
            email = ""
        if email:
            account = email.split("@", 1)[0]
    meta = [{"provider": "gemini", "account": account,
             "kind": "oauth-pair" if refresh else "jwt-access",
             "access_len": len(access), "refresh_len": len(refresh),
             "expires_at": exp or jwt_exp,
             "issuer": C.jwt_issuer(id_token) or C.jwt_issuer(access)}]
    raw = [{"account": account, "access": access, "refresh": refresh, "id_token": id_token}]
    return meta, raw


def _generic_entries(provider: str, data):
    meta, raw = [], []
    for trail, d in C.find_token_dicts(data):
        m = C.normalize_token_dict(trail, d)
        m["provider"] = provider
        access = next((d[k] for k in C._ACCESS_KEYS if isinstance(d.get(k), str) and d.get(k)), "")
        refresh = next((d[k] for k in C._REFRESH_KEYS if isinstance(d.get(k), str) and d.get(k)), "")
        raw.append({"account": m["account"], "access": access, "refresh": refresh})
        meta.append(m)
    return meta, raw


def _flat_kv_entries(provider: str, data):
    meta, raw = [], []
    for key, value in data.items():
        if not isinstance(value, str) or not value:
            continue
        exp = C.jwt_exp_iso(value)
        meta.append({"provider": provider, "account": key,
                     "kind": "jwt-access" if exp else "api-key",
                     "access_len": len(value), "refresh_len": 0,
                     "expires_at": exp, "issuer": C.jwt_issuer(value)})
        raw.append({"account": key, "access": value, "refresh": ""})
    return meta, raw


def _aws_sso_entries(paths):
    meta, raw = [], []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        exp = None
        if isinstance(data.get("expiresAt"), str):
            iso = C.parse_iso(data["expiresAt"])
            exp = iso.astimezone(C._dt.timezone.utc).isoformat(timespec="seconds") if iso else None
        tag = "%s/%s" % (data.get("region", "?"), p.name[:4])
        has_token = bool(data.get("accessToken"))
        meta.append({"provider": "aws-sso", "account": tag,
                     "kind": "sso-cache", "access_len": len(data.get("accessToken") or ""),
                     "refresh_len": 0, "expires_at": exp, "issuer": "aws-sso-oidc"})
        raw.append({"account": tag, "access": data.get("accessToken") or "", "refresh": ""})
        if not has_token:
            meta[-1]["access_len"] = 0
    return meta, raw


# ---------------------------------------------------------------------------
# sqlite names-only probe (cursor-desktop / gcloud dbs)

def sqlite_auth_names(path: pathlib.Path, limit: int = 40):
    """Open read-only, list tables, and select ONLY key NAMES that look
    auth-related. Values are never selected."""
    out = {"tables": [], "auth_key_names": []}
    try:
        uri = "file:%s?mode=ro&immutable=1" % str(path).replace("\\", "/").replace("?", "%3f")
        con = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            out["tables"] = tables[:20]
            pattern = re.compile(r"(?i)auth|token|credential|session|login")
            for table in tables:
                try:
                    cols = [r[1] for r in con.execute('PRAGMA table_info("%s")' % table)]
                except sqlite3.Error:
                    continue
                if "key" not in [c.lower() for c in cols]:
                    continue
                try:
                    rows = con.execute('SELECT key FROM "%s" LIMIT 2000' % table)
                    for (key,) in rows:
                        if isinstance(key, str) and pattern.search(key):
                            out["auth_key_names"].append("%s:%s" % (table, key))
                            if len(out["auth_key_names"]) >= limit:
                                return out
                except sqlite3.Error:
                    continue
        finally:
            con.close()
    except sqlite3.Error as exc:
        out["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:100])
    return out


# ---------------------------------------------------------------------------
# gh hosts / yaml names-only

def gh_hosts_flags(path: pathlib.Path):
    hosts, current = {}, None
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^(\S+):", line)
            if m:
                current = m.group(1)
                hosts.setdefault(current, [])
                continue
            if current and re.match(r"^\s+(\w+):", line):
                key = re.match(r"^\s+(\w+):", line).group(1)
                hosts[current].append(key)
    except OSError:
        pass
    return hosts  # host -> field NAMES only (oauth_token presence is a flag)


def yaml_top_names(path: pathlib.Path):
    names = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^([A-Za-z_][\w-]*):", line)
            if m:
                names.append(m.group(1))
    except OSError:
        pass
    return names


# ---------------------------------------------------------------------------
# store iteration

def resolved_paths(store_id: str):
    cfg = C.STORES[store_id]
    paths = []
    if cfg.get("glob"):
        import glob as _glob
        paths.extend(sorted(pathlib.Path(g) for g in _glob.glob(str(cfg["glob"]))))
    paths.extend([p for p in cfg.get("paths", []) if p])
    return cfg, paths


def collect(store_id: str):
    """-> (meta_entries, raw_entries, notes). Raw values stay in memory."""
    cfg, paths = resolved_paths(store_id)
    notes = []
    meta, raw = [], []
    parser = cfg.get("parser", "")
    if parser == "grok-issuer-map" and paths:
        data = json.loads(paths[0].read_text(encoding="utf-8"))
        return (*_grok_entries(data), notes)
    if parser == "gemini-oauth" and paths:
        data = json.loads(paths[0].read_text(encoding="utf-8"))
        return (*_gemini_entries(data, cfg.get("sibling_account_file")), notes)
    if parser == "aws-sso-cache":
        return (*_aws_sso_entries(paths), notes)
    if parser == "gh-hosts":
        for p in paths:
            hosts = gh_hosts_flags(p)
            for host, fields in hosts.items():
                meta.append({"provider": "gh", "account": host, "kind": "env-token",
                             "access_len": 0, "refresh_len": 0, "expires_at": None,
                             "issuer": "github.com"})
                raw.append({"account": host, "access": "", "refresh": ""})
                notes.append("gh host %s fields: %s" % (host, ",".join(fields)))
        return meta, raw, notes
    if parser in ("yaml-names", "json-names"):
        for p in paths:
            if not p.exists():
                continue
            names = yaml_top_names(p) if parser == "yaml-names" else sorted(json.loads(p.read_text(encoding="utf-8")).keys()) if p.suffix == ".json" else []
            notes.append("%s top-level names: %s" % (p.name, ",".join(names[:20])))
            meta.append({"provider": store_id, "account": p.name, "kind": "config-names",
                         "access_len": 0, "refresh_len": 0, "expires_at": None, "issuer": None})
            raw.append({"account": p.name, "access": "", "refresh": ""})
        return meta, raw, notes
    if parser == "flat-kv":
        for p in paths:
            if not p.exists():
                continue
            if p.stat().st_size > C.MAX_PARSE_BYTES:
                notes.append("skip parse (oversize): %s" % p)
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            m, r = _flat_kv_entries(store_id, data)
            meta.extend(m)
            raw.extend(r)
        return meta, raw, notes
    if "sqlite" in parser:
        for p in paths:
            if not p.exists():
                continue
            if p.stat().st_size > C.MAX_PARSE_BYTES:
                notes.append("oversize (>200MB) -- probe only, names probe skipped: %s" % p)
                meta.append({"provider": store_id, "account": p.name, "kind": "sqlite-oversize-probe",
                             "access_len": 0, "refresh_len": 0, "expires_at": None, "issuer": None})
                raw.append({"account": p.name, "access": "", "refresh": ""})
                continue
            probe_res = sqlite_auth_names(p)
            notes.append("sqlite %s tables=%s auth_key_names=%d" %
                         (p.name, ",".join(probe_res["tables"][:6]), len(probe_res["auth_key_names"])))
            for name in probe_res["auth_key_names"][:10]:
                meta.append({"provider": store_id, "account": name, "kind": "sqlite-key-name",
                             "access_len": 0, "refresh_len": 0, "expires_at": None, "issuer": None})
                raw.append({"account": name, "access": "", "refresh": ""})
        for db in cfg.get("dbs", []):
            if db.exists():
                probe_res = sqlite_auth_names(db)
                notes.append("sqlite %s auth_key_names=%d sample=%s" %
                             (db.name, len(probe_res["auth_key_names"]),
                              ";".join(probe_res["auth_key_names"][:5]) or "-"))
        return meta, raw, notes
    # token-dict-walk (+ optional sqlite part)
    for p in paths:
        if not p.exists():
            continue
        if p.stat().st_size > C.MAX_PARSE_BYTES:
            notes.append("skip parse (oversize): %s" % p)
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            notes.append("parse failed %s: %s" % (p.name, type(exc).__name__))
            continue
        m, r = _generic_entries(store_id, data)
        meta.extend(m)
        raw.extend(r)
    for db in cfg.get("dbs", []):
        if db.exists():
            probe_res = sqlite_auth_names(db)
            notes.append("sqlite %s auth_key_names=%d" % (db.name, len(probe_res["auth_key_names"])))
    legacy = cfg.get("legacy_dir")
    if legacy and legacy.exists():
        accounts = sorted(p.name for p in legacy.iterdir() if p.is_dir())
        notes.append("legacy_credentials account dirs: %s" % (", ".join(accounts) or "-"))
    return meta, raw, notes


def load_json_safe(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# sinks

def sink_env(store_id, meta, raw, args):
    base = PROVIDER_ENV_BASE.get(store_id, store_id.upper().replace("-", "_") + "_KEY")
    plans = []
    for entry in raw:
        tag = sanitize_tag(entry["account"])
        if entry.get("access"):
            plans.append(("%s_ACCESS__%s" % (base, tag), entry["access"]))
        if entry.get("refresh"):
            plans.append(("%s_REFRESH__%s" % (base, tag), entry["refresh"]))
    scopes = ["User"] + (["Machine"] if args.machine else [])
    if args.dry_run or not args.apply:
        for name, _value in plans:
            print("env-sink dry-run: would set %s (scope=%s)" % (name, "+".join(scopes)))
        print("env-sink dry-run: %d value(s) held in memory only, nothing written" % len(plans))
        return 0
    written = 0
    for name, value in plans:
        ok = all(C.env_set_value(name, value, machine=m) for m in (False, True) if (m and args.machine) or not m)
        print("env-sink: %s -> %s (%s)" % (name, "set" if ok else "FAILED", "+".join(scopes)))
        written += 1 if ok else 0
    return 0 if written == len(plans) else 1


def bridge_admin_auth(base_url):
    """Admin credentials from env-held names (preferred) or the bridge
    config.yaml bootstrapAdmin block (grok-lane-wire.py:22-25 pattern).
    Values straight to the login POST; only lengths are printed."""
    user = os.environ.get("FORGE_BRIDGE_ADMIN_USER") or ""
    pw = os.environ.get("FORGE_BRIDGE_ADMIN_PASS") or ""
    if not (user and pw) and BRIDGE_CFG.exists():
        src = BRIDGE_CFG.read_text(encoding="utf-8", errors="replace")
        block = re.search(r"bootstrapAdmin:\s*\n((?:\s+\S+.*\n)+)", src)
        if block:
            vals = {}
            for line in block.group(1).splitlines():
                m = re.match(r"\s*([A-Za-z_]+):\s*(\S.*)", line)
                if m:
                    vals[m.group(1)] = m.group(2).strip().strip("'\"")
            user = user or vals.get("username", "")
            pw = pw or vals.get("password", "")
    if not (user and pw):
        print("FAIL: bridge admin credentials not available (env names FORGE_BRIDGE_ADMIN_USER/PASS or %s)" % BRIDGE_CFG)
        return None, None
    body = json.dumps({"username": user, "password": pw}).encode()
    req = urllib.request.Request(base_url + "/api/admin/v1/auth/login", data=body,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, ValueError) as exc:
        print("FAIL: bridge login: %s" % type(exc).__name__)
        return None, None
    tok = (data.get("data", {}).get("tokens", {}) or {}).get("accessToken")
    if not tok:
        return None, None
    print("bridge login OK (admin token len=%d)" % len(tok))
    return tok, {"Authorization": "Bearer " + tok}


def sink_bridge(store_id, meta, raw, args):
    base = args.bridge_url or os.environ.get("FORGE_BRIDGE_URL") or DEFAULT_BRIDGE
    provider_name = {"grok": "grok_build"}.get(store_id, store_id)
    docs = []
    for entry in raw:
        if not (entry.get("access") or entry.get("refresh")):
            continue
        docs.append({"provider": provider_name,
                     "access_token": entry.get("access", ""),
                     "refresh_token": entry.get("refresh", ""),
                     "user_id": (entry.get("extra") or {}).get("user_id", ""),
                     "email": entry.get("account", ""),
                     "team_id": (entry.get("extra") or {}).get("team_id", ""),
                     "expires_at": (entry.get("extra") or {}).get("expires_at", ""),
                     "client_id": (entry.get("extra") or {}).get("oidc_client_id", "")})
    if not docs:
        print("bridge-sink: nothing importable (no access/refresh material) for store=%s" % store_id)
        return 0
    print("bridge-sink: %d single-entry doc(s) built (provider=%s)" % (len(docs), provider_name))
    for i, d in enumerate(docs):
        print("  doc[%d]: access_len=%d refresh_len=%d" % (i, len(d["access_token"]), len(d["refresh_token"])))
    if args.dry_run or not args.apply:
        print("bridge-sink dry-run: would POST multipart to %s/api/admin/v1/accounts/import" % base)
        return 0
    tok, auth = bridge_admin_auth(base)
    if tok is None:
        return 1
    for i, d in enumerate(docs):
        cred = json.dumps(d).encode()
        boundary = uuid.uuid4().hex
        part = (("--%s\r\n" % boundary).encode() +
                b'Content-Disposition: form-data; name="files"; filename="auth.json"\r\n' +
                b"Content-Type: application/json\r\n\r\n" + cred + b"\r\n" +
                ("--%s--\r\n" % boundary).encode())
        req = urllib.request.Request(base + "/api/admin/v1/accounts/import", data=part,
                                     headers={**auth, "Content-Type": "multipart/form-data; boundary=" + boundary,
                                              "Accept": "text/event-stream, application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                print("bridge-sink: doc[%d] import HTTP %d" % (i, resp.status))
        except urllib.error.HTTPError as exc:
            print("FAIL: bridge-sink doc[%d] HTTP %d" % (i, exc.code))
            return 1
        except urllib.error.URLError as exc:
            print("FAIL: bridge-sink doc[%d]: %s" % (i, type(exc).__name__))
            return 1
    return 0


def sink_vault(store_id, meta, raw, args):
    import subprocess
    op = C.find_op()
    if op is None:
        print("vault-sink: op CLI not found on this box -- vault lane degraded "
              "(see 1password-ops; op-personal wrapper cannot be exec'd from python)")
        return 1
    items = []
    for entry in raw:
        if not entry.get("access"):
            continue
        tag = sanitize_tag(entry["account"])
        items.append(("%s__%s" % (PROVIDER_ENV_BASE.get(store_id, store_id.upper()), tag),
                      entry["access"], entry.get("refresh", "")))
    print("vault-sink: %d item(s) prepared" % len(items))
    for name, _a, _r in items:
        print("  candidate item: %s" % name)
    if args.dry_run or not args.apply:
        print("vault-sink dry-run: nothing written; password-shaped vars are never force-migrated (naming-spec.md)")
        return 0
    env = C.op_base_env()
    ok = 0
    for name, access, refresh in items:
        exists = subprocess.run([str(op), "item", "get", name], env=env, capture_output=True, timeout=60).returncode == 0
        cmd = [str(op), "item", "create", "--category=Password", "--title", name]
        if not exists:
            # NOTE (honest limit): the op CLI takes field values via argv; the
            # value is process-visible for the duration of the call on this
            # owner's own box. Documented in references/hygiene.md.
            proc = subprocess.run(cmd + ["password=%s" % access], env=env, capture_output=True, timeout=60)
            print("vault-sink: %s create rc=%d" % (name, proc.returncode))
            ok += 1 if proc.returncode == 0 else 0
        else:
            print("vault-sink: %s already present (idempotent reveal, no re-mint)" % name)
            ok += 1
    return 0 if ok == len(items) else 1


# ---------------------------------------------------------------------------
# commands

def cmd_list(_args):
    print("store-id | status | size | mtime_age_days | refresh_owner | design_status")
    for store_id, cfg in C.STORES.items():
        cfg2, paths = resolved_paths(store_id)
        found = [C.probe(p) for p in paths]
        found = [f for f in found if f]
        if not found:
            print("%s | absent | - | - | %s | %s" % (store_id, cfg.get("refresh_owner"), cfg.get("design_status")))
            continue
        for f in found:
            print("%s | %s | %d | %s | %s | %s" % (store_id, C.mtime_verdict(f), f["size"],
                                                   f["mtime_age_days"], cfg.get("refresh_owner"),
                                                   cfg.get("design_status")))
    return 0


def cmd_store(args):
    if args.store == "all":
        rc = 0
        for store_id in C.STORES:
            print("== store %s" % store_id)
            rc |= _one(store_id, args)
        return rc
    if args.store not in C.STORES:
        print("FAIL: unknown store %r (see --list)" % args.store)
        return 2
    return _one(args.store, args)


def _one(store_id, args):
    cfg, paths = resolved_paths(store_id)
    found = [C.probe(p) for p in paths]
    found = [f for f in found if f]
    if not found:
        print("store %s: absent (design status: %s)" % (store_id, cfg.get("design_status")))
        return 0
    if args.sink == "none":  # --dry-shape
        for f in found:
            print("=== %s (mtime=%s, size=%d, %s)" % (f["path"], f["mtime"], f["size"], C.mtime_verdict(f)))
        if args.store in ("cursor",) or any(f["size"] > C.MAX_PARSE_BYTES for f in found):
            # oversize or sqlite: probe-only shape
            for f in found:
                if f["size"] > C.MAX_PARSE_BYTES:
                    print("shape: <oversize probe-only: %d bytes, names probe skipped by default>" % f["size"])
            try:
                meta, raw, notes = collect(store_id)
            except Exception as exc:  # noqa: BLE001
                print("collect error: %s: %s" % (type(exc).__name__, str(exc)[:120]))
                return 0
            for note in notes:
                print("note: %s" % note)
            for m in meta:
                print(C.entry_line(store_id, m))
            return 0
        try:
            data = load_json_safe(paths[0]) if paths[0].suffix == ".json" else None
        except OSError:
            data = None
        if data is not None:
            print(json.dumps(C.shape(data), indent=1))
        try:
            meta, raw, notes = collect(store_id)
        except Exception as exc:  # noqa: BLE001
            print("collect error: %s: %s" % (type(exc).__name__, str(exc)[:120]))
            return 0
        for note in notes:
            print("note: %s" % note)
        for m in meta:
            print(C.entry_line(store_id, m))
        return 0
    # sink modes parse into memory even if the file is JSON we already shaped
    try:
        meta, raw, notes = collect(store_id)
    except Exception as exc:  # noqa: BLE001
        print("FAIL: %s %s" % (type(exc).__name__, str(exc)[:150]))
        return 1
    for m in meta:
        print(C.entry_line(store_id, m))
    for note in notes:
        print("note: %s" % note)
    if args.sink == "env":
        return sink_env(store_id, meta, raw, args)
    if args.sink == "bridge":
        return sink_bridge(store_id, meta, raw, args)
    if args.sink == "vault":
        return sink_vault(store_id, meta, raw, args)
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="harvest.py",
        description="credential-forge store harvester (values in memory only; prints names/lengths)",
        epilog="Store registry: references/store-map.md. Sinks require --apply for live writes; "
               "--dry-run prints the plan only.",
    )
    ap.add_argument("--list", action="store_true", help="list mapped stores with probe status")
    ap.add_argument("--store", help="store id from store-map (or 'all')")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-shape", dest="sink", action="store_const", const="none",
                      help="shape-dump names/types/lengths + offline expiry decode (default)")
    mode.add_argument("--sink", choices=["env", "bridge", "vault"], help="sink for normalized entries")
    ap.add_argument("--dry-run", action="store_true", help="print the sink plan, write nothing")
    ap.add_argument("--apply", action="store_true", help="REQUIRED for any live sink write")
    ap.add_argument("--machine", action="store_true",
                    help="also persist to Machine scope (reserved for named client keys; GROK_LANE_KEY precedent)")
    ap.add_argument("--bridge-url", help="bridge admin base URL (default %s or FORGE_BRIDGE_URL)" % DEFAULT_BRIDGE)
    ap.add_argument("--dry", action="store_true", help="alias for --dry-run")
    args = ap.parse_args(argv)
    if args.dry:
        args.dry_run = True
    if args.list:
        return cmd_list(args)
    if not args.store:
        ap.print_usage()
        print("FAIL: --store is required (or --list)")
        return 2
    return cmd_store(args)


if __name__ == "__main__":
    raise SystemExit(main())
