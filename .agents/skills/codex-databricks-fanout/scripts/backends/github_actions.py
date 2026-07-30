r"""VerifyBackend: the ONLY tier that reads a repo's real ubuntu+windows+macos matrix (R7 correlation
half). Correlate check-runs by the branch's exact HEAD SHA (no workflow_dispatch 204->list-runs race).
Trigger machinery (draft-PR open, workflow_dispatch fallback with a per-run UUID, per-repo trigger
detection) is DEFERRED (Roadmap): verify() READS a verdict for an already-triggered SHA — it does not
itself fire CI.

Caveats that MUST travel with any caller of this class:
- An empty platform dict is NOT green (no-CI != pass). Fails CLOSED.
- A queued/in_progress run has conclusion=None and therefore reads RED — verify() is a SETTLED-STATE
  read, not a liveness poll; the caller must wait for settlement (the `status` field is what
  distinguishes "still pending" from "genuinely failed"). Fails CLOSED.
- Several check-runs may match the SAME platform token (a `test (ubuntu-latest, 3.11)` + `3.12`
  matrix, or a `lint (ubuntu-latest)` job beside `test (ubuntu-latest)`): the legs are folded
  ANY-RED-WINS, so a red leg can never be erased by a later green one and the verdict does not
  depend on check_runs ordering (which this module does not control).
- `all_green` is the PLATFORM-MATRIX verdict, NOT "all of CI passed": a red NON-platform job (e.g.
  `lint`) is ignored by design, so a caller gating a merge must AND this with its own non-matrix
  checks.

Platform matching takes a family prefix PLUS the runner's own suffix — `(?:ubuntu|windows|macos)-[\w.]+`
— so PINNED runners (`windows-2022`, `ubuntu-24.04`, `macos-14`) are counted under their FULL token as
distinct keys. Deliberately NOT collapsed to a family key (`ubuntu`), which would merge distinct
runners into one verdict slot.

REFUTED WORDING (the round-1 docstring, quoted so the dead end is not re-walked rather than silently
deleted): "the platform regex recognises only the `*-latest` labels, so PINNED runner versions
(ubuntu-24.04, windows-2022, macos-14) do not match and a fully green matrix on such a repo reads as
not-green. Fails CLOSED". FALSE for a MIXED matrix. Executed against the round-1 module,
`[test (ubuntu-latest)=success, test (windows-2022)=failure]` yielded `platforms={'ubuntu-latest':
True}` and `all_green=True` — the RED leg was silently DROPPED, i.e. FAIL-OPEN, the same shape the
any-red-wins fold exists to prevent. The companion claim "no red is ever hidden" is retracted too.

REFUTED WORDING #2 (the round-2 over-match caveat, quoted for the same reason): "Neither can erase a
red leg — a spurious key only adds a value, and the fold is any-red-wins — so these can make the
verdict stricter, never greener." FALSE as an unconditional safety property. Falsifier, executed:
`[test (3.11)=failure, windows-installer=success]` -> `platforms={'windows-installer': True}`,
`all_green=True` — a RED leg is present and the verdict is GREEN. The sentence conflated "cannot erase
a MATCHED red leg" (TRUE — control below) with "cannot make the verdict greener" (FALSE — a spurious
GREEN key defeats the empty-dict fail-CLOSED at :75).

RESIDUAL after the widening — scoped, NOT a blanket "fails closed":
- Name-based correlation can only see a platform that is NAMED in the check-run name. A red leg whose
  name carries a self-hosted/custom label (`self-hosted`, `linux-arm64`) or omits the OS entirely
  (`build`, `test (3.11)`) is still DROPPED, so those shapes remain FAIL-OPEN. The real fix is reading
  each job's `runs-on`/labels from the workflow-run API rather than its display name (Roadmap, with
  the trigger half).
- Matching is CASE-SENSITIVE (`re.compile` with no `re.IGNORECASE`), yet GitHub runner labels are
  case-INsensitive and title-cased job names are common — so a red leg named `Test (Windows-Latest)`
  is DROPPED, exactly like the OS-less shape above. Executed: `[Test (Windows-Latest)=failure,
  test (ubuntu-latest)=success]` -> `platforms={'ubuntu-latest': True}`, `all_green=True`; control,
  the same pair lower-cased -> `platforms={'windows-latest': False, 'ubuntu-latest': True}`,
  `all_green=False`. A reader auditing their repo against this list must check job-name CASE too, not
  only whether the OS is named. `re.IGNORECASE` is the eventual fix but it WIDENS the over-match
  below, so it is deliberately NOT applied here (Roadmap, with the `runs-on` read).
- Over-matching is only CONDITIONALLY fail-safe: a job that merely MENTIONS a runner
  (`docs (mentions ubuntu-latest)`) is counted as that platform, and a longer label
  (`ubuntu-latest-4-cores`) truncates to `ubuntu-latest` and AND-folds into it. An over-match cannot
  erase a leg that WAS matched — the any-red-wins fold protects that, and it is measured both ways:
  `windows-installer=success` beside a MATCHED `test (windows-latest)=failure` yields
  `all_green=False`, and a same-KEY collision (`test (ubuntu-latest-4-cores)=success` folding onto a red
  `test (ubuntu-latest)`) yields `{'ubuntu-latest': False}` in EITHER check_runs order.
  But a spurious GREEN key IS the path that turns an otherwise-EMPTY `platforms`
  into `all_green=True`, because `all_green = bool(platforms) and all(...)` (:75) derives the
  documented no-CI-fails-CLOSED purely from the dict being empty. So over-matching is fail-safe ONLY
  while at least one real platform leg is matched; pair it with a red leg this module cannot match (the
  two residuals above) and a red matrix reads GREEN. Controls: the red leg alone -> `platforms={}`,
  `all_green=False` (fail-CLOSED as documented); the over-match alone -> `all_green=True`. The real fix
  needs an EXPECTED-platform set to compare the matched keys against, and only the DEFERRED trigger
  half knows that set (Roadmap) — do NOT patch it by widening the regex or changing the fold."""

from __future__ import annotations

import re
from typing import Protocol

from backends.base import MatrixVerdict

_PLATFORM = re.compile(r"((?:ubuntu|windows|macos)-[\w.]+)")


class GhClient(Protocol):
    """Injection seam for the DEFERRED real client — this module performs no network I/O."""

    def head_sha(self, repo: str, branch: str) -> str: ...
    def check_runs(self, repo: str, sha: str) -> list[dict]: ...


class GithubActionsVerifyBackend:
    def __init__(self, gh_client: GhClient):
        self.gh = gh_client

    def verify(self, repo: str, branch: str) -> MatrixVerdict:
        sha = self.gh.head_sha(repo, branch)
        platforms: dict[str, bool] = {}
        for run in self.gh.check_runs(repo, sha):
            m = _PLATFORM.search(run.get("name", ""))
            if m:
                ok = run.get("conclusion") == "success"
                key = m.group(1)  # FULL token, never the family key
                platforms[key] = platforms.get(key, True) and ok  # any-red-wins fold
        all_green = bool(platforms) and all(platforms.values())
        return MatrixVerdict(
            repo=repo,
            branch=branch,
            head_sha=sha,
            platforms=platforms,
            all_green=all_green,
        )
