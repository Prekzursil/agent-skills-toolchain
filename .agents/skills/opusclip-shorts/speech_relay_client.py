#!/usr/bin/env python
"""speech_relay_client.py — submit ASR jobs to the ZCode-hosted speech relay from ANY harness.

The online channel (Seed-ASR via Coding Plan) is a ZCode entitlement: identity headers are
minted per tool call by the ZCode host and cannot be exported. The relay solves this with a
file queue: a ZCode automation polls ~/.agents/speech-relay/queue and runs each job through
the host-authenticated video-agent-kit MCP. Metering stays on your plan, as designed.

Usage (blocking):
  python speech_relay_client.py transcribe <AUDIO_OR_VIDEO> <OUT_JSON> [--language ro] [--chunk 600]
  python speech_relay_client.py synthesize <TEXT> <OUT_WAV> [--voice <id>]   # if TTS needed
  env ZCODE_SPEECH_RELAY_DIR override (default ~/.agents/speech-relay)

Protocol: writes queue/<id>.job.json {kind, input_path|text, args, output_path};
relay writes results/<id>.result.json {ok, output_json|error, word_count, elapsed};
job file removed when picked up. Client polls until result or timeout (default 15 min).
"""
import argparse, json, os, sys, time, uuid

RELAY = os.environ.get("ZCODE_SPEECH_RELAY_DIR") or os.path.join(os.path.expanduser("~"), ".agents", "speech-relay")

def wait_result(job_id, timeout_s):
    res = os.path.join(RELAY, "results", job_id + ".result.json")
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if os.path.exists(res):
            return json.load(open(res, encoding="utf-8"))
        time.sleep(3)
    return {"ok": False, "error": f"relay timeout after {timeout_s}s (is the ZCode speech-relay automation running?)"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["transcribe", "synthesize"])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--language", default="ro")
    ap.add_argument("--chunk", type=float, default=600)
    ap.add_argument("--voice", default=None)
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()
    os.makedirs(os.path.join(RELAY, "queue"), exist_ok=True)
    os.makedirs(os.path.join(RELAY, "results"), exist_ok=True)
    job_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    args = {"language": a.language, "chunk_seconds": a.chunk} if a.kind == "transcribe" else (
           {"voice": a.voice} if a.voice else {})
    job = {"id": job_id, "kind": a.kind, "args": args,
           "input_path": os.path.abspath(a.input), "output_path": os.path.abspath(a.output)}
    open(os.path.join(RELAY, "queue", job_id + ".job.json"), "w", encoding="utf-8").write(
        json.dumps(job, ensure_ascii=False))
    print(f"submitted {job_id}; waiting for relay… (for instant service, ask any live ZCode agent: \"drain the speech relay queue\")", file=sys.stderr)
    res = wait_result(job_id, a.timeout)
    if res.get("ok"):
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print("RELAY ERROR:", res.get("error"), file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
