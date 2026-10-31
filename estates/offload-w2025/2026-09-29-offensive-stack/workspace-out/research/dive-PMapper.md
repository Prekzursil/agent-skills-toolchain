---
title: dive-PMapper
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-pmapper
---

# Deep-dive: PMapper (Principal Mapper) — nccgroup/PMapper

Lane: ad-entra-paths (note: PMapper targets **AWS IAM**, not AD/Entra ID — its graph/authz-simulation pattern is presumably why it surfaced in this lane).
Date of dive: 2026-09-29. Local test copies this session: shallow clone at `$TEMP/PMapper-verify` (master) and a venv at `$TEMP/pmapper-venv` (Python 3.14.6); upstream repo untouched.

## 1. Claim vs reality

Claim: "1582-star AWS IAM privilege-escalation graph: models users/roles as directed graph, answers 'can X do Y' with local authorization simulation."

| Claim element | Verdict | Evidence |
|---|---|---|
| 1582 stars | **Exact match** | `gh api repos/nccgroup/PMapper` → `stargazers_count: 1582` (198 forks, 36 open issues) |
| Directed graph of users/roles | **True** | README.md intro (fetched via contents API); modules `principalmapper/graphing/`, `principalmapper/common/graphs.py` in tree |
| "can X do Y" queries | **True** | README usage: `query 'who can do iam:CreateUser'`, `argquery -s --action ... --condition ...` |
| Local authorization simulation | **True** | `principalmapper/querying/local_policy_simulation.py:37` `has_matching_statement`, `:57` `policy_has_matching_statement` (grep-verified); README: "uses a local simulation of AWS's authorization behavior" |
| Priv-esc detection | **True** | `query -s 'preset privesc *'` in README; presets on disk: `querying/presets/{privesc,connected,endgame,serviceaccess,wrongadmin,clusters}.py` |

Repo metadata (gh api, 2026-09-29): created 2018-05-23, pushed_at **2024-08-02**, license **AGPL-3.0**, language Python, archived=false, default branch master, open_issues 36.

**But pushed_at is misleading.** The 2024-08-02 push is PR #142 "Dev" — opened and closed same day, never merged (issue list + timestamps). Actual last activity:
- master: `91d2e601`, **2022-02-03** (CI matrix tweaks — last commits on master)
- v1.2.0-dev: `06f1dc1e`, 2022-04-12 ("fix for #114…"); v1.2.0-dev-query-outputs: 2022-03-30 (CSV/JSON output) — **never merged to master**
- PR #109 "v1.2.0" (head `v1.2.0-dev`): open since 2022-02-03, `mergeable_state: clean`, still unmerged 4.5 years later (`gh api repos/nccgroup/PMapper/pulls/109`)
- Latest release **v1.1.5, 2022-01-13**; all 8 releases have **zero release assets** (pip-only distribution)
- Still watched: `/events` shows stars 2026-09-02…09-25, fork 2026-09-02 — attention yes, maintenance no.

**Verdict: dormant, not fake.** Real code, real 1.5k-star reputation, zero maintainer activity since April 2022.

## 2. Packaging / real install command

- PyPI package name is **`principalmapper`**; the CLI binary is `pmapper` (entry point `pmapper = principalmapper.__main__:main` in setup.py). Real install: **`pip install principalmapper`** (README) or `pip install .` from clone, or Docker.
- PyPI (`curl https://pypi.org/pypi/principalmapper/json`): latest **1.1.5, uploaded 2022-01-13** — nothing in ~4.7 years. `requires_python: >=3.5, <4`; classifiers stop at 3.9 (setup.py).
- `setup.py` install_requires: `botocore`, `packaging`, `python-dateutil`, `pydot`; `requirements.txt` pins `botocore > 1.13`.
- Dockerfile: `FROM python:3.8-slim-buster` + `apt-get install graphviz` — pinned to an EOL base image; update PR #143 (2026-05) unmerged.
- **pydot is a hard import at CLI startup**: `principalmapper/visualizing/graphviz_writer.py:18` `import pydot` (grep-verified). The Graphviz *system binary* is only needed for `visualize` rendering (png/svg/dot); graph/query/analysis never shell out to `dot` — confirmed by the test suite passing with no `dot` on PATH.

## 3. Windows-native feasibility — TESTED on this VM

Environment: `C:\Python314\python.exe` = **Python 3.14.6** (`python --version`); also `C:\Python312` = Python 3.12.10; **no ≤3.9 interpreter on the box**.

1. `python -m venv $TEMP/pmapper-venv` + `pip install principalmapper` → **exit 0**. Installed: principalmapper 1.1.5, botocore 1.43.104 (current 2026 build), packaging 26.3, pydot 4.0.1, python-dateutil 2.9.0.post0 (`pip list` in venv). All deps pure-Python — Windows-clean.
2. `pmapper.exe -h` → **CRASH, exit 1**:
   ```
   File "...principalmapper\util\case_insensitive_dict.py", line 34, in <module>
     from collections import Mapping, MutableMapping, OrderedDict
   ImportError: cannot import name 'Mapping' from 'collections'
   ```
   **Out of the box, PMapper 1.1.5 cannot start on ANY Python ≥ 3.10.** Line 34 verified in the fetched source. Known upstream: issues #130 (3.10, includes the exact fix), #131 (3.11, same line 34), #140 (2023-11-06, open); fix PRs #122 (open since 2022-11), #139 (open since 2023-11), #144 (2026-05, "Python 3.12 import compatibility") — **all unmerged**.
3. **One-line workaround verified** (patched only my scratch copies in `$TEMP`): line 34 → `from collections.abc import Mapping, MutableMapping` + `from collections import OrderedDict`. Result:
   - `pmapper -h` → prints full usage (graph/orgs/query/argquery/repl/visualize/analysis), exit 0.
   - Full repo suite in the patched clone: `python -m unittest discover -s tests -v` → **"Ran 32 tests … OK"** on Python 3.14.6, Windows-native, no graphviz binary present. (Unpatched clone first: `FAILED (errors=8)` — all collection errors from the same import.)
4. Repo CI `.github/workflows/test_PRs.yml` matrices **`windows-latest`** with Python 3.6/3.10 (added 2022-02-03) — Windows was an officially tested platform. Note its "3.10" pass predates the full removal fallout users report; my run shows the real behavior on 3.12/3.14.
5. Grep for `distutils` / `import imp` / `asyncore` across `principalmapper/`: **no hits** — the collections.abc line is the only modern-Python breakage found.

Conclusion: **Windows-native = yes, conditional on a trivial 1-line patch** (or a Python ≤3.9 venv, which this VM lacks — 3.12 is present and also ≥3.10). After the patch it installs, boots, and passes its own 32 tests on 3.14.

## 4. Issue-tracker breakage signals (issues read via `gh api .../issues?state=all`)

- **Python ≥3.10 ImportError** — #130/#131/#140; unmerged fix PRs #122/#139/#144 (above). The single biggest practical defect.
- **Performance ceiling on large accounts** — #137: rdegraaf measured **5 hours** for a 1,487-principal account (63 admins); references #55 ("16 days to complete" on a giant account); the perf work (lru_cache sizing, ~60% small-account speedup) was done by community member **Fennerr in his own fork**, not upstream; perf PR #141 (2024-06) unmerged. No maintainer replies in the thread.
- **Crash scanning principals with deprecated permission policies** — #136 (open).
- **Stack traces on missing credentials (#135) and bad `PMAPPER_STORAGE` env var (#134)** — open.
- **Permission boundaries not considered when querying** — #129 (open): a documented correctness gap in "can X do Y" answers.
- **MFA-conditioned roles can produce misleading results** — #116 (open).
- #115 (2022) stuck "Generating Edges based on lambda data"; #120 FileNotFoundError in graph_cli; #145 (2026-08) fresh feature idea, maintainer silent.
- PR #109 (v1.2.0) and #144 sit `mergeable_state: clean` — merges would be trivial, maintainer absent since 2022.

## 5. Independent mentions & alternatives (Exa API, `$EXA_API_KEY`, 2 queries; WebFetch of top 2 refs)

First-party: NCC Group research page "Principal Mapper (pmapper)" (nccgroup.com, 2018-06-22); GitHub wiki pages still rank for all PMapper queries.

Third-party:
- **haitmg.pl, 2026-04-28, "5 AWS IAM Privesc Scanners vs 57 Paths"** (WebFetch'd): cloud-audit 53/57 (93% — author's own tool, 25/57 paths from its catalog, disclosed bias), Prowler 5.25.0 37/57 (65%; 31/32 on the neutral Bishop-Fox subset), Cloudsplaining 0.8.2 20/57 (35%), **PMapper 19/57 (33%)** (1m59s; 14/32=44% bias-free subset), CloudFox 4/57 (7%). PMapper praised as catching a **3-hop AssumeRole chain via trust-policy traversal** that others skipped by design; called "**functionally dead** — last release January 2022, Python 3.10+ broken for over four years… requires a Python 3.9 venv workaround" (my patch shows it's softer than stated: 1 line fixes 3.14).
- **ramimac.me "An AWS IAM Security Tooling Reference" (2024-08-16)** (WebFetch'd): recommends PMapper for "who can escalate privileges / which principals can access other principals"; notes 1.0+ added resource policies, permission boundaries, session policies, SCPs; flags the original as less maintained and points to **Fennerr/PMapper** as the more-recently-maintained fork (adds `externalaccess` preset).
- codeshield.io comparison to PMapper (2022-08-22); cybersectools.com Cloudsplaining-vs-PMapper side-by-side; dev.to/yayopalacios 2026-09-01 on IAM privesc path tools — still a standard reference point in 2024–2026 content.
- **Fork status** (`gh api repos/Fennerr/PMapper`): 77 stars, pushed 2024-05-27, last commit 2023-12-10 — has py3.10-era fixes + perf work, **also now 2+ years stale**.

Alternatives if maintained tooling is preferred: Prowler (highest neutral-subset coverage), Cloudsplaining (policy-level, not graph pathing), CloudFox, cloud-audit, plus managed AWS IAM Access Analyzer. None replicates PMapper's local-simulation REPL + transitive "who can do X" query UX exactly.

## 6. Value assessment for this estate

- Real capability: "who can do X, including indirect access" graph queries backed by full local IAM policy simulation remain differentiated — the 2026 benchmark still needed PMapper(-class) chain detection in its coverage combo. AGPL-3.0 is fine for internal use on a private estate; do not embed in redistributed products.
- Costs: upstream dead since 2022; **broken on Python ≥3.10 out of the box** (1-line fix, proven here); 33% single-tool privesc-path coverage; severe large-account performance; correctness blind spots (#129 permission boundaries, #116 MFA conditions); AWS-only — no Entra ID coverage, so for the lane's nominal focus it fills only the adjacent AWS-identity half.
- Score: **medium** — usable and unique-ish, but you adopt a 4-year-frozen AGPL tool that ships broken on modern Python. If adopted: 1-line `collections.abc` patch (or Fennerr fork), expect long runtimes on big orgs, cross-check query results against the #129/#116 blind spots; pair with a maintained baseline scanner (e.g. Prowler).

## 7. Facts not verified / not run

- Did not run `graph create` against a live AWS account (no AWS credentials in scope of this ask) — the AWS-API code path is untested here; only offline install, CLI boot, and the 32-test unit suite were run.
- Did not test `visualize` rendering (needs the Graphviz `dot` binary, not on PATH).
- v1.2.0-dev branch code (#109/#144) not build-tested; findings apply to master/PyPI 1.1.5.

## 8. Commands actually run (for the record)

```
gh api repos/nccgroup/PMapper                                   # metadata: 1582 stars, AGPL-3.0, pushed_at
gh api .../commits  .../releases  .../tags  .../branches  .../events  .../git/trees/master?recursive=1
gh api .../contents/{README.md,setup.py,requirements.txt,Dockerfile,MANIFEST.in,test_PRs.yml,case_insensitive_dict.py}
gh api .../issues?state=all   .../issues/130  .../issues/131  .../issues/137/comments  .../pulls/109
gh api repos/Fennerr/PMapper (+ commits)                        # fork: 77 stars, push 2024-05-27
curl https://pypi.org/pypi/principalmapper/json                 # 1.1.5, 2022-01-13
python -m venv $TEMP/pmapper-venv; pip install principalmapper  # exit 0
pmapper -h                                                      # ImportError: collections.Mapping (case_insensitive_dict.py:34)
# 1-line patch -> collections.abc
pmapper -h                                                      # usage, exit 0
git clone --depth 1 ... $TEMP/PMapper-verify; patch line 34; python -m unittest discover -s tests -v   # Ran 32 tests, OK (Py 3.14.6)
grep distutils/imp/asyncore over principalmapper/               # no hits
curl api.exa.ai/search (2 queries)                              # mentions/alternatives
WebFetch ramimac.me/aws-iam-tools-2024 ; haitmg.pl benchmark    # recommendations + coverage numbers
```