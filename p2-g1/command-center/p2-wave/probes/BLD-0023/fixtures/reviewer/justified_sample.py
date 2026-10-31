"""Ten JUSTIFIED except:pass sites (reason+expiry) plus one decorative UNACCOUNTED."""


def _call() -> None:
    raise RuntimeError("x")


try:
    _call()
except Exception:
    pass  # expiry: 2026-12-31 reason: until 2026-12-31 Windows CI job WIN-441 stays red on CRLF checkout

try:
    _call()
except Exception:
    pass  # expiry: 2027-01-15 reason: until 2027-01-15 flake issue #882 when the vendor 429 budget is exhausted

try:
    _call()
except Exception:
    pass  # expiry: 2026-09-30 reason: because hooks/semantic-router embed pull is still unpinned (bug EMB-12)

try:
    _call()
except Exception:
    pass  # expiry: 2026-11-01 reason: remove after the POSIX-only path is gated by AUD-0054 platform census

try:
    _call()
except Exception:
    pass  # expiry: 2028-03-01 reason: until 2028-03-01 the cloud-batch substrate has no reachability probe

try:
    _call()
except Exception:
    pass  # expiry: 2026-10-10 reason: if routing-benchmark.yml is restored, this shadow step stays continue-on-error

try:
    _call()
except Exception:
    pass  # expiry: 2027-06-01 reason: when jsonschema is absent the contract checker is dark (ready_units LIT/DARK)

try:
    _call()
except Exception:
    pass  # expiry: 2026-08-31 reason: because git worktree isolation is missing on this Linux worker until IMP-0440

try:
    _call()
except Exception:
    pass  # expiry: 2027-02-28 reason: until 2027-02-28 PowerShell SilentlyContinue sites lack a documented sunset

try:
    _call()
except Exception:
    pass  # expiry: 2026-12-01 reason: tracked failure class green-not-live until quality.yml grows unitgate

try:
    _call()
except Exception:
    pass  # best effort
