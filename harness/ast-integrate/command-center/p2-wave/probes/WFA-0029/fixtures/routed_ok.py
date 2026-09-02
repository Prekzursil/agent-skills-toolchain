"""Sweep-lane shaped call that routes through the scheduler choke point."""
from acquire import credentialed_call
import urllib.request


def scheduled_transport(request):
    # I/O lives only as the injected transport of credentialed_call.
    return {"status": 200, "url": request.get("url")}


def fetch_release_index(scheduler):
    return credentialed_call(
        "github",
        scheduled_transport,
        request={"url": "https://api.github.com/repos/example/workflow/releases"},
        scheduler=scheduler,
    )


def fetch_via_lambda(scheduler):
    return credentialed_call(
        "github",
        lambda req: urllib.request.urlopen(req.get("url") or "https://example.invalid"),
        request={"url": "https://api.github.com/zen"},
        scheduler=scheduler,
    )
