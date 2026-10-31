---
title: HARDENING
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/pentagi/hardening
---

# PentAGI staging hardening — Docker socket isolation

Staging root: `D:\opt\pentagi` (Windows 11 estate VM, Docker Desktop).
Backup of the pre-hardening config: `.env.bak-hardening` (contains secrets — keep local, same ACL as `.env`).

## Why the Docker socket is the crown jewel here

`docker-compose.yml:206` mounts the engine socket into the PentAGI app ("worker")
container unconditionally:

```yaml
- ${PENTAGI_DOCKER_SOCKET:-/var/run/docker.sock}:/var/run/docker.sock
```

The app needs it to create the per-flow primary terminal (sandbox) containers.
That mount is trusted app code — agents never get a shell in the app container.
The question is whether the socket ever reaches the *sandbox* containers, where
agents download and execute arbitrary binaries. That is what `DOCKER_INSIDE`
controls (see the security note in `.env:255-261`, upstream issue #337).

## The escape chain this closes

On this box the configured engine backend is WSL2
(`AppData\Roaming\Docker\settings-store.json`: `WslEngineEnabled = True`),
i.e. the Docker daemon runs as root inside the Docker Desktop WSL2 utility VM.

1. **Agent downloads a binary.** A pentest/coder agent fetches and executes an
   arbitrary binary inside its sandbox container. This does not require a
   malicious agent — prompt injection from task text or from web content
   scraped mid-task is enough.
2. **Binary reaches the Docker socket.** With `DOCKER_INSIDE=true` the same
   engine socket is mounted into every sandbox. The Docker API is
   root-equivalent on the engine: create/exec containers, mount any path the
   engine can see.
3. **WSL2 VM escape.** From root-on-engine the binary spawns a privileged
   container or bind-mounts the VM root (`/`) into a fresh container and
   chroots into it — now it is root inside the Docker Desktop WSL2 VM.
4. **Mount `C:\`.** The WSL2 VM has the Windows drives shared into it — that is
   exactly the mechanism that makes `-v D:\opt\pentagi:/work` bind mounts work.
   Root in the VM reads/writes `C:\` and `D:\` through that share: estate
   secrets (`OPEN_AI_KEY`, `COOKIE_SIGNING_SALT`, vault, SSH material) and the
   rest of the single-owner host are gone.

Sandbox → socket → engine-root → WSL2 VM-root → `C:\` is four steps, all
mechanical, once the socket appears inside a sandbox.

## Settings that close it (current `.env`)

| Setting | Value | Effect |
|---|---|---|
| `DOCKER_INSIDE` | `false` (`.env:262`) | The socket is **not** mounted into agent sandboxes; step 1→2 is severed. |
| `DOCKER_NET_ADMIN` | `false` (`.env:263`) | Sandboxes get no `NET_ADMIN` capability (compose default is also false, `docker-compose.yml:188`): no interface/route/iptables tampering inside the isolation environment. |
| Two-node worker block | commented out (`.env:278-286`) | Documents the sanctioned way to give agents a Docker daemon — a disposable worker node over mTLS, never this host's engine. |

Two subtleties worth writing down:

- `DOCKER_SOCKET=/var/run/docker.sock` (`.env:264`) is **inert while
  `DOCKER_INSIDE=false`**. It matters only if DinD is ever re-enabled: per the
  `.env:268-270` comment, an explicit `DOCKER_SOCKET` takes precedence over
  `DOCKER_INSIDE_HOST` and is mounted into sandboxes *as before* — so enabling
  the two-node block without also clearing `DOCKER_SOCKET` would silently
  re-mount this host's socket and defeat the whole point.
- `AppData\Roaming\Docker\settings-store.json` shows
  `ExposeDockerAPIOnTCP2375 = True` on this VM: the engine API is additionally
  reachable unauthenticated on loopback `tcp://localhost:2375`. That is a
  host-side exposure independent of the sandbox chain (any host process can
  drive the engine). Not changed here — flip it off in Docker Desktop settings
  when no local tooling needs it.

## Tripwire: bring-up preflight

`bring-up.ps1` now refuses to start while `DOCKER_INSIDE` is truthy
(`1`/`t`/`true`, case-insensitive, per Go `strconv.ParseBool` semantics) in the
`.env` it is about to deploy — including inline-comment forms like
`DOCKER_INSIDE=true # ...`. A config regression cannot silently re-open the
chain; re-enabling DinD requires consciously editing the preflight. Run the
check alone with:

```powershell
powershell -File .\bring-up.ps1 -PreflightOnly
```

## Two-node worker config (worker_node guide pattern) — disabled

`.env:278-286` carries the commented block:

```
# DOCKER_INSIDE=true
# DOCKER_INSIDE_HOST=tcp://worker:2376
# DOCKER_INSIDE_TLS_VERIFY=true
# DOCKER_INSIDE_CERT_PATH=/opt/pentagi/worker-certs
```

- `DOCKER_INSIDE_HOST=tcp://worker:2376` — sandbox DinD traffic goes to a
  dedicated worker node's daemon; that also stops auto-mounting the host
  socket (unless `DOCKER_SOCKET` is set — see the subtlety above).
- `DOCKER_INSIDE_TLS_VERIFY=true` + `DOCKER_INSIDE_CERT_PATH` — mTLS required;
  the cert path is resolved on the worker node and bind-mounted read-only at
  the same path inside the container (`.env:271`).
- Blast radius if an agent pops that daemon: the worker VM, not this estate
  host. This deployment keeps the block commented; a two-node deployment lives
  where its own bring-up runs, and `bring-up.ps1` on this node still refuses
  `DOCKER_INSIDE=true`.
- Per the worker_node guide: workers reach the daemon over its **TLS endpoint**
  instead of a mounted socket — there is no mount to race on at startup, every
  request passes the daemon's authorization policy, and the client certificates
  are mounted read-only so an agent can use them but not rewrite them.

## Sanctioned alternative: remote engine over Tailscale

Run the engine — and therefore every sandbox — on a different machine; this VM
only drives it. `bring-up.ps1` already supports the override (header comment):

```powershell
$env:DOCKER_HOST = "tcp://100.x.y.z:2375"   # Tailscale IP of the remote docker host
.\bring-up.ps1
```

- The stack is deployed on the remote engine, so the socket mount at
  `docker-compose.yml:206` binds the *remote* engine's socket and all sandboxes
  are created there. An escape lands on the disposable remote host; `C:\` and
  `D:\` are never shared with anything the agent controls.
- `DOCKER_INSIDE` stays `false` — the remote engine is reached by the compose
  CLI, not by the sandboxes.
- The tailnet is the access control for the plaintext 2375 port. Prefer TLS:
  `DOCKER_HOST=tcp://100.x.y.z:2376` plus `DOCKER_TLS_VERIFY=1` and
  `DOCKER_CERT_PATH=...` in `.env` (`docker-compose.yml:184-186` wires these to
  the app container's client).

## Verification state at time of writing

- `.env` block re-read after edit (lines 262-264, 278-286 above) — verified.
- `docker compose config` on the edited `.env` and the preflight tests — run
  commands and outputs are in the hardening change record; engine was
  unhealthy (HTTP 500 on the Desktop engine pipe) during this session, which
  affects nothing above: the chain is grounded in the configured backend
  (`WslEngineEnabled=True`), and `wsl.exe -l -v` reporting no registered
  distros while `%LOCALAPPDATA%\Docker\wsl\main\ext4.vhdx` exists matches the
  engine being down, not a different backend.