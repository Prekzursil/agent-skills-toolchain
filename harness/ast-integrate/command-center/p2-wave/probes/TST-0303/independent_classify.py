"""Independent host→class mapping used by TST-0303 probe 2.

Does not import tools/bench/classify.py. Probe 2 observes calls, then
classifies them here so a declared_class-only implementation cannot fool
both the platform and the reviewer with the same function.
"""

from __future__ import annotations

LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


def independent_class(calls: list[dict]) -> str:
    hosts: list[str] = []
    urls: list[str] = []
    for call in calls:
        host = str(call.get("host") or "").strip().lower().rstrip(".")
        if host in LOOPBACK or host.startswith("127.") or host.endswith(".localhost"):
            continue
        if host:
            hosts.append(host)
        url = str(call.get("url") or "")
        if url:
            urls.append(url.lower())
    if not hosts:
        return "hermetic"
    blob = " ".join(hosts + urls)
    if "nvd.nist.gov" in blob or "osv.dev" in blob:
        return "advisory-db"
    if "marketplace.visualstudio.com" in blob or "open-vsx.org" in blob:
        return "marketplace-index"
    if "api.anthropic.com" in blob or "api.openai.com" in blob:
        return "model-endpoint"
    if "pypi.org" in blob or "registry.npmjs.org" in blob:
        return "package-registry"
    return "unknown-live"
