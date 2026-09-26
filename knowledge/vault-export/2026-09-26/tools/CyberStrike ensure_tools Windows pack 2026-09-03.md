---
title: CyberStrike ensure_tools Windows pack 2026-09-03
type: note
permalink: main/tools/cyber-strike-ensure-tools-windows-pack-2026-09-03
tags:
- decision
- fact
- cyberstrike
- ensure-tools
---

# CyberStrike ensure_tools Windows pack 2026-09-03

- [decision] G-5 B: install the CyberStrike `ensure_tools` allowlist on this Windows host now (not HexStrike's 127-tool catalog). Bolt (G-3 B) still deploys after the grill.
- [fact] 21/22 OK. Receipt `D:\\opt\\cs-tools\\ensure-tools-receipt.json`. Wrappers/binaries in `C:\\Users\\Prekzursil\\.local\\bin`. Python clones under `D:\\opt\\cs-tools\\src`.
- [fact] Renamed `C:\\Python314\\Scripts\\httpx.exe` to `httpx-python.exe` so ProjectDiscovery `httpx` in `.local\\bin` is what `httpx` resolves to. Python library `import httpx` unchanged.
- [fact] Added: hakrawler, dalfox, gospider, crlfuzz (go), arjun/paramspider/git-dumper (pipx), commix/ssrfmap (git+cmd), nikto 2.6.1 (Strawberry Perl + XML::Writer), wpscan 4.1.0 (scoop ruby + ridk MSYS2 + libcurl.dll alias).
- [fact] FAIL: nosqlmap — codingo/NoSQLMap is Python 2 only (`print` statements). Wrapper exists but SyntaxError on 3.14.
- [fact] HexStrike `/health?full=1` still ~24/127 available; G-5 did not try to fill that catalog.

Related: [[Grok PR 310 search-hub live 2026-09-03]] [[CyberStrike MCPs restored 2026-09-02]]