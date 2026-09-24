# REPRODUCE — bringing this CV system up on a second machine

Goal: from the repository alone, get to a rendered, gate-approved set of documents.
Everything below was executed on this box on **2026-09-24**; the numbers are measured,
not estimated.

---

## 0. What you need — and what you do NOT

**Need**

| | |
|---|---|
| Python | **3.14.6** proven here. RenderCV 2.8 declares `Requires-Python: >=3.12`. Below 3.12 will not install. |
| Disk | ~**302 MB** for `.venv`, ~**3 MB** for rendered documents. |
| Network | Only for `pip install`. **Rendering is fully offline.** |
| Shell | PowerShell 7 (`build.ps1`, **verified end to end here**) **or** GNU make (`Makefile`, see the honesty note below). |

> **Honesty note on the `Makefile`.** `make` is **not installed on the box this was built on**,
> so the Makefile was **never executed**. What *was* checked: its `.PHONY` target names match
> `build.ps1` exactly (asserted automatically by `./build.ps1 list`, and that assertion was
> proven to fire on injected drift), all **67** recipe lines are tab-indented, there are no CRLF
> line endings, and every recipe invokes a Python entry point that was individually verified.
> It is structurally sound and the commands underneath it are proven — but the first person to
> run `make` on a POSIX box is its first real test. Use `build.ps1` where you have a choice.

**Do NOT need** — this trips people up, so it is stated explicitly:

- ❌ **No LaTeX.** Nothing in this pipeline uses TeX.
- ❌ **No system Typst binary.** The `typst` **Python** package (0.15.0) is pulled by pip and
  is the whole typesetter.
- ❌ **No OS font install.** All **62** font files (including **XCharter**, which the ATS and
  Romanian templates pin because it renders the full comma-below Romanian set without
  substituting cedilla forms) ship inside the `rendercv_fonts` package. Verified: `XCharter`
  is **not** present in `C:\Windows\Fonts` on this box, yet the Romanian CV renders correctly.
- ❌ **No Node.** Only the optional legacy JSON Resume HTML path wants Node; the shipped
  pipeline does not.
- ❌ **No network at render time.**

---

## 1. Clone

```bash
git clone <the private agent-skills-toolchain remote> agents
cd agents/cv
```

> **Note for whoever commits this:** at the time of writing, `cv/` is **untracked**
> (`git status` → `?? cv/`). It must be committed for this document to be true. A
> `cv/.gitignore` is in place so that `out/` (~2.7 MB of generated PDFs), `.venv/`
> (~302 MB) and the caches are excluded — only the **sources** are versioned.

What must be present after the clone (these are the sources; everything else is generated):

```
cv/
  profile.yaml              the facts — the single source of truth
  requirements.lock.txt     33 pinned packages (see §2)
  build.ps1  Makefile       one-command drivers
  README.md  TODO-CONFIRM.md  REPRODUCE.md
  tools/      zerofab.py  build.py  verify.py  + their tests
  templates/  render_template.py  emit.py  docgate.py  killlist.py
              ats-en/ ro/ academic/ research-profile/ cover-letter/
              linkedin/ platform-packs/ europass/ _shared/
```

---

## 2. Dependency preflight and venv

One command creates the venv and installs everything:

```powershell
./build.ps1 setup          # POSIX: make setup
```

For a **deterministic** install, use the lockfile instead of floating versions — this is
what was verified:

```powershell
C:/Python314/python.exe -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
```

Then confirm the toolchain:

```powershell
./build.ps1 preflight
```

Expected, exactly:

```
==> preflight
  OK    venv python  Python 3.14.6
  OK    rendercv   2.8
  OK    pymupdf    1.28.2
  OK    pyyaml     6.0.3
  OK    typst      0.15.0
  OK    profile.yaml  52309 bytes

SUCCESS:preflight
```

**Measured:** venv creation **4.3 s**; the lockfile install completes without a single
version conflict.

### Reproducibility is proven, not assumed

A throwaway venv was built from `requirements.lock.txt` alone, with no other setup, and used
to render the ATS view. The resulting PDF is **byte-identical** to the one from the working
venv — same SHA-256 (`33a437fbe72ffa99…`), 49,854 bytes, all 7 output checks PASS. The build
is deterministic across environments.

---

## 3. First render

```powershell
./build.ps1 all            # POSIX: make all
```

This runs, in order and fail-closed: `preflight → gate → research-profile → views →
templates → aux → clean-copy → verify → test`. The first non-zero exit stops everything.

Faster first look — just the flagship document:

```powershell
./build.ps1 research-profile
```

Rendering is quick: each document is roughly **2 s**; a full `all` is about a minute,
dominated by the 122-case test suite (15.5 s) rather than by typesetting.

---

## 4. What to check — acceptance

`./build.ps1 all` must end with `SUCCESS:all` and **exit code 0**. Check the exit code, not
just the text:

```powershell
./build.ps1 all; echo $LASTEXITCODE     # expect 0
```

Then confirm these four things:

**4.1 — Ten PDFs exist, with these page counts.** They are asserted by the contract, so a
wrong count is a failure, not a cosmetic difference.

| File | Pages |
|---|---|
| `out/Andrei-Mihai_Visalon_research_profile_onepage.pdf` | **1** |
| `out/Andrei_Mihai_Visalon_ats_en.pdf` | 2 |
| `out/Andrei_Mihai_Visalon_ro.pdf` | 2 |
| `out/Andrei_Mihai_Visalon_academic.pdf` | 2 |
| `out/Andrei_Mihai_Visalon_research_profile.pdf` | 2 |
| `out/Andrei_Mihai_Visalon_europass.pdf` | 3 |
| `out/templates/academic_cv.pdf` | 3 |
| `out/templates/ats-en/Andrei-Mihai_Visalon_ATS_EN.pdf` | 2 |
| `out/templates/ro/Andrei-Mihai_Visalon_CV_RO.pdf` | 2 |
| `out/templates-clean/academic_cv.pdf` | 2 |

Plus 15 markdown packs and 2 Europass YAML files under `out/templates*/`.

**4.2 — Every manifest says the gate ran.**

```powershell
Select-String -Path out/*.manifest.json -Pattern 'gate_skipped'
# every line must read "gate_skipped": false
```

A `true` there means the document was produced with `--skip-gate` and **must not be sent to
anyone**.

**4.3 — The tests and all three gate self-tests pass.**

```
122 passed
SUCCESS:selftest (11 cases)      # tools/verify.py
SUCCESS:selftest 29 checks       # templates/docgate.py
SUCCESS:killlist-self-test       # templates/killlist.py
```

Each self-test proves its checks in **both** states: every check is shown to go RED on a
deliberately broken fixture and GREEN when clean. A suite that only ever passes proves nothing.

**4.4 — The gate is genuinely fail-closed.** Do not take this on trust; break it on purpose:

```powershell
Copy-Item profile.yaml /tmp/p.yaml
Add-Content /tmp/p.yaml '  fake_claim: "shipped 4,821 features"'
.venv/Scripts/python.exe tools/zerofab.py /tmp/p.yaml    # expect: ZF001 error, exit 1
```

An unsourced figure must produce an error and a non-zero exit. If it does not, the gate is
not protecting you and nothing below it should be trusted.

---

## 5. Expected non-failures — do not "fix" these

| What you will see | Why it is correct |
|---|---|
| `SKIPPED:designed`, `SKIPPED:cover`, `SKIPPED:linkedin`, `SKIPPED:platform-packs` | Those views declare no renderer. `cover`/`linkedin`/`platform-packs` are emitted as **text** by `emit.py`. `designed` has no producer at all and is routed to `design-studio` by hand. |
| **14 `ZF010` warnings** from the gate | Verified evidence in `x_metrics` that renders on no surface. A review queue, not a defect. Exit stays 0. |
| Visible `TODO-CONFIRM` markers in the PDFs | Deliberate. Facts the owner has not confirmed are printed as gaps rather than guessed. Use `--todo omit` for a reader copy — the gap stops printing, it does not stop existing. |
| `Dates: 2021-05 to TODO-CONFIRM` on the DINUPLAST entry | The end date is genuinely unknown (two 2023 CVs contradict each other). The renderer refuses to substitute `present`, which would assert an ongoing engagement nobody verified. |
| Documents marked **DRAFT** | `docgate`'s D9 check counts TODO markers and downgrades the status. Correct until the owner answers §7. |

---

## 6. Troubleshooting

**`No venv at …` →** run `./build.ps1 setup`.

**`GATE zerofab gate exited 1 - render refused` (exit 3) →** working as designed. Read the
`ZF…` codes; a `ZF008` means a repo is described as "open-source" with no declared LICENSE.
Fix the **profile**, never the gate.

**A RenderCV validation error with a `KeyError` in `pydantic_error_handling.py` →** RenderCV
2.8's own error handler crashes while reporting a validation error, masking the real cause.
Diagnose by validating the intermediate directly:

```python
import yaml
from rendercv.schema.models.rendercv_model import RenderCVModel
RenderCVModel(**yaml.safe_load(open('out/<slug>.rendercv.yaml', encoding='utf-8')))
```

**`verify` fails on `letter.pdf` / `twocol.pdf` / `ligature.pdf` →** you are verifying test
fixtures. `verify.py --selftest` writes deliberately broken PDFs into `out/_selftest/` to prove
each check fires. Both drivers skip any `_`-prefixed directory; if you call `verify.py` by hand,
skip them yourself. *(This was a real bug in the driver, found by running it twice.)*

**Romanian diacritics render as cedilla forms (ş/ţ) instead of comma-below (ș/ț) →** the
XCharter font did not load. Confirm `rendercv_fonts` is installed; do **not** install a system
font as a workaround, because then the build stops being portable.

**Git mangles line endings / a `.sh` file breaks →** this repo is edited from both PowerShell
and Git Bash on Windows. Git will warn `LF will be replaced by CRLF`. Harmless for the Python
and YAML here; do not "fix" it by rewriting files wholesale.

**MSYS path weirdness →** under Git Bash, a `/c/Users/...` path handed to a **Windows** Python
will not resolve. Use Windows-style paths when crossing that boundary. This has produced silent
false-green results before: a mutation test wrote its fixtures to a `/tmp` the test runner never
read, so every mutant "passed".

---

## 7. What reproduction does NOT give you

A green build is **not** a sendable document. The content gaps travel with the repo:

- **27 open facts** in `TODO-CONFIRM.md`, in four blocking tiers.
- The blocking ones: DINUPLAST title/end-date/location · ChemRxiv title + DOI · Zenodo DOI ·
  exact English CEFR level · the ORCID record (zero works, and it credits the BSc to the wrong
  university) · LICENSE status for ZHMModSDK, Reframe and the GRACE repo · named referees.
- **No CI.** Nothing re-runs these gates automatically. On a second machine, `./build.ps1 all`
  before every send is the whole safety net.

Reproducing the *pipeline* is a solved, one-command problem. Reproducing the *facts* requires
the owner.
