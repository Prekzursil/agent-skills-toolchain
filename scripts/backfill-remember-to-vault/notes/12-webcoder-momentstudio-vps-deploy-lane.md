---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] WebCoder PR #169's hydration error had TWO stacked causes, and only fixing both cleared it: a Grammarly browser-extension script version mismatch injecting into the page, and a missing MUI `ThemeProvider` in `providers.tsx` - which is also why the login and problems routes still rendered old Material-UI.
- [fact] The backend was deliberately removed from `main` for Rocket compatibility and was never deployed, so "the backend is missing" is intended state, not a regression.
- [fact] The VPS target was probed over MCP before any deploy (vs.chroot.ro, 17 tools) and was POWERED OFF with 0 usage. Disk was reclaimed in two passes: 10.8 GB (100% -> 86%) and later 46.6 GB, of which 35.9 GB was extensions. The host topology, layout and Caddy wiring are NOT restated here - they are owned by the deploy note this one relates to.
- [fact] Phase A went live with 5 containers, API and momentstudio responding, after fixing 3 Django bugs (Celery broker, static files, the `docker.io` package) and patching 4 further issues (hardcoded DEBUG and ALLOWED_HOSTS, docker socket exposure, `runserver` in a served path).
- [decision] A socket FILTER replaced the planned nginx allowlist, because Docker's connection hijack is incompatible with an nginx allowlist - the allowlist cannot see the hijacked stream it is supposed to police. Container creation is an escalation path, so the filter is the control that matters. The filter's own design rationale (prefix-routing cannot express exec-without-create) is owned by the deploy note.
- [fact] The judge passed end-to-end on exec, I/O, exit code, timeout and security. Residual blockers: the DNS A record for webcoder to 89.42.42.35 (needs an admin API key for the cert), momentstudio.ro returning 308 behind Caddy pending DNS, and PR #169 unit tests failing on encoding issues.
- relates_to [[project_webcoder_deploy_momentstudio_vps_2026-09-29]]
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
<!-- backfill-id: L6-BF-12 src: .remember/today-2026-09-29.md 03:35-03:57, 04:04, 05:54, 06:37, 06:51, 07:01, 07 sha256: 16c85f25ef78 -->
