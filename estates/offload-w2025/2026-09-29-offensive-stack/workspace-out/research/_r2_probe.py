import asyncio, json, os, re, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

OUT = r"out\research\_r2_probe"
os.makedirs(OUT, exist_ok=True)

# filler values by fuzzy arg-name match
def filler(name):
    n = name.lower()
    if "url" in n: return "http://twd6bfktqvwshbzykcncm3m7wwgitpuhjsnsfcdrrwzuyd7gjhtp4vcad.onion"
    if "query" in n or "search" in n or "term" in n or n in ("q",): return "lockbit"
    if "group" in n or "name" in n: return "lockbit3"
    if n == "ip": return "185.243.218.225"
    if "address" in n: return "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    if "domain" in n: return "example.com"
    if "hash" in n or n=="tx": return "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
    if "cve" in n: return "CVE-2021-44228"
    if "password" in n: return "P@ssw0rd"
    if "account" in n or "email" in n or "username" in n: return "test@example.com"
    if "country" in n: return "US"
    if "sector" in n or "industry" in n: return "Healthcare"
    if "value" in n or "indicator" in n: return "1.1.1.1"
    if "id" in n: return "CVE-2021-44228"
    if "limit" in n or "count" in n or "days" in n: return 5
    if "malware" in n or "tag" in n or "threat" in n: return "zeus"
    return "test"

PROBES = {
  "tor_fetch_onion": {}, "tor_scrape_onion": {}, "tor_search_onion": {},
  "tor_exit_nodes": {}, "tor_exit_check": {}, "tor_exit_details": {},
  "ransomwareGroup": {}, "ransomwareGroupVictims": {}, "ransomwareSearch": {},
  "ransomwareByCountry": {}, "ransomwareBySector": {}, "ransomlookGroups": {},
  "breachList": {}, "breachGet": {}, "breachLatest": {}, "breachDataClasses": {},
  "breachPassword": {}, "breachSearch": {}, "breachPastes": {},
  "greynoise_check": {}, "pulsedive_indicator": {}, "pulsedive_search": {}, "pulsedive_explore": {},
  "otx_ip": {}, "otx_domain": {}, "otx_hash": {}, "otx_cve": {}, "otx_search_pulses": {},
  "btc_address": {}, "btc_balance": {}, "btc_tx": {},
  "malware_search": {}, "malware_overview": {}, "malware_feed": {},
  "phishing_check": {}, "vulners_id": {}, "vulners_exploit": {},
  "onion_lookup": {}, "btc_abuse_check": {}, "urlhausLookup": {}, "bazaarHash": {},
  "abuseipdb_check": {}, "intelx_phonebook": {}, "stealer_ip": {}, "threatfoxGetIocs": {},
}

REQ_RE = re.compile(r"Required at ([a-zA-Z_]+)")

async def one(s, tool, args):
    try:
        res = await s.call_tool("harness_invoke", {"backend":"darknet","tool":tool,"arguments":json.dumps(args)})
        return res.content[0].text
    except Exception as e:
        return f"EXC: {e}"

async def main():
    async with streamablehttp_client("http://127.0.0.1:31100/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            summary = {}
            for tool, args in PROBES.items():
                args = dict(args)
                for attempt in range(3):
                    txt = await one(s, tool, args)
                    m = REQ_RE.search(txt)
                    if m:
                        args[m.group(1)] = filler(m.group(1))
                        continue
                    break
                with open(os.path.join(OUT, tool + ".json"), "w", encoding="utf-8") as f:
                    f.write(txt)
                try:
                    j = json.loads(txt)
                    ok = j.get("ok")
                    res = str(j.get("result", ""))[:110].replace("\n", " ")
                    err = "" if ok else ""
                except Exception:
                    ok = "?"; res = txt[:110].replace("\n", " ")
                summary[tool] = f"{'LIVE ' if ok else 'FAIL'} {res}"
                print(f"{tool:28s} {'LIVE ' if ok else 'FAIL'} {res}")
            with open(os.path.join(OUT, "_summary.json"), "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=1)

asyncio.run(main())
