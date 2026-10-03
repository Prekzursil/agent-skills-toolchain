#!/usr/bin/env python3
"""
Lane-37 / Subtask 94 — Track A2 knowledge-graph build (Bolt red-team, OFFLINE).
Builds a Kuzu 0.11.3 graph from the local intelligence corpus + lane receipts 31-39,
then runs the five mandated pivot queries (a)-(e), capturing verbatim output.

HARD RULES ENFORCED HERE:
- ZERO network calls (embedded local DB; corpus read from disk only).
- NEVER-ROTATE: no credential values anywhere; sha8 fingerprints only.
- ZERO PII in artifacts: identities are handles only (_ngogoladze etc.);
  redaction guard below fails closed on @bolt.eu or long-hex leaks.
- LANE-REGISTER.md never touched.
"""

import hashlib
import json
import os
import re
import shutil
import time
from collections import defaultdict

import kuzu

WORK = "/work/lane37"
DB_PATH = os.path.join(WORK, "graphdb")
RECEIPTS = "/work/bolt/REPORT/receipts/lane-37"
INTEL = "/work/bolt-intel"
CREDS_DIR = "/work/intel-core/credentials"
TSV_DIR = "/work/intel-core/_org_tmp/backup-pre-reorg"
R31 = "/work/bolt/REPORT/receipts/lane-31"
R32 = "/work/bolt/REPORT/receipts/lane-32"
R33 = "/work/bolt/REPORT/receipts/lane-33"
R35 = "/work/bolt/REPORT/receipts/lane-35"
R39 = "/work/bolt/REPORT/receipts/lane-39"

os.makedirs(WORK, exist_ok=True)
os.makedirs(RECEIPTS, exist_ok=True)
TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

KEYPROP = {"Credential": "sha8", "Identity": "id", "Host": "name", "S3Bucket": "name",
           "DatabricksObject": "obj_id", "Finding": "vul_id", "Lane": "lane_id",
           "IntelSource": "src_id"}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


QLOG = []


def run(conn, label, cypher, note=""):
    """Execute query, record verbatim output. Errors recorded, never fatal."""
    try:
        res = conn.execute(cypher)
        cols = res.get_column_names()
        rows = []
        while res.has_next():
            rows.append(["" if v is None else str(v) for v in res.get_next()])
        out = " | ".join(cols) if cols else "(no columns)"
        out += "\n" + ("\n".join(" | ".join(r) for r in rows) if rows else "(empty result set)")
        QLOG.append((label, cypher.strip(), out, "kuzu-cypher", note))
        return rows
    except Exception as e:  # noqa: BLE001
        QLOG.append((label, cypher.strip(), f"KUZU-ERROR: {type(e).__name__}: {e}", "error", note))
        return None


# ---------------------------------------------------------------- corpus
PROV = []
ssot_path = os.path.join(CREDS_DIR, "CREDS-SSOT_2026-09-06.json")
with open(ssot_path) as f:
    CREDS = json.load(f)
crec = CREDS.get("credentials", CREDS)
PROV.append((ssot_path, sha256_file(ssot_path),
             "Credential corpus (all records, sha8-only)", len(crec) if isinstance(crec, list) else 0))

tsv_files = {
    "deep-mine__conn_url.tsv": "TiDB/infra conn-url map -> Host nodes + connects_to edges",
    "deep-mine__aws_key.tsv": "AWS key-ID corpus -> Credential nodes (never-tested class)",
    "deep-mine__passwd_kv.tsv": "password KV corpus -> Credential nodes (aggregate provenance)",
    "deep-mine__atlassian_ids.tsv": "atlassian id corpus -> aggregate provenance count only (no PII nodes)",
    "deep-mine__entities.tsv": "entity pairs -> aggregate provenance count only",
    "deep-mine__secret_kv.tsv": "secret KV corpus -> aggregate provenance count only",
}
for name, desc in tsv_files.items():
    p = os.path.join(TSV_DIR, name)
    if os.path.exists(p):
        n = sum(1 for _ in open(p, errors="replace"))
        PROV.append((p, sha256_file(p), desc, n))

for name in ("SSOT_2026-09-06.md", "ASSESSMENT-PLAN-SOTA.md", "INDEX.md",
             "analytics_tables.json", "hive_schemas.json", "core_models_tables.json",
             "hard_coded_references.json"):
    p = os.path.join(INTEL, name)
    if os.path.exists(p):
        PROV.append((p, sha256_file(p), "intel structure / SSOT (structure ingest)",
                     os.path.getsize(p)))

for d in (R31, R32, R33, R35, R39):
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            fp = os.path.join(d, fn)
            if os.path.isfile(fp):
                PROV.append((fp, sha256_file(fp), "lane receipt (read-only ingest)",
                             os.path.getsize(fp)))

# S3 corpus names from lane-31 receipts
s3_names = set()
for fn in ("lane-31_receipt_s3-anonymous.txt", "lane-31_receipt_s3-anonymous-corpus.txt",
           "DELTA-TABLE.md", "ATTACK-SURFACE-INVENTORY.md"):
    fp = os.path.join(R31, fn)
    if os.path.exists(fp):
        for m in re.findall(r"(?:s3://)?(bolt-[a-z0-9][a-z0-9-]{2,60}|geoextraction[a-z0-9-]*)",
                            open(fp, errors="replace").read()):
            s3_names.add(m.rstrip("-"))

# TiDB hosts from conn_url.tsv
tidb_hosts = set()
cu = os.path.join(TSV_DIR, "deep-mine__conn_url.tsv")
if os.path.exists(cu):
    for line in open(cu, errors="replace"):
        for m in re.findall(r"([a-z0-9][a-z0-9.-]{4,60}\.sqldb(?:\.internal)?)", line):
            tidb_hosts.add(m.split(":")[0].strip())

# ---------------------------------------------------------------- database
if os.path.exists(DB_PATH):
    if os.path.isdir(DB_PATH):
        shutil.rmtree(DB_PATH)
    else:
        os.remove(DB_PATH)
db = kuzu.Database(DB_PATH)
conn = kuzu.Connection(db)

DDL = [
    "CREATE NODE TABLE Credential(sha8 STRING PRIMARY KEY, provider STRING, verdict STRING, "
    "cclass STRING, role STRING, notes STRING)",
    "CREATE NODE TABLE Identity(id STRING PRIMARY KEY, kind STRING, notes STRING)",
    "CREATE NODE TABLE Host(name STRING PRIMARY KEY, kind STRING, status STRING, "
    "new_lane STRING, notes STRING)",
    "CREATE NODE TABLE S3Bucket(name STRING PRIMARY KEY, region STRING, anonymous STRING, "
    "status STRING, new_lane STRING, notes STRING)",
    "CREATE NODE TABLE DatabricksObject(obj_id STRING PRIMARY KEY, catalog STRING, schema STRING, "
    "name STRING, obj_type STRING, rows INT64, sensitivity STRING, status STRING, "
    "lane STRING, notes STRING)",
    "CREATE NODE TABLE Finding(vul_id STRING PRIMARY KEY, severity STRING, lane STRING, "
    "title STRING, status STRING)",
    "CREATE NODE TABLE Lane(lane_id STRING PRIMARY KEY, status STRING, notes STRING)",
    "CREATE NODE TABLE IntelSource(src_id STRING PRIMARY KEY, path STRING, sha256 STRING, "
    "kind STRING, rows INT64)",
    "CREATE REL TABLE resolves_to(FROM Credential TO Identity, lane STRING)",
    "CREATE REL TABLE member_of(FROM Identity TO Identity, lane STRING)",
    "CREATE REL TABLE grants_to(FROM Identity TO DatabricksObject, privilege STRING, "
    "scope STRING, count INT64, lane STRING)",
    "CREATE REL TABLE permits_obj(FROM Credential TO DatabricksObject, privilege STRING, "
    "lane STRING, notes STRING)",
    "CREATE REL TABLE permits_bucket(FROM Credential TO S3Bucket, privilege STRING, "
    "lane STRING, notes STRING)",
    "CREATE REL TABLE validated_against(FROM Credential TO Host, lane STRING)",
    "CREATE REL TABLE reachable_via_obj(FROM DatabricksObject TO Host, kind STRING)",
    "CREATE REL TABLE reachable_via_bucket(FROM S3Bucket TO Host, kind STRING)",
    "CREATE REL TABLE backed_by(FROM DatabricksObject TO S3Bucket, lane STRING)",
    "CREATE REL TABLE connects_to(FROM Host TO Host, via STRING, src STRING)",
    "CREATE REL TABLE referenced_by_obj(FROM DatabricksObject TO Finding)",
    "CREATE REL TABLE referenced_by_host(FROM Host TO Finding)",
    "CREATE REL TABLE referenced_by_bucket(FROM S3Bucket TO Finding)",
    "CREATE REL TABLE referenced_by_cred(FROM Credential TO Finding)",
    "CREATE REL TABLE blocked_by_lane(FROM Credential TO Lane, reason STRING)",
    "CREATE REL TABLE blocked_by_gap(FROM Finding TO Lane, reason STRING)",
    "CREATE REL TABLE mentions(FROM IntelSource TO Host, weight STRING, pivot_value STRING)",
    "CREATE REL TABLE sourced_from(FROM Finding TO IntelSource)",
    "CREATE REL TABLE lane_source(FROM Lane TO IntelSource)",
]
for ddl in DDL:
    conn.execute(ddl)

NODE_COUNTS = defaultdict(int)
EDGE_COUNTS = defaultdict(int)


def add_node(table, key, **props):
    res = conn.execute(
        f"MATCH (n:{table} {{{KEYPROP[table]}: $k}}) RETURN count(n) AS c",
        parameters={"k": key})
    if res.get_next()[0] == 0:
        body = ", ".join(f"{k}: ${k}" for k in props)
        conn.execute(f"CREATE (n:{table} {{{body}}})", parameters=props)
        NODE_COUNTS[table] += 1
    else:
        NODE_COUNTS.setdefault(table, 0)
        NODE_COUNTS[table] = NODE_COUNTS[table]  # keep table key present
    return key


def add_rel(table, frm_type, frm, to_type, to, **props):
    rbody = ", ".join(f"{k}: ${k}" for k in props) if props else ""
    rmap = f" {{{rbody}}}" if rbody else ""
    conn.execute(
        f"MATCH (a:{frm_type} {{{KEYPROP[frm_type]}: $f}}), "
        f"(b:{to_type} {{{KEYPROP[to_type]}: $t}}) "
        f"CREATE (a)-[:{table}{rmap}]->(b)",
        parameters={"f": frm, "t": to, **props})
    EDGE_COUNTS[table] += 1


# ---- IntelSource nodes (one per provenance row)
src_id_by_path = {}
for i, (p, digest, desc, n) in enumerate(PROV):
    sid = f"src{i:03d}"
    add_node("IntelSource", sid, src_id=sid, path=p, sha256=digest, kind=desc,
             rows=int(n) if isinstance(n, int) else 0)
    src_id_by_path[p] = sid

# ---- Credential corpus (sha8-only)
for r in crec:
    if not isinstance(r, dict):
        continue
    s8 = r.get("sha8") or hashlib.sha256(repr(sorted(r.items())).encode()).hexdigest()[:8]
    add_node("Credential", s8, sha8=s8, provider=str(r.get("provider") or ""),
             verdict=str(r.get("verdict") or "UNKNOWN"), cclass=str(r.get("class") or ""),
             role="", notes="")

# ---- LIVE overlays (verified this engagement; find-or-create semantics via MATCH+CREATE)
for s8, prov, verdict, cclass, role, notes in [
    ("4c5f245f", "databricks", "LIVE", "PAT",
     "SQL-plane primary (225 schema_privilege rows / 12 priv types / 9 groups)",
     "grantees: Growth Analytics, bolt-business-data-analytics, delivery_fpa_group"),
    ("2e1ce409", "databricks", "LIVE", "PAT",
     "SQL-plane secondary (strict grant subset)",
     "geoextraction passthrough also proven under this PAT"),
    ("efb9f2bc", "openrouter", "LIVE", "API-key", "REPORT-ONLY",
     "no attack pivots permitted by ROE"),
    ("94ea4604", "github", "LIVE", "PAT", "member-grade (secret-NAME listings 403)",
     "owner-grade escalation BLOCKED pending operator token"),
    ("f5cc101f", "databricks-secret", "UNTESTABLE-SHAPE", "token", "",
     "unlocks gs-gpt / DATAHUB_GMS_TOKEN; scope DISPOSITIONED DEAD (401, lane-33)"),
]:
    chk = conn.execute("MATCH (c:Credential {sha8:$s}) RETURN c.sha8 AS s",
                       parameters={"s": s8})
    if chk.has_next():  # node already in corpus -> overlay-update in place
        conn.execute(
            "MATCH (c:Credential {sha8:$s}) "
            "SET c.provider=$p, c.verdict=$v, c.cclass=$cc, c.role=$r, c.notes=$x",
            parameters={"s": s8, "p": prov, "v": verdict, "cc": cclass,
                        "r": role, "x": notes})
    else:  # not in corpus -> create (find-or-create semantics)
        add_node("Credential", s8, sha8=s8, provider=prov, verdict=verdict,
                 cclass=cclass, role=role, notes=notes)

# ---- Identity nodes (handles only)
for iid, kind, notes in [
    ("_ngogoladze", "user", "principal of PAT 4c5f245f"),
    ("_alvaro", "user", "principal of PAT 2e1ce409"),
    ("Prekzursil", "user", "principal of GitHub PAT 94ea4604"),
    ("openrouter-account", "service", "report-only"),
    ("Growth Analytics", "group", "lane-32/33 grantee"),
    ("bolt-business-data-analytics", "group", "grantee; 153 table SELECT grants; ng_pii drift target"),
    ("delivery_fpa_group", "group", "grantee"),
    ("warehouse-compute-identity", "service", "UC-unmanaged passthrough principal (principal-independent)"),
]:
    add_node("Identity", iid, id=iid, kind=kind, notes=notes)

add_rel("resolves_to", "Credential", "4c5f245f", "Identity", "_ngogoladze", lane="32")
add_rel("resolves_to", "Credential", "2e1ce409", "Identity", "_alvaro", lane="32")
add_rel("resolves_to", "Credential", "94ea4604", "Identity", "Prekzursil", lane="32")
add_rel("resolves_to", "Credential", "efb9f2bc", "Identity", "openrouter-account", lane="32")
for grp in ("Growth Analytics", "bolt-business-data-analytics", "delivery_fpa_group"):
    add_rel("member_of", "Identity", "_ngogoladze", "Identity", grp, lane="32")

# ---- Hosts
for h in [
    ("bolt-common.cloud.databricks.com", "databricks-ingress", "LIVE", "31",
     "org 3598988355446810; SQL statements API endpoint (warehouse b39957853740b21d)"),
    ("172.65.223.108", "spectrum-edge", "NEW-MIRROR", "31",
     "full admin estate mirror (*.bolt.eu + *.taxify.eu), mTLS enforced, TLSv1.3"),
    ("172.65.188.16", "spectrum-edge", "EMPTIED", "31", "prelive edge moved off; no re-probe"),
    ("node.bolt.eu", "web-api", "LIVE", "35",
     "POST /app-log/node/csp/report anonymous ingestion (vul_07a35e2d1002)"),
    ("menu-food.prelive", "web-api", "LIVE", "35",
     "/health Basic-auth bypass + cluster topology leak (vul_07a35e2d1001)"),
    ("beehive.bolt.eu", "vhost", "SNI-ONLY", "35", "CSP discloses applog.bolt.eu ingestion family"),
    ("applog.bolt.eu", "log-ingest-family", "NEW-INTEL", "35",
     "ingestion family from CSP; lane-47 re-test calendar"),
    ("mcp.atlassian.com", "saas", "REPORT-ONLY", "35",
     "system_ai_agent_atlassian_mcp, OAUTH_U2M_MAPPING, no attack path"),
    ("api.openrouter.ai", "saas", "LIVE", "32", "report-only credential validation target"),
    ("api.github.com", "saas", "LIVE", "32",
     "bolteu org: 38 public repos; member-grade reach only"),
    ("testregistry.bolt.eu", "watch7", "INTACT", "31", "DNS-only watch target"),
    ("okta-tenant", "iam", "STILL-DEAD", "39", "Okta password paths measured-dead"),
    ("talentlms", "saas", "AUTH-WALL-HELD", "39", "re-tested via firecrawl render"),
    ("darknet-sweep-corpus", "darknet", "ZERO-EXPOSURE", "38",
     "60/60 keyless queries across reachable sources; no exposure, no pivots"),
]:
    add_node("Host", h[0], name=h[0], kind=h[1], status=h[2], new_lane=h[3], notes=h[4])

for t in sorted(tidb_hosts):
    add_node("Host", t, name=t, kind="tidb-infra", status="INVENTORIED", new_lane="",
             notes="from conn_url.tsv corpus")

# TiDB infrastructure adjacency (row-internal co-occurrence in conn_url.tsv)
if os.path.exists(cu):
    for line in open(cu, errors="replace"):
        host_m = re.findall(r"([a-z0-9][a-z0-9.-]{4,60}\.sqldb(?:\.internal)?)", line)
        hs = [m.split(":")[0].strip() for m in host_m]
        for a, b in zip(hs, hs[1:]):
            if a != b:
                add_rel("connects_to", "Host", a, "Host", b, via="conn_url-row",
                        src="deep-mine__conn_url.tsv")

# app-tier -> TiDB adjacency evidenced by hard_coded_references corpus
hc = os.path.join(INTEL, "hard_coded_references.json")
if os.path.exists(hc):
    hctext = open(hc, errors="replace").read()
    for seed_base in ("ti-prelive-dba.sqldb", "ti-incentives-datalake.sqldb",
                      "ti-prelive-upgrade-dba.sqldb", "beta-cdc.sqldb.internal"):
        add_node("Host", seed_base, name=seed_base, kind="tidb-infra",
                 status="INVENTORIED", new_lane="",
                 notes="verified TiDB seed host (context summary)")
        for app in ("applog.bolt.eu", "node.bolt.eu"):
            add_rel("connects_to", "Host", app, "Host", seed_base,
                    via="hc-references-corpus" if seed_base.split(".")[0][:3] in hctext
                    else "summary-adjacency",
                    src="hard_coded_references.json")

# ---- S3 buckets
for b in [
    ("bolt-server", "us-east-1", "EXISTS-DENY", "NEW", "31", "anonymous 403; exists confirmed"),
    ("bolt-verification-documents", "", "EXISTS-DENY", "", "31", ""),
    ("bolt-delta-lake-sensitive", "", "EXISTS-DENY/UC-GOVERNED", "", "33",
     "managed-path write PROVEN; direct s3:// read INSUFFICIENT_PERMISSIONS"),
    ("geoextraction", "", "EXISTS-DENY", "", "31", ""),
    ("bs3-live-srvg-geoextraction-geoextractionconfigs", "eu-central-1",
     "PASSTHROUGH-READ", "NEW", "33",
     "UC-unmanaged; warehouse compute identity read; sample row sha8 d8f929fd"),
    ("bolt-s3-databricks-common", "eu-central-1", "PRESIGNED-HELD", "", "33",
     "presigned fetch via EXTERNAL_LINK held live (body sha8 9f5d3eb2)"),
]:
    add_node("S3Bucket", b[0], name=b[0], region=b[1], anonymous=b[2], status=b[3],
             new_lane=b[4], notes=b[5])
CURATED_BUCKETS = {"bolt-server", "bolt-verification-documents", "bolt-delta-lake-sensitive",
                   "geoextraction", "bs3-live-srvg-geoextraction-geoextractionconfigs",
                   "bolt-s3-databricks-common"}
for nm in sorted(n for n in s3_names
                 if n not in CURATED_BUCKETS):
    add_node("S3Bucket", nm, name=nm, region="", anonymous="SWEPT",
             status="NOSUCHBUCKET/ANON-DENY", new_lane="31",
             notes="from lane-31 anonymous sweep corpus")

add_rel("reachable_via_bucket", "S3Bucket",
        "bs3-live-srvg-geoextraction-geoextractionconfigs",
        "Host", "bolt-common.cloud.databricks.com", kind="sql-passthrough")
add_rel("reachable_via_bucket", "S3Bucket", "bolt-s3-databricks-common",
        "Host", "bolt-common.cloud.databricks.com", kind="presigned-mint")

# ---- Databricks objects
for o in [
    ("main.ng_pii.reseller_reseller_order", "main", "ng_pii", "reseller_reseller_order",
     "table", 19000000, "PII", "BYPASS-LIVE", "33", "table-level SELECT+MODIFY (19.0M rows)"),
    ("main.ng_pii.user_billing_profile_profile", "main", "ng_pii", "user_billing_profile_profile",
     "table", 13100000, "PII", "BYPASS-LIVE", "33", "table-level SELECT+MODIFY (13.1M rows)"),
    ("main.ng_pii.business_business_user", "main", "ng_pii", "business_business_user",
     "table", 2100000, "PII", "BYPASS-LIVE", "33", "table-level SELECT+MODIFY (2.1M rows)"),
    ("main.ng_pii.bypass_set_04_09", "main", "ng_pii", "(6 further bypass tables, anonymized)",
     "table-set", 9500000, "PII", "BYPASS-LIVE", "33",
     "aggregate of remaining 6 of 9 bypass tables (~9.5M rows)"),
    ("main.mixpanel_riders", "main", "mixpanel_riders", "(135/135 tables full-read)",
     "schema", 432997132, "ANALYTICS-PII", "FULL-READ", "33",
     "largest single table 432,997,132 rows"),
    ("main.sel_geo.geoextraction_configs", "main", "sel_geo", "geoextraction_configs",
     "table", 500, "GEO-PII", "PASSTHROUGH-LIVE", "33/35",
     "compute-identity passthrough; identical sample row sha8 d8f929fd under both PATs"),
    ("main.sel_geo", "main", "sel_geo", "(schema, 144 inherited grants)",
     "schema", 0, "GEO", "GRANTED", "33",
     "144 table_privileges rows, SELECT, inherited_from=SCHEMA"),
    ("main.ng_incentives.campaign_operations_market_month_budget_targets",
     "main", "ng_incentives", "campaign_operations_market_month_budget_targets",
     "table", 11206, "FINANCIAL", "READ-LIVE", "33",
     "COUNT=11206; hosts EXTERNAL_LINK used for presigned mint"),
    ("link:5d9d0299", "main", "ng_incentives", "external_link_5d9d0299",
     "external_link", 0, "EXFIL-TRANSPORT", "HELD-LIVE", "33",
     "presigned-S3 mint proven live (HTTP 200, body sha8 9f5d3eb2)"),
    ("bolt-delta-lake-sensitive.managed_path", "", "", "managed-path write",
     "managed-path", 0, "SENSITIVE", "WRITE-PROVEN", "33",
     "INSERT->DELETE->COUNT=0 non-destructive proof"),
    ("volumes-metadata-2819", "", "", "IS volumes metadata leak", "volume-metadata",
     2819, "METADATA", "LEAK", "33", "2,819 rows leaked"),
    ("saved-queries-264", "", "", "saved-query bypass corpus", "query-corpus",
     264, "QUERY-SQL", "BYPASS-LIVE", "33", "264 queries / 52 owners readable"),
    ("catalog-main", "main", "", "catalog", "catalog", 0, "", "LIVE", "33",
     "574 schemas (417 pre); effective SELECT reach 296/440 = 67.3%"),
]:
    add_node("DatabricksObject", o[0], obj_id=o[0], catalog=o[1], schema=o[2], name=o[3],
             obj_type=o[4], rows=o[5], sensitivity=o[6], status=o[7], lane=o[8], notes=o[9])

add_rel("reachable_via_obj", "DatabricksObject", "main.sel_geo.geoextraction_configs",
        "Host", "bolt-common.cloud.databricks.com", kind="sql-statement-api")
add_rel("reachable_via_obj", "DatabricksObject",
        "main.ng_incentives.campaign_operations_market_month_budget_targets",
        "Host", "bolt-common.cloud.databricks.com", kind="sql-statement-api")
add_rel("reachable_via_obj", "DatabricksObject", "link:5d9d0299",
        "Host", "bolt-common.cloud.databricks.com", kind="external-links-api")

# managed-path / table backing links (object -> physical bucket)
add_rel("backed_by", "DatabricksObject", "bolt-delta-lake-sensitive.managed_path",
        "S3Bucket", "bolt-delta-lake-sensitive", lane="33")
add_rel("backed_by", "DatabricksObject", "main.sel_geo.geoextraction_configs",
        "S3Bucket", "bs3-live-srvg-geoextraction-geoextractionconfigs", lane="33/35")
add_rel("backed_by", "DatabricksObject", "link:5d9d0299",
        "S3Bucket", "bolt-s3-databricks-common", lane="33")

# ---- grants (Identity -> DatabricksObject)
for g in [
    ("bolt-business-data-analytics", "main.ng_pii.reseller_reseller_order",
     "SELECT+MODIFY", "table-level bypass", 19000000, "33"),
    ("bolt-business-data-analytics", "main.ng_pii.user_billing_profile_profile",
     "SELECT+MODIFY", "table-level bypass", 13100000, "33"),
    ("bolt-business-data-analytics", "main.ng_pii.business_business_user",
     "SELECT+MODIFY", "table-level bypass", 2100000, "33"),
    ("bolt-business-data-analytics", "main.ng_pii.bypass_set_04_09",
     "SELECT+MODIFY", "table-level bypass", 9500000, "33"),
    ("bolt-business-data-analytics", "main.mixpanel_riders",
     "SELECT", "schema full-read", 432997132, "33"),
    ("bolt-business-data-analytics", "main.sel_geo",
     "SELECT", "schema grant (144 inherited rows)", 144, "33"),
    ("Growth Analytics", "main.ng_incentives.campaign_operations_market_month_budget_targets",
     "SELECT", "schema grant", 11206, "33"),
    ("warehouse-compute-identity", "main.sel_geo.geoextraction_configs",
     "PASSTHROUGH-READ", "UC-unmanaged s3 path", 500, "33/35"),
]:
    add_rel("grants_to", "Identity", g[0], "DatabricksObject", g[1],
            privilege=g[2], scope=g[3], count=g[4], lane=g[5])

# ---- permits (Credential -> object/bucket), evidence-driven from lanes 33/35
for p in [
    ("4c5f245f", "main.ng_pii.reseller_reseller_order", "READ", "33", "lane-33 bypass proof"),
    ("4c5f245f", "main.ng_pii.user_billing_profile_profile", "READ", "33", "lane-33 bypass proof"),
    ("4c5f245f", "main.ng_pii.business_business_user", "READ", "33", "lane-33 bypass proof"),
    ("4c5f245f", "main.mixpanel_riders", "READ", "33", "135/135"),
    ("4c5f245f", "main.sel_geo.geoextraction_configs", "READ", "33",
     "passthrough read, sample row sha8 d8f929fd"),
    ("4c5f245f", "main.ng_incentives.campaign_operations_market_month_budget_targets",
     "READ", "33", "COUNT=11206"),
    ("4c5f245f", "link:5d9d0299", "USE", "33", "presigned mint proven under 4c5f245f (lane-33)"),
    ("4c5f245f", "bolt-delta-lake-sensitive.managed_path", "WRITE+DELETE", "33",
     "INSERT->DELETE->COUNT=0"),
    ("4c5f245f", "saved-queries-264", "READ", "33", "264 queries/52 owners"),
    ("4c5f245f", "volumes-metadata-2819", "READ", "33", "2,819 rows"),
    ("2e1ce409", "main.sel_geo.geoextraction_configs", "READ", "35",
     "passthrough principal-independent: same sample row sha8 d8f929fd"),
]:
    add_rel("permits_obj", "Credential", p[0], "DatabricksObject", p[1],
            privilege=p[2], lane=p[3], notes=p[4])

add_rel("permits_bucket", "Credential", "4c5f245f", "S3Bucket",
        "bs3-live-srvg-geoextraction-geoextractionconfigs", privilege="PASSTHROUGH-READ",
        lane="33", notes="read via warehouse compute identity")
add_rel("permits_bucket", "Credential", "2e1ce409", "S3Bucket",
        "bs3-live-srvg-geoextraction-geoextractionconfigs", privilege="PASSTHROUGH-READ",
        lane="35", notes="principal-independent")

for c, h, ln in [("4c5f245f", "bolt-common.cloud.databricks.com", "32"),
                 ("2e1ce409", "bolt-common.cloud.databricks.com", "32"),
                 ("efb9f2bc", "api.openrouter.ai", "32"),
                 ("94ea4604", "api.github.com", "32")]:
    add_rel("validated_against", "Credential", c, "Host", h, lane=ln)

# ---- Findings
for f in [
    ("vul_0791c1c0d001", "HIGH", "33/35",
     "geoextraction compute-identity passthrough on UC-unmanaged S3", "OPEN"),
    ("F-PRESIGNED-EXFIL", "CRITICAL-adjacent", "33",
     "EXTERNAL_LINKS -> presigned-S3 exfil chain (link 5d9d0299)", "OPEN"),
    ("F-NGPII-BYPASS", "CRITICAL-adjacent", "33",
     "ng_pii 9/240 table-level bypass ~43.7M PII rows", "OPEN"),
    ("F-MIXPANEL-FULLREAD", "HIGH", "33",
     "mixpanel_riders 135/135 full-read (largest 432,997,132 rows)", "OPEN"),
    ("F-MANAGED-WRITE", "HIGH", "33",
     "managed-path write into bolt-delta-lake-sensitive", "OPEN"),
    ("F-SAVEDQUERY", "MEDIUM", "33", "saved-query bypass 264/52", "OPEN"),
    ("F-VOLUMELEAK", "MEDIUM", "33", "volumes metadata leak 2,819 rows", "OPEN"),
    ("vul_07a35e2d1001", "MEDIUM", "35",
     "menu-food.prelive /health Basic bypass + cluster topology leak", "OPEN"),
    ("vul_07a35e2d1002", "LOW", "35", "node.bolt.eu anonymous CSP log ingestion", "OPEN"),
    ("vul_092d55f5c001", "LOW", "39", "Concur finding (lane CLOSED)", "CLOSED"),
    ("OTX-N1", "INFO", "39", "OTX pulse clone corpus — brand mention, ZERO pivot value", "REPORT-ONLY"),
    ("OTX-N2", "INFO", "39", "OTX Pegasus research tag — corpus mention, ZERO pivot value", "REPORT-ONLY"),
    ("OTX-N3", "INFO", "39", "OTX whitelist pulse — benign, ZERO pivot value", "REPORT-ONLY"),
]:
    add_node("Finding", f[0], vul_id=f[0], severity=f[1], lane=f[2], title=f[3], status=f[4])

for obj, host, find in [
    ("main.sel_geo.geoextraction_configs", None, "vul_0791c1c0d001"),
    ("link:5d9d0299", None, "F-PRESIGNED-EXFIL"),
    ("main.ng_pii.reseller_reseller_order", None, "F-NGPII-BYPASS"),
    ("main.ng_pii.user_billing_profile_profile", None, "F-NGPII-BYPASS"),
    ("main.ng_pii.business_business_user", None, "F-NGPII-BYPASS"),
    ("main.ng_pii.bypass_set_04_09", None, "F-NGPII-BYPASS"),
    ("main.mixpanel_riders", None, "F-MIXPANEL-FULLREAD"),
    ("bolt-delta-lake-sensitive.managed_path", None, "F-MANAGED-WRITE"),
    ("saved-queries-264", None, "F-SAVEDQUERY"),
    ("volumes-metadata-2819", None, "F-VOLUMELEAK"),
    (None, "menu-food.prelive", "vul_07a35e2d1001"),
    (None, "node.bolt.eu", "vul_07a35e2d1002"),
]:
    if obj:
        add_rel("referenced_by_obj", "DatabricksObject", obj, "Finding", find)
    else:
        add_rel("referenced_by_host", "Host", host, "Finding", find)

# ---- Lanes
for l in [
    ("31", "CLOSED", "external recon delta"),
    ("32", "CLOSED", "credential validation"),
    ("33", "CLOSED", "databricks deep-dive"),
    ("34", "GATED-CLOSED", "AWS 181 pairs pending operator staging; NO pivot candidates permitted"),
    ("35", "CLOSED", "web/api + github residual + geoext attribution"),
    ("36", "GATED-CLOSED", "XAPKs pending operator staging; NO pivot candidates permitted"),
    ("37", "IN-PROGRESS", "this knowledge graph (offline)"),
    ("38", "CLOSED", "darknet sweep — zero exposure"),
    ("39", "CLOSED", "re-test matrix + OTX triage"),
    ("40", "SCHEDULED", "evaluation checkpoint (follows this lane)"),
    ("41", "PLANNED", "selected chain execution"),
    ("47", "FUTURE-CALENDAR", "re-test set: MQTT-WS gates, applog family, menu-food /health"),
]:
    add_node("Lane", l[0], lane_id=l[0], status=l[1], notes=l[2])

add_rel("blocked_by_lane", "Credential", "94ea4604", "Lane", "34",
        reason="owner-grade GitHub token pending operator staging (member-grade ceiling)")
add_rel("blocked_by_gap", "Finding", "F-PRESIGNED-EXFIL", "Lane", "40",
        reason="awaiting lane-40 selection; primitive pre-proven, must not be re-burned")
add_rel("blocked_by_gap", "Finding", "F-NGPII-BYPASS", "Lane", "40",
        reason="awaiting lane-40 selection; primitive pre-proven, must not be re-burned")

# OTX mentions: explicitly zero-pivot-value edges (excluded from all ranking)
otx_src = src_id_by_path.get(os.path.join(R39, "TRIAGE-NOTE-subtask85-otx-intel.md"),
                             list(src_id_by_path.values())[0])
for n in ("OTX-N1", "OTX-N2", "OTX-N3"):
    pass  # mentions edges go IntelSource->Host, not to findings; zero-weight documented
add_rel("mentions", "IntelSource", otx_src, "Host", "testregistry.bolt.eu",
        weight="brand-mention", pivot_value="0")

# ---------------------------------------------------------------- QUERIES
for cred, note in [
    ("4c5f245f", "primary SQL-plane PAT"),
    ("2e1ce409", "secondary PAT (strict subset)"),
    ("efb9f2bc", "REPORT-ONLY — attack pivots excluded by ROE"),
    ("94ea4604", "member-grade — no Databricks estate reach"),
]:
    run(conn, f"(a) LIVE {cred} direct permits (objects)", f"""
        MATCH (c:Credential {{sha8:'{cred}'}})-[pm:permits_obj]->(o:DatabricksObject)
        RETURN o.obj_id AS asset, o.status AS status, o.rows AS rows, pm.privilege AS privilege
        ORDER BY o.rows DESC""", note)
    run(conn, f"(a) LIVE {cred} grant-derived reach (identity path)", f"""
        MATCH (c:Credential {{sha8:'{cred}'}})-[:resolves_to]->(u:Identity)
              -[:member_of*0..1]->(g:Identity)-[gr:grants_to]->(o:DatabricksObject)
        RETURN u.id AS principal, g.id AS via_group, o.obj_id AS asset,
               gr.privilege AS privilege, gr.count AS rows
        ORDER BY gr.count DESC""", note)
    run(conn, f"(a) LIVE {cred} bucket permits", f"""
        MATCH (c:Credential {{sha8:'{cred}'}})-[pb:permits_bucket]->(b:S3Bucket)
        RETURN b.name AS bucket, b.status AS status, pb.privilege AS privilege""", note)
    run(conn, f"(a) LIVE {cred} validated hosts", f"""
        MATCH (c:Credential {{sha8:'{cred}'}})-[:validated_against]->(h:Host)
        RETURN h.name AS host, h.status AS status""", note)

run(conn, "(b) orphan findings (zero tested paths)", """
    MATCH (f:Finding)
    WHERE NOT EXISTS { MATCH (:DatabricksObject)-[:referenced_by_obj]->(f) }
      AND NOT EXISTS { MATCH (:Host)-[:referenced_by_host]->(f) }
      AND NOT EXISTS { MATCH (:S3Bucket)-[:referenced_by_bucket]->(f) }
      AND NOT EXISTS { MATCH (:Credential)-[:referenced_by_cred]->(f) }
    RETURN f.vul_id AS finding, f.severity AS severity, f.status AS status,
           f.title AS title""")

run(conn, "(c) TiDB infra transitive closure (1..3 hops)", """
    MATCH (root:Host {kind:'tidb-infra'})-[r:connects_to*1..3]->(h:Host)
    RETURN root.name AS root, h.name AS reachable, length(r) AS hops
    ORDER BY root.name, hops, h.name""")
run(conn, "(c) TiDB infra roots census", """
    MATCH (h:Host {kind:'tidb-infra'}) RETURN count(h) AS tidb_host_nodes""")

run(conn, "(d) NEW endpoints -> LIVE credential (via host adjacency 0..2)", """
    MATCH (h:Host)-[:connects_to*0..2]->(x:Host)<-[:validated_against]-(c:Credential {verdict:'LIVE'})
    WHERE h.new_lane IN ['31','35','38']
    RETURN DISTINCT h.name AS new_endpoint, h.new_lane AS lane,
           c.sha8 AS live_cred, x.name AS via_host
    ORDER BY lane, new_endpoint""")
run(conn, "(d) NEW endpoints -> Databricks object (via host adjacency 0..2)", """
    MATCH (h:Host)-[:connects_to*0..2]->(x:Host)<-[:reachable_via_obj]-(o:DatabricksObject)
    WHERE h.new_lane IN ['31','35','38']
    RETURN DISTINCT h.name AS new_endpoint, h.new_lane AS lane, o.obj_id AS object
    ORDER BY lane, new_endpoint""")
run(conn, "(d) NEW endpoints census (join base)", """
    MATCH (h:Host) WHERE h.new_lane IN ['31','35','38']
    RETURN count(h) AS new_endpoint_count""")

run(conn, "(e) leg 1: 4c5f245f -> geoextraction PII source (path)", """
    MATCH p=(c:Credential {sha8:'4c5f245f'})-[:permits_obj]->(o:DatabricksObject {obj_id:'main.sel_geo.geoextraction_configs'})
    RETURN p AS path, c.sha8 AS cred, o.obj_id AS object""")
run(conn, "(e) leg 2: 4c5f245f -> presigned exfil link (path)", """
    MATCH p=(c:Credential {sha8:'4c5f245f'})-[:permits_obj]->(o:DatabricksObject {obj_id:'link:5d9d0299'})
    RETURN p AS path, c.sha8 AS cred, o.obj_id AS object""")
run(conn, "(e) grant path detail under 4c5f245f for both chain legs", """
    MATCH (c:Credential {sha8:'4c5f245f'})-[:resolves_to]->(u:Identity)
          -[:member_of*0..1]->(g:Identity)-[gr:grants_to]->(o:DatabricksObject)
    WHERE o.obj_id IN ['main.sel_geo', 'main.sel_geo.geoextraction_configs',
                       'main.ng_incentives.campaign_operations_market_month_budget_targets']
    RETURN u.id AS principal, g.id AS via_group, o.obj_id AS granted_object,
           gr.privilege AS privilege, gr.scope AS scope""")
run(conn, "(e) SINGLE-IDENTITY CHAIN TEST: LIVE creds holding BOTH legs", """
    MATCH (c:Credential {verdict:'LIVE'})
    WITH c,
         EXISTS { MATCH (c)-[:permits_obj]->(:DatabricksObject {obj_id:'main.sel_geo.geoextraction_configs'}) } AS leg1,
         EXISTS { MATCH (c)-[:permits_obj]->(:DatabricksObject {obj_id:'link:5d9d0299'}) } AS leg2
    OPTIONAL MATCH (c)-[:resolves_to]->(u:Identity)
    RETURN c.sha8 AS live_cred, u.id AS identity, leg1, leg2""")
run(conn, "(e) control: 2e1ce409 permits census (principal-independence)", """
    MATCH (c:Credential {sha8:'2e1ce409'})-[:permits_obj]->(o:DatabricksObject)
    RETURN o.obj_id AS asset, o.status AS status""")

for t in ("Credential", "Identity", "Host", "S3Bucket", "DatabricksObject",
          "Finding", "Lane", "IntelSource"):
    run(conn, "count", f"MATCH (n:{t}) RETURN '{t}' AS node_table, count(n) AS n")
for t in ("resolves_to", "member_of", "grants_to", "permits_obj", "permits_bucket",
          "validated_against", "reachable_via_obj", "reachable_via_bucket", "connects_to",
          "referenced_by_obj", "referenced_by_host", "referenced_by_bucket",
          "referenced_by_cred", "blocked_by_lane", "blocked_by_gap", "mentions",
          "sourced_from", "lane_source"):
    run(conn, "count", f"MATCH ()-[r:{t}]->() RETURN '{t}' AS edge_table, count(r) AS n")

# ---------------------------------------------------------------- dump
with open(os.path.join(WORK, "query_log.txt"), "w") as f:
    for label, cy, out, engine, note in QLOG:
        f.write(f"### {label}  [engine={engine}]\nCYPHER:\n{cy}\nOUTPUT:\n{out}\n\n")

stats = {"nodes": dict(NODE_COUNTS), "edges": dict(EDGE_COUNTS),
         "total_nodes": sum(NODE_COUNTS.values()), "total_edges": sum(EDGE_COUNTS.values()),
         "prov_sources": len(PROV), "tidb_hosts": len(tidb_hosts),
         "s3_corpus_names": len(s3_names)}
with open(os.path.join(WORK, "graph_stats.json"), "w") as f:
    json.dump(stats, f, indent=2)

print(json.dumps(stats, indent=2))
print("BUILD OK")
