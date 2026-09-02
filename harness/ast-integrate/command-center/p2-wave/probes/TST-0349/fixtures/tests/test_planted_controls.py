"""Planted both-states controls for TST-0349.

These tests are AST-scanned, not collected as the program's suite. They
assert plenty (they are not C23 vacuous tests): the defect is that some
of them patch the very subject they claim to verify.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from subject_pkg.http_client import HttpClient
from subject_pkg.neighbour import DnsResolver


@patch("subject_pkg.http_client.HttpClient")
def test_http_client_patches_own_subject(mock_cls):
    mock_cls.return_value.get.return_value = MagicMock(status_code=200, text="ok")
    body = mock_cls.return_value.get("http://example.test/health")
    assert body.status_code == 200
    assert body.text == "ok"
    mock_cls.return_value.get.assert_called_once()


@patch("subject_pkg.http_client.HttpClient.get")
def test_http_client_patches_own_subject_low(mock_get):
    mock_get.return_value = MagicMock(status_code=204)
    assert mock_get("http://example.test").status_code == 204
    mock_get.assert_called()


@patch("subject_pkg.neighbour.DnsResolver.resolve")
def test_http_client_patches_neighbour(mock_resolve):
    mock_resolve.return_value = "203.0.113.8"
    assert mock_resolve("example.test") == "203.0.113.8"
    mock_resolve.assert_called_once_with("example.test")


def test_mention_only_does_not_patch():
    snippet = 'patch("subject_pkg.http_client.HttpClient")'
    # patch("subject_pkg.http_client.HttpClient")
    assert "HttpClient" in snippet
    assert snippet.startswith("patch")
    client = HttpClient
    assert client.__name__ == "HttpClient"


@patch.object(HttpClient, "get")
def test_patch_object_own_subject(mock_get):
    mock_get.return_value = MagicMock(status_code=201)
    assert mock_get("http://example.test/create").status_code == 201
    mock_get.assert_called()


def test_mocker_patches_own_subject(mocker):
    mocked = mocker.patch("subject_pkg.http_client.HttpClient")
    mocked.return_value.get.return_value = MagicMock(status_code=200)
    assert mocked.return_value.get("http://example.test").status_code == 200


@patch("os.environ.get")
@patch("socket.create_connection")
@patch("subject_pkg.neighbour.DnsResolver.resolve")
def test_three_neighbour_mocks(mock_dns, mock_sock, mock_env):
    mock_dns.return_value = "198.51.100.10"
    mock_sock.return_value = MagicMock()
    mock_env.return_value = "1"
    assert mock_dns("example.test") == "198.51.100.10"
    assert mock_env("FLAG") == "1"
    mock_sock.assert_not_called()
    assert DnsResolver.__name__ == "DnsResolver"


def test_context_manager_patches_own_subject():
    with patch("subject_pkg.http_client.HttpClient") as mock_cls:
        mock_cls.return_value.get.return_value = MagicMock(status_code=200)
        assert mock_cls.return_value.get("http://example.test").status_code == 200
        mock_cls.return_value.get.assert_called()
