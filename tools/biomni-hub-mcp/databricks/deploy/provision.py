"""biomni-hub :: one-time Databricks provisioning (Track B, Phase-1).

Idempotently prepares the bolt-datascience workspace so the Databricks adapter
can run. Everything here is CHEAP (no compute): secret scope + key, and the
data-lake directory layout. Run once (re-runnable).

Uses ``databricks-sdk`` with the active ``bolt-ds`` profile
(``DATABRICKS_HOST`` / ``DATABRICKS_TOKEN``). Equivalent cloud-hub dbx_* calls
are noted so it can also be driven from the MCP.

WHAT IT SETS UP  (all verified working in Phase-1)
--------------------------------------------------
  * secret scope ``biomni-hub`` (OWNED by the caller -- the pre-existing
    ``anthropic`` scope is NOT readable by this identity) with key
    ``anthropic_api_key`` = the Claude key Biomni's A1 uses as its LLM.
  * DBFS data-lake layout under ``dbfs:/biomni-hub`` (default DATA_ROOT):
        tasks/      per-task working + result dirs (A1 path=...)
        inputs/     user-uploaded files (upload_file)
        data_lake/  Biomni's ~11GB reference data lake (provisioned LATER,
                    on first real A1 run -- NOT downloaded here)
        hub_meta.json   control-plane store (projects/current_project)

WHY DBFS not a UC Volume by default: SQL-warehouse access is disabled for this
identity (no ``databricks-sql-access`` entitlement), so ``SHOW CATALOGS`` /
Volume DDL via SQL is unavailable. DBFS works today with zero extra entitlement.
If/when a writable UC Volume exists, set BIOMNI_DBX_DATA_ROOT to
``/Volumes/<cat>/<schema>/<vol>`` and use dbx_volume_* instead (the adapter
already speaks both -- it only manipulates paths + the Files/DBFS API).
"""

import os
import sys

SCOPE = os.environ.get("BIOMNI_DBX_SECRET_SCOPE", "biomni-hub")
KEY = os.environ.get("BIOMNI_DBX_SECRET_KEY", "anthropic_api_key")
DATA_ROOT = os.environ.get("BIOMNI_DBX_DATA_ROOT", "dbfs:/biomni-hub")
SUBDIRS = ("tasks", "inputs", "data_lake")


def main() -> int:
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    print(f"[provision] workspace = {w.config.host}")
    print(f"[provision] identity  = {w.current_user.me().user_name}")

    # 1) secret scope (idempotent) -- dbx_secret_scope_create
    scopes = {s.name for s in w.secrets.list_scopes()}
    if SCOPE not in scopes:
        w.secrets.create_scope(SCOPE)
        print(f"[provision] created secret scope {SCOPE!r}")
    else:
        print(f"[provision] secret scope {SCOPE!r} already exists")

    # 2) LLM key -- dbx_secret_put. Only write if caller supplies it; never
    #    overwrite a real key with a placeholder.
    claude_key = os.environ.get("ANTHROPIC_API_KEY")
    if claude_key:
        w.secrets.put_secret(SCOPE, KEY, string_value=claude_key)
        print(f"[provision] stored {SCOPE}/{KEY} (len={len(claude_key)})")
    else:
        print(f"[provision] ANTHROPIC_API_KEY not set; leaving {SCOPE}/{KEY} "
              "as-is. Set it and re-run, or "
              f"`dbx_secret_put scope={SCOPE} key={KEY} string_value=sk-ant-...`")

    # 3) data-lake dirs -- dbx_dbfs_mkdirs
    for sub in SUBDIRS:
        path = f"{DATA_ROOT.rstrip('/')}/{sub}"
        w.dbfs.mkdirs(path)
        print(f"[provision] ensured {path}")

    # 4) seed control-plane store if absent
    import base64
    import json
    meta_path = f"{DATA_ROOT.rstrip('/')}/hub_meta.json"
    try:
        w.dbfs.read(meta_path)
        print(f"[provision] {meta_path} already present")
    except Exception:
        blob = base64.b64encode(
            json.dumps({"projects": {}, "current_project": None}).encode()
        ).decode()
        w.dbfs.put(meta_path, contents=blob, overwrite=True)
        print(f"[provision] seeded {meta_path}")

    print("[provision] DONE. Adapter default DATA_ROOT / secret align with "
          "these values.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
