"""Manual verification of the playwright-touching half against the LIVE rail.

Not a unit test: it needs a browser started by Start-BrowserRail.ps1. Run it by
hand and paste the output as evidence. It drives example.com only -- it never
touches one of the owner's authenticated sites.

Run:  python manual_probe_live.py
"""

from __future__ import annotations

import time

from browser_rail import (
    AuthSignals,
    PayloadInlinedError,
    classify_auth,
    evaluate_with_arg,
    find_or_open_page,
    is_authed,
    rail,
    upload_text_as_file,
    visible_role_names,
)

URL = "https://example.com/"

# Artificial but real: example.com renders a "Learn more" link and no "Sign in"
# control. Both directions are configured, so the detector can fire either way --
# which is what makes the verdict meaningful.
#
# The first run of this probe used "More information" here (the page's OLD link
# text). It did NOT match, and the verdict came back UNKNOWN rather than a
# confident wrong answer. That is the AuthVerdict(None) state doing its job.
SIGNALS = AuthSignals(
    logged_out_url_substrings=("/login",),
    logged_out_names=("Sign in",),
    logged_in_names=("Learn more",),
)
STALE_SIGNALS = AuthSignals(
    logged_out_names=("Sign in",),
    logged_in_names=("More information",),  # deliberately stale
)


def main() -> int:
    print(f"both_states_ready={SIGNALS.both_states_ready}")
    started = time.time()
    with rail() as browser:
        # This spans playwright DRIVER startup + connect_over_cdp, not the CDP
        # handshake alone. Report it as such -- the sub-second figure quoted for
        # connect_over_cdp does not include bringing the driver up.
        print(
            f"driver_start_plus_connect={time.time() - started:.2f}s "
            f"contexts={len(browser.contexts)}"
        )

        nav_started = time.time()
        page, opened = find_or_open_page(browser, URL)
        print(
            f"page_url={page.url} opened={opened} "
            f"nav_secs={time.time() - nav_started:.2f}"
        )

        names = visible_role_names(page)
        print(f"role_names={names}")

        verdict = is_authed(page, SIGNALS)
        print(
            f"verdict authed={verdict.authed} reason={verdict.reason} ev={verdict.evidence!r}"
        )

        # Detector must also fire in the OTHER direction on the same page.
        flipped = classify_auth(page.url, ["Sign in"], SIGNALS)
        print(f"flipped authed={flipped.authed} reason={flipped.reason}")

        # ...and a STALE marker must degrade to UNKNOWN, never to a false verdict.
        stale = classify_auth(page.url, names, STALE_SIGNALS)
        print(f"stale authed={stale.authed} reason={stale.reason} known={stale.known}")

        # evaluate-with-arg: content travels as an argument.
        payload = "rail-arg-transport-check-" + "x" * 20
        echoed = evaluate_with_arg(page, "(arg) => arg.text.length", {"text": payload})
        print(f"evaluate_arg_len={echoed} expected={len(payload)}")

        # ...and the guard must REFUSE the inlined form.
        try:
            evaluate_with_arg(page, f"(arg) => '{payload}'", {"text": payload})
            print("guard=NOT-FIRED (BUG)")
        except PayloadInlinedError as exc:
            print(f"guard=fired ok ({type(exc).__name__})")

        # File upload via DataTransfer, content as an ARG.
        page.set_content('<input id="f" type="file">')
        result = upload_text_as_file(page, "#f", "note.txt", "hello from the rail")
        print(f"upload_result={result}")

        if opened:
            page.close()
            print("closed_page_we_opened=true")
    print("SUCCESS:manual-probe live rail exercised")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
