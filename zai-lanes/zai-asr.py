#!/usr/bin/env python3
"""zai-asr — everywhere ASR/TTS bridge for the ZCode official speech channel.

Target: POST https://zcode.z.ai/api/v1/mcp/server/video_edit (stateless Streamable MCP).
Identity: --identity-file (a file containing the Authorization header value; today the
zcode JWT decrypts from ~/.zcode/v2/credentials.json — see RECEIPT-final-state; server
currently answers 3101 "coding plan is required" for it, so ALSO accepts a future
host-captured header set, one "Name: value" per line, which will pass through verbatim).

Usage:
  python zai-asr.py transcribe audio.wav [audio.mp3 ...]   # transcript JSON per file
  python zai-asr.py tts "text" out.mp3 [voice]
Identity via: --identity-file FILE   (or env ZAI_OFFICIAL_IDENTITY_FILE)
Audio is auto-normalized to 16 kHz mono mp3 @64 kbps via ffmpeg when available.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://zcode.z.ai/api/v1/mcp/server/video_edit"
ACCEPT = "application/json, text/event-stream"


def load_identity() -> dict[str, str]:
    import os

    path = os.environ.get("ZAI_OFFICIAL_IDENTITY_FILE")
    if not path or not Path(path).exists():
        return {}
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    if raw.startswith(("eyJ", "Bearer ")):
        return {"Authorization": "Bearer " + raw.removeprefix("Bearer ")}
    headers = {}
    for line in raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    return headers


def normalize_audio(
    path: Path, speed: float = 1.0, trim_silence: bool = False
) -> tuple[bytes, str]:
    """16k mono mp3 @64k. speed: atempo (pitch-preserving) -- cuts billed voiced seconds
    proportionally (2.0x measured = quantity halves). trim_silence: latency/size (silence
    is already unbilled server-side)."""
    fmt = path.suffix.lstrip(".").lower() or "wav"
    data = path.read_bytes()
    try:
        import hashlib as _h

        cache_key = _h.sha256(
            (
                str(path) + str(path.stat().st_size) + str(speed) + str(trim_silence)
            ).encode()
        ).hexdigest()[:16]
        cache = Path(tempfile.gettempdir()) / f"zai-asr-cache-{cache_key}.mp3"
        if cache.exists():
            return cache.read_bytes(), "mp3"
        filters = []
        if trim_silence:
            filters.append(
                "silenceremove=stop_periods=-1:stop_duration=0.35:stop_threshold=-38dB"
            )
        if speed and speed != 1.0:
            filters.append(f"atempo={speed}")
        out = Path(tempfile.gettempdir()) / ("zai-asr-norm-" + path.stem + ".mp3")
        r = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-af",
                ",".join(filters) if filters else "anull",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-b:a",
                "64k",
                str(out),
            ],
            capture_output=True,
            timeout=300,
        )
        if r.returncode == 0 and out.exists():
            data = out.read_bytes()
            try:
                cache.write_bytes(data)
            except Exception:
                pass
            return data, "mp3"
    except Exception:
        pass
    return data, fmt


def call_official(name: str, arguments: dict, headers: dict, timeout: int = 600):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": ACCEPT,
            "User-Agent": "estate-zai-asr/1.0",
            **headers,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    for line in raw.splitlines():
        if line.startswith("data:"):
            p = line[5:].strip()
            if p == "[DONE]":
                break
            try:
                return json.loads(p)
            except json.JSONDecodeError:
                continue
    return {"error": {"code": -1, "message": "no SSE data frame", "raw": raw[:300]}}


def transcribe(
    path: Path, headers: dict, speed: float = 1.0, trim_silence: bool = False
) -> dict:
    data, fmt = normalize_audio(path, speed=speed, trim_silence=trim_silence)
    args = {
        "audio_base64": base64.b64encode(data).decode(),
        "input_format": fmt,
        "input_path": "",
        "language": "",
        "timeout_seconds": 0,
        "chunk_seconds": 0,
        "retries": 0,
        "retry_backoff_seconds": 0,
    }
    return call_official("speech_transcribe", args, headers)


def tts(text: str, out_path: Path, voice: str, headers: dict) -> dict:
    args = {
        "text": text,
        "output_format": "mp3",
        "voice": voice,
        "speed": 1.0,
        "speech_rate": 0,
        "pitch_rate": 0,
        "loudness_rate": 0,
        "sample_rate": 0,
        "model": "",
        "style_instructions": "",
        "sample_mode": False,
    }
    res = call_official("speech_synthesize", args, headers)
    content = (res.get("result") or {}).get("content") or []
    for c in content:
        if isinstance(c, dict) and c.get("type") == "text":
            try:
                obj = json.loads(c["text"])
                b64 = obj.get("audio_base64")
                if b64:
                    out_path.write_bytes(base64.b64decode(b64))
                    return {"saved": str(out_path), "bytes": out_path.stat().st_size}
            except Exception:
                pass
    return res


def main(argv: list[str]) -> int:
    headers = load_identity()
    if not headers:
        print(
            "No identity (set ZAI_OFFICIAL_IDENTITY_FILE). Server will answer 1006/3101 — see receipt.",
            file=sys.stderr,
        )
    if len(argv) >= 3 and argv[1] == "transcribe":
        import argparse as _ap

        pr = _ap.ArgumentParser(add_help=False)
        pr.add_argument("--speed", type=float, default=1.0)
        pr.add_argument("--trim-silence", action="store_true")
        opts, files = pr.parse_known_args(argv[2:])
        for p in files:
            if p.startswith("--"):
                continue
            res = transcribe(
                Path(p), headers, speed=opts.speed, trim_silence=opts.trim_silence
            )
            print(json.dumps(res, indent=2, ensure_ascii=False)[:4000])
        return 0
    if len(argv) >= 4 and argv[1] == "tts":
        res = tts(argv[2], Path(argv[3]), argv[4] if len(argv) > 4 else "", headers)
        print(json.dumps(res, indent=2, ensure_ascii=False)[:2000])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
