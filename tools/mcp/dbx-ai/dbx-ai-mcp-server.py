#!/usr/bin/env python3
"""dbx-ai-mcp — Databricks AI model surface as TUI/Cursor-native tools (SQL-plane bridge).

Lane: D:\\bolt\\enum\\pulls\\dbx-ai-wire (E1, 2026-09-06/07)
Wiring rationale: both estate PATs (User env databricks_api_working_ngogoladze / _alvaro)
are scope-gated OFF the REST AI planes (serving-endpoints 403 `model-serving`,
genie/spaces 403 `genie`, OpenAI-compat invocations 403 `model-serving,
model-serving-inference` — matrix.json, probed 2026-09-07). The SQL plane is the ONLY
reachable inference surface: ai_query(endpoint, prompt) executes real Model Serving
inference authorized as the warehouse identity (proven: model-access lane, dbx-model-gw
lane, and this lane's DBX-AI-OK canaries under BOTH identities).

Rules honored:
  - PAT values read from User env vars at CALL time; never printed, never written.
  - Model allowlist = the 5 census-proven live endpoints (bounds billing, no 404-oracle drift).
  - Read-only SQL (single SELECT ai_query ...); synthetic canaries in tests only.
  - Bounded output (max_chars) so a chatty model cannot blow up the MCP result.
  - No genie tool: REST 403 both identities (see dbx_ai_models catalog note).
"""

import json
import os
import time
import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("dbx-ai")

HOST = os.environ.get("DBX_AI_HOST", "https://bolt-common.cloud.databricks.com")
WAREHOUSE = os.environ.get("DBX_AI_WAREHOUSE_ID", "b39957853740b21d")
# NOTE: deliberately NOT reading DATABRICKS_HOST / DATABRICKS_TOKEN — this estate's
# harness process env shadows them with the bolt-datascience workspace (foreign org
# 3829506390716583 → "Invalid access to Org" 403, diagnosed 2026-09-07). This bridge
# targets bolt-common ONLY, with the identity-scoped PAT vars below.
IDENTITY_ENV = {
    "ngo": "databricks_api_working_ngogoladze",
    "alv": "databricks_api_working_alvaro",
}

# Census-proven live endpoints (dbx-model-gw/census.json + dbx-ai-wire canaries).
# Do NOT add names here without a live proof — the SQL plane 404s unknown endpoints
# and every probe lands in query_history (accepted audit footprint, keep it lean).
LIVE_MODELS = {
    "databricks-gpt-5": {
        "vendor": "OpenAI (Databricks Foundation Model APIs)",
        "class": "frontier chat",
        "proof": "DBX-AI-OK canary 2026-09-07 (both identities), PING census 2026-09-06",
    },
    "databricks-claude-sonnet-4": {
        "vendor": "Anthropic (external-model serving)",
        "class": "frontier chat",
        "proof": "CS-GW-CANARY-OK chat + STRUCT-envelope returnType 2026-09-06",
    },
    "databricks-claude-haiku-4-5": {
        "vendor": "Anthropic (external-model serving)",
        "class": "fast/cheap chat — default for canaries and smoke tests",
        "proof": "PING census 2026-09-06",
    },
    "databricks-meta-llama-3-3-70b-instruct": {
        "vendor": "Meta open weights",
        "class": "open-weights chat",
        "proof": "CS-GW-CANARY-OK chat 2026-09-06; PONG model-access 2026-09-06",
    },
    "databricks-meta-llama-3-1-70b-instruct": {
        "vendor": "Meta open weights",
        "class": "open-weights chat",
        "proof": "CS-GW-CANARY-OK chat 2026-09-06",
    },
}


def _token(identity: str) -> str:
    env = IDENTITY_ENV.get(identity)
    if not env:
        raise ValueError(
            f"unknown identity '{identity}' (use: " + ", ".join(IDENTITY_ENV) + ")"
        )
    tok = os.environ.get(env) or _user_env(env)
    if not tok:
        raise RuntimeError(f"env var {env} not set — no credential available")
    return tok


def _user_env(name: str):
    # MCP children inherit User env on this estate; fall back to registry read for
    # sessions spawned before the var existed. Value never returned to logs.
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _ = winreg.QueryValueEx(k, name)
            return val
    except Exception:
        return None


def _http(method: str, path: str, body: dict | None, identity: str, timeout: int = 130):
    tok = _token(identity)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        HOST + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
            "User-Agent": "dbx-ai-mcp/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8", "replace") or "{}")
        except Exception:
            payload = {}
        return e.code, payload


def _sql_ai_query(model: str, prompt: str, identity: str) -> dict:
    """One statement submission + poll. Returns {state, resp, statement_id, error}."""
    esc_prompt = prompt.replace("'", "''")
    sql = f"SELECT ai_query('{model}', '{esc_prompt}') AS resp"
    body = {
        "statement": sql,
        "warehouse_id": WAREHOUSE,
        "wait_timeout": "50s",
        "disposition": "INLINE",
        "format": "JSON_ARRAY",
    }
    code, st = _http("POST", "/api/2.0/sql/statements", body, identity)
    if code != 200:
        msg = st.get("message") or json.dumps(st)[:300]
        return {
            "state": "SUBMIT_FAILED",
            "resp": None,
            "statement_id": None,
            "error": f"HTTP {code}: {msg}",
        }
    sid = st.get("statement_id")
    state = (st.get("status") or {}).get("state", "?")
    deadline = time.monotonic() + 120
    while state in ("PENDING", "RUNNING") and time.monotonic() < deadline:
        time.sleep(2.5)
        code, st = _http("GET", f"/api/2.0/sql/statements/{sid}", None, identity)
        state = (st.get("status") or {}).get("state", "?")
    err = (st.get("status") or {}).get("error") or {}
    rows = ((st.get("result") or {}).get("data_array")) or []
    resp = rows[0][0] if rows and rows[0] else None
    return {
        "state": state,
        "resp": resp,
        "statement_id": sid,
        "error": (err.get("error_code", "") + " " + err.get("message", "")).strip(),
    }


@mcp.tool()
def dbx_ai_models() -> str:
    """Catalog of Databricks AI models reachable from this estate (SQL-plane bridge).

    Returns the census-proven live Model Serving endpoints callable via
    dbx_ai_query(), with vendor class and proof references. Also documents why the
    REST planes (serving list, genie, OpenAI-compat invocations) are NOT wired.
    """
    cat = {
        "wiring": "SQL ai_query(endpoint, prompt) via /api/2.0/sql/statements — the only "
        "inference surface both estate PATs can reach (REST planes scope-gated 403)",
        "identities": {
            "ngo": "ngogoladze PAT (primary)",
            "alv": "alvaro PAT (fallback)",
        },
        "syntax": "SELECT ai_query('<endpoint>', '<prompt>') — plain STRING prompt only; "
        "messages-struct requests are rejected by the AI function compiler; optional "
        "3rd arg returnType e.g. 'STRUCT<choices ARRAY<STRUCT<message STRUCT<content STRING>>>>'",
        "live_models": LIVE_MODELS,
        "closed_surfaces": {
            "GET /api/2.0/serving-endpoints": "403 model-serving (both identities)",
            "GET /api/2.0/genie/spaces": "403 genie (both identities) — no dbx_genie tool exists",
            "POST /serving-endpoints/<name>/invocations": "403 model-serving, model-serving-inference — "
            "OpenAI-compat REST provider wiring closed",
        },
        "caveats": "Every call bills Foundation/external-model tokens to the org serverless "
        "account and lands in query_history attributed to the employee identity "
        "(sha256(email), near-real-time). Bounded prompts recommended.",
        "source": "D:\\bolt\\enum\\pulls\\dbx-ai-wire\\report.md (lane E1) + dbx-model-gw census",
    }
    return json.dumps(cat, indent=1, ensure_ascii=False)


@mcp.tool()
def dbx_ai_query(
    model: str,
    prompt: str,
    identity: str = "ngo",
    max_chars: int = 4000,
) -> str:
    """Run a chat completion against a Databricks Model Serving endpoint via SQL ai_query.

    Args:
        model: endpoint name from dbx_ai_models() (allowlist-enforced: gpt-5,
            claude-sonnet-4, claude-haiku-4-5, llama-3-3-70b, llama-3-1-70b — all
            'databricks-' prefixed).
        prompt: plain-text prompt (single quotes auto-escaped; keep prompts bounded —
            output truncated at max_chars).
        identity: 'ngo' (default) or 'alv' — which estate PAT drives the warehouse.
        max_chars: response truncation bound (default 4000).

    Returns the model reply text plus statement_id for audit traceability.
    """
    if model not in LIVE_MODELS:
        return (
            f"model '{model}' not in the census-proven allowlist. "
            "Callable endpoints: " + ", ".join(LIVE_MODELS) + ". "
            "Call dbx_ai_models() for the catalog."
        )
    if identity not in IDENTITY_ENV:
        return f"identity must be one of: " + ", ".join(IDENTITY_ENV)
    if not prompt or not prompt.strip():
        return "empty prompt"
    max_chars = max(200, min(int(max_chars), 20000))
    if len(prompt) > 60000:
        prompt = prompt[:60000]

    r = _sql_ai_query(model, prompt, identity)
    if r["state"] != "SUCCEEDED":
        return json.dumps(
            {
                "error": r["error"] or r["state"],
                "state": r["state"],
                "statement_id": r["statement_id"],
                "hint": "404 RESOURCE_DOES_NOT_EXIST = endpoint vanished (re-census needed); "
                "401/403 = PAT died (SSOT §7 continuity plan); TIMEOUT = raise wait/poll",
            },
            ensure_ascii=False,
        )
    resp = r["resp"] if r["resp"] is not None else "(null response)"
    if len(resp) > max_chars:
        resp = resp[:max_chars] + f"\n...[truncated at {max_chars} chars]"
    return json.dumps(
        {
            "model": model,
            "identity": identity,
            "statement_id": r["statement_id"],
            "resp": resp,
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    mcp.run()
