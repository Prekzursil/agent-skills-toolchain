#!/usr/bin/env python3
"""Lane-47 items (b) applog family, (c) menu-food oracle, (d) beehive SNI edges.
All payloads synthetic (l47probe*), zero PII, zero credential shapes. <=1 rps, single attempt
per endpoint/shape. Reuses l47.py helpers."""
import json, os, re, shutil, sys, time
sys.path.insert(0, "/work/lane47")
from l47 import http_probe, fmt_http, now_iso, sha8, WORK, REC, BUDGET_FILE

# ---- synthetic payloads ------------------------------------------------
CSP_REPORT = ('{"csp-report":{"document-uri":"https://bolt.eu/l47probe","referrer":"https://bolt.eu/",'
              '"violated-directive":"script-src \'self\'","effective-directive":"script-src",'
              '"original-policy":"l47probe-synthetic","blocked-uri":"self","line-number":1,'
              '"column-number":1,"source-file":"l47probe","status-code":0,"script-sample":"l47probe"}}')
NDJSON = ('{"ts":"2026-10-03T17:00:00Z","lvl":"info","app":"l47probe",'
          '"msg":"synthetic lane-47 ndjson probe","seq":1}\n')
OVERSIZED = ('{"csp-report":{"document-uri":"https://bolt.eu/l47probe","blocked-uri":"self",'
             '"original-policy":"' + ("l47probe-pad-" * 5120) + '"}}')   # ~66 KB
assert len(OVERSIZED) > 65536 - 2048, len(OVERSIZED)

def post(url, body, ctype, label):
    r = http_probe(url, method="POST", data=body, ctype=ctype)
    r["label"] = label
    return r

def phase_applog():
    out = ["# LANE-47 ITEM (b) applog.bolt.eu ingestion family re-test — anonymous, synthetic payloads only",
           "# baseline lane-35: node.bolt.eu POST /app-log/node/csp/report -> 200 {\"code\":0,\"message\":\"OK\"} (anon OPEN)",
           "#                  beehive-bolt-eu.applog / beehive-csp.applog -> DISCLOSED-NOT-PROBED (CSP report-uri only)",
           f"# generated {now_iso()}"]
    res = {}
    res["csp-01"] = post("https://beehive-csp.applog.bolt.eu/beehive/csp/report",
                         CSP_REPORT, "application/csp-report", "beehive-csp csp-report json")
    res["ing-01"] = post("https://beehive-bolt-eu.applog.bolt.eu/beehive/csp/report",
                         CSP_REPORT, "application/csp-report", "beehive-bolt-eu csp-report json (path=/beehive/csp/report)")
    # node-pattern mirror only if the /beehive/ path did not accept on the ingest vhost
    if str(res["ing-01"].get("status", "000")).startswith("2"):
        res["ing-02"] = None
    else:
        res["ing-02"] = post("https://beehive-bolt-eu.applog.bolt.eu/app-log/beehive/csp/report",
                             CSP_REPORT, "application/csp-report", "beehive-bolt-eu csp-report json (node-pattern mirror)")
    res["csp-02"] = post("https://beehive-csp.applog.bolt.eu/beehive/csp/report",
                         NDJSON, "application/x-ndjson", "beehive-csp ndjson shape")
    # acceptance ceiling probes on the BEST accepting endpoint
    cands = [k for k in ("ing-01", "ing-02") if res.get(k) and str(res[k].get("status", "0")).startswith("2")]
    target_key = cands[0] if cands else "csp-01"
    tgt = res[target_key]["url"]
    out.append(f"# acceptance-ceiling probes target {tgt} (key={target_key})")
    res["oversize"] = post(tgt, OVERSIZED, "application/csp-report", "oversized ~66KB csp-report")
    res["oddtype"] = post(tgt, CSP_REPORT, "text/plain", "odd content-type text/plain csp-report body")
    res["node-retest"] = post("https://node.bolt.eu/app-log/node/csp/report",
                              CSP_REPORT, "application/csp-report", "node.bolt.eu sink re-test (baseline 200)")
    out.append("## call results")
    for k in ("csp-01", "ing-01", "ing-02", "csp-02", "oversize", "oddtype", "node-retest"):
        if res.get(k) is None:
            out.append(f"[{k}] skipped (not needed)"); continue
        out.append(f"[{k}] " + fmt_http(res[k]).splitlines()[0])
        for ln in fmt_http(res[k]).splitlines()[1:]:
            out.append("   " + ln)
    out.append("## payload shapes (synthetic, no PII)")
    out.append("csp-report json len=%d sha8=%s | ndjson len=%d sha8=%s | oversized len=%d sha8=%s" %
               (len(CSP_REPORT), sha8(CSP_REPORT), len(NDJSON), sha8(NDJSON), len(OVERSIZED), sha8(OVERSIZED)))
    txt = "\n".join(out) + "\n"
    open(os.path.join(REC, "b-applog-family.txt"), "w").write(txt)
    open(os.path.join(WORK, "b-applog-res.json"), "w").write(json.dumps(res, indent=2))
    print(txt)

def phase_menu():
    out = ["# LANE-47 ITEM (c) menu-food.prelive.bolt.eu oracle re-measure",
           "# baseline lane-35: GET /health -> 200, 0B, x-envoy-upstream-healthchecked-cluster: prelive-euc-1-public (vul_07a35e2d1001 MEDIUM)",
           "#                  control GET /api -> 401 Basic realm=\"Authentication Required\" 1394B sha8=42fe3df2",
           f"# generated {now_iso()}"]
    r1 = http_probe("https://menu-food.prelive.bolt.eu/health")
    r2 = http_probe("https://menu-food.prelive.bolt.eu/api")
    out.append(fmt_http(r1)); out.append("")
    out.append(fmt_http(r2)); out.append("")
    for r, name in ((r1, "/health"), (r2, "/api")):
        cl = ""
        m = re.search(r"(?im)^x-envoy-upstream-healthchecked-cluster:\s*(.+)$", r.get("headers_raw", ""))
        if m: cl = m.group(1).strip()
        out.append(f"ORACLE {name}: status={r.get('status')} cluster_header={cl or '(none)'}")
    txt = "\n".join(out) + "\n"
    open(os.path.join(REC, "c-menu-food-oracle.txt"), "w").write(txt)
    print(txt)

BASELINE_INTEL = [
    "beehive.bolt.eu", "beehive-bolt-eu.applog.bolt.eu", "beehive-csp.applog.bolt.eu",
    "node.bolt.eu", "food.bolt.eu", "static.bolt.eu", "images.bolt.eu", "admin.bolt.eu",
    "api.sinch.com", "boltint.net", "ingest.de.sentry.io", "ingest.sentry.io",
    "places.googleapis.com", "bolt.docebosaas.com", "cdn5.dcbstatic.com", "upload.taxify.eu",
    "bolt-verification-documents", "taxify-fleet", "bolt-voice-call-records", "s3-accelerate",
]

def phase_beehive():
    out = ["# LANE-47 ITEM (d) beehive.bolt.eu SNI-only vhost re-characterization — both live edges",
           "# baseline lane-35 (2026-10-01): both edges HTTP/2 200, etag e9db2e98f5973ed72e1d02ef890a651a,",
           "#   14174 B, body sha8=042c2c71, server envoy, S3-backed, byte-identical parity",
           f"# generated {now_iso()}"]
    bodies = {}
    for edge in ("172.65.240.204", "172.65.223.108"):
        r = http_probe("https://beehive.bolt.eu/", resolve=f"beehive.bolt.eu:443:{edge}")
        bf = os.path.join(WORK, f"b.txt")
        dst = os.path.join(WORK, f"beehive-{edge}.body")
        shutil.copyfile(bf, dst)
        bodies[edge] = open(dst, "rb").read()
        out.append(f"--- edge {edge}")
        out.append(fmt_http(r)); out.append("")
    b1, b2 = bodies["172.65.240.204"], bodies["172.65.223.108"]
    out.append(f"PARITY: edge-240.204 len={len(b1)} sha8={sha8(b1)} | edge-223.108 len={len(b2)} sha8={sha8(b2)} | identical={b1 == b2}")
    # NEW-INTEL: hostnames / S3 refs not present in the lane-35 baseline intel set
    blob = (b1 + b2).decode("utf-8", "replace")
    hosts = set(re.findall(r"(?:https?://|wss?://)?([a-z0-9][a-z0-9.-]*\.(?:bolt\.eu|boltint\.net|taxify\.eu|sinch\.com|sentry\.io|amazonaws\.com|s3[.-][a-z0-9.-]*|docebosaas\.com|dcbstatic\.com|googleapis\.com))",
                           blob, re.I))
    new = sorted(h for h in hosts if not any(b.lower() in h.lower() for b in BASELINE_INTEL))
    out.append("NEW-INTEL hostnames/S3 refs (vs lane-35 snapshot): " + (", ".join(new) if new else "NONE"))
    txt = "\n".join(out) + "\n"
    open(os.path.join(REC, "d-beehive-edges.txt"), "w").write(txt)
    print(txt)

if __name__ == "__main__":
    m = sys.argv[1]
    {"applog": phase_applog, "menu": phase_menu, "beehive": phase_beehive}[m]()
