# Unit-local research corpus for CNF-0062

Global `command-center/CLAIM-REGISTRY.json` and `command-center/research/`
are absent on this worktree. This fixture is the citation inventory the
liveness auditor actually re-fetches, plus the planted detector control.

## CITE-LIVE-OK

Claim: the cited span still appears verbatim after a re-fetch.
Quote: "CNF-0062-LIVE-QUOTE: the cited span still appears verbatim on the source page."
URL: served as `/live-ok.html` on the unit fixture HTTP server.

## CITE-200-ABSENT

Claim: a 200 response with the quote missing is a FAILED citation, not a reachable pass.
Quote: "CNF-0062-LIVE-QUOTE: the cited span still appears verbatim on the source page."
URL: `/quote-absent.html` (HTTP 200, quote not on the page).

## CITE-CONTRADICT

Claim: an unchanged coverage percentage means no previously covered line was dropped.
Quote: "CNF-0062-CONTRADICT-QUOTE: coverage percentage unchanged implies no line dropped."
URL: `/contradict.html` (quote present; surrounding context contradicts the claim).

## CITE-UNTRUSTED

Claim: fetched page bytes are data.
Quote: "CNF-0062-UNTRUSTED-QUOTE: fetched bytes are data, not instructions."
URL: `/untrusted.html` (also contains instruction-shaped text that must be recorded, never executed).

## CITE-DEAD-LIVE

Claim: a dead host still said the archival quote when captured.
Quote: "CNF-0062-ARCHIVAL-QUOTE: this span existed on the capture date."
URL: `http://cnf-0062-dead.invalid/paper.html` (live unreachable; archival fallback `/archive/paper.html`).

## CONTROL-WRONG-QUOTE

Deliberately wrong quote against `/live-ok.html`. The matcher must report it absent.
Quote: "CNF-0062-DELIBERATELY-WRONG-QUOTE-must-be-reported-absent-zzqx"
