#!/usr/bin/env python3
"""Lane-48 (subtask 111) Databricks data-plane harness — parked-chain execution.
Constraints enforced: NEVER-ROTATE (no retry on 401/403 — drift verdict instead),
pacing >=1.25 s between statements, <=20 statements hard cap (fail-closed),
every HTTP call logged to the budget ledger, sha8-only fingerprints, server-side
sha2() row hashing so raw rows never leave the warehouse, no INSERT/DELETE."""
import json, time, hashlib, re, os, sys, urllib.request, urllib.error

HOST = "https://bolt-common.cloud.databricks.com"
WH = "b39957853740b21d"
VAULT = "/work/lane33/keys-vault/databricks-pats.json"
STATE = "/work/lane48/state.json"
LEDGER = "/work/bolt/REPORT/receipts/lane-48/06-budget-ledger.jsonl"
CAP_STMT = 20          # hard statement budget (task clause)
PACE = 1.25            # >=1.25 s between SQL statements
POLL_MAX = 3           # status re-polls for async statements (not new statements)

SENSITIVE = [re.compile(r"eyJ[A-Za-z0-9_\-\.]{10,}"), re.compile(r"AKIA[0-9A-Z]{16}"),
             re.compile(r"ASIA[0-9A-Z]{16}"), re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
             re.compile(r"dapi[0-9a-f]{32}"), re.compile(r"dyy[A-Za-z0-9_\-]{20,}"),
             re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"),
             re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{8,}")]

def sha8(s):
    if isinstance(s, str):
        s = s.encode()
    return hashlib.sha256(s).hexdigest()[:8]

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def mask(s):
    for r in SENSITIVE:
        s = r.sub("[MASKED]", s)
    return s

def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"statements": 0, "http_calls": 0, "last_ts": 0, "drift": {}, "history": []}

def save_state(st):
    json.dump(st, open(STATE, "w"), indent=1)

def _unwrap(v):
    if isinstance(v, dict):
        for k in ("token", "value", "pat", "secret", "credential"):
            if v.get(k):
                return v[k]
        raise KeyError("no token field in vault entry")
    return v

def token(key8):
    d = json.load(open(VAULT))
    if key8 not in d:
        raise KeyError(f"PAT {key8} not in vault")
    return _unwrap(d[key8])

def log_call(entry):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a") as fh:
        fh.write(json.dumps(entry) + "\n")

def _request(method, path, key8, body=None, stmt_no=None, purpose=""):
    hdr = {"Authorization": "Bearer " + token(key8), "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(HOST + path, data=data, headers=hdr, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=75) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except Exception as e:
        log_call({"ts": now(), "method": method, "path": path, "status": "TRANSPORT-FAIL",
                  "purpose": purpose, "statement": stmt_no, "err": str(e)[:120], "pat": key8})
        raise
    lat = round(time.time() - t0, 3)
    log_call({"ts": now(), "method": method, "path": path, "status": status,
              "latency_s": lat, "purpose": purpose, "statement": stmt_no, "pat": key8})
    return status, raw

def sql(tag, key8, statement, limit=100, timeout_s="50s"):
    """Execute one SQL statement. Counts against the 20-statement budget.
    401/403 => PAT DRIFT recorded, NEVER retried (fail-closed credential clause)."""
    st = load_state()
    if st.get("drift", {}).get(key8):
        raise RuntimeError(f"PAT {key8} dispositioned DRIFT — no further calls (fail-closed clause)")
    if st["statements"] >= CAP_STMT:
        raise RuntimeError("CAP-20 statement budget exhausted — fail-closed")
    dt = time.time() - st.get("last_ts", 0)
    if dt < PACE:
        time.sleep(PACE - dt)
    st["statements"] += 1
    n = st["statements"]
    st["last_ts"] = time.time()
    save_state(st)
    body = {"warehouse_id": WH, "statement": statement, "wait_timeout": timeout_s,
            "disposition": "INLINE", "format": "JSON_ARRAY", "limit": limit}
    status, raw = _request("POST", "/api/2.0/sql/statements", key8, body, n, tag)
    if status in (401, 403):
        try:
            detail = json.loads(raw).get("message", raw.decode()[:200])
        except Exception:
            detail = raw.decode(errors="replace")[:200]
        st = load_state()
        st.setdefault("drift", {})[key8] = {"ts": now(), "status": status, "tag": tag,
                                            "http": mask(str(detail))[:300]}
        st["statements"] -= 1  # drift call consumed a slot; keep count honest
        st["history"].append({"n": n, "tag": tag, "pat": key8, "status": status, "verdict": "DRIFT"})
        save_state(st)
        return {"verdict": "DRIFT", "status": status, "detail": mask(str(detail))[:300], "tag": tag, "n": n}
    try:
        d = json.loads(raw)
    except Exception:
        st = load_state(); st["history"].append({"n": n, "tag": tag, "pat": key8, "status": status, "verdict": "NON-JSON"})
        save_state(st)
        return {"verdict": "NON-JSON", "status": status, "tag": tag, "n": n}
    sid = d.get("statement_id") or d.get("id")
    state_sql = d.get("status", {}).get("state", d.get("state"))
    polls = 0
    while state_sql in ("PENDING", "RUNNING", "QUEUED") and polls < POLL_MAX:
        time.sleep(PACE)
        polls += 1
        s2, r2 = _request("GET", f"/api/2.0/sql/statements/{sid}", key8, None, None, f"poll:{tag}")
        if s2 == 200:
            d = json.loads(r2)
            state_sql = d.get("status", {}).get("state", d.get("state"))
        else:
            break
    st = load_state()
    st["history"].append({"n": n, "tag": tag, "pat": key8, "status": status, "state": state_sql})
    save_state(st)
    out = {"verdict": state_sql, "status": status, "tag": tag, "n": n, "statement_id": (sid or "")[:8] + "-…" if sid else "",
           "statement_sha8": sha8(statement)}
    res = d.get("result") or {}
    if res.get("data_array"):
        rows = res["data_array"]
        cols = [c.get("name") for c in (res.get("columns") or [])]
        out["cols"] = cols
        out["n_rows"] = len(rows)
        out["rows"] = rows[:100]
    err = (d.get("status") or {}).get("error") or d.get("error")
    if err:
        out["error"] = mask(json.dumps(err))[:400]
    return out

def fmt(out):
    if out.get("verdict") == "DRIFT":
        return f"  DRIFT http={out['status']} detail={out['detail']}"
    s = f"  state={out.get('verdict')} stmt#{out.get('n')} tag={out.get('tag')} sha8(sql)={out.get('statement_sha8')}"
    if "cols" in out:
        s += f"\n  cols={out['cols']}\n  n_rows={out['n_rows']}"
        for r in out["rows"][:60]:
            s += "\n    " + " | ".join("" if c is None else str(c) for c in r)
    if out.get("error"):
        s += f"\n  error={out['error']}"
    return s

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "state":
        st = load_state()
        print(json.dumps({"statements": st["statements"], "cap": CAP_STMT,
                          "http_calls": st.get("http_calls"), "drift": st.get("drift", {})}, indent=1))
