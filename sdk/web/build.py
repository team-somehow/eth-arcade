"""Build the docs site from the Markdown that is already in the repo.

    python web/build.py            # writes web/dist/
    python web/build.py --serve    # ... then serves it and opens a browser

The Markdown files stay the single source of truth. Nothing here is written by
hand twice: edit `README.md` or `docs/*.md`, run this, and the site follows.
Every Python file in the SDK is rendered too, so a link from the prose to
`tick/market.py` lands on the actual code with the docstrings intact -- which
is where most of the reasoning lives.

Standard library only, and the output is plain files: open
`web/dist/index.html` from disk with no server at all.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

import mdlite

ROOT = Path(__file__).resolve().parent.parent      # the sdk/ folder
WEB = ROOT / 'web'
DIST = WEB / 'dist'
THEME = WEB / 'theme'

VERSION = re.search(r"__version__ = '([^']+)'",
                    (ROOT / 'tick' / '__init__.py').read_text()).group(1)

# ---------------------------------------------------------------- pages ----
# (output name, source file, nav group, nav label, one-line blurb)
PAGES = [
    ('index.html', 'README.md', 'Start', 'Overview',
     'What the SDK is, and a game in thirty lines.'),
    ('plan.html', 'PLAN.md', 'Start', 'The plan',
     'First principles, the rules and what each one cost, and the build order.'),
    ('writing-a-game.html', 'docs/writing-a-game.md', 'Start', 'Writing a game',
     'Nothing to playable, step by step.'),
    ('prices-substreams.html', 'docs/prices-substreams.md', 'Build with', 'Prices on-chain',
     'A price your game can settle on: Substreams, pools, and one number.'),
    ('money-arc.html', 'docs/money-arc.md', 'Build with', 'Real money',
     'Escrowed USDC sessions, and why there is no transaction per bet.'),
    ('identity-ens.html', 'docs/identity-ens.md', 'Build with', 'Player names',
     'ENS subnames, records, and a leaderboard with no server.'),
    ('api.html', 'docs/api.md', 'Reference', 'API',
     'The whole public surface on one page.'),
    ('device.html', 'docs/device.md', 'Reference', 'The device',
     'Screen, dial, buttons, sound, and the Pi.'),
    ('docs-site.html', 'web/README.md', 'Reference', 'This site',
     'How the docs site is generated, and how to add a page.'),
]

EXAMPLES = [
    ('examples/coinflip.py', 'Coinflip', 'The smallest real game: up or down at the bell.'),
    ('examples/ladder.py', 'Ladder', 'Park a box on the price -- the shape most games take.'),
    ('examples/ticker.py', 'Ticker', 'The data layer with no game and no pygame.'),
    ('examples/pools.py', 'Pools', 'Every pool in the on-chain stream, block by block.'),
    ('tick/templates/game.py', 'Template', 'What `tick new` writes for you.'),
]

SOURCE_DIRS = ('tick', 'examples', 'tests')


def source_page(relative: str) -> str:
    """Output filename for a rendered source file."""
    return 'src-' + str(relative).replace('/', '-').replace('.py', '') + '.html'


def source_files() -> list[Path]:
    found: list[Path] = []
    for folder in SOURCE_DIRS:
        found += sorted(p for p in (ROOT / folder).rglob('*.py')
                        if '__pycache__' not in p.parts)
    return found


# ----------------------------------------------------------------- links ---
def build_link_map(page_dir: Path, docs: dict[str, str], sources: dict[str, str]):
    """Rewrite a Markdown href into a page in the site, or drop it.

    Returning None drops the link and leaves the label as plain text: a dead
    link in documentation is worse than no link, because it costs the reader a
    click to find out.
    """
    def rewrite(href: str):
        if href.startswith(('http://', 'https://', 'mailto:', '#')):
            return href
        base, _, anchor = href.partition('#')
        anchor = f'#{anchor}' if anchor else ''
        if not base:
            return anchor
        try:
            target = (page_dir / base).resolve().relative_to(ROOT)
        except (ValueError, OSError):
            return None
        key = str(target)
        # A link into the built site is already a page of it.
        if key.startswith('web/dist/'):
            return key[len('web/dist/'):] + anchor
        if key in docs:
            return docs[key] + anchor
        if key in sources:
            return sources[key] + anchor
        if key.endswith('/') or (ROOT / key).is_dir():
            return 'source.html#' + mdlite.slug(key.strip('/'))
        return None
    return rewrite


# --------------------------------------------------------------- search ----
_FENCE = re.compile(r'^```')
_HEAD = re.compile(r'^(#{1,4})\s+(.*)$')


def sections(markdown: str) -> list[tuple[str, str, str]]:
    """(title, anchor, text) per heading, so search can point at a section."""
    out: list[tuple[str, str, list[str]]] = []
    seen: dict[str, int] = {}
    in_code = False
    for line in markdown.split('\n'):
        if _FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            if out:
                out[-1][2].append(line)
            continue
        head = _HEAD.match(line)
        if head:
            title = re.sub(r'[`*]', '', head.group(2)).strip()
            base = mdlite.slug(head.group(2))
            seen[base] = seen.get(base, 0) + 1
            anchor = base if seen[base] == 1 else f'{base}-{seen[base]}'
            out.append((title, anchor, []))
        elif out:
            out[-1][2].append(line)
    return [(title, anchor, re.sub(r'\s+', ' ', ' '.join(body)).strip()[:600])
            for title, anchor, body in out]


# ------------------------------------------------------------- templates ---
def nav_html(groups, current: str) -> str:
    out = ['<nav class="nav" aria-label="Documentation">']
    for group, items in groups:
        out.append(f'<div class="nav-group"><h4>{html.escape(group)}</h4><ul>')
        for url, label, _ in items:
            active = ' class="on"' if url == current else ''
            out.append(f'<li><a href="{url}"{active}>{html.escape(label)}</a></li>')
        out.append('</ul></div>')
    out.append('</nav>')
    return ''.join(out)


def toc_html(headings) -> str:
    inner = [h for h in headings if h[0] in (2, 3)]
    # A very long page's contents list is worse than a short one: drop to the
    # top level rather than printing sixty entries nobody can scan.
    if len(inner) > 22:
        inner = [h for h in headings if h[0] == 2]
    if len(inner) < 2:
        return ''
    out = ['<aside class="toc"><h4>On this page</h4><ul>']
    for level, title, ident in inner:
        out.append(f'<li class="l{level}"><a href="#{ident}">{html.escape(title)}</a></li>')
    out.append('</ul></aside>')
    return ''.join(out)


SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{blurb}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='26' font-size='26'>&#127918;</text></svg>">
<link rel="stylesheet" href="style.css">
<script>(function(){{try{{var t=localStorage.getItem('tick-theme');if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
</head>
<body>
<header class="top">
  <a class="brand" href="index.html"><span class="mark">T</span> TICK <span class="sdk">SDK</span></a>
  <div class="find">
    <input id="q" type="search" placeholder="Search the docs&hellip;  /" autocomplete="off" spellcheck="false">
    <div id="results" class="results" hidden></div>
  </div>
  <div class="tools">
    <span class="version">v{version}</span>
    <button id="theme" class="ghost" type="button" aria-label="Switch theme">&#9680;</button>
    <button id="menu" class="ghost only-narrow" type="button" aria-label="Menu">&#9776;</button>
  </div>
</header>
<div class="shell">
  <div class="side" id="side">{nav}</div>
  <main>
    <article class="doc">{body}</article>
    {footer}
  </main>
  {toc}
</div>
<script src="search-index.js"></script>
<script src="app.js"></script>
</body>
</html>
"""


def page(title: str, blurb: str, nav: str, body: str, toc: str, footer: str) -> str:
    return SHELL.format(title=html.escape(title), blurb=html.escape(blurb), version=VERSION,
                        nav=nav, body=body, toc=toc, footer=footer)


def pager(previous, following) -> str:
    if not previous and not following:
        return ''
    out = ['<nav class="pager">']
    if previous:
        out.append(f'<a class="prev" href="{previous[0]}"><span>Previous</span>'
                   f'{html.escape(previous[1])}</a>')
    if following:
        out.append(f'<a class="next" href="{following[0]}"><span>Next</span>'
                   f'{html.escape(following[1])}</a>')
    out.append('</nav>')
    return ''.join(out)


# ----------------------------------------------------------------- build ---
def build() -> Path:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    files = source_files()
    sources = {str(p.relative_to(ROOT)): source_page(p.relative_to(ROOT)) for p in files}
    docs = {source: name for name, source, *_ in PAGES}

    groups: dict[str, list] = {}
    for name, _, group, label, blurb in PAGES:
        groups.setdefault(group, []).append((name, label, blurb))
    groups.setdefault('Examples', [])
    for relative, label, blurb in EXAMPLES:
        groups['Examples'].append((sources[relative], label, blurb))
    groups['Examples'].append(('source.html', 'All source', 'Every file in the SDK.'))
    ordered = [(group, groups[group]) for group in
               ('Start', 'Build with', 'Reference', 'Examples')]

    flat = [(url, label) for _, items in ordered for url, label, _ in items]
    index: list[dict] = []

    # ---- the documentation pages
    for position, (name, source, _group, label, blurb) in enumerate(PAGES):
        markdown = (ROOT / source).read_text()
        link_map = build_link_map((ROOT / source).parent, docs, sources)
        doc = mdlite.render(markdown, link_map)
        title = doc.title or label
        spot = [i for i, (url, _) in enumerate(flat) if url == name][0]
        footer = pager(flat[spot - 1] if spot else None,
                       flat[spot + 1] if spot + 1 < len(flat) else None)
        (DIST / name).write_text(page(
            f'{title} - TICK SDK' if name != 'index.html' else 'TICK SDK',
            blurb, nav_html(ordered, name), doc.html, toc_html(doc.headings), footer))
        for heading, anchor, text in sections(markdown):
            index.append({'u': name, 'p': label, 't': heading, 'a': anchor, 'x': text})

    # ---- one page per source file
    for path in files:
        relative = str(path.relative_to(ROOT))
        body = path.read_text()
        head = (f'<h1 id="top">{html.escape(path.name)}'
                f'<a class="anchor" href="#top">#</a></h1>'
                f'<p class="path">{html.escape(relative)} &middot; '
                f'{len(body.splitlines())} lines</p>')
        numbers = ''.join(f'<span>{n}</span>' for n in range(1, len(body.splitlines()) + 1))
        code = (f'<div class="code source"><span class="lang">python</span>'
                f'<button class="copy" type="button" aria-label="Copy">copy</button>'
                f'<div class="rows"><div class="numbers">{numbers}</div>'
                f'<pre><code>{mdlite.highlight(body, "python")}</code></pre></div></div>')
        spot = [i for i, (url, _) in enumerate(flat) if url == sources[relative]]
        footer = ''
        if spot:
            at = spot[0]
            footer = pager(flat[at - 1] if at else None,
                           flat[at + 1] if at + 1 < len(flat) else None)
        (DIST / sources[relative]).write_text(page(
            f'{relative} - TICK SDK', f'Source of {relative}.',
            nav_html(ordered, sources[relative]), head + code, '', footer))
        # The module docstring is the useful part to search on.
        doc_string = re.match(r'^\s*(?:"""|\'\'\')([\s\S]*?)(?:"""|\'\'\')', body)
        index.append({'u': sources[relative], 'p': 'Source', 't': relative, 'a': '',
                      'x': re.sub(r'\s+', ' ', doc_string.group(1)).strip()[:600]
                      if doc_string else ''})

    # ---- the source index
    listing = ['<h1 id="top">All source<a class="anchor" href="#top">#</a></h1>',
               '<p>Every Python file in the SDK, rendered with its docstrings. '
               'The reasoning lives in the code as much as in the prose.</p>']
    for folder in SOURCE_DIRS:
        listing.append(f'<h2 id="{mdlite.slug(folder)}">{folder}/'
                       f'<a class="anchor" href="#{mdlite.slug(folder)}">#</a></h2>')
        listing.append('<div class="table"><table><thead><tr><th>File</th>'
                       '<th>Lines</th><th>What it is</th></tr></thead><tbody>')
        for path in files:
            relative = str(path.relative_to(ROOT))
            if not relative.startswith(folder + '/'):
                continue
            body = path.read_text()
            # The first line of the module docstring. Stopping at the first
            # quote instead would cut "a player's money" at the apostrophe.
            doc_string = re.match(r'^\s*(?:"""|\'\'\')([^\n]*)', body)
            summary = doc_string.group(1).strip() if doc_string else ''
            listing.append(f'<tr><td><a href="{sources[relative]}"><code>{html.escape(relative)}'
                           f'</code></a></td><td>{len(body.splitlines())}</td>'
                           f'<td>{mdlite.inline(summary)}</td></tr>')
        listing.append('</tbody></table></div>')
    (DIST / 'source.html').write_text(page(
        'All source - TICK SDK', 'Every file in the SDK.',
        nav_html(ordered, 'source.html'), ''.join(listing), '', ''))

    (DIST / 'search-index.js').write_text(
        'window.DOCS=' + json.dumps(index, separators=(',', ':')) + ';\n')
    for asset in ('style.css', 'app.js'):
        shutil.copyfile(THEME / asset, DIST / asset)

    print(f'built {len(PAGES)} pages, {len(files)} source pages, '
          f'{len(index)} search entries -> {DIST}')
    return DIST


def serve(port: int, open_browser: bool = True) -> None:
    import functools
    import http.server
    import threading
    import webbrowser
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    url = f'http://127.0.0.1:{port}/'
    print(f'docs on {url}  (ctrl-c to stop)')
    if open_browser:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--serve', action='store_true', help='serve after building')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args(argv)
    build()
    if args.serve:
        serve(args.port, not args.no_open)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
