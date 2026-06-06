"""Offline, deterministic tests for the lawful-access policy (no network)."""
import pytest

from scholarly_access import policy


@pytest.mark.parametrize("url", [
    "https://sci-hub.se/10.1/x",
    "http://sci-hub.st/10.1/x",
    "https://libgen.is/scimag/10.1/x",
    "https://libgen.rs/x",
    "https://annas-archive.org/scidb/10.1/x",
    "https://z-lib.org/x",
    "https://example.com/scidownl/x",
])
def test_denied_sources_blocked(url):
    assert policy.is_denied(url) is True
    with pytest.raises(PermissionError):
        policy.assert_lawful(url)


@pytest.mark.parametrize("url", [
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/pdf/",
    "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123/pdf/",
    "https://europepmc.org/articles/PMC123?pdf=render",
    "https://arxiv.org/pdf/2401.00001",
    "https://www.biorxiv.org/content/10.1101/x.full.pdf",
    "https://api.core.ac.uk/v3/works/123/download",
    "https://journals.plos.org/plosone/article/file?id=10.1371/x",
    "https://www.mdpi.com/2076-3417/1/1/1/pdf",
    "https://research.manchester.ac.uk/files/123/FULL_TEXT.PDF",
    "https://hal.science/hal-02485707/document",
])
def test_allowlisted_hosts_pass(url):
    assert policy.is_denied(url) is False
    assert policy.is_allowed_host(url) is True
    policy.assert_lawful(url)  # must not raise


@pytest.mark.parametrize("url", [
    "https://onlinelibrary.wiley.com/doi/pdf/10.1/x",   # publisher paywall page
    "https://www.sciencedirect.com/science/article/pii/x",
    "https://www.researchgate.net/publication/123",      # not an authorized OA host
    "https://www.academia.edu/123",
])
def test_offallowlist_hosts_refused(url):
    assert policy.is_denied(url) is False        # not a pirate site...
    assert policy.is_allowed_host(url) is False  # ...but not an authorized OA host either
    with pytest.raises(PermissionError):
        policy.assert_lawful(url)


def test_categories_distinct():
    cats = {policy.OA_PDF, policy.FREE_NOT_REDIST, policy.SUBSCRIPTION, policy.UNAVAILABLE, policy.UNKNOWN}
    assert len(cats) == 5
