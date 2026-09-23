#!/usr/bin/env python3
"""T0 OpenRouter chat completion. Prints generation id + usage. Never logs the secret.

Request hardening (T0-5): ``provider.require_parameters`` is sent whenever the
body carries ``tools`` or ``response_format`` (never otherwise) and
``provider.data_collection = "deny"`` is sent by default
(``--allow-data-collection`` opts out). ``--rank`` reads the keyless
``GET /api/v1/models`` catalog and lists the top N models by
``benchmarks.artificial_analysis``, skipping rows that expire within 30 days or
whose ``status`` is present and not ``live``.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

BASE = "https://openrouter.ai/api/v1"
MODELS_URL = BASE + "/models"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
APP_TITLE = "agents-openrouter-sidecar"
APP_REFERER = "https://local.agents.openrouter"
RANK_HORIZON_DAYS = 30
RANK_INDICES = ("intelligence_index", "coding_index", "agentic_index")
DEFAULT_RANK_INDEX = RANK_INDICES[0]
DEFAULT_RANK_TOP = 10


def build_request_body(
    model: str,
    prompt: str,
    max_tokens: int,
    *,
    tools: Any = None,
    response_format: Any = None,
    deny_data_collection: bool = True,
) -> dict[str, Any]:
    """Chat-completions body; ``provider`` carries only the hardening fields that apply."""
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if tools is not None:
        body["tools"] = tools
    if response_format is not None:
        body["response_format"] = response_format
    provider: dict[str, Any] = {}
    if tools is not None or response_format is not None:
        provider["require_parameters"] = True
    if deny_data_collection:
        provider["data_collection"] = "deny"
    if provider:
        body["provider"] = provider
    return body


def fetch_models_catalog(
    url: str = MODELS_URL, timeout: int = 30
) -> list[dict[str, Any]]:
    """Keyless catalog read: no Authorization header is ever attached."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise ValueError("models payload lacks a data list")
    return data


@dataclasses.dataclass(frozen=True)
class RankedModel:
    id: str
    score: float
    expiration_date: str | None
    prompt_price: str | None
    completion_price: str | None


@dataclasses.dataclass(frozen=True)
class RankReport:
    ranked: tuple[RankedModel, ...]
    candidates: int
    scored: int
    skipped_expiring: int
    skipped_not_live: int


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def model_is_live(model: Mapping[str, Any]) -> bool:
    status = model.get("status")
    return status is None or status == "live"


def model_expires_soon(model: Mapping[str, Any], today: datetime.date) -> bool:
    """True when ``expiration_date`` is present but unparseable, or under 30 days out."""
    raw = model.get("expiration_date")
    if raw is None:
        return False
    if not isinstance(raw, str):
        return True
    try:
        expires = datetime.date.fromisoformat(raw[:10])
    except ValueError:
        return True
    return (expires - today).days < RANK_HORIZON_DAYS


def model_score(model: Mapping[str, Any], index: str) -> float | None:
    benchmarks = model.get("benchmarks")
    if not isinstance(benchmarks, dict):
        return None
    analysis = benchmarks.get("artificial_analysis")
    if isinstance(analysis, dict):
        return _number(analysis.get(index))
    return _number(analysis)


def rank_models(
    models: list[dict[str, Any]],
    n: int,
    today: datetime.date,
    *,
    index: str = DEFAULT_RANK_INDEX,
) -> RankReport:
    """Top ``n`` live, non-expiring models by ``benchmarks.artificial_analysis[index]``."""
    scored: list[RankedModel] = []
    skipped_expiring = 0
    skipped_not_live = 0
    for model in models:
        if not model_is_live(model):
            skipped_not_live += 1
            continue
        if model_expires_soon(model, today):
            skipped_expiring += 1
            continue
        score = model_score(model, index)
        if score is None:
            continue
        pricing = model.get("pricing")
        prices = pricing if isinstance(pricing, dict) else {}
        scored.append(
            RankedModel(
                id=str(model.get("id")),
                score=score,
                expiration_date=model.get("expiration_date"),
                prompt_price=prices.get("prompt"),
                completion_price=prices.get("completion"),
            )
        )
    scored.sort(key=lambda item: (-item.score, item.id))
    return RankReport(
        ranked=tuple(scored[:n]),
        candidates=len(models),
        scored=len(scored),
        skipped_expiring=skipped_expiring,
        skipped_not_live=skipped_not_live,
    )


def print_rank_report(report: RankReport, index: str, source: str) -> None:
    print(f"rank_source={source}")
    print(f"rank_index={index}")
    print(f"rank_candidates={report.candidates}")
    print(f"rank_scored={report.scored}")
    print(f"rank_skipped_expiring={report.skipped_expiring}")
    print(f"rank_skipped_not_live={report.skipped_not_live}")
    for position, item in enumerate(report.ranked, start=1):
        print(
            f"rank={position} model={item.id} {index}={item.score} "
            f"expiration_date={item.expiration_date or '-'} "
            f"prompt_price={item.prompt_price or '-'} "
            f"completion_price={item.completion_price or '-'}"
        )


def redact(text: str, secret: str) -> str:
    if not secret or not text:
        return text
    return text.replace(secret, "[REDACTED]")


def request(
    method: str, url: str, secret: str, body: dict | None = None, timeout: int = 90
) -> tuple[int, object]:
    raw_bytes = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + secret,
        "HTTP-Referer": APP_REFERER,
        "X-OpenRouter-Title": APP_TITLE,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=raw_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = int(exc.code)
    except urllib.error.URLError as exc:
        print("ERROR network: " + redact(str(exc.reason), secret), file=sys.stderr)
        return 0, {"error": "network"}
    raw = redact(raw, secret)
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def snippet(text: str, n: int = 120) -> str:
    compact = " ".join(str(text).split())
    return compact if len(compact) <= n else compact[: n - 1] + "..."


def main(
    argv: list[str] | None = None,
    fetch_models: Callable[[], list[dict[str, Any]]] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="T0 OpenRouter completion (never logs the secret)"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default="Reply with the single word: pong")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--show-limits", action="store_true")
    parser.add_argument("--skip-generation", action="store_true")
    parser.add_argument(
        "--tools-json",
        type=json.loads,
        default=None,
        dest="tools",
        help="inline JSON tools array; its presence turns on provider.require_parameters",
    )
    parser.add_argument(
        "--response-format-json",
        type=json.loads,
        default=None,
        dest="response_format",
        help="inline JSON response_format; its presence turns on provider.require_parameters",
    )
    parser.add_argument(
        "--deny-data-collection",
        dest="deny_data_collection",
        action="store_true",
        default=True,
        help="send provider.data_collection=deny (default)",
    )
    parser.add_argument(
        "--allow-data-collection",
        dest="deny_data_collection",
        action="store_false",
        help="omit provider.data_collection (providers that train on prompts stay eligible)",
    )
    parser.add_argument(
        "--rank",
        action="store_true",
        help="keyless mode: list the top models from GET /models by "
        "benchmarks.artificial_analysis, then exit (no completion is sent)",
    )
    parser.add_argument("--top", type=int, default=DEFAULT_RANK_TOP)
    parser.add_argument(
        "--rank-index", choices=RANK_INDICES, default=DEFAULT_RANK_INDEX
    )
    args = parser.parse_args(argv)

    if args.rank:
        try:
            models = (fetch_models or fetch_models_catalog)()
        except (urllib.error.URLError, ValueError) as exc:
            print("ERROR rank: " + snippet(str(exc), 240), file=sys.stderr)
            return 3
        report = rank_models(models, args.top, _today(), index=args.rank_index)
        print_rank_report(report, args.rank_index, MODELS_URL)
        return 0

    secret = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not secret:
        print(
            "ERROR: environment variable OPENROUTER_API_KEY is missing", file=sys.stderr
        )
        return 2

    if args.show_limits:
        status, payload = request("GET", BASE + "/key", secret)
        print(f"key_http_status={status}")
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        if isinstance(data, dict):
            for field in (
                "is_free_tier",
                "is_management_key",
                "limit",
                "limit_reset",
                "limit_remaining",
                "usage",
                "usage_daily",
                "usage_weekly",
                "usage_monthly",
            ):
                if field in data:
                    print(f"key_{field}={data[field]}")

    body = build_request_body(
        args.model,
        args.prompt,
        args.max_tokens,
        tools=args.tools,
        response_format=args.response_format,
        deny_data_collection=args.deny_data_collection,
    )
    status, payload = request("POST", BASE + "/chat/completions", secret, body=body)
    print(f"http_status={status}")
    print(f"model_requested={args.model}")
    if not isinstance(payload, dict):
        print("ERROR non-json response: " + snippet(payload, 200), file=sys.stderr)
        return 3
    if status >= 400:
        err = payload.get("error", payload)
        if isinstance(err, dict):
            if "code" in err:
                print(f"error_code={err['code']}")
            meta = err.get("metadata") if isinstance(err.get("metadata"), dict) else {}
            if "limit_source" in meta:
                print(f"error_limit_source={meta['limit_source']}")
            rendered = json.dumps(err)
        else:
            rendered = str(err)
        print(f"ERROR http {status}: " + snippet(rendered, 240), file=sys.stderr)
        return 3

    model_used = payload.get("model") or args.model
    gen_id = payload.get("id")
    usage = payload.get("usage") or {}
    choices = payload.get("choices") or []
    content = ""
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        content = str(msg.get("content") or "")
    print(f"model_used={model_used}")
    print(f"generation_id={gen_id or ''}")
    if isinstance(usage, dict):
        print(f"prompt_tokens={usage.get('prompt_tokens', '')}")
        print(f"completion_tokens={usage.get('completion_tokens', '')}")
        print(f"total_tokens={usage.get('total_tokens', '')}")
    print(f"response_snippet={snippet(content)}")

    if gen_id and not args.skip_generation:
        gen_status, gen_payload = 0, {}
        encoded = urllib.parse.quote(str(gen_id), safe="")
        for attempt in range(4):
            if attempt:
                time.sleep(1.5)
            gen_status, gen_payload = request(
                "GET", BASE + "/generation?id=" + encoded, secret
            )
            if (
                gen_status == 200
                and isinstance(gen_payload, dict)
                and gen_payload.get("data")
            ):
                break
        print(f"generation_http_status={gen_status}")
        data = gen_payload.get("data") if isinstance(gen_payload, dict) else {}
        if isinstance(data, dict):
            for field in (
                "total_cost",
                "usage",
                "tokens_prompt",
                "tokens_completion",
                "model",
                "provider_name",
            ):
                if field in data:
                    print(f"generation_{field}={data[field]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
