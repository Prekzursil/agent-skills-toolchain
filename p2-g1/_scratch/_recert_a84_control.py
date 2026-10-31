"""Shard2-w1 completion 2026-10-24: AUD-0084 stale control row re-certification.

The artifact's use-versus-mention-control row reads result=NOT-RUN with
output_tail "NOT-RUN: ... sidecar script ... absent on this checkout; PASS is
not re-certified". The control itself runs live inside probe2
(census.evaluate_control over the rebuilt fixtures/use_vs_mention_fixture.py,
both-states, mutant-goes-red) and passes on this host. This script:
  1. runs the control live and captures its dict verbatim,
  2. updates ONLY that tests row (result PASS, the command that actually ran,
     the live output tail, and a provenance note),
  3. refreshes the per-unit manifest primary sha256 row (CRLF-normalized),
  4. refreshes SUBAGENT-RETURN artifact sha/bytes + a completion note.
Everything else in the artifact (counts, adjudication, reviewer closure)
stays byte-identical.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
HERE = REPO / "command-center/p2-wave/probes/AUD-0084"
ART = REPO / "command-center/audit/AUD-0084-hardcoded-path-census.json"
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0084/probe2_ast_adjudication.py"
)


def digest(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def write_json_lf(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, indent=1, ensure_ascii=True) + "\n").encode("utf-8"))


def main() -> int:
    control = C.evaluate_control()
    if not control.get("passed"):
        print("FAILED:recert live control did not pass")
        print(json.dumps(control, indent=1, sort_keys=True)[:2000])
        return 1

    doc = json.loads(ART.read_text(encoding="utf-8"))
    row = None
    for t in doc.get("tests") or []:
        if isinstance(t, dict) and t.get("id") == "use-versus-mention-control":
            row = t
            break
    if row is None:
        print("FAILED:recert control row absent")
        return 1

    row["result"] = "PASS"
    row["command"] = CMD
    row["output_tail"] = (
        "control_passed=%s regex_silent=%s docstring_silent=%s open_flagged=%s "
        "relative_glob_excluded=%s write_text_payload_excluded=%s "
        "mutant_goes_red=%s good_classes=%s"
        % (
            control.get("passed"),
            control.get("regex_silent"),
            control.get("docstring_silent"),
            control.get("open_flagged"),
            control.get("relative_glob_excluded"),
            control.get("write_text_payload_excluded"),
            control.get("mutant_context_filter_disabled_goes_red"),
            json.dumps(control.get("good_classes"), sort_keys=True),
        )
    )
    row["recertified_live"] = (
        "shard2-w1 2026-10-24: prior row was stale bookkeeping (NOT-RUN: sidecar "
        "absent at canonical write time). Control re-run live on this host via "
        "census.evaluate_control over fixtures/use_vs_mention_fixture.py "
        "(both-states, mutant red); row updated with the live command and "
        "verbatim tail. All other artifact content unchanged."
    )

    write_json_lf(ART, doc)

    sha, nbytes = digest(ART)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    for a in man.get("artifacts") or []:
        rel = str(a.get("path") or "").replace("\\", "/")
        if rel == ART.relative_to(REPO).as_posix():
            a["sha256"] = sha
            a["bytes"] = nbytes
            a["present"] = True
    man["ts"] = now
    write_json_lf(man_path, man)

    ret_path = HERE / "SUBAGENT-RETURN.json"
    ret = json.loads(ret_path.read_text(encoding="utf-8"))
    ret["artifact_bytes"] = nbytes
    ret["artifact_sha256_crlf_normalized"] = sha
    ret["notes"] = str(ret.get("notes") or "") + (
        " shard2-w1 2026-10-24: use-versus-mention-control row re-certified "
        "live (was stale NOT-RUN bookkeeping); manifest sha refreshed."
    )
    ret["ts"] = now
    write_json_lf(ret_path, ret)

    print("recert artifact sha256=%s bytes=%d" % (sha, nbytes))
    print("SUCCESS:AUD-0084 control-row re-certified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
