# Research notes: pentagi-hardening (PentAGI two-node worker hardening)

Date: 2026-09-29. Researcher lane: "pentagi-hardening".
All local artifacts downloaded under `out/research/` (worker_node.md, worker_node/ bundle of 12 files, client_go_main.go, client_go_v210.go, docker-compose.yml (main + v2.1.0), env_example.txt (main + v2.1.0), pentagi_readme.md, backend_docker_doc.md, cve_cveawg.json, cve_nvd.json, cve_14784.json, exploit_readme.md).

## Executive summary

- PentAGI (`vxcontrol/pentagi`, 25,108★, pushed 2026-09-23, MIT) shipped a full **two-node worker hardening guide** (`examples/guides/worker_node.md` + a 12-file config bundle) worked on 2026-07-29 → 2026-08-01 — i.e. immediately around the CVE disclosures. The guide replaces the dangerous "bind-mount the docker socket into every sandbox" pattern with: worker node host-docker on **TLS :2376**, a hardened **Docker-in-Docker on TLS :3376** policed by an **OPA authorization plugin (fail-closed)** + daemon-wide **seccomp profile** that blocks block-device `mknod`.
- The socket-escape the ask refers to is real and **two CVEs**, both affecting PentAGI ≤ 2.1.0, both filed by the same researcher (ez-lbz):
  - **CVE-2026-14784** (VulDB 376374, pub 2026-07-06, CVSS4.0 5.3 / CVSS3.1 6.3): the DOCKER socket bind-mount sandbox escape itself — `backend/pkg/docker/client.go`, references issue #337 + PR #355.
  - **CVE-2026-18593** (VulDB 385421, pub 2026-08-03, CVSS4.0 6.3 / CVSS3.1 5.6): `backend/pkg/templates/prompts/pentester.tmpl` tool-management — no guard against executing target-served foreign binaries → sandbox RCE, which in the public PoC chains with the socket escape to reach the **Windows host** via Docker Desktop's `/run/desktop/mnt/host/`.
- **Fixes verified in code**: v2.1.0 `client.go:282-284` unconditionally bind-mounts `dc.socket` when `dc.inside`; **main** branch `client.go:337-351` mounts only when `dc.socket != ""`, else injects `DOCKER_INSIDE_HOST/_TLS_VERIFY/_CERT_PATH` as `DOCKER_HOST/...` env + read-only cert bind-mount. `DOCKER_INSIDE` default flipped `true` (v2.1.0 `.env.example:216`) → `false` (main `.env.example:262`, compose line 187). PR #355 (no-new-privileges, PidsLimit=2048, CapDrop ALL on tools) merged 2026-07-29; PRs #356 (docker-socket-proxy) and #394 (Deaf Guard classifier) closed **unmerged**. No tagged release after v2.1.0 yet → **the fixed code is only on `main`**.
- **Estate applicability (verified locally)**: Docker CLI 29.8.1 is installed but the engine is down (`docker info` → `ERROR: request returned 500 ... dockerDesktopLinuxEngine`; `wsl -l -v` → no installed distributions). PentAGI ships a Windows amd64 installer (README:591, pentagi.com/downloads/windows/amd64/installer-latest.zip) but still needs a working Linux Docker engine, which this GCP VM cannot provide without VT-x. Recommendation for the estate: run PentAGI main-branch on a Linux worker node (the guide's model), keep `DOCKER_INSIDE=false` or point it at a hardened dind TLS endpoint, never mount a socket.

## 1. PentAGI repo state (verified via gh api)

`gh api repos/vxcontrol/pentagi` → created 2025-01-06, MIT, 25,108★, 3,231 forks, 14 open issues, pushed 2026-09-23, homepage pentagi.com, default branch `main`. Releases: v2.1.0 (2026-05-29, latest), v2.0.0, v1.2.0, v1.1.0, v1.0.1, v1.0.0, v0.3.0, v0.2.0. Topics include offensive-security, autonomous-agents, penetration-testing.

`gh api repos/vxcontrol/pentagi/security-advisories` → **empty** (no GHSA advisories; CVEs exist only via VulDB/CVE records).

Guide history (`gh api 'repos/vxcontrol/pentagi/commits?path=examples/guides/worker_node.md'`):
- b90ea471 2026-03-26 "repo final state"
- 464dca89 2026-07-29 "feat(worker_node): enhance Docker-in-Docker setup with security and cleanup features"
- c383086a 2026-07-30 "refactor(worker_node): improve worker node guide and policy test script"
- 341a9def 2026-08-01 "feat(worker_node): add browser scraper deployment instructions"
- f6fe867a 2026-08-01 "feat(worker_node): enhance monitoring setup and documentation"

## 2. The two CVEs and the public exploit chain

### CVE-2026-18593 (out/research/cve_cveawg.json, out/research/cve_nvd.json)
- CNA: VulDB. Title: "vxcontrol PentAGI Tool Management Protocol pentester.tmpl sandbox". CWE-265 (Sandbox Issue) + CWE-264. Affects vendor vxcontrol / product PentAGI versions 2.0, 2.1.0 ("up to 2.1.0"), module "Tool Management Protocol Handler", file `backend/pkg/templates/prompts/pentester.tmpl`.
- Desc: remote, high complexity, "exploit has been made available to the public", "vendor was contacted early about this disclosure but did not respond in any way". CVSS4.0 6.3 MEDIUM (AV:N/AC:H/AT:N/PR:N/UI:N/VC:L/VI:L/VA:L/E:P), CVSS3.1 5.6. NVD status: **Deferred**.
- References: vuldb.com/vuln/385421, vuldb submit 851348 ("vxcontrol PentAGI <=v2.1.0 rce + docker escape"), **github.com/ez-lbz/pentagi-vul-report** (exploit).

### CVE-2026-14784 (out/research/cve_14784.json; DDG surfaced basefortify.eu report)
- Title: "vxcontrol PentAGI Docker API client.go sandbox". Same VulDB CNA, published 2026-07-06, same affected versions (2.0, 2.1.0). CVSS4.0 5.3 (AV:N/AC:L/PR:L), CVSS3.1 6.3. References: vuldb 376374, **github.com/vxcontrol/pentagi/issues/337**, **pulls/355**. "The pull request to fix this issue awaits acceptance" (at publication).
- basefortify.eu summary (WebFetch): mitigations listed = `DOCKER_INSIDE=false`, least-privilege socket proxy, rootless/sysbox dind, apply PR #355 hardening; noted PR #355 alone is defense-in-depth, not root cause.

### The public exploit (out/research/exploit_readme.md, ez-lbz/pentagi-vul-report, created 2026-06-08, 0★)
"PentAGI: Binary Execution + Docker Socket Exposure Enables Windows Host Compromise", targets PentAGI 2.1.0:
1. **Vuln 1** — `pentester.tmpl` lines 338-350 constrain package-manager use but not `curl`+`chmod`+execute of foreign binaries. PoC: target-served 503 page tells the agent to fetch a "VPN client"; agent spends 8 min on static analysis (`file`/`strings`/hexdump — strings XOR-encrypted), then runs it → reverse shell in sandbox.
2. **Vuln 2** — `backend/pkg/docker/client.go:282-284`: `if dc.inside { hostConfig.Binds = append(..., dc.socket, defaultDockerSocketPath) }` mounts the host Docker socket into every per-flow sandbox. Escape: `docker run --rm --privileged -v /:/host debian ls /host/run/desktop/mnt/host/c/Users/` → **read/write C:\Users on the Windows host** (Docker Desktop WSL2 mounts Windows drives at `/run/desktop/mnt/host/`). No privesc needed between steps.
- Repo also carries app.py / check_server.py (compiles obfuscated Go reverse-shell at startup) / rev.py / video-poc.mkv.
- Vendor tracking: issue **#337** "[Bug]: PentAGI Container Escape via Prompt Injection" by ez-lbz, opened 2026-06-05, closed 2026-09-23 (same day as last push).

### Verified fix state (code diff, downloaded and inspected)
- **v2.1.0** `client.go:282-284` (out/research/client_go_v210.go): unconditional socket bind — the vulnerable code, exactly as reported.
- **main** `client.go` (out/research/client_go_main.go, 1331 lines vs 855): `:337-342` binds socket only `if dc.socket != ""` with comment "The socket is empty when DOCKER_INSIDE_HOST designates a daemon endpoint instead; binding \"\" would produce a malformed mount spec"; `:345` injects `dc.insideEnv` (DOCKER_HOST/TLS_VERIFY/CERT_PATH, `_INSIDE_` dropped); `:347-351` mounts cert dir read-only at identical path. `:147-151` skips socket autodetect when `DOCKER_INSIDE_HOST` set; `:151+` warns when DOCKER_INSIDE=true with neither set.
- **Defaults**: v2.1.0 `.env.example:216` = `DOCKER_INSIDE=true # enable to use docker socket` (this is the shipped "default true" the exploit means; v2.1.0 compose line 165 was already `${DOCKER_INSIDE:-false}`). Main `.env.example:262` = `DOCKER_INSIDE=false` + security note at :255; main compose :187 `${DOCKER_INSIDE:-false}`; main `.env.example:266-275` adds DOCKER_INSIDE_HOST/_TLS_VERIFY/_CERT_PATH block.
- **PRs**: #355 "fix(sandbox): harden sandbox containers against privilege escalation" **merged 2026-07-29** (no-new-privileges:true, PidsLimit=2048, CapDrop ALL + NET_RAW/NET_ADMIN on tools containers, boot warning; PR body itself states nnp does NOT close the socket vector). #356 "add docker-socket-proxy to restrict DinD API access" **closed unmerged**. #394 "Deaf Guard pre-execution command classification" (9-tier regex log/warn/block on terminal tool calls) **closed unmerged**. No release tag after v2.1.0 carries these fixes.

## 3. worker_node.md — the two-node hardening guide (out/research/worker_node.md, 900 lines)

Architecture (mermaid at :7-41): Main node PentAGI container → TLS → worker-node **host Docker :2376** (creates `pentagi-terminal-N` workers) → workers reach **dind :3376 TLS** (`DOCKER_INSIDE_*`) → nested containers. Alternative "Direct" mode: PentAGI → dind directly; workers become nested containers, policy denies host bind-mounts ⇒ Docker Access must be off and Work Directory empty (Docker volume).

**Why TLS instead of a mounted socket (:47-57)** — earlier guide revisions mounted `/var/run/docker-dind/docker.sock`:
- *Boot-order race*: missing bind-mount source is materialized as a **directory** by Docker; after reboot a worker (restart=on-failure) can start before dind, breaking the daemon until manual fix.
- *Blast radius*: avoiding the race requires mounting the **host** daemon socket — hands an autonomous agent the node: privileged container + mount `/` ⇒ full takeover. "That is precisely the risk this two-node architecture exists to remove." TLS endpoint: no mount race, every request passes the dind authz policy, client certs mounted read-only.
- `DOCKER_SOCKET` "remains supported for single-node setups where the host daemon is already trusted, but it is not recommended here" (:57).

**dind hardening — 3 independent layers (:215-224, :336-359)**:
1. *Container*: no `--privileged`; `--cap-drop ALL` then add back exactly what dockerd needs — SYS_ADMIN, NET_ADMIN, NET_RAW, SETUID, SETGID, MKNOD, FOWNER, DAC_OVERRIDE, CHOWN, AUDIT_WRITE, KILL, SYS_CHROOT, FSETID, SETFCAP, SETPCAP, NET_BIND_SERVICE (verified in run-dind.sh:141-157); resource limits CPU 2 / MEM 4G / PIDS 2048 (:312); dind itself runs `--security-opt seccomp=unconfined` (unavoidable for dind, run-dind.sh:160).
2. *Daemon API*: **OPA authorization plugin** (`opa-docker-authz`) as a managed plugin INSIDE dind, `--authorization-plugin`, **fail-closed** (`default allow = false`, authz.rego:43). Controlled endpoints (authz.rego:25-39): containers/create + exec (policy-checked), containers/update (DeviceCgroupRules), containers/archive GET (denied — PKI extraction), commit/build/session(images load)/plugins/swarm (denied outright), volumes/create (bind-emulation driver opts), networks/create (macvlan/ipvlan). Denied for nested containers (worker_node.md:342-353): `--privileged`, cap-add outside whitelist, `--device`/device-cgroup-rules, `--security-opt`, `--pid/--ipc/--userns/--cgroupns/--uts` sharing, MaskedPaths/ReadonlyPaths overrides (→ modprobe_path escape), **all host bind-mounts**, `--sysctl`, DeviceRequests, non-runc runtime, CgroupParent, docker cp/commit/build/image load/plugin install/Swarm, bind-emulating volumes, L2 networks. Allowed: default caps + NET_ADMIN/NET_RAW, named/anonymous volumes, tmpfs, pull, lifecycle, bridge + `--network host` (intentional — pentest tools need raw sockets; warning at :359 never to keep outer-daemon client certs or plaintext HTTP file servers on the worker node).
3. *Kernel*: daemon-wide `seccomp.json` via dind `daemon.json` `{"seccomp-profile": "/etc/docker/seccomp.json"}` — `defaultAction: SCMP_ACT_ERRNO`, 41 rules; `mknod`/`mknodat` allowed **only** for S_IFCHR/S_IFREG/S_IFIFO/S_IFSOCK via SCMP_CMP_MASKED_EQ on the mode argument (mask 0xF000); **S_IFBLK (block devices) falls through to ERRNO** — kills `mknod /dev/sda b 8 0` + debugfs raw-host-disk reads. Dual enforcement because CAP_MKNOD cannot be dropped from Docker's default set (worker_node.md:357); authz.rego also blocks `--cap-add MKNOD` and every `--security-opt` override so the profile can't be replaced. authz.rego header honestly notes it is a **deny-list**, "only as strong as its completeness … For a kernel-enforced guarantee, use dind-rootless" (authz.rego:18-21).

**TLS pattern**: two **separate easy-rsa PKIs** (host :100-137, dind :228-263 — "must not share a CA"); SANs localhost/127.0.0.1/${PRIVATE_IP}; `sudo -E` needed so EASYRSA_EXTRA_EXTS survives (:140); host daemon.json `tls+tlsverify` + `-H tcp://${PRIVATE_IP}:2376` (:148-174); dind listens `${PRIVATE_IP}:3376` (must differ from 2376 because `--network host`, :316); entrypoint (dockerd-entrypoint.sh:170-177) runs dockerd `--host=$DOCKER_API_HOST --tlsverify --tlscacert/--tlscert/--tlskey`. Client wrappers `docker-host-tls` / `docker-dind-tls.sh` set DOCKER_HOST/DOCKER_TLS_VERIFY/DOCKER_CERT_PATH.

**Operational pieces**: policy hash recorded in `/var/lib/docker-dind/.authz-policy-hash`; on change run-dind restarts WITHOUT authz, force-removes ALL nested containers, restarts with new policy (old HostConfigs would survive with superseded privileges, :363); `dind-cleanup` systemd timer removes nested containers older than MAX_AGE_HOURS (24); `dind-policy-tests` = 68KB isolation suite run from a kali container wired exactly like a real worker (env-supplied TLS endpoint, no socket mount, :398-418) — positive tests (nmap/masscan/sqlmap/nginx/volumes/lifecycle) and negative tests (privileged, dangerous caps, host namespaces, bind-mounts, block mknod, nsenter); "A failed negative test is an isolation gap; a failed positive test is a false positive".

**Other worker-node services**: scraper (Browserless+Chrome, Basic Auth over self-signed HTTPS :9443, --shm-size 2g, cap-drop-all + minimal adds, no-new-privileges, off host network); cAdvisor :8080 (needs /var/run rw — socket-trust level, keep on 127.0.0.1) and node-exporter :9100. Port table (:688-698): 2376/3376/9443 on PRIVATE_IP (main-node only!), 9323/9324/8080/9100 metrics on METRICS_IP (default 127.0.0.1), OOB range 28000-30000 (2 ports/worker).

**Cert discipline (:846-855)**: host-daemon client certs live on the MAIN node (`/opt/pentagi/docker-host-ssl`); dind client certs stay at `/etc/docker/dind/certs/client` on the WORKER node; "Never point Worker Docker Certificate Path at /etc/docker/certs/client … handing them to an agent grants it the host Docker API on :2376, which defeats the entire isolation model".

**Canonical main-node .env (:871-890)**: `DOCKER_HOST=tcp://IP:2376`, `DOCKER_TLS_VERIFY=1`, `PENTAGI_DOCKER_CERT_PATH=/opt/pentagi/docker-host-ssl`, `DOCKER_INSIDE=true`, `DOCKER_SOCKET=` (empty), `DOCKER_INSIDE_HOST=tcp://IP:3376`, `DOCKER_INSIDE_TLS_VERIFY=1`, `DOCKER_INSIDE_CERT_PATH=/etc/docker/dind/certs/client`, SCRAPER urls, `DOCKER_NET_ADMIN=true`, `DOCKER_NETWORK=pentagi-network`, `DOCKER_PUBLIC_IP=IP`.

## 4. backend/docs/docker.md resolution algorithm (out/research/backend_docker_doc.md)

Two separate questions (:207-208): which daemon **PentAGI** creates workers on (DOCKER_HOST/_TLS_VERIFY/_CERT_PATH) vs which daemon a **worker container** may talk to (DOCKER_INSIDE/_SOCKET/_INSIDE_HOST/_INSIDE_TLS_VERIFY/_INSIDE_CERT_PATH). `DOCKER_INSIDE=false` (envDefault, :121) ⇒ sandbox gets no Docker at all. With it true: `DOCKER_SOCKET` set → that socket bind-mounted; `DOCKER_SOCKET` empty + `DOCKER_INSIDE_HOST` set → no mount, env injected (DOCKER_INSIDE_HOST=tcp://10.0.0.5:3376 → DOCKER_HOST inside worker, :235-237); cert path additionally bind-mounted ro (:239). Same socket-mount critique repeated (:255-261).

## 5. Safe single-node configs (synthesis of README:661-696 + guide)

1. **Safest**: `DOCKER_INSIDE=false` (now the shipped default) — agents get no Docker in-sandbox; everything else works.
2. **Agents-with-Docker, recommended**: `DOCKER_INSIDE=true`, `DOCKER_SOCKET` empty, `DOCKER_INSIDE_HOST=tcp://<host>:3376` → hardened dind TLS endpoint (README:677-687 gives the 4-line config). Works single-node too (dind on the same box).
3. **Discouraged**: `DOCKER_SOCKET=/var/run/docker.sock` — "only on single-node development setups where the host daemon is already trusted" (README:694, guide :57).
4. Defense-in-depth on any node: PR #355 hardening (nnp, PidsLimit, CapDrop ALL), never store outer-daemon client certs on a node reachable from nested `--network host` containers.
5. **Trap found**: the official docs site (vxcontrol-pentagi.mintlify.app/deployment/worker-node, WebFetch) still describes the **old** layout — Standard Mode "workers use dind via socket mapping /var/run/docker-dind/docker.sock" and "dind launched `--privileged`", no OPA/seccomp mention. The repo guide + code are newer and authoritative; do not copy the docs-site pattern.

## 6. Estate applicability (checks run on this VM)

- `docker --version` → "Docker version 29.8.1, build 4a63305" (CLI present; context desktop-linux; Docker agent plugin v1.141.0).
- `docker info` → "ERROR: request returned 500 Internal Server Error … dockerDesktopLinuxEngine pipe … check if the server supports the requested API version" → **engine down**.
- `wsl -l -v` → "Windows Subsystem for Linux has no installed distributions" → no WSL2 backend, consistent with ask's "GCP no VT-x"; `systeminfo` → "A hypervisor has been detected" (GCP) but VBS not enabled.
- Conclusion: PentAGI (docker-compose based; Windows installer exists at README:591 but still requires a Linux Docker engine) **cannot run on this VM today**. The staged "docker-pending" plan should target a Linux worker node (or a future nested-virt window). Meanwhile the hardening knowledge transfers: the MCP gateway's own stdio workers, and any future engine on this box, should adopt the same deny-list authz + seccomp + no-socket-mount discipline. Also note the exploit's Windows-specific impact (Docker Desktop `/run/desktop/mnt/host/`) is exactly the risk profile if Docker Desktop ever comes up here.
- Ollama qwen3:4b: PentAGI supports Ollama (README:1592 notes it needs custom models with larger context windows than default).

## 7. Tools identified

| Tool | Repo | Role in this pattern | Windows w/o Docker | Estate value |
|---|---|---|---|---|
| PentAGI | github.com/vxcontrol/pentagi | The platform itself; main branch carries all post-CVE fixes | No (needs engine) | high |
| worker_node bundle | …/pentagi/tree/main/examples/guides/worker_node | Turnkey hardened-dind pattern (authz.rego, seccomp.json, run-dind, policy-tests) | No (systemd+Linux) | high |
| opa-docker-authz | github.com/open-policy-agent/opa-docker-authz (106★, pushed 2026-09-28) | The Docker authorization plugin the guide bootstraps into dind | No (Linux daemon plugin) | high |
| docker-socket-proxy | github.com/Tecnativa/docker-socket-proxy (2,804★, pushed 2026-08-31) | Env-var allowlist proxy in front of a socket (unmerged PR #356 approach) | No (Linux container) | medium |
| Sysbox | github.com/nestybox/sysbox (3,885★, pushed 2026-09-15) | runc replacement: unprivileged dind, kernel-enforced isolation | No (Linux runtime) | medium |
| gVisor | github.com/google/gvisor (19,455★, pushed 2026-09-29) | runsc application kernel; strongest sandbox for nested containers | No (Linux runtime) | medium |
| docker-bench-security | github.com/docker/docker-bench-security (9,699★) | CIS Docker benchmark audit for the future engine/worker node | No (audits Linux daemon) | medium |
| pentagi-vul-report | github.com/ez-lbz/pentagi-vul-report | The PoC (fake target + obfuscated Go payload + listener) to validate staging before deploy | Partial (python PoC side runs natively) | medium |

Rootless Docker (`dockerd-rootless`, dind-rootless image) — recommended by authz.rego:18-21 as the kernel-enforced alternative — is docs/pattern, not a separate tool repo (moby/moby). Blacktop/seccomp-gen (49★, stale 2021) noted, low value. Awesome-security walk surfaced only docker-bench-security as relevant (entries for gvisor/sysbox absent from that list).

## 8. Query log (everything issued this session)

GitHub API (gh): search/repositories q=pentagi (50); repos/vxcontrol/pentagi; contents/examples/guides; contents/examples/guides/worker_node; git/trees/main recursive (filtered worker|seccomp|docker-inside); commits?path=examples/guides/worker_node.md; releases; issues?state=all; issues/337; pulls/356; pulls/355; pulls/394; security-advisories; repos/ez-lbz/pentagi-vul-report + contents + commits + readme; repos/Tecnativa/docker-socket-proxy; repos/open-policy-agent/opa-docker-authz (+readme); repos/nestybox/sysbox; repos/google/gvisor; repos/docker/docker-bench-security; repos/sbilly/awesome-security (+readme grep); repos/reddelexc/hackerone-reports; repos/0x4D31/awesome-awesome-security (404); topic sweep: `topic:docker-security+topic:hardening`, `docker-in-docker+hardening`, `dind+rootless`, `docker+seccomp+profile+generator`, `pentagi+hardening`, `docker+socket+escape+protection` (last returned zero items).
curl raw.githubusercontent: worker_node.md; README.md; 12× worker_node/* files; client.go (main+v2.1.0); docker-compose.yml (main+v2.1.0); .env.example (main+v2.1.0); backend/docs/docker.md; ez-lbz README (raw failed exit 23 twice → gh api readme instead). curl CVE APIs: cveawg.mitre.org CVE-2026-18593 + CVE-2026-14784; services.nvd.nist.gov CVE-2026-18593.
Exa (worked, key present): 'PentAGI worker node docker-in-docker hardening TLS OPA seccomp'; 'docker-socket-proxy restrict docker API allowlist tecnativa'; 'rootless docker-in-docker nested containers kernel isolation security'; 'OPA docker authorization plugin opa-docker-authz policy examples'; 'sysbox runtime secure docker-in-docker without privileged'; 'PentAGI installer Windows support platform requirements'; 'safe single-node PentAGI deployment DOCKER_INSIDE false'.
Firecrawl: /v1/search "CVE-2026-18593 PentAGI" → **HTTP 401 — FIRECRAWL_API_KEY in env is an unexpanded placeholder string `${FIRECRAWL_API_KEY}` (len 20), same for FIRECRAWL_API_KEY_2/TAVILY keys; unusable this session**. Worked around with Exa + ddgs + WebFetch.
DDG (ddgs 9.16.0): 'CVE-2026-18593'; 'PentAGI DOCKER_INSIDE docker socket escape'; 'PentAGI worker node hardening'; 'docker-in-docker TLS 2376 OPA authorization seccomp'; 'PentAGI 加固 docker 沙箱逃逸'; 'PentAGI 脆弱性 CVE-2026'; 'PentAGI docker socket エスケープ'.
WebFetch: vxcontrol-pentagi.mintlify.app/deployment/worker-node; basefortify.eu/cve_reports/2026/07/cve-2026-14784.html.
Local: docker --version/info; wsl -l -v / --status; systeminfo (virt lines); env key inspection; pip show ddgs.

## 9. Dead ends / gaps

- Firecrawl + Tavily keys broken (placeholders) — Firecrawl scrape of vuldb.com/vuln/385421 not done; vuldb reached only via MITRE/NVD mirrors and DDG snippets. VulDB full CTI page not read (permissions-required tag).
- `gh search 'docker+socket+escape+protection'` returned zero items (query phrasing too narrow).
- No GHSA advisories from vxcontrol; vendor "did not respond" to VulDB disclosure per CNA text; no post-2.1.0 release tag, so consumers pinned to releases are still exposed.
- Docs site (mintlify) is stale (socket-mapping + --privileged dind) — flagged above, not otherwise deep-read.
- Not run: any live PentAGI deployment/test (no engine on this VM) — all findings are from source/docs/CVE records read this session.
