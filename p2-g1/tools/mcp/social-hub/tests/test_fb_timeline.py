#!/usr/bin/env python3
"""Tests for fb_timeline: DYI parsing, mojibake repair, Graph feed, output shape."""

from __future__ import annotations

import json
import os
import zipfile

import fb_timeline as T


# ---- mojibake repair (detector-gated) ------------------------------------- #
def test_repair_mojibake_fixes_double_encode():
    original = "Mă bucur că am scris — viață și artă"
    corrupted = original.encode("utf-8").decode("latin-1")
    assert corrupted != original
    assert T.repair_mojibake(corrupted) == original


def test_repair_mojibake_leaves_clean_text_untouched():
    clean = "A perfectly normal English sentence."
    assert T.repair_mojibake(clean) == clean


def test_repair_mojibake_non_string_passthrough():
    assert T.repair_mojibake(None) is None


def test_repair_mojibake_undecodable_returns_original():
    # Looks mojibake'd (has markers) but is not valid latin-1->utf-8; keep as-is.
    weird = "Ã\udcff plain"
    assert T.repair_mojibake(weird) == weird


# ---- DYI parsing ---------------------------------------------------------- #
def _write(root, rel, obj):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    return path


def test_parse_dyi_dir_variants_and_filtering(tmp_path):
    root = str(tmp_path)
    _write(
        root,
        "your_activity_across_facebook/posts/your_posts_1.json",
        {
            "your_posts_v2": [
                {"timestamp": 100, "data": [{"post": "hello world one"}]},
                {"timestamp": 50, "data": [{"post": "earlier post two"}]},
                {"timestamp": 200, "data": [{"post": "x"}]},  # too short
            ]
        },
    )
    rows = T.parse_dyi(root, min_chars=5)
    assert [r["text"] for r in rows] == ["earlier post two", "hello world one"]
    assert all(r["source"] == "facebook" and r["kind"] == "post" for r in rows)


def test_parse_dyi_top_level_list(tmp_path):
    root = str(tmp_path)
    _write(
        root,
        "posts/your_posts.json",
        [{"timestamp": 10, "data": [{"post": "a bare list of posts here"}]}],
    )
    rows = T.parse_dyi(root, min_chars=3)
    assert len(rows) == 1 and "bare list" in rows[0]["text"]


def test_parse_dyi_title_only_body(tmp_path):
    root = str(tmp_path)
    _write(
        root,
        "posts/your_posts.json",
        {"your_posts": [{"timestamp": 10, "title": "Andrei\nStatus body only"}]},
    )
    rows = T.parse_dyi(root, min_chars=3)
    assert rows and "Status body only" in rows[0]["text"]


def test_parse_dyi_zip(tmp_path):
    src = _write(
        str(tmp_path),
        "your_posts.json",
        {"your_posts": [{"timestamp": 1, "data": [{"post": "zipped post body here"}]}]},
    )
    zp = os.path.join(str(tmp_path), "export.zip")
    with zipfile.ZipFile(zp, "w") as zf:
        zf.write(src, "your_activity_across_facebook/posts/your_posts_1.json")
    rows = T.parse_dyi(zp, min_chars=3)
    assert len(rows) == 1 and "zipped post" in rows[0]["text"]


def test_parse_dyi_single_file(tmp_path):
    fp = _write(
        str(tmp_path),
        "your_posts.json",
        {"your_posts": [{"timestamp": 1, "data": [{"post": "single file post body"}]}]},
    )
    rows = T.parse_dyi(fp, min_chars=3)
    assert len(rows) == 1


def test_parse_dyi_skips_bad_json(tmp_path):
    root = str(tmp_path)
    path = os.path.join(root, "posts", "your_posts.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not valid json")
    assert T.parse_dyi(root) == []


def test_extract_text_ignores_non_string_and_non_dict():
    assert (
        T._extract_text({"data": ["x", {"post": 5}, {"post": "keep me"}]}) == "keep me"
    )
    assert T._extract_text({"data": None}) == ""


def test_post_records_unknown_shape():
    assert T._post_records({"nope": []}) == []
    assert T._post_records(42) == []


# ---- timestamps ----------------------------------------------------------- #
def test_ts19_variants():
    assert T._ts19("2020-01-02T03:04:05+00:00") == "2020-01-02 03:04:05"
    assert T._ts19(0) == ""
    assert T._ts19(None) == ""
    assert len(T._ts19(1600000000)) == 19


# ---- output --------------------------------------------------------------- #
def test_write_corpus(tmp_path):
    rows = [
        {
            "ts": "2020-01-01 00:00:00",
            "source": "facebook",
            "kind": "post",
            "url": "http://x",
            "text": "one two three",
        },
    ]
    stats = T.write_corpus(rows, str(tmp_path))
    assert stats["posts"] == 1 and stats["words"] == 3
    assert os.path.getsize(stats["jsonl"]) > 0
    assert os.path.getsize(stats["txt"]) > 0
    assert stats["oldest"] == "2020-01-01 00:00:00"


def test_write_corpus_empty(tmp_path):
    stats = T.write_corpus([], str(tmp_path))
    assert stats["posts"] == 0 and stats["oldest"] is None


# ---- graph rail (mocked network) ------------------------------------------ #
def test_fetch_graph_feed_paginates(monkeypatch):
    pages = [
        {
            "data": [
                {
                    "message": "post A",
                    "created_time": "2020-01-01T00:00:00+0000",
                    "permalink_url": "http://a",
                },
                {
                    "message": "  ",
                    "created_time": "2020-01-02T00:00:00+0000",
                },  # blank -> skip
            ],
            "paging": {"next": f"{T.GRAPH_ROOT}/{T.GRAPH_VERSION}/me/feed?after=CUR"},
        },
        {"data": [{"message": "post B", "created_time": "2019-01-01T00:00:00+0000"}]},
    ]
    calls = {"n": 0}

    def fake_get(path, params):
        i = calls["n"]
        calls["n"] += 1
        return pages[i]

    monkeypatch.setattr(T, "_graph_get", fake_get)
    rows = T.fetch_graph_feed("TOKEN", limit=10)
    texts = [r["text"] for r in rows]
    assert texts == ["post B", "post A"]  # sorted by ts ascending
    assert calls["n"] == 2  # followed the paging cursor once


def test_fetch_graph_feed_stops_at_max_pages(monkeypatch):
    monkeypatch.setattr(
        T,
        "_graph_get",
        lambda p, q: {"data": [], "paging": {"next": "http://x/v21.0/me/feed?x=1"}},
    )
    assert T.fetch_graph_feed("TOKEN", max_pages=3) == []


# ---- main() dispatch ------------------------------------------------------ #
def test_main_dyi_missing_path(capsys):
    rc = T.main(["dyi", "/no/such/path"])
    assert rc == 1 and "FAILED:fb-timeline" in capsys.readouterr().out


def test_main_dyi_success(tmp_path, capsys):
    root = str(tmp_path / "exp")
    _write(
        root,
        "posts/your_posts.json",
        {"your_posts": [{"timestamp": 1, "data": [{"post": "a real post body"}]}]},
    )
    rc = T.main(["dyi", root, "--out", str(tmp_path / "out"), "--min-chars", "3"])
    assert rc == 0 and "SUCCESS:fb-timeline 1 posts" in capsys.readouterr().out


def test_main_graph_no_token(monkeypatch, capsys):
    monkeypatch.delenv("FB_USER_TOKEN", raising=False)
    rc = T.main(["graph"])
    assert rc == 1 and "FB_USER_TOKEN is not set" in capsys.readouterr().out


def test_main_graph_success(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FB_USER_TOKEN", "TOK")
    monkeypatch.setattr(
        T,
        "fetch_graph_feed",
        lambda *a, **k: [
            {
                "ts": "2020",
                "source": "facebook",
                "kind": "post",
                "url": "",
                "text": "hi",
            }
        ],
    )
    rc = T.main(["graph", "--out", str(tmp_path)])
    assert rc == 0 and "SUCCESS:fb-timeline 1 posts" in capsys.readouterr().out


def test_main_graph_error(monkeypatch, capsys):
    monkeypatch.setenv("FB_USER_TOKEN", "TOK")

    def boom(*a, **k):
        raise ValueError("graph exploded")

    monkeypatch.setattr(T, "fetch_graph_feed", boom)
    rc = T.main(["graph"])
    assert rc == 1 and "graph error" in capsys.readouterr().out
