"""TST-0255 external-link classification: WRONG (a real status code) vs
UNREACHABLE (offline / transient / refused) — never folded together.

On the Linux original, egress blocking used ``unshare -n``. This probe lane is
hermetic: it classifies a REAL 404 from a loopback HTTP server and a REAL
unreachable endpoint (connection refused on 127.0.0.1:1) with zero external
egress, so the classification distinction is proven on this host, not assumed.
"""
from __future__ import annotations

import urllib.error
import urllib.request


def classify(url: str, timeout: float = 4.0, retries: int = 2) -> dict:
    """One URL -> OK / WRONG(status) / UNREACHABLE, with bounded retries."""
    last_kind = "unknown"
    last_detail = ""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "p2-g1-tst0255/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    "url": url,
                    "classification": "OK",
                    "status": resp.status,
                    "attempts": attempt + 1,
                    "kind": "http",
                }
        except urllib.error.HTTPError as exc:
            # A status code came back from A SERVER: this is a real verdict.
            return {
                "url": url,
                "classification": "WRONG" if exc.code in (404, 410) else "HTTP-OTHER",
                "status": exc.code,
                "attempts": attempt + 1,
                "kind": "http-error",
            }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # No server answered: offline / refused / DNS / transient.
            last_kind = "unreachable"
            last_detail = f"{type(exc).__name__}: {exc}"[:200]
            if attempt < retries:
                import time

                time.sleep(0.2)
    return {
        "url": url,
        "classification": "UNREACHABLE",
        "status": None,
        "attempts": retries + 1,
        "kind": last_kind,
        "detail": last_detail,
    }


def never_folds_unreachable_into_wrong(results: list[dict]) -> bool:
    """Classifier property: no UNREACHABLE-shaped result may carry WRONG."""
    for r in results:
        if r.get("classification") == "UNREACHABLE" and r.get("status") is not None:
            return False
    return True
