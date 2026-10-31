---
title: dive-ROADtools
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-roadtools
---

# Deep-dive: ROADtools (ad-entra-paths lane)

Date: 2026-09-29 · Verifier: lead-verifier subagent · Repo: https://github.com/dirkjanm/ROADtools

## Claim vs. reality

| Claim | Verdict | Evidence |
|---|---|---|
| 2725 stars | **EXACT** | `gh api repos/dirkjanm/ROADtools` → `stargazers_count: 2725` (run 2026-09-29) |
| Actively pushed 2026-08 | **EXACT** | `pushed_at: 2026-08-05T13:43:22Z`; commits that day: "add fido assertion script", "roadtx: fix fido assertion argument handling in fidoauth command" |
| Entra/Azure AD offensive+defensive toolkit (ROADrecon etc.) | **TRUE** | README.md:9-24; description "A collection of Azure AD/Entra tools for offensive and defensive security purposes" |
| Baseline for Entra enumeration/abuse | **SUPPORTED** | Unit42 (2026-05-22), Elastic detection rule (2026-07-15), pentest handbooks — see Independent mentions |

## Repo metadata (gh api, run 2026-09-29)

- full_name: dirkjanm/ROADtools · created 2020-03-28 · not archived, not disabled
- stars 2725 · forks 395 · open_issues 13 · language Python · license MIT · default branch master
- Recent commits: 2026-08-05 (×2, fido/winhello assertion), 2026-05-21/20 (maintenance sprint: autotoken refactor, passkeys-from-keepass, policy plugin, py3.14 CI + drop 3.9), 2026-01 (frontend/pagination work)
- Maintainer (dirkjanm) is broadly active: askWAM pushed 2026-09-11, blog 2026-08-20, BloodHound.py, krbrelayx — not a single-project maintainer

## Packaging — the REAL install

- Top-level `setup.py` is a **meta-package** (`roadtools 0.0.2`, install_requires roadlib+roadrecon+roadtx). Not what you install.
- Real packages (each has its own setup.py, on PyPI):
  - **roadlib 1.7.0** (`roadlib/setup.py:2-3,19`): deps requests, cryptography, sqlalchemy>=1.4, pyjwt>=2.0, cbor2; aiohttp as `async` extra
  - **roadrecon 2.0.0** (`roadrecon/setup.py:2-3,29-40`): deps roadlib>=1.7, flask<3, sqlalchemy>=1.4, marshmallow<4, flask-sqlalchemy>=2.5, flask-marshmallow, flask-cors, marshmallow-sqlalchemy>=0.29, aiohttp, openpyxl; console_scripts `roadrecon`, `roadrecon-gui`; pyyaml/numpy/pandas extra for road2timeline
  - **roadtx 1.22.1** (`roadtx/setup.py:2-3,20-29`): deps roadlib>=1.7, requests, selenium, **selenium-wire-roadtx>=5.2.4**, pyotp, pycryptodomex, signxml>3, setuptools; console_script `roadtx`
- README.md:32,69 — official install: **`pip install roadrecon`** and **`pip install roadtx`** (roadlib comes in as a dependency).
- No Dockerfile, no GitHub release binaries. CI publishes wheels as Azure Pipelines artifacts (README.md:35).
- Python >= 3.10 required (README.md:26,66); CI matrix 3.10–3.14 (`azure-pipelines.yml:16-25`).

## PyPI freshness (pypi.org/pypi JSON, fetched 2026-09-29)

- roadlib 1.7.0 → 2026-05-21 (prior: 1.5.0 2025-10-24, 1.6.0 2025-10-28)
- roadrecon 2.0.0 → 2026-05-21 (major bump; prior: 1.7.3 2026-01-26, 1.7.4 2026-02-04)
- roadtx 1.22.1 → 2026-08-05 (same day as last repo push; prior: 1.21.1 2025-12-25, 1.22.0 2026-05-21)
- Consistent release cadence: roughly every 1–3 months through 2025–2026.

## Dependency health (Windows support)

All runtime deps are pure Python or ship Windows wheels (cryptography, pycryptodomex, cbor2). Verified live install resolved cleanly on Windows (below).
- **selenium-wire-roadtx**: upstream selenium-wire is unmaintained; the maintainer maintains his own fork (github.com/dirkjanm/selenium-wire-roadtx, pushed 2026-05-20; PyPI 5.2.3 2026-05-19 → 5.2.4 2026-05-20). Dependency risk is actively self-managed.
- Selenium flows (`interactiveauth`, `prtenrich`, `browserprt*`, `fidoauth`) additionally need Firefox + geckodriver on PATH; the rest of roadtx works without a browser.
- No OS-specific compiled deps; no C build step on install.

## Windows-native feasibility — TESTED ON THIS VM (Python 3.14.6, C:\Python314)

1. `python -m venv rtvenv` → ok
2. `pip install roadrecon roadtx` → **exit 0**, no build errors
3. `roadrecon --help` → RC=0; subcommands: auth, gather, dump, iggather/igdump (ingraph), pimgather/pimdump (PIM), azgather/azdump, gatherall/dumpall, gui, plugin
4. `roadtx --help` → RC=0; 45+ subcommands incl. prt, prtauth, winhello, fidoauth, prtenrich, desktopsso, devicelessprt, bulkenrollmenttoken, registerpasskey
5. `roadrecon-gui --help` → RC=0
6. **Offline end-to-end pipeline**: `database.init(create=True, dburl='sqlite:///winreal.db')` (same call as `roadrecon/roadtools/roadrecon/gather.py:642`; schema creation at `roadlib/roadtools/roadlib/metadef/database.py:1794-1806`) → inserted a User row → `roadrecon-gui -d winreal.db --port 5123` → `curl http://127.0.0.1:5123/api/users` → **HTTP 200** returning the inserted user as JSON. Windows backslash sqlite URLs resolve correctly (SQLAlchemy percent-encodes for display only).
7. Windows is a first-class *target* surface, not just host: `winhello` (register Windows Hello key, main.py:171), `fidoauth` (Windows Hello/passkey auth, main.py:179), and the 2026-08-05 addition `winhello_assertion/fido_assertion.ps1` (PowerShell).

### Test-suite run on Windows (exact command: `python -m pytest tests/ -q` in repo root)

Result: **6 failed** — test_asyncauth (needs live rtuser/rtpass env), test_database, 4× test_guiserver. Diagnosis: these tests require a pre-dumped `roadrecon.db` tenant fixture in cwd (CI generates it by a real `roadrecon dump` against a test tenant before pytest — `azure-pipelines.yml:55-66,131-137`; fixtures point at `sqlite:/// + os.getcwd()/roadrecon.db` — `tests/test_database.py:14`, `server.py:1031`). Proof it's fixture-missing, not Windows breakage: after placing my own 1-user DB as `roadrecon.db`, `test_db_has_users` failed with `AssertionError: assert 1 > 5` (count assertion) instead of `TypeError: NoneType`, and the API endpoint itself returned the user fine. **Upstream CI runs ubuntu-latest only** (`azure-pipelines.yml:12`), so Windows is not covered upstream — my live install/e2e test above is the Windows evidence.

## Issues / breakage (gh api, read 2026-09-29)

- 13 open issues total; maintainer triaged/closed a large batch on 2026-05-19/20/21.
- **#147** "gather fails with HTTP 403" — CLOSED 2026-06-03. Cause: tenant blocked the client_id for graph resource, not a tool regression; maintainer replied with diagnosis + fix on master.
- **#154** "Selenium headless auth with ESTSCookie gets stuck" — OPEN, 0 comments; PR #155 open with a headless fix. Edge-case flow only.
- **#107** SSLCertVerificationError behind TLS-inspecting proxies — OPEN; maintainer acknowledged (wants a consistent CLI flag; manual workaround exists). **Relevant if this estate has SSL inspection.**
- **#144** "gather phase getting stuck" — OPEN; affects the mostly-untested MsGraph branch; the default AadGraph path is unaffected (maintainer comment).
- **#143** pkg_resources deprecation warning — CLOSED (setuptools now pinned in roadtx deps).

## Independent mentions (Exa search + fetch, run 2026-09-29)

- **Unit42 / Palo Alto, 2026-05-22**: "Paved With Intent: ROADtools and Nation-State Tactics in the Cloud" — "ROADtools is a publicly available toolkit ... that attackers have integrated into cloud attacks"; "The use of ROADtools has evolved from a red-team utility to an attack tool"; used by Cloaked Ursa/Midnight Blizzard (APT29), Curious Serpens (APT33), UTA0355.
- **Elastic detection rule** "Azure AD Graph Potential Enumeration (ROADrecon)" via detection.fyi, updated 2026-07-15 — the defensive ecosystem actively tracks it.
- **Syslifters pentest handbook** uses ROADtools as the reference Entra enumeration tool; kb.offsec.nl KB entry; vk9-sec walkthrough; incendium.rocks notes.
- **fwd:cloudsec 2025 talk** "Rebuilding ROADRecon for the Modern Entra Environment"; dirkjanm's WWHF "Evolving ROADtools" talk; dirkjanm.io release blogs.
- Alternatives exist per-domain (GraphSpy for tokens, AzureHound for BloodHound ingestion) but nothing replaces the combined dump+GUI+token-exchange surface; ROADtools is consistently the comparison baseline.

## Verdict

Live, healthy, and the de-facto baseline for authenticated Entra ID enumeration (roadrecon) plus token/PRT abuse (roadtx). Claim verified on every count. Windows-native: confirmed by actual install + CLI smoke + full offline dump→GUI→API round-trip on Python 3.14. Score: **high value, native Windows**.

Minor caveats: CI is Linux-only (Windows verified by me, not upstream); selenium flows need Firefox+geckodriver; SSL-inspected proxies need the documented workaround until #107 ships a flag; MsGraph gather branch is experimental.

## Artifacts of this dive

- Clone: out/research/ROADtools-src (shallow, master @ 2026-08-05)
- Test venv: out/research/rtvenv (roadrecon 2.0.0, roadtx 1.22.1, roadlib 1.7.0 from PyPI)
- Test DBs: out/research/wintest.db (0 bytes, abandoned probe), out/research/winreal.db (working schema + 1 user)