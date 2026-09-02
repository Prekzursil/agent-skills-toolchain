#!/usr/bin/env python
"""Regenerate the committed hermetic HOME fixture under `fixtures/home/`.

WHY THIS EXISTS
---------------
`index.HOME` binds five discovery roots (`index.py:93-97`) under `$ROUTING_HOME` or
`Path.home()`. Nothing in the test suite or CI ever set `ROUTING_HOME`, so the routing
lane silently measured whatever live harness the host happened to have. MEASURED: on a
Linux runner with an empty `~/.claude`, `discover()` returned 383 records instead of 912
and 22 of the lane's tests failed -- including the lane's own positive-form floor guard
("corpus implausibly small (383)"). Reproduced locally on Windows with
`ROUTING_HOME=<empty dir>`: the identical 22 failures.

This generator freezes a scrubbed snapshot of the live harness trees into the repo so the
lane has a corpus that travels with the checkout.

FROZEN ON PURPOSE
-----------------
The fixture is a SNAPSHOT, not a mirror. A regression gate whose corpus moves every time
a skill is edited cannot hold a metric bar (`L1 gold-hit@5 >= 0.60`, `tail >= 0.85`)
steady -- the bar would measure the corpus, not the router. Re-run this script
deliberately when the corpus should move, and re-measure the bars in the same commit.

ROUTING-EQUIVALENCE, NOT A VERBATIM COPY
----------------------------------------
Only the bytes the indexer actually reads are kept:

  * skills   -- frontmatter + `body[:1500]` + the first 14 `#`/`##`/`###` headings
                (`index.skills()`), the cut extended to the next newline so a heading is
                never sliced in half.
  * agents /
    commands -- frontmatter + `body[:900]` (`index._md_units()`).

`verify()` grades the shrinker against a SECOND tree built from the same source with
shrinking disabled and the same scrubber applied, requiring exact equality of
`routing_text`, `desc_source` and `card` on every HOME-sourced record. Because both sides
are scrubbed, the scrub cancels out and any surviving difference is a shrinker bug; a file
that produces one is re-emitted IN FULL. Measured at build time: 0 differences, 0
fallbacks. The unscrubbed live index is compared too, but only REPORTED -- see below.

SCRUBBING (never negotiable)
----------------------------
  * the OS username and every path spelling that embeds it -> `agentuser`
  * named credential families (OpenAI/Anthropic/GitHub/HF/Slack/AWS/GCP/GitLab/npm/JWT/
    PEM) -> `REDACTED-SECRET`
  * `.mcp.json` -- the whole `env` block is DROPPED. That is where the live API keys sit,
    and `index.mcp()` never reads it. `command`/`args` are kept verbatim.
  * `installed_plugins.json` -- `installPath` becomes the `__FIXTURE_HOME__` token, which
    `conftest.py` renders to the session's fixture root. Timestamps are dropped.

Because `agentuser` is one character shorter than the real username, the `body[:1500]`
window slides where the name appeared, so 27 records' `routing_text` differ from the live
tree. That delta is REPORTED, never gated -- gating on it would be gating on the redaction.

A generic high-entropy pattern is REPORTED, never auto-replaced: silently rewriting long
base64-looking runs would corrupt legitimate documentation and hide what it touched.

Usage
-----
    python platform/routing/fixtures/build_fixture.py            # build + verify
    python platform/routing/fixtures/build_fixture.py --verify   # verify only
    python platform/routing/fixtures/build_fixture.py --source <home>
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROUTING = HERE.parent
BUILD_ROOT = ROUTING.parent
FIXTURE_HOME = HERE / "home"

if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

#: Token the committed `installed_plugins.json` carries in place of an absolute path.
#: `conftest.py` substitutes the session fixture root for it.
HOME_TOKEN = "__FIXTURE_HOME__"

FAKE_USER = "agentuser"

#: Byte budgets copied from the indexer, not guessed. `index.skills()` reads
#: `body[:1500]`; `index._md_units()` reads `body[:900]`.
SKILL_BODY_KEEP = 1500
MD_BODY_KEEP = 900

#: Same expression `index.skills()` uses, so the heading set is preserved exactly.
HEAD_RX = re.compile(r"^#{1,3}\s+(.{3,90})$", re.M)
HEAD_LIMIT = 14

#: Sentinel for the `full` set meaning "emit every file unshrunk". Used to build the
#: reference tree `verify()` grades the shrinker against.
ALL_FILES = frozenset({"*"})


def _emit_full(full: frozenset[str] | set[str], key: str) -> bool:
    return "*" in full or key in full


#: Named credential families. Conservative on purpose -- each has a fixed prefix, so a
#: match is a credential and not a word that happens to be long.
SECRET_RX = tuple(
    re.compile(p)
    for p in (
        r"sk-ant-[A-Za-z0-9_-]{10,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"hf_[A-Za-z0-9]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_-]{30,}",
        r"glpat-[A-Za-z0-9_-]{15,}",
        r"npm_[A-Za-z0-9]{30,}",
        r"eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    )
)

#: REPORTED, never auto-replaced (see the module docstring).
ENTROPY_RX = re.compile(
    r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{60,}={0,2}(?![A-Za-z0-9+/=])"
)


# --------------------------------------------------------------------------- scrubbing


class Scrubber:
    """Username + credential redaction, with a per-run tally so the report is auditable."""

    def __init__(self, username: str) -> None:
        # Case-insensitive on the bare username: replacing it also fixes every path
        # spelling that embeds it (`C:\\Users\\X`, `C:/Users/X`, `/c/Users/X`,
        # `/mnt/c/Users/X`, `%USERPROFILE%` expansions) in one pass.
        self.user_rx = re.compile(re.escape(username), re.I)
        # The 8.3 short form Windows hands out for a long profile name.
        short = f"{username[:6].upper()}~1"
        self.short_rx = re.compile(re.escape(short), re.I)
        self.user_hits = 0
        self.secret_hits = 0
        self.entropy_hits: list[str] = []

    def __call__(self, text: str) -> str:
        text, n = self.short_rx.subn(FAKE_USER, text)
        self.user_hits += n
        text, n = self.user_rx.subn(FAKE_USER, text)
        self.user_hits += n
        for rx in SECRET_RX:
            text, n = rx.subn("REDACTED-SECRET", text)
            self.secret_hits += n
        for m in ENTROPY_RX.finditer(text):
            self.entropy_hits.append(m.group(0)[:24] + "...")
        return text


# --------------------------------------------------------------------------- shrinking


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (verbatim frontmatter incl. its closing fence, body).

    Mirrors `index._frontmatter()`'s split point exactly so re-emitting the two halves
    reproduces the same parse.
    """
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end < 0:
        return "", text
    return text[: end + 4], text[end + 4 :]


def _cut_at_line(body: str, keep: int) -> str:
    """`body[:keep]` extended forward to the end of its line.

    EXTENDING is what makes this safe. The indexer reads `body[:keep]`, so the kept text
    must start with those exact characters -- taking MORE always satisfies that, while
    taking less, or cutting mid-line, does not. A mid-line cut also turns a sliced
    heading into a different heading (`$` matches at end-of-string), which would silently
    change the mined heading set.
    """
    if len(body) <= keep:
        return body
    nl = body.find("\n", keep)
    return body if nl < 0 else body[: nl + 1]


def shrink_skill(text: str) -> str:
    """Keep the routing-relevant prefix of a SKILL.md, headings included."""
    fm, body = _split_frontmatter(text)
    want = HEAD_RX.findall(body)[:HEAD_LIMIT]
    kept = _cut_at_line(body, SKILL_BODY_KEEP)
    got = HEAD_RX.findall(kept)[:HEAD_LIMIT]
    if got != want:
        if (
            want[: len(got)] != got
        ):  # pragma: no cover - defensive; caller re-emits full
            return text
        tail = "\n".join(f"### {h}" for h in want[len(got) :])
        kept = f"{kept}\n{tail}\n"
    return fm + kept


def shrink_md(text: str) -> str:
    """Keep the routing-relevant prefix of an agent/command markdown unit."""
    fm, body = _split_frontmatter(text)
    return fm + _cut_at_line(body, MD_BODY_KEEP)


# --------------------------------------------------------------------------- emit


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": the fixture must be byte-identical to what a Linux runner checks out
    # (windows-shell.md 8b -- a CRLF working tree is not the blob CI reads).
    path.write_text(text, encoding="utf-8", newline="\n")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def emit_skill_tree(src: Path, dst: Path, scrub: Scrubber, full: set[str]) -> int:
    n = 0
    if not src.is_dir():
        return 0
    for md in sorted(src.glob("*/SKILL.md")):
        raw = _read(md)
        body = raw if _emit_full(full, md.parent.name) else shrink_skill(raw)
        _write(dst / md.parent.name / "SKILL.md", scrub(body))
        n += 1
    return n


def emit_md_tree(
    src: Path, dst: Path, pattern: str, scrub: Scrubber, full: set[str]
) -> int:
    n = 0
    if not src.is_dir():
        return 0
    for md in sorted(src.glob(pattern)):
        rel = md.relative_to(src)
        raw = _read(md)
        body = raw if _emit_full(full, md.stem) else shrink_md(raw)
        _write(dst / rel, scrub(body))
        n += 1
    return n


def emit_mcp(src: Path, dst: Path, scrub: Scrubber) -> int:
    """`.mcp.json` with every `env` block DROPPED; `command`/`args` kept verbatim.

    `index.mcp()` reads only the server NAME, `command` and `args[:8]`. `env` is exactly
    where the live API keys sit, so dropping the whole block removes the credential
    surface outright instead of redacting it value by value.

    `command`/`args` are NOT rewritten beyond the username scrub. An earlier version
    basename'd anything containing a slash and measurably corrupted real routing tokens:
    `@playwright/mcp@0.0.78` became `mcp@0.0.78` (npm scope destroyed) and
    `http://127.0.0.1:9222` became `127.0.0.1:9222` (URL scheme destroyed). Those strings
    carry no user identity -- the username scrub already handles the paths that do -- so
    rewriting them was inventing a difference for no security gain.
    """
    doc = json.loads(_read(src))
    servers = doc.get("mcpServers") or {}
    out: dict[str, Any] = {}
    for name in sorted(servers):
        cfg = servers[name] if isinstance(servers[name], dict) else {}
        entry: dict[str, Any] = {"command": str(cfg.get("command") or "")}
        args = cfg.get("args")
        if isinstance(args, list):
            entry["args"] = [str(a) for a in args]
        out[str(name)] = entry
    _write(dst, scrub(json.dumps({"mcpServers": out}, indent=2) + "\n"))
    return len(out)


def emit_plugins(src_home: Path, dst_home: Path, scrub: Scrubber) -> tuple[int, int]:
    """Plugin registry + the vendor manifests `index.plugins()` reads.

    `installPath` is emitted as the `__FIXTURE_HOME__` token because an absolute path
    committed here would only resolve on the machine that generated it -- the exact
    host-coupling this whole unit exists to remove.

    Only `name`/`displayName`/`description`/`keywords`/`version` are copied from each
    vendor manifest; those are the five fields `index.plugins()` reads.
    """
    src = src_home / ".claude" / "plugins" / "installed_plugins.json"
    doc = json.loads(_read(src))
    plugins = doc.get("plugins") or {}
    out: dict[str, Any] = {}
    manifests = 0
    for key in sorted(plugins):
        name, _, market = str(key).partition("@")
        slug = f"{market or 'local'}/{name}"
        rel = Path(".claude") / "plugins" / "store" / (market or "local") / name
        out[str(key)] = [
            {"scope": "user", "installPath": f"{HOME_TOKEN}/{rel.as_posix()}"}
        ]
        manifest: dict[str, Any] = {}
        for inst in plugins[key] if isinstance(plugins[key], list) else []:
            root = Path(str((inst or {}).get("installPath") or ""))
            for cand in (Path(".claude-plugin") / "plugin.json", Path("plugin.json")):
                p = root / cand
                if p.is_file():
                    try:
                        m = json.loads(_read(p))
                    except ValueError:
                        continue
                    if isinstance(m, dict):
                        manifest = m
                        break
            if manifest:
                break
        if not manifest:
            continue
        keep = {
            k: manifest[k]
            for k in ("name", "displayName", "description", "keywords", "version")
            if k in manifest
        }
        _write(
            dst_home / rel / ".claude-plugin" / "plugin.json",
            scrub(json.dumps(keep, indent=2) + "\n"),
        )
        manifests += 1
        del slug
    _write(
        dst_home / ".claude" / "plugins" / "installed_plugins.json",
        scrub(json.dumps({"version": 1, "plugins": out}, indent=2) + "\n"),
    )
    return len(out), manifests


# --------------------------------------------------------------------------- roots


def live_roots(home: Path):
    from routing import index as ix

    return ix.Roots(
        workflows=ix.PLATFORM / "workflows",
        protocols=ix.PLATFORM / "council" / "protocols",
        presets=ix.PLATFORM / "council" / "presets",
        registry=ix.PLATFORM / "registry",
        skills=[home / ".agents" / "skills", home / ".claude" / "skills"],
        plugins_json=home / ".claude" / "plugins" / "installed_plugins.json",
        mcp_json=home / ".mcp.json",
        agents=home / ".claude" / "agents",
        commands=home / ".claude" / "commands",
    )


def render(fixture_home: Path, dest: Path) -> Path:
    """Materialise a runnable HOME from the committed fixture.

    The one thing the committed tree cannot hold is an absolute path, and
    `index.plugins()` follows `installPath` to each vendor manifest. So the registry
    ships the `__FIXTURE_HOME__` token and this function resolves it against wherever the
    fixture was placed. Everything else is copied unchanged.

    Shared by `verify()` and `conftest.py` so the fixture the tests run against is
    byte-for-byte the one the generator checked.
    """
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(fixture_home, dest)
    reg = dest / ".claude" / "plugins" / "installed_plugins.json"
    if reg.is_file():
        reg.write_text(
            _read(reg).replace(HOME_TOKEN, dest.resolve().as_posix()),
            encoding="utf-8",
            newline="\n",
        )
    return dest


def verify(source_home: Path, fixture_home: Path) -> dict[str, Any]:
    """Two comparisons, because they answer two different questions.

    1. SHRINK LOSSLESSNESS (the gate). Build a second tree from the same source with
       shrinking disabled -- same scrubber, full bodies -- and require the committed
       fixture to be EXACTLY identical to it on every field. Both sides are scrubbed, so
       the scrub cancels out and any surviving difference is a shrinker bug. This is the
       claim that actually needs proving, and it is proven exactly rather than by a
       tolerance.

    2. SCRUB DELTA (reported, not gated). Compare against the UNSCRUBBED live index. A
       difference here is expected wherever the username appeared in indexed text:
       `agentuser` is one character shorter than the real name, so the `body[:1500]`
       window slides and admits one more character. Gating on this would be gating on
       the redaction, which is not optional.
    """
    import tempfile

    from routing import index as ix

    tmp = Path(tempfile.mkdtemp(prefix="routing-fixture-verify-"))
    try:
        ref_home = tmp / "reference"
        build(source_home, ref_home, full=ALL_FILES)
        ref = ix.discover(live_roots(render(ref_home, tmp / "ref-rendered"))).by_id()
        fix = ix.discover(live_roots(render(fixture_home, tmp / "home"))).by_id()
        live = ix.discover(live_roots(source_home)).by_id()
        out = _compare(ref, fix)
        out["scrub_delta_vs_live"] = {
            k: len(v) if isinstance(v, list) else v
            for k, v in _compare(live, fix)["diffs"].items()
        }
        out["live_total"] = len(live)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _compare(live: dict, fix: dict) -> dict[str, Any]:
    home_classes = {"skill", "agent", "command", "mcp", "plugin"}
    live_ids = {i for i, r in live.items() if r.cls in home_classes}
    fix_ids = {i for i, r in fix.items() if r.cls in home_classes}
    diffs: dict[str, list[str]] = {"routing_text": [], "desc_source": [], "card": []}
    for i in sorted(live_ids & fix_ids):
        for field in diffs:
            if getattr(live[i], field) != getattr(fix[i], field):
                diffs[field].append(i)
    return {
        "reference_total": len(live),
        "fixture_total": len(fix),
        "missing_in_fixture": sorted(live_ids - fix_ids),
        "extra_in_fixture": sorted(fix_ids - live_ids),
        "diffs": diffs,
        "identical": all(not v for v in diffs.values())
        and live_ids == fix_ids
        and len(live) == len(fix),
    }


# --------------------------------------------------------------------------- driver


def build(
    source_home: Path, out: Path, full: frozenset[str] | set[str] | None = None
) -> dict[str, Any]:
    full = full or frozenset()
    scrub = Scrubber(source_home.name)
    if out.exists():
        shutil.rmtree(out)
    counts = {
        "agents_skills": emit_skill_tree(
            source_home / ".agents" / "skills", out / ".agents" / "skills", scrub, full
        ),
        "claude_skills": emit_skill_tree(
            source_home / ".claude" / "skills", out / ".claude" / "skills", scrub, full
        ),
        "agents": emit_md_tree(
            source_home / ".claude" / "agents",
            out / ".claude" / "agents",
            "*.md",
            scrub,
            full,
        ),
        "commands": emit_md_tree(
            source_home / ".claude" / "commands",
            out / ".claude" / "commands",
            "**/*.md",
            scrub,
            full,
        ),
        "mcp_servers": emit_mcp(source_home / ".mcp.json", out / ".mcp.json", scrub),
    }
    counts["plugins"], counts["plugin_manifests"] = emit_plugins(
        source_home, out, scrub
    )
    return {
        "counts": counts,
        "scrub": {
            "username_replacements": scrub.user_hits,
            "secret_replacements": scrub.secret_hits,
            "entropy_candidates": sorted(set(scrub.entropy_hits))[:20],
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=str(Path.home()))
    ap.add_argument("--out", default=str(FIXTURE_HOME))
    ap.add_argument("--verify", action="store_true", help="verify only, do not rebuild")
    a = ap.parse_args(argv)
    src, out = Path(a.source), Path(a.out)

    report: dict[str, Any] = {}
    if not a.verify:
        report = build(src, out)
        v = verify(src, out)
        # A field that survived shrinking as a difference gets its whole source file
        # re-emitted verbatim, then the comparison is repeated. Falling back per FILE
        # keeps the fixture small without ever trading away routing equivalence.
        bad = {i.split(":", 1)[1] for f in v["diffs"].values() for i in f}
        if bad:
            report = build(src, out, full=bad)
            v = verify(src, out)
        report["retried_full"] = sorted(bad)
    else:
        v = verify(src, out)
    report["verify"] = v

    print(json.dumps(report, indent=2))
    if v["identical"]:
        print(f"SUCCESS:routing-fixture records={v['fixture_total']}")
        return 0
    print(
        "FAILED:routing-fixture "
        f"missing={len(v['missing_in_fixture'])} "
        f"extra={len(v['extra_in_fixture'])} "
        f"diffs={ {k: len(x) for k, x in v['diffs'].items()} }"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
