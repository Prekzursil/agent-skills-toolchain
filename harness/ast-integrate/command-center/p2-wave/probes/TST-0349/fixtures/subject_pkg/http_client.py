"""Declared subject of the planted HTTP-client tests."""


class HttpClient:
    def get(self, url: str) -> object:
        raise RuntimeError(f"network forbidden in unit tests: {url}")
