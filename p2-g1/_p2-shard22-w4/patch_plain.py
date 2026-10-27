from pathlib import Path
p = Path('tools/monitorcore/monitorcore/unified.py')
raw = p.read_bytes()
crlf = raw.count(b'\r\n') > 0
text = raw.decode('utf-8').replace('\r\n', '\n')

anchor_once = '''    ap.add_argument(
        "--once", action="store_true", help="render a single read-only frame and exit"
    )
'''
assert text.count(anchor_once) == 1, f'anchor_once count {text.count(anchor_once)}'
plain_arg = anchor_once + '''    ap.add_argument(
        "--plain",
        action="store_true",
        help="accessibility mode: render EVERY pane's frame line-oriented, "
        "no cursor addressing and no escapes, then exit (implies --once)",
    )
'''
text = text.replace(anchor_once, plain_arg)

anchor_main = '''    state = BoardState(pane=args.pane)
    if args.once or not supported_fn():
'''
assert text.count(anchor_main) == 1, f'anchor_main count {text.count(anchor_main)}'
plain_branch = '''    state = BoardState(pane=args.pane)
    if getattr(args, "plain", False):
        # --plain (screen-reader mode, TST-0247): reuse the very same frame()
        # the interactive board paints, for EVERY pane, but print the lines
        # newline-oriented with no cursor addressing and no cursor column.
        # One poll feeds every pane so the panes cannot disagree mid-dump.
        snaps = poll_all(srcs, clock=clock)
        for pane in panes:
            rendered = frame(
                BoardState(pane=pane.id),
                snaps=snaps,
                panes=panes,
                cols=args.width,
                now=clock(),
                cursor=False,
            )
            out(f"=== pane {pane.id} ===")
            for line in rendered.lines:
                out(line)
        return 0
    if args.once or not supported_fn():
'''
text = text.replace(anchor_main, plain_branch)

if crlf:
    text = text.replace('\n', '\r\n')
p.write_bytes(text.encode('utf-8'))
print('patched, new size', len(text.encode('utf-8')), 'crlf=', crlf)
