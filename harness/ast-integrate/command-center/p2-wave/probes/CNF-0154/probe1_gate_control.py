#!/usr/bin/env python3
"""Probe 1: gate control, arg-limit, background ban, unsourced CONFIRMED invalid."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from claims import p0_ids  # noqa: E402
from dispatch_one import run_claim, write_prompt  # noqa: E402
from blinding import assemble  # noqa: E402
from claims import claim_by_id  # noqa: E402
from rail import dispatch  # noqa: E402
from record_schema import schema_errors  # noqa: E402
from windows_argv import INLINE_PROMPT_MEASURED  # noqa: E402

ART = REPO / "command-center" / "receipts" / "CNF-0154.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0154-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0154" not in text:
        return fail("sentinel absent")

    unsourced = {
        "claim_id": "smuggle",
        "confirmer": {"identity": "x", "vendor": "openai"},
        "blinding_attestation": "a" * 64,
        "baseline_repro": {},
        "corrected_repro": {},
        "rollback_repro": {},
        "regression_diff": {},
        "discrepancies": [],
        "verdict": "CONFIRMED",
        "source_probe": "",
        "verifier_probe": "b" * 64,
        "residual_caveat": "none",
    }
    if not schema_errors(unsourced):
        return fail("unsourced CONFIRMED was schema-valid")

    with tempfile.TemporaryDirectory(prefix="cnf0154-p1-") as tmp:
        root = Path(tmp)
        inline = "Q" * INLINE_PROMPT_MEASURED
        arglim = dispatch(
            prompt_inline=inline,
            output_last_message=root / "arglim" / "output-last-message.json",
            claim_id="ARG-LIMIT-CONTROL",
        )
        if arglim.get("classification") != "win-arg-limit":
            return fail(f"arg-limit class={arglim.get('classification')}")
        if arglim.get("verdict") is not None:
            return fail("arg-limit produced a verdict")
        if arglim.get("exit_code") != 206:
            return fail(f"arg-limit exit {arglim.get('exit_code')} want 206")

        assembled = assemble(claim_by_id(p0_ids()[0]))
        prompt = write_prompt(assembled, root / "retry" / "prompt.json")
        retry = dispatch(
            prompt_file=prompt,
            output_last_message=root / "retry" / "output-last-message.json",
            claim_id=p0_ids()[0],
        )
        if retry.get("classification") != "SUCCESS":
            return fail(f"prompt-by-file retry class={retry.get('classification')}")

        severed = dispatch(
            prompt_file=prompt,
            output_last_message=root / "severed" / "output-last-message.json",
            backend="severed-empty",
            claim_id="GATE-SEVERED",
        )
        if severed.get("classification") != "severed-stream":
            return fail(f"gate class={severed.get('classification')}")
        if severed.get("verdict") is not None:
            return fail("severed-stream produced a verdict")
        if severed.get("exit_code") != 0:
            return fail("severed control must be exit 0 with missing output")

        bg = dispatch(
            prompt_file=prompt,
            output_last_message=root / "bg" / "output-last-message.json",
            background=True,
            claim_id="BG-BAN",
        )
        if bg.get("classification") != "background-ban":
            return fail(f"background class={bg.get('classification')}")
        if "--background" not in (bg.get("command_string") or ""):
            return fail("background command_string missing --background flag (control)")
        live_cmds = [
            arglim.get("command_string") or "",
            retry.get("command_string") or "",
            severed.get("command_string") or "",
        ]
        for cmd in live_cmds:
            if "--background" in cmd.split():
                return fail("production dispatch used --background")

        receipt_bytes = (
            HERE / "fixtures" / "contamination" / "receipts" / "implementer-receipt.json"
        ).read_text(encoding="utf-8")
        extra = {"receipts/implementer-receipt.json": receipt_bytes}
        clean = assemble(claim_by_id(p0_ids()[0]))
        dropped = assemble(claim_by_id(p0_ids()[0]), extra_candidates=extra)
        leaked = assemble(
            claim_by_id(p0_ids()[0]), extra_candidates=extra, exclusion_enabled=False
        )
        if dropped["attestation"] == leaked["attestation"]:
            return fail("exclusion did not change attestation")
        if dropped["attestation"] != clean["attestation"]:
            return fail("dropping a denied receipt should match the clean payload")
        blob = json.dumps(leaked["payload"])
        if "implementer already CONFIRMED" not in blob:
            return fail("both-states contamination not visible with exclusion off")
        blob_clean = json.dumps(dropped["payload"])
        if "implementer already CONFIRMED" in blob_clean:
            return fail("implementer conclusion leaked into blinded payload")

    recorded = doc.get("dispatch_records") or []
    if len(recorded) < len(p0_ids()):
        return fail(f"artifact dispatch_records {len(recorded)} < P0 {len(p0_ids())}")
    for row in recorded:
        cmd = row.get("command_string") or ""
        if "--background" in cmd.split():
            return fail(f"artifact dispatch used --background {row.get('claim_id')}")
        for key in (
            "prompt_file_path",
            "output_last_message_path",
            "output_bytes",
            "exit_code",
            "schema_validation",
        ):
            if key not in row:
                return fail(f"artifact dispatch missing {key} on {row.get('claim_id')}")

    out = {
        "probe": "probe1-gate-arglimit-background",
        "unit_id": "CNF-0154",
        "unsourced_confirmed_invalid": True,
        "arg_limit_classification": "win-arg-limit",
        "inline_prompt_chars": INLINE_PROMPT_MEASURED,
        "severed_stream_no_verdict": True,
        "background_ban": True,
        "blinding_exclusion": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0154-probe1 gate control, arg-limit, background ban")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
