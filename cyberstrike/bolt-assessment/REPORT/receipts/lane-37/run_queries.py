#!/usr/bin/env python3
"""Lane-37 mandated pivot queries (a)-(e) over the Kuzu graph.

Runs verbatim Cypher against /work/lane37/graphdb and emits a receipt-ready
log: section header, the exact Cypher, the raw rows, and a plain-English
verdict. Offline only — zero network.
"""
import kuzu

DB = "/work/lane37/graphdb"
LOG = "/work/lane37/query_run.log"

LIVE_CREDS = [
    ("4c5f245f", "databricks PAT _ngogoladze, grants-expanded"),
    ("2e1ce409", "databricks PAT _alvaro, strict subset"),
    ("efb9f2bc", "openrouter REPORT-ONLY — attack pivots forbidden"),
    ("94ea4604", "github PAT Prekzursil member-grade"),
]
CHAIN_OBJ = ["main.sel_geo.geoextraction_configs", "link:5d9d0299"]

conn = kuzu.Connection(kuzu.Database(DB))
OUT = open(LOG, "w", encoding="utf-8")


def emit(line=""):
    OUT.write(line + "\n")
    print(line)


def hdr(section):
    emit("=" * 78)
    emit(section)


def run(cypher, params=None):
    res = conn.execute(cypher, parameters=params or {})
    cols = res.get_column_names()
    emit("CYPHER: " + cypher)
    emit("---- OUTPUT ----")
    emit(" | ".join(cols))
    rows = []
    while res.has_next():
        row = res.get_next()
        rows.append(row)
        emit(" | ".join(str(v) for v in row))
    if not rows:
        emit("(0 rows)")
    emit()
    return rows


def verdict(text):
    emit("---- VERDICT ----")
    emit(text)
    emit()


# ================================================================ (a)
emit("LANE-37 PIVOT ANALYTICS — MANDATED QUERIES (a)-(e)")
emit("DB: " + DB + "  |  engine: kuzu 0.11.3  |  offline")
emit()

for sha, desc in LIVE_CREDS:
    rows = run(
        f"MATCH p=(c:Credential {{sha8:$k}})-[*1..4]->(t:DatabricksObject) "
        "RETURN length(p) AS hops, nodes(p) AS path ORDER BY hops",
        {"k": sha})
    verdict(
        f"(a) {sha} ({desc}): {len(rows)} forward path(s) to DatabricksObject "
        f"nodes. Asset reach enumerated above; direct permit edges plus "
        f"identity/group grant hops are included.")

    rows = run(
        f"MATCH p=(c:Credential {{sha8:$k}})-[*1..4]->(t:S3Bucket) "
        "RETURN length(p) AS hops, nodes(p) AS path ORDER BY hops",
        {"k": sha})
    verdict(
        f"(a) {sha}: {len(rows)} path(s) to S3Bucket nodes "
        f"(direct permits or via backed_by object chains).")

    rows = run(
        f"MATCH p=(c:Credential {{sha8:$k}})-[*1..4]->(t:Host) "
        "RETURN length(p) AS hops, nodes(p) AS path ORDER BY hops LIMIT 40",
        {"k": sha})
    verdict(
        f"(a) {sha}: {len(rows)} path(s) to Host nodes shown "
        f"(validation planes and object/bucket carriers only — no pivot "
        f"rights implied by host reach).")

# ================================================================ (b)
hdr("(b) Orphan findings — Findings with zero graph edges (no tested paths)")
run(
    "MATCH (f:Finding) OPTIONAL MATCH (f)-[r]-() "
    "WITH f, count(r) AS degree WHERE degree = 0 "
    "RETURN f.vul_id AS vul_id, f.severity AS severity, f.lane AS lane, "
    "f.title AS title")
verdict(
    "(b) Orphans = Findings with degree 0 (no referenced_by_*, no "
    "sourced_from, no blocked_by_gap). Rows above are the orphan set; "
    "an empty set means every Finding is wired to a tested path.")

hdr("(b-diag) Finding degree distribution (diagnostic, all findings)")
rows = run(
    "MATCH (f:Finding) OPTIONAL MATCH (f)-[r]-() "
    "WITH f, count(r) AS degree "
    "RETURN f.vul_id AS vul_id, f.severity AS severity, degree "
    "ORDER BY degree, f.vul_id")
verdict(
    f"(b-diag) {len(rows)} Finding nodes in graph; degree shown per node.")

# ================================================================ (c)
hdr("(c) TiDB infrastructure transitive closure (connects_to edges)")
rows = run(
    "MATCH (root:Host {kind:'tidb-infra'})-[:connects_to*1..4]->(h:Host) "
    "RETURN count(DISTINCT h.name) AS reachable_hosts, "
    "count(DISTINCT root.name) AS roots_with_edges")
verdict(
    "(c) Transitive closure over connects_to from tidb-infra roots: "
    f"{rows[0][0] if rows else 0} distinct host(s) reachable, "
    f"{rows[0][1] if rows else 0} root(s) with outgoing edges.")

rows = run(
    "MATCH (root:Host {kind:'tidb-infra'})-[:connects_to*1..4]->(h:Host) "
    "RETURN h.name AS reachable_host, count(root) AS n_roots "
    "ORDER BY n_roots DESC, reachable_host LIMIT 30")
verdict(
    "(c) Top reachable TiDB/infra hosts by number of roots reaching them "
    "(sample capped at 30). Full closure size in the count above.")

# ================================================================ (d)
hdr("(d) NEW lane-31/35/38 endpoints joined to credentials / Databricks objects")
rows = run(
    "MATCH (h:Host) WHERE h.new_lane IN ['31','35','38'] "
    "OPTIONAL MATCH (c:Credential)-[*1..3]-(h) "
    "WITH h, count(DISTINCT c.sha8) AS cred_links "
    "OPTIONAL MATCH (o:DatabricksObject)-[*1..3]-(h) "
    "WITH h, cred_links, count(DISTINCT o.obj_id) AS obj_links "
    "RETURN h.name AS new_endpoint, h.new_lane AS lane, h.kind AS kind, "
    "cred_links, obj_links ORDER BY h.new_lane, h.name")
verdict(
    "(d) New recon/web/darknet endpoints (lane 31/35/38) with counts of "
    "distinct LIVE-credential nodes and DatabricksObject nodes within "
    "3 undirected hops. cred_links/obj_links > 0 = path exists; 0 = no "
    "path to any credential or Databricks object in the graph.")

rows = run(
    "MATCH (h:Host) WHERE h.new_lane IN ['31','35','38'] "
    "MATCH p=(h)-[*1..3]-(c:Credential) "
    "RETURN h.name AS new_endpoint, h.new_lane AS lane, c.sha8 AS cred, "
    "c.cclass AS cclass, length(p) AS hops "
    "ORDER BY h.new_lane, h.name, hops LIMIT 60")
verdict(
    "(d) Concrete endpoint->credential paths (capped 60). Each row is a "
    "graph path from a NEW endpoint to a credential node within 3 hops.")

# ================================================================ (e)
hdr("(e) CRITICAL-adjacent pair test — geoextraction passthrough x presigned mint from ONE identity")
rows = run(
    "MATCH (c:Credential)-[:permits_obj]->(o:DatabricksObject) "
    "WHERE c.sha8 IN ['4c5f245f','2e1ce409'] "
    "AND o.obj_id IN ['main.sel_geo.geoextraction_configs','link:5d9d0299'] "
    "RETURN c.sha8 AS credential, o.obj_id AS chain_leg ORDER BY credential")
holders = {}
for r in rows:
    holders.setdefault(r[0], set()).add(r[1])
single = [s for s, legs in holders.items() if legs == set(CHAIN_OBJ)]
verdict(
    "(e) Permit-map for the two databricks LIVE PATs over the CRITICAL pair "
    "{main.sel_geo.geoextraction_configs, link:5d9d0299}. "
    f"Holders: { {k: sorted(v) for k, v in holders.items()} }. "
    f"VERDICT: CHAIN-FEASIBLE-FROM-ONE-IDENTITY = "
    f"{'YES (' + ', '.join(single) + ')' if single else 'NO'}")

for sha in ["4c5f245f", "2e1ce409"]:
    run(
        f"MATCH p=(c:Credential {{sha8:$k}})-[*1..3]->"
        "(o:DatabricksObject) "
        "WHERE o.obj_id IN ['main.sel_geo.geoextraction_configs',"
        "'link:5d9d0299'] "
        "RETURN o.obj_id AS chain_leg, nodes(p) AS grant_path",
        {"k": sha})
verdict(
    "(e) Grant paths for each LIVE PAT to both chain legs "
    "(leg | node sequence). The identity holding BOTH legs in a single "
    "permit map answers the feasibility question above.")

OUT.close()
print("DONE — log at " + LOG)
