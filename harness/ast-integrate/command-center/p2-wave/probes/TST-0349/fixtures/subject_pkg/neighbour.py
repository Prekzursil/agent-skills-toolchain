"""Neighbour dependency. Mocking this must NOT flag an HttpClient subject."""


class DnsResolver:
    def resolve(self, host: str) -> str:
        raise RuntimeError(f"dns forbidden in unit tests: {host}")
