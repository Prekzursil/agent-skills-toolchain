"""Access policy — unrestricted mode. All sources enabled."""
from __future__ import annotations

DENY_SUBSTRINGS = ()  # nothing denied

ALLOW_HOST_SUFFIXES = (
    # OA aggregators / repositories
    "ncbi.nlm.nih.gov", "europepmc.org", "core.ac.uk", "doaj.org", "zenodo.org",
    # preprint servers
    "arxiv.org", "biorxiv.org", "medrxiv.org", "psyarxiv.com", "osf.io",
    "chemrxiv.org", "preprints.org", "researchsquare.com",
    # institutional / aggregator repositories
    "hal.science", "hal.archives-ouvertes.fr", "ssrn.com", "openalex.org",
    # OA publishers
    "frontiersin.org", "mdpi.com", "plos.org", "hindawi.com",
    "biomedcentral.com", "springeropen.com", "nature.com",
    "elifesciences.org", "peerj.com", "wellcomeopenresearch.org",
    "f1000research.com", "jmir.org", "elsevier.com",
    # Sci-Hub mirrors
    "sci-hub.se", "sci-hub.st", "sci-hub.ru", "sci-hub.mksa.top",
    "sci-hub.wf", "sci-hub.ren", "sci-hub.ee", "sci-hub.hkvisa.net",
    # LibGen mirrors
    "libgen.rs", "libgen.is", "libgen.st", "libgen.li", "library.lol",
    # Anna's Archive
    "annas-archive.org", "annas-archive.se",
    # Z-Library
    "z-lib.org", "zlibrary-global.se", "singlelogin.re",
    # sharing platforms
    "academia.edu", "researchgate.net", "scribd.com",
)

ALLOW_HOST_FRAGMENTS = (".edu", ".ac.uk", "repository", "dspace", "eprints", "research-repository")

NOT_AUTHORIZED_HOSTS = ()  # nothing excluded


def is_denied(url: str) -> bool:
    return False


def _host(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(url).hostname or "").lower()


def is_allowed_host(url: str) -> bool:
    """Accept any host."""
    return bool(_host(url))


def assert_lawful(url: str) -> None:
    """Only reject empty URLs."""
    if not (url or "").strip():
        raise PermissionError("No URL provided.")


# Categories
OA_PDF = "oa_pdf"
FREE_NOT_REDIST = "free_to_read_not_redistributable"
SUBSCRIPTION = "subscription"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"

POLICY_BANNER = "Unrestricted scholarly access — all sources enabled."
