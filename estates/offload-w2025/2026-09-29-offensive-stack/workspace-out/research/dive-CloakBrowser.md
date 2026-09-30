# Deep-dive: CloakBrowser (browser-offense lane)

Date: 2026-09-29. Verifier session on the estate Windows VM. All API reads via `gh api` against `CloakHQ/CloakBrowser` unless noted.

## Verdict in one paragraph

REAL and actively maintained, not fake, not dead — but the claim as written overstates what you get for free. The repo is the MIT-licensed **wrapper** (Python + JS + .NET humanized Playwright/Puppeteer replacement); the actual stealth Chromium **binary is closed-source** and the newest build (Chromium 152, 87 patches) is **license-gated** (paid Pro, or a free GitHub-sign-in key limited to 1 concurrent session). The last no-license public build is Chromium **146 with 58 patches** (May 2026). Windows x64 is genuinely supported natively (free v146 zip on GitHub Releases, 304,483 downloads; v152 Windows build exists per checksummed release notes but downloads only with a key from their CDN). Detection-pass claims are self-reported (Aug 2026, Pro build) and independently corroborated for an earlier build — while open issues show field failures on FingerprintJS Pro, DataDome, and reCAPTCHA v2.

## Claim-by-claim correction

| Claim | Verdict | Evidence |
|---|---|---|
| 31,790 stars | TRUE | `gh api repos/CloakHQ/CloakBrowser` → `stargazers_count: 31790`; also `forks: 2643`, `watchers/subscribers: 152`, `open_issues: 237`, created `2026-02-22`, pushed `2026-09-27`. 31.8k stars in ~7 months (viral trajectory). Star-listing API returned 403 for this PAT (`Resource not accessible by personal access token` on `/stargazers`), so per-star authenticity (bought-star check) was NOT run; traction is corroborated by ~570 issues, 12,683 NuGet downloads, 300k+ release downloads. |
| 87 source-level C++ fingerprint patches (not JS injection) | TRUE for the **Pro** binary; patches are **closed-source, not in this repo** | README lines 39/289 claim it. Full git tree (255 paths) contains **zero** `patch*` files — the repo ships only the wrapper. Independent audit (pim97/cloakbrowser-analyze, created 2026-03-17) describes a "closed-source, patched Chromium binary … based on ungoogled-chromium", 441 MB ELF, with patches "compiled in" but uninspectable. Free binary = 58 patches (README platform table line 893-897); macOS free = 26 patches. Patch-count history 26→33→58→87 tracks paid tiers. |
| humanize=True — mouse curves, keyboard timing | TRUE, and this part IS open in the repo | Tree: `cloakbrowser/human/{mouse,keyboard,scroll,actionability}.py` (+`_async`), `js/src/human/*`, `dotnet/.../Human/*`. README line 40/169: Bézier curves, per-character typing, realistic scroll. |
| Passes Turnstile/FingerprintJS/BrowserScan across 30+ detectors | PARTLY — self-reported, tier-dependent, with field failures | README "Test Results" table (lines 222-238): "Last tested: Aug 2026 (Chromium 151)", many rows annotated "Pro/current build". Independent test (ekofyi.com/blog/cloakbrowser-real-test) corroborated reCAPTCHA v3 0.9, Turnstile auto-resolve, FingerprintJS pass, BrowserScan 4/4 — on an earlier free build. **Counter-evidence in open issues:** #541 "fingerprint pro detects browser tampering" (7 comments), #538 Docker persistent context `tampering: true` on Fingerprint Pro Playground (7 comments), #553 FPJS Pro same Visitor ID across seeds + tampering, #556 DataDome refuses Vinted.fr login on Chromium 151, #545 reCAPTCHA v2 challenges ~9/10 attempts, #546 Google CAPTCHA/2FA after IP changes. "Passes every bot detection test" is marketing; strong against the named three (Turnstile/FingerprintJS/BrowserScan) on the current Pro build, not universal. |
| Windows x64 builds confirmed in README (Chromium 152 patch set on Linux and Windows) | TRUE in text, but the v152 Windows **binary is not on GitHub Releases** — license-gated | Release `chromium-v152.0.7977.82.1-pro` (2026-09-23) assets = `SHA256SUMS` (313 B) + `SHA256SUMS.sig` only — no browser archives; body says "With a valid CloakBrowser key, the wrapper automatically selects the Stable build." Every release since 2026-06-22 is "(Pro)" with checksums-only assets. Last release carrying actual binaries: `chromium-v146.0.7680.177.5` (2026-05-21) with `cloakbrowser-windows-x64.zip` 562,000,438 B, 304,483 downloads. Wrapper pins free windows-x64 to 146: `cloakbrowser/config.py` line 25 `"windows-x64": "146.0.7680.177.5"`. |

## Repo facts (gh api, 2026-09-29)

- `stargazers_count 31790`, `forks 2643`, `open_issues 237`, license **MIT**, `language: Python`, size 7,292 KB, homepage cloakbrowser.dev, topics include anti-detect/captcha-bypass/cloudflare-bypass.
- Org `CloakHQ` created `2026-02-22T08:03:47Z` (same day as repo), 7 public repos (includes open-source GUI: CloakBrowser-Manager).
- Contributors: Cloak-HQ 263 commits; dependabot 17; evelaa123 13 (humanize/Windows fix/.NET); 16 others ≤4. Effectively single-vendor.
- Commits current: latest `2026-09-24` "release: v0.5.11"; pushes through `2026-09-27`. CHANGELOG cadence 0.5.9 (2026-08-25) → 0.5.10 (2026-08-30) → 0.5.11 (2026-09-24).
- Releases every 1–2 weeks since 2026-02-27; binary versions march with upstream Chromium (142→145→146→148→150→151→152).

## Business model (the critical correction)

- `LICENSE` = MIT **for the wrapper only**. `BINARY-LICENSE.md` v1.3 (July 2026): the compiled binary is proprietary; "downloading and using the **latest major** Binary version requires an active paid subscription." Older free versions remain usable under the binary license.
- Tiers (README "CloakBrowser Pro" section): **Free no-key** = Chromium 146 on GitHub Releases ("ages fast as detection evolves"). **Free key** (GitHub sign-in at cloakbrowser.dev/free or `cloakbrowser login`) = newest build, 1 concurrent session. **Pro paid** = 5–2,000+ concurrent sessions, Linux/Windows/macOS.
- Gating verified in code: `cloakbrowser/download.py` imports `validate_license`; no key → free pinned build; valid key → Pro download from their CDN (`DOWNLOAD_BASE_URL`, overridable via `CLOAKBROWSER_DOWNLOAD_URL`); invalid key now aborts instead of silently downgrading (CHANGELOG 0.5.10). Community concern about the paywall trajectory: issue #537 "Will 146 be the final unrestricted version?"
- Community-confirmed issue #547 asks when Windows 152/153 arrives for users — Windows Pro binary shipped 2026-09-23 per release notes.

## Real install command (verified)

- **Python:** `pip install cloakbrowser` (README line 104; pyproject `name = "cloakbrowser"`, `requires-python >=3.9`, deps `playwright>=1.40`, `httpx>=0.24`, `cryptography>=41.0`).
  - **Ran on this VM:** `C:/Python314/python.exe -m pip install --dry-run cloakbrowser` → `Would install cloakbrowser-0.5.11`, deps (playwright 1.x, httpx, cryptography) already satisfied on Python 3.14 — resolves clean even though classifiers only list 3.9–3.13.
  - First `launch()` auto-downloads the free Windows binary (~562 MB zip) from GitHub Releases and verifies Ed25519-signed SHA256SUMS. NOT run to completion here (download + live launch not executed).
- **JS:** `npm install cloakbrowser playwright-core` (or `puppeteer-core`).
- **.NET:** `dotnet add package CloakBrowser` (NuGet shows 0.5.11, 12,683 downloads).
- **Docker:** `docker run --rm cloakhq/cloakbrowser cloaktest` (Dockerfile = python:3.12-slim + Xvfb; Linux-oriented, not needed on Windows).
- Registries all current at 0.5.11 / uploaded 2026-09-24: PyPI (checked pypi.org JSON), npm (created 2026-02-23), NuGet.

## Windows-native feasibility

- **Native: yes.** Free Windows x64 binary publicly downloadable (release asset above, 304k downloads); wrapper is pure Python with Windows-wheel deps; Windows-specific fixes are actively merged (CHANGELOG 0.5.10 fixed cp1252-console `UnicodeEncodeError` abort; contributor credit for "Windows fix"). Not Docker/WSL-dependent.
- Caveats on Windows: Widevine CDM is Linux-only ("On Windows the CDM can't initialise" — README line 485); the Linux persona story (spoof-as-Windows + Windows font metrics) is a Linux concern — on real Windows the binary passes through native GPU values ("Windows native GPU passthrough", README line 159).
- Issue #562 (`ImportError: DLL load failed ... _rust`) is the `cryptography` wheel on the reporter's Python, not the browser itself.

## Breakage / risk picture (issues + discussions)

- Healthy issue flow: ~567 issues in 7 months; maintainers respond (comment counts on the detection issues).
- Real field breakage to expect: FingerprintJS **Pro** tampering detection (#541, #538, #553), DataDome on some logins (#556), reCAPTCHA v2 elevated challenge rate (#545), Google account friction after IP change (#546), Turnstile behaving differently under production stacks (discussion #91).
- Trust model: you run a 440–560 MB closed-source executable. Independent audit pim97/cloakbrowser-analyze ran 9 automated Docker behavior tests on the v145 binary: **no malicious behavior detected**, but explicitly notes it cannot be fully verified. Wrapper verifies binary signature+checksum (Ed25519) on download.
- Alternatives visible in the space (from README comparisons and audit context): playwright-stealth / undetected-chromedriver (both stale per README), patchright (discussion #154), commercial anti-detect managers (Multilogin/GoLogin/AdsPower — CloakBrowser Manager positions as self-hosted alternative).

## Independent mentions (Exa search, 2026-09-29)

Query `CloakBrowser CloakHQ stealth chromium review` returned: ekofyi.com independent 5-detector test (results above), pim97/cloakbrowser-analyze (security audit, 9 stars), pim97/anti-detect-browser-tools-tech-comparison, reviews on andrew.ooo (+dev.to cross-post), toolbrain.net, capsolver.com, agentpedia.codes, techtimes.com article (2026-05-15, "Defeats Cloudflare, DataDome, and PerimeterX"). Coverage skews affiliate/SEO-review heavy but includes two genuinely independent technical evaluations. Not a ghost repo — the mention ecosystem is consistent with real mass adoption.

## Checks run vs not run

RUN: repo metadata via gh api; full tree listing (255 paths); README (1,491 lines) + release bodies + SHA256SUMS listing; pyproject.toml, BINARY-LICENSE.md, config.py, download.py inspection; contributors; open issues list + #541/#556 bodies; discussions list; commit log; PyPI/npm/NuGet registry checks; `pip install --dry-run` on Python 3.14; Exa independent-mention search; independent audit + independent detector test read.

NOT RUN: actual `pip install` + binary download + live launch/detection test on this VM (562 MB download, would create a licensing context, and detection outcomes are time-sensitive); stargazer-authenticity sampling (`/stargazers` 403 for this PAT); pricing page scrape of cloakbrowser.dev.
