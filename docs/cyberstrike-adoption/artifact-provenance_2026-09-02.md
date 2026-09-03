# Windows-native CyberStrike adoption artifact provenance

Date: 02.09.2026  
Status: disk-verified staging evidence; installation and runtime acceptance are separate gates.

This receipt records immutable inputs for the Windows-native CyberStrike, Metasploit,
and Bolt rollout. It contains no authorization grant and does not enable active testing.
Sliver, payload handlers, reverse shells, Meterpreter command channels, persistence,
credential harvesting, and all other C2-equivalent paths remain hard denied.

## CyberStrike 1.1.16

- Package: `@cyberstrike-io/cyberstrike@1.1.16`
- License metadata: `AGPL-3.0-only`
- Registry tarball: `https://registry.npmjs.org/@cyberstrike-io/cyberstrike/-/cyberstrike-1.1.16.tgz`
- Registry/packed/computed SRI: `sha512-Yf4fb54n6Apw7qZZFNG32Ok6aMBcfIW+OzvUHovsW/ImP/ETRHdX90ZjFT24/UFgmdYqNy+x9T0dF6yI451FQA==`
- Windows package: `@cyberstrike-io/cyberstrike-windows-x64@1.1.16`
- Windows package registry/packed/computed SRI: `sha512-XbmvwTCtncxnRUh+Xhju8NINE9ZjXnMTBu+JwMGPfNxxD0WIp6ozqQOqj8bATEFVnpWuHCb62LXGcHcf2Ce02g==`
- Windows executable SHA-256: `8AA4531E3075949E159AFEA9BBB5FB7B9A918F4B81100FD5BC3CD9E6626023A2`
- Windows executable Authenticode: `NotSigned`
- Microsoft Defender custom scan: no threats, exit `0`, signature version `1.457.447.0`, remediation disabled for the scan.

The package postinstall is not approved for execution. It may run an npm install with
`NODE_TLS_REJECT_UNAUTHORIZED=0`, and it deletes/replaces the installed web and skill
directories. Installation therefore uses npm lifecycle scripts disabled, followed by a
backup-first, explicit deployment of the bundled web/skill/worker files and a normal-TLS
Playwright installation. Existing CyberStrike configuration, authentication, sessions,
database, state, and prompt history are preserved.

## Rapid7 Metasploit Framework 6.5.3

- `LATEST` resolved on 02.09.2026 to `metasploit-framework-6.5.3-20260826060514-1rapid7-1-x64.msi`.
- Immutable download URL: `https://windows.metasploit.com/metasploit-framework-6.5.3-20260826060514-1rapid7-1-x64.msi`
- Detached signature URL: same URL with `.asc` suffix.
- Downloaded size: `399974400` bytes.
- MSI SHA-256: `2556D431EF76FD85D39D0C914B604ADCF9D7050A61393B770C4319547501D8C7`
- MSI SHA-512: `1439EB70212AA5242D21F062C2D978C023134D2FEFCB0B0010C2F24E77117738300DEA66448A86A71DF88B2D7181A428C4932620D18B17E6B6E198977A895F8B`
- Authenticode: `NotSigned`; this sub-gate is unavailable and is not reported as passed.
- Detached OpenPGP signature: valid (`gpg` exit `0`).
- Signing identity: `Release Engineering <r7_re@rapid7.com>`.
- Signing key fingerprint: `97B32012EA1176F053727A95C048F0B49DEEC457`.
- Signing-key source: Rapid7 `metasploit-omnibus` commit `21d459344aa291e9d8c0abdd6cbd9806fdb84791`, file `config/templates/metasploit-framework-wrappers/msfupdate.erb`.
- Pinned signing-source SHA-256: `D12FEA4D1339EBECB09D8CC36920D9F5E5E7E9FFFBE092B1E1CD09255CC16825`.
- MSI ProductName: `Metasploit-framework v6.5.3`; ProductVersion: `6.5.3.1`.
- MSI payload-stream SHA-256: `CD976D3A02EA16FB8C6AEF1CE3738AC039B5F9C49DA16E6F6ED4CF5E25B344AC`.

Offline payload inspection proves the archive contains `bin/msfconsole.bat`,
`bin/msfrpcd.bat`, `embedded/bin/ruby.exe`, `embedded/framework/msfmcpd`, both MCP
configuration examples, and the MCP integration specifications. There is no
`bin/msfmcpd.bat`; the managed primary path is the bundled Ruby executable plus the
official `embedded/framework/msfmcpd` script, with absolute argv, the framework working
directory, stdio MCP, and stable create-once RPC credentials outside Git. The raw daemon
is never registered directly in an agent runtime.

Staged files are under
`C:\Users\Prekzursil\.cache\cyberstrike-adoption\metasploit\6.5.3-20260826060514`.
Installation must not disable Defender or Windows Firewall or add an exclusion. A
pre-existing host setting had real-time Defender monitoring disabled before this work;
this rollout does not change that setting or the existing exclusion lists.

## Bolt image

- OCI index: `ghcr.io/cyberstrikeus/bolt@sha256:90ef2d10a8e255369981e7ce2eb7b89e1ac337ad6a5cf9f21f803c8585eea277`
- Selected Windows-host Docker Desktop platform: `linux/amd64`.
- Platform manifest: `sha256:b5ddb610ea214656fd97223ed790d3bb50a3d44ae188dc937e64c87a83cc4459`.
- Both digests resolved successfully through `docker buildx imagetools inspect`.

The digest receipt does not authorize a pull or run. Runtime acceptance additionally
requires loopback-only publication, no host network, no privileged mode, no Docker socket,
no broad user-profile mounts, no `SYS_ADMIN`, `restart: no`, an ACL-restricted create-once
secret file, and demonstrated allowlisted egress. Until egress is proven, Bolt remains
installed/discoverable but disconnected.

## Host gates observed

- Windows process identity is Administrator, allowing the MSI installation step.
- CyberStrike currently resolves to the npm global shim and reported `1.1.15` before upgrade.
- Metasploit was absent before installation.
- Docker Desktop was installed and running.
- Free physical RAM was `1.83 GB` of `31.63 GB`; heavy tests, Docker pulls, database setup,
  and parallel workers remain gated until at least `8 GB` is free.
- The source repository is on `handoff/cloud-agent-2026-09-02` with unrelated dirty files.
  Target paths were checked independently and were clean; those unrelated changes must not
  be stashed, reset, overwritten, or included in this change.

## Primary sources

- https://registry.npmjs.org/@cyberstrike-io/cyberstrike/1.1.16
- https://windows.metasploit.com/LATEST
- https://windows.metasploit.com/
- https://github.com/rapid7/metasploit-framework/blob/master/docs/metasploit-framework.wiki/Nightly-Installers.md
- https://github.com/rapid7/metasploit-framework/blob/master/docs/metasploit-framework.wiki/How-to-use-Metasploit-MCP-Server.md
- https://github.com/CyberStrikeus/bolt

UNIT-COMPLETE: cyberstrike-artifact-provenance-2026-09-02
