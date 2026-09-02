"""Independent syntactic fan-out arity.

This module must NOT import the Claude-workflow adapter. Probe 1 compares
this walk against the adapter's FanOut.units length. Agreement is the second
signal the catalog requires; a shared helper would collapse the two
derivations into one.
"""
from __future__ import annotations


def _strip_comments_and_strings(src: str) -> str:
    """Replace comments and string bodies with spaces, keeping length."""
    out = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(" " * (j - i))
            i = j
            continue
        if c in "'\"`":
            q = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if q == "`" and src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    depth = 1
                    j += 2
                    while j < n and depth:
                        if src[j] == "{":
                            depth += 1
                        elif src[j] == "}":
                            depth -= 1
                        elif src[j] == "\\":
                            j += 2
                            continue
                        j += 1
                    continue
                if src[j] == q:
                    j += 1
                    break
                j += 1
            out.append(" " + ("_" * max(j - i - 2, 0)) + " ")
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _match_paren(s: str, open_idx: int) -> int:
    depth = 0
    for k in range(open_idx, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _match_bracket(s: str, open_idx: int) -> int:
    depth_br = depth_p = depth_c = 0
    for k in range(open_idx, len(s)):
        c = s[k]
        if c == "[":
            depth_br += 1
        elif c == "]":
            depth_br -= 1
            if depth_br == 0 and depth_p == 0 and depth_c == 0:
                return k
        elif c == "(":
            depth_p += 1
        elif c == ")":
            depth_p -= 1
        elif c == "{":
            depth_c += 1
        elif c == "}":
            depth_c -= 1
    return -1


def parallel_array_widths(source: str) -> list[int]:
    """Count top-level elements of every `parallel([ ... ])` array.

    Commas inside nested (), [], {} are ignored. A trailing comma does not
    add an empty element. This is array arity, not a semantic agent() count.
    """
    s = _strip_comments_and_strings(source)
    widths: list[int] = []
    i = 0
    needle = "parallel"
    while True:
        j = s.find(needle, i)
        if j < 0:
            break
        # ident boundary
        before = s[j - 1] if j else ""
        after = s[j + len(needle)] if j + len(needle) < len(s) else ""
        if before.isalnum() or before in "_$" or after.isalnum() or after in "_$":
            i = j + len(needle)
            continue
        k = j + len(needle)
        while k < len(s) and s[k].isspace():
            k += 1
        if k >= len(s) or s[k] != "(":
            i = j + len(needle)
            continue
        close = _match_paren(s, k)
        if close < 0:
            i = j + len(needle)
            continue
        inner = s[k + 1 : close]
        # find first '[' at depth 0 of the arg list
        p = 0
        while p < len(inner) and inner[p].isspace():
            p += 1
        if p >= len(inner) or inner[p] != "[":
            i = close + 1
            continue
        arr_close_rel = _match_bracket(inner, p)
        if arr_close_rel < 0:
            i = close + 1
            continue
        body = inner[p + 1 : arr_close_rel]
        depth_br = depth_p = depth_c = 0
        elems = 0
        started = False
        for ch in body:
            if ch == "[":
                depth_br += 1
            elif ch == "]":
                depth_br -= 1
            elif ch == "(":
                depth_p += 1
            elif ch == ")":
                depth_p -= 1
            elif ch == "{":
                depth_c += 1
            elif ch == "}":
                depth_c -= 1
            if depth_br == 0 and depth_p == 0 and depth_c == 0:
                if ch == ",":
                    if started:
                        elems += 1
                        started = False
                    continue
            if not ch.isspace():
                started = True
        if started:
            elems += 1
        widths.append(elems)
        i = close + 1
    return widths


def _default_bound(s: str, name: str) -> int | None:
    """Independent of the adapter: default integer on a one-line `const NAME = ... : N`.

    Saved workflows in this repo omit semicolons (ASI). Scanning to the next `;`
    over-reads into a later ternary and misses the default.
    """
    for line in s.splitlines():
        t = line.strip()
        matched = False
        for kw in ("const ", "let ", "var "):
            prefix = kw + name
            if not t.startswith(prefix):
                continue
            after = t[len(prefix) :]
            if after and (after[0].isalnum() or after[0] in "_$"):
                continue
            eq = after.find("=")
            if eq < 0:
                continue
            rhs = after[eq + 1 :].strip()
            # trailing `: <int>` on this line (ternary default)
            colon = rhs.rfind(":")
            if colon >= 0:
                tail = rhs[colon + 1 :].strip()
                if tail.isdigit():
                    return int(tail)
            if rhs.isdigit():
                return int(rhs)
            matched = True
            break
        if matched:
            continue
    return None


def loop_bound_parallel_widths(source: str) -> list[int]:
    """Fan-out width from `for (i=0; i<N; i++) IDENT.push(() => agent)` + `parallel(IDENT)`.

    N's default integer is read from the `const N = ... : <int>` ternary, not from
    executing the script. Independent of the importer.
    """
    s = _strip_comments_and_strings(source)
    widths: list[int] = []
    i = 0
    while True:
        j = s.find("for", i)
        if j < 0:
            break
        before = s[j - 1] if j else ""
        after = s[j + 3] if j + 3 < len(s) else ""
        if before.isalnum() or before in "_$" or after.isalnum() or after in "_$":
            i = j + 3
            continue
        k = j + 3
        while k < len(s) and s[k].isspace():
            k += 1
        if k >= len(s) or s[k] != "(":
            i = j + 3
            continue
        close = _match_paren(s, k)
        if close < 0:
            i = j + 3
            continue
        header = s[k + 1 : close]
        # let|var|const VAR = 0; VAR < BOUND
        eq = header.find("=")
        if eq < 0 or "0" not in header[eq : eq + 4]:
            i = close + 1
            continue
        lt = header.find("<")
        if lt < 0:
            i = close + 1
            continue
        bound_tok = header[lt + 1 :].strip()
        bound_name = ""
        bound_n: int | None = None
        p = 0
        while p < len(bound_tok) and (bound_tok[p].isalnum() or bound_tok[p] in "_$"):
            bound_name += bound_tok[p]
            p += 1
        if bound_name.isdigit():
            bound_n = int(bound_name)
        elif bound_name:
            # reject `pairs.length` — p did not consume `.length`
            if p < len(bound_tok) and bound_tok[p] == ".":
                i = close + 1
                continue
            bound_n = _default_bound(s, bound_name)
        if bound_n is None:
            i = close + 1
            continue
        body_at = close + 1
        while body_at < len(s) and s[body_at].isspace():
            body_at += 1
        if body_at >= len(s) or s[body_at] != "{":
            i = close + 1
            continue
        body_close = -1
        depth = 0
        for q in range(body_at, len(s)):
            if s[q] == "{":
                depth += 1
            elif s[q] == "}":
                depth -= 1
                if depth == 0:
                    body_close = q
                    break
        if body_close < 0:
            i = close + 1
            continue
        body = s[body_at : body_close + 1]
        push_at = body.find(".push")
        if push_at < 0 or "agent" not in body:
            i = close + 1
            continue
        # IDENT immediately before .push
        ident_end = body_at + push_at
        ident_start = ident_end
        while ident_start > 0 and (s[ident_start - 1].isalnum() or s[ident_start - 1] in "_$"):
            ident_start -= 1
        ident = s[ident_start:ident_end]
        if not ident:
            i = close + 1
            continue
        # require a later parallel(IDENT)
        needle = "parallel"
        found_par = False
        r = 0
        while True:
            t = s.find(needle, r)
            if t < 0:
                break
            u = t + len(needle)
            while u < len(s) and s[u].isspace():
                u += 1
            if u < len(s) and s[u] == "(":
                inner_start = u + 1
                inner_close = _match_paren(s, u)
                if inner_close > 0 and s[inner_start:inner_close].strip() == ident:
                    found_par = True
                    break
            r = t + len(needle)
        if found_par:
            widths.append(bound_n)
        i = body_close + 1
    return widths


def independent_fanout_widths(source: str) -> list[int]:
    """Literal `parallel([..])` arity, else for-bound thunk-list defaults."""
    lit = parallel_array_widths(source)
    if lit:
        return lit
    return loop_bound_parallel_widths(source)
