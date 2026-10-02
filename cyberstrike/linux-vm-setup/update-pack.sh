#!/bin/bash
set -e
# MCP helper into the agent pack
cp /tmp/mcp_probe.py /opt/agent-pack/mcp-gateway-helper.py 2>/dev/null || true

cat > /opt/agent-pack/README-INTEL.txt << 'EOF'
=== ENGAGEMENT INTEL & TOOLING IN THIS SANDBOX ===

-- INTEL --
/work/bolt-intel/         curated pack: SSOT_2026-09-06.md (Databricks PATs, JWTs, AWS keys, staff),
                          AUTHORIZATION.md (full force, no exclusions), ASSESSMENT-PLAN-SOTA.md,
                          LANE-REGISTER.md (measured-dead lanes, re-testable), INDEX.md, config.md, schema JSONs
/work/intel-core/         bolt core: credentials/ (52M), _org_tmp/, admin-crack-2026-09-19/
/work/intel-manifest.txt  manifest of the FULL 12G staged archive (enum pulls, Bolt GitHub source,
                          databricks-harvest, cowork research) — ask the flow operator to inject
                          specific paths into /work/on-demand/ when needed

The task prompt's /opt/bolt/ mount == /work/bolt-intel/ here.

-- ESTATE MCP GATEWAY (59-backend cyberstrike arsenal) --
Endpoint: http://172.17.0.1:31100/mcp   (StreamableHTTP JSON-RPC; loopback-tunneled, private)
Tools:
  harness_capabilities  {}                     -> full live backend manifest (names + honest availability)
  harness_invoke        backend, tool, args    -> dispatch ANY backend tool through the gateway
  harness_bridge_status {}                     -> gateway self-status
Backends include: metasploit (msgrpc), darknet/deep-web intel, burp, Nuclei/shodan-class recon,
RE bridges, cloud audit lanes, and more — ALWAYS run harness_capabilities first to get the live list.
Helper: /work/mcp-gateway-helper.py (python3, shows init + tools/list). Example invoke:
  harness_invoke {"backend":"<name-from-capabilities>","tool":"<tool>","arguments":"{...}"}
Auth: none needed from inside the sandbox (source IP allow-listed via the tunnel).

-- LOCAL KALI TOOLSET --
nmap masscan amass subfinder httpx naabu katana nuclei sqlmap ffuf gobuster dirsearch wpscan nikto
whatweb theHarvester crackmapexec netexec(nxc) evil-winrm impacket responder mitmproxy proxychains4
tor testssl exiftool volatility3 sherlock holehe massdns pypykatz john hashcat hydra medusa radare2
binwalk foremost + seclists wordlists (in /usr/share/).

Every command you run should tee evidence:  <cmd> 2>&1 | tee -a /work/evidence/<lane>.log
EOF

# Reinject README + helper into the LIVE flow volume
V=/var/lib/docker/volumes/pentagi-terminal-5-data/_data
cp /opt/agent-pack/README-INTEL.txt $V/README-INTEL.txt
cp /opt/agent-pack/mcp-gateway-helper.py $V/ 2>/dev/null || true
mkdir -p $V/evidence
chmod -R a+rwX $V 2>/dev/null || true
ls $V/
