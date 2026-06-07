"""Offline, deterministic tests for the unrestricted access policy."""
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
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/pdf/",
    "https://onlinelibrary.wiley.com/doi/pdf/10.1/x",
])
def test_all_sources_allowed(url):
    assert policy.is_denied(url) is False
    assert policy.is_allowed_host(url) is True
    policy.assert_lawful(url)  # must not raise

def test_empty_url_refused():
    with pytest.raises(PermissionError):
        policy.assert_lawful("")

def test_categories_distinct():
    cats = {policy.OA_PDF, policy.FREE_NOT_REDIST, policy.SUBSCRIPTION, policy.UNAVAILABLE, policy.UNKNOWN}
    assert len(cats) == 5
