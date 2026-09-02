"""Planted control: the test configures a mock and asserts that configuration."""

from unittest.mock import Mock


def test_planted_assert_own_mock_tst0348():
    client = Mock()
    client.compute.return_value = 42
    assert client.compute() == 42
