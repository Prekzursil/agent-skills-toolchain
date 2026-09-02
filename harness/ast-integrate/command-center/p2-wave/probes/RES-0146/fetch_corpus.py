#!/usr/bin/env python3
"""Fetch and freeze a 50-document provenance-labeled corpus.

Tries live URLs first. Shortfalls are filled from the HC3 dataset
(collection labels, not this unit's style judgement). Probes replay
from captures/ and do not fetch.
"""
from __future__ import annotations

import gzip
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    CAPTURE_DIR,
    INDEX_PATH,
    N_PER_CLASS,
    UA,
    dump_json,
    sha256_bytes,
)
from corpus import (  # noqa: E402
    HC3_DATASET,
    HC3_PAPER,
    HC3_PROVENANCE_CHATGPT,
    HC3_PROVENANCE_HUMAN,
    HC3_ROWS_URL,
    MILL,
    PRACTITIONER,
)
from textutil import body_text  # noqa: E402

TIMEOUT = 20
MIN_TEXT = 80
CTX = ssl.create_default_context()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_url(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,text/plain,application/json;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, identity",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read()
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip" or raw[:2] == b"\x1f\x8b":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
            status = getattr(resp, "status", None) or resp.getcode() or 200
            final = resp.geturl() or url
            return int(status), raw, final
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read() or b""
        except Exception:
            body = b""
        return int(exc.code), body, url
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError):
        return 0, b"", url


def persist(doc_id: str, raw: bytes) -> str:
    name = f"{doc_id}.body"
    (CAPTURE_DIR / name).write_bytes(raw)
    return name


def reuse_capture(cand: dict) -> dict | None:
    fname = f"{cand['id']}.body"
    path = CAPTURE_DIR / fname
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if len(raw) < 200:
        return None
    text = body_text(raw)
    if len(text.strip()) < MIN_TEXT:
        return None
    return {
        "id": cand["id"],
        "label": cand["label"],
        "file": fname,
        "path": f"command-center/p2-wave/probes/RES-0146/captures/{fname}",
        "permalink": cand["urls"][0],
        "requested_url": cand["urls"][0],
        "fetch_timestamp": utc_now(),
        "http_status": 200,
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "text_chars": len(text),
        "provenance_kind": cand["provenance_kind"],
        "provenance_basis": cand["provenance_basis"],
        "source_class": cand["label"],
        "fill": "reused-capture",
    }


def try_candidates(pool: list[dict], want: int, taken_ids: set[str]) -> list[dict]:
    out: list[dict] = []
    for cand in pool:
        if len(out) >= want:
            break
        if cand["id"] in taken_ids:
            continue
        reused = reuse_capture(cand)
        if reused:
            out.append(reused)
            taken_ids.add(cand["id"])
            print(f"REUSE {reused['id']} bytes={reused['bytes']}")
            continue
        got = None
        for url in cand["urls"]:
            status, raw, final = fetch_url(url)
            if status != 200 or len(raw) < 200:
                continue
            text = body_text(raw)
            if len(text.strip()) < MIN_TEXT:
                continue
            fname = persist(cand["id"], raw)
            got = {
                "id": cand["id"],
                "label": cand["label"],
                "file": fname,
                "path": f"command-center/p2-wave/probes/RES-0146/captures/{fname}",
                "permalink": final,
                "requested_url": url,
                "fetch_timestamp": utc_now(),
                "http_status": 200,
                "sha256": sha256_bytes(raw),
                "bytes": len(raw),
                "text_chars": len(text),
                "provenance_kind": cand["provenance_kind"],
                "provenance_basis": cand["provenance_basis"],
                "source_class": cand["label"],
                "fill": "live-url",
            }
            break
        if got:
            out.append(got)
            taken_ids.add(cand["id"])
            print(f"OK {got['id']} bytes={got['bytes']} {got['permalink'][:80]}")
        else:
            print(f"SKIP {cand['id']}")
    return out


def fetch_hc3_rows(offset: int, length: int) -> tuple[list[dict], dict]:
    url = HC3_ROWS_URL.format(offset=offset, length=length)
    status, raw, final = fetch_url(url)
    meta = {
        "permalink": final,
        "requested_url": url,
        "http_status": status,
        "sha256": sha256_bytes(raw) if raw else "",
        "bytes": len(raw),
        "fetch_timestamp": utc_now(),
    }
    if status != 200 or not raw:
        return [], meta
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return [], meta
    rows = payload.get("rows") or []
    out = []
    for item in rows:
        row = item.get("row") or {}
        out.append(row)
    meta["n_rows"] = len(out)
    # Keep the raw HC3 page as a lineage capture too.
    (CAPTURE_DIR / f"hc3-offset-{offset}.json").write_bytes(raw)
    meta["file"] = f"hc3-offset-{offset}.json"
    return out, meta


def fill_hc3(
    need_prac: int,
    need_mill: int,
    taken_ids: set[str],
) -> tuple[list[dict], list[dict], list[dict]]:
    prac: list[dict] = []
    mill: list[dict] = []
    offset = 0
    lineage = []
    while (len(prac) < need_prac or len(mill) < need_mill) and offset < 400:
        batch, meta = fetch_hc3_rows(offset, 20)
        lineage.append(meta)
        if not batch:
            print(f"HC3 empty offset={offset} status={meta.get('http_status')}")
            if int(meta.get("http_status") or 0) in {429, 0}:
                break
            offset += 20
            continue
        for i, row in enumerate(batch):
            human = ""
            chatgpt = ""
            hval = row.get("human_answers") or row.get("human")
            cval = row.get("chatgpt_answers") or row.get("chatgpt")
            if isinstance(hval, list) and hval:
                human = str(hval[0])
            elif isinstance(hval, str):
                human = hval
            if isinstance(cval, list) and cval:
                chatgpt = str(cval[0])
            elif isinstance(cval, str):
                chatgpt = cval
            q = str(row.get("question") or "")
            if len(human.strip()) >= MIN_TEXT and len(prac) < need_prac:
                doc_id = f"h-human-{offset + i:04d}"
                if doc_id not in taken_ids:
                    raw = human.encode("utf-8")
                    fname = persist(doc_id, raw)
                    prac.append(
                        {
                            "id": doc_id,
                            "label": "practitioner",
                            "file": fname,
                            "path": (
                                "command-center/p2-wave/probes/RES-0146/captures/"
                                + fname
                            ),
                            "permalink": HC3_DATASET,
                            "requested_url": meta["requested_url"],
                            "fetch_timestamp": meta["fetch_timestamp"],
                            "http_status": 200,
                            "sha256": sha256_bytes(raw),
                            "bytes": len(raw),
                            "text_chars": len(human),
                            "provenance_kind": "dataset-collection-label",
                            "provenance_basis": HC3_PROVENANCE_HUMAN,
                            "source_class": "practitioner",
                            "fill": "hc3-human",
                            "hc3_question_sha256": sha256_bytes(q.encode("utf-8")),
                            "hc3_paper": HC3_PAPER,
                        }
                    )
                    taken_ids.add(doc_id)
            if len(chatgpt.strip()) >= MIN_TEXT and len(mill) < need_mill:
                doc_id = f"h-chatgpt-{offset + i:04d}"
                if doc_id not in taken_ids:
                    raw = chatgpt.encode("utf-8")
                    fname = persist(doc_id, raw)
                    mill.append(
                        {
                            "id": doc_id,
                            "label": "mill",
                            "file": fname,
                            "path": (
                                "command-center/p2-wave/probes/RES-0146/captures/"
                                + fname
                            ),
                            "permalink": HC3_DATASET,
                            "requested_url": meta["requested_url"],
                            "fetch_timestamp": meta["fetch_timestamp"],
                            "http_status": 200,
                            "sha256": sha256_bytes(raw),
                            "bytes": len(raw),
                            "text_chars": len(chatgpt),
                            "provenance_kind": "dataset-collection-label",
                            "provenance_basis": HC3_PROVENANCE_CHATGPT,
                            "source_class": "mill",
                            "fill": "hc3-chatgpt",
                            "hc3_question_sha256": sha256_bytes(q.encode("utf-8")),
                            "hc3_paper": HC3_PAPER,
                        }
                    )
                    taken_ids.add(doc_id)
            if len(prac) >= need_prac and len(mill) >= need_mill:
                break
        offset += 20
    return prac, mill, lineage


def main() -> int:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    taken: set[str] = set()
    print("=== practitioner live ===")
    prac = try_candidates(PRACTITIONER, N_PER_CLASS, taken)
    print("=== mill live ===")
    mill = try_candidates(MILL, N_PER_CLASS, taken)
    need_p = max(0, N_PER_CLASS - len(prac))
    need_m = max(0, N_PER_CLASS - len(mill))
    hc3_lineage: list[dict] = []
    if need_p or need_m:
        print(f"=== HC3 fill need_p={need_p} need_m={need_m} ===")
        hp, hm, hc3_lineage = fill_hc3(need_p, need_m, taken)
        prac.extend(hp)
        mill.extend(hm)
    prac = prac[:N_PER_CLASS]
    mill = mill[:N_PER_CLASS]
    docs = prac + mill
    if len(prac) != N_PER_CLASS or len(mill) != N_PER_CLASS:
        print(
            f"FAILED:corpus incomplete practitioner={len(prac)} mill={len(mill)}"
        )
        return 1
    index = {
        "unit_id": "RES-0146",
        "n": len(docs),
        "n_practitioner": len(prac),
        "n_mill": len(mill),
        "label_rule": (
            "label is publication provenance (venue/author/publication-pattern "
            "or HC3 collection label), never this unit's stylistic judgement"
        ),
        "fetched_at": utc_now(),
        "hc3_lineage": hc3_lineage,
        "documents": docs,
    }
    dump_json(INDEX_PATH, index)
    print(f"wrote {INDEX_PATH} n={len(docs)}")
    print("SUCCESS:RES-0146-fetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
