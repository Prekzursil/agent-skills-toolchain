"""The lawful-access policy — the heart of this MCP.

Hard rules (non-negotiable, enforced in code, not just docs):
  * NO Sci-Hub / LibGen / SciDownl / scihub.py / shadow-library / mirror scraping — EVER.
  * NO paywall bypass.
  * NO fake "open-access" classification: a copy that is only *free-to-read* behind a
    publisher bot-wall (e.g. PMC web reader, not in the redistributable OA subset) is NOT
    classified as a downloadable OA PDF.
  * NO silent fallback to an unauthorized source.
  * download_oa_pdf only accepts a URL that a legitimate resolver returned AND whose host is
    on the allowlist AND whose bytes are a real %PDF. URLs are never *constructed*.

Access categories returned by `access_status` (honest, mutually exclusive):
  oa_pdf                         — a redistributable OA PDF exists at a legitimate source (downloadable)
  free_to_read_not_redistributable — readable on a publisher/PMC page but no license/clean API to fetch
                                     (we will NOT circumvent the access control — cite, don't download)
  subscription                   — paywalled; no authorized free copy (cite only)
  unavailable                    — no full text located anywhere legitimate
  unknown                        — could not determine (resolver error / no DOI)
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# DENYLIST — sources we will never touch. Presence of any of these in a URL is
# a hard error, regardless of how the URL arrived.
# ---------------------------------------------------------------------------
DENY_SUBSTRINGS = (
    "sci-hub", "scihub", "sci_hub", "sci.hub",
    "libgen", "library.lol", "libgen.rs", "libgen.is", "libgen.st",
    "scidownl", "annas-archive", "annas archive", "z-lib", "zlibrary", "z-library",
    "booksc", "b-ok", "1lib", "sci-mcp-server",
)

# ---------------------------------------------------------------------------
# ALLOWLIST — the only hosts download_oa_pdf will fetch from. These are
# legitimate OA aggregators, repositories, preprint servers, and OA publishers.
# (Suffix match on the registrable host.)
# ---------------------------------------------------------------------------
ALLOW_HOST_SUFFIXES = (
    # OA aggregators / repositories
    "ncbi.nlm.nih.gov", "europepmc.org", "core.ac.uk", "doaj.org", "zenodo.org",
    # preprint servers
    "arxiv.org", "biorxiv.org", "medrxiv.org", "psyarxiv.com", "osf.io",
    "chemrxiv.org", "preprints.org", "researchsquare.com",
    # institutional / aggregator repositories
    "hal.science", "hal.archives-ouvertes.fr", "ssrn.com", "openalex.org",
    # fully-OA publishers (serve free PDFs on their own domain)
    "frontiersin.org", "mdpi.com", "plos.org", "hindawi.com",
    "biomedcentral.com", "springeropen.com", "nature.com",
    "elifesciences.org", "peerj.com", "wellcomeopenresearch.org",
    "f1000research.com", "jmir.org", "elsevier.com",  # Elsevier = entitled-fulltext API only
)

# Generic academic-repository host fragments we also trust (institutional repos).
ALLOW_HOST_FRAGMENTS = (".edu", ".ac.uk", "repository", "dspace", "eprints", "research-repository")

# Hosts that LOOK institutional (end in .edu etc.) but are author-upload / sharing platforms,
# NOT authorized OA repositories. The spec explicitly excludes these. Off-allowlist (cite, don't fetch).
NOT_AUTHORIZED_HOSTS = ("academia.edu", "www.academia.edu", "researchgate.net", "scribd.com")


def is_denied(url: str) -> bool:
    u = (url or "").lower()
    return any(bad in u for bad in DENY_SUBSTRINGS)


def _host(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(url).hostname or "").lower()


def is_allowed_host(url: str) -> bool:
    """True only if the URL is on the legitimate allowlist (and not denied)."""
    if is_denied(url):
        return False
    host = _host(url)
    if not host:
        return False
    if any(host == bad or host.endswith("." + bad) for bad in NOT_AUTHORIZED_HOSTS):
        return False  # author-upload/sharing site masquerading as institutional — not authorized
    if any(host == s or host.endswith("." + s) or host.endswith(s) for s in ALLOW_HOST_SUFFIXES):
        return True
    return any(frag in host for frag in ALLOW_HOST_FRAGMENTS)


def assert_lawful(url: str) -> None:
    """Raise on any URL that is denied or off-allowlist. Use before any fetch."""
    if is_denied(url):
        raise PermissionError(
            f"Refused: '{url}' resolves to a shadow-library / unauthorized source. "
            "This MCP never touches Sci-Hub/LibGen/SciDownl or any mirror."
        )
    if not is_allowed_host(url):
        raise PermissionError(
            f"Refused: host of '{url}' is not on the legitimate OA allowlist. "
            "download_oa_pdf only fetches resolver-provided OA copies from authorized hosts."
        )


# Categories (string constants so callers/tests don't typo them).
OA_PDF = "oa_pdf"
FREE_NOT_REDIST = "free_to_read_not_redistributable"
SUBSCRIPTION = "subscription"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"

POLICY_BANNER = (
    "Lawful scholarly access only — open-access + rights-holder-entitled sources. "
    "No Sci-Hub/LibGen/SciDownl/shadow libraries, no paywall bypass, no fake-OA, no silent fallback."
)
