# The docs site

`web/` turns the Markdown already in this repo into a small static site, so the
documentation can be read in a browser with a sidebar, a contents rail and
search — instead of scrolling through raw `.md` files.

```bash
tick docs                      # build and open it
python web/build.py            # build only, into web/dist/
python web/build.py --serve    # build, serve on :8000, open a browser
open web/dist/index.html       # or just open the file; no server needed
```

## How it works

```
README.md, PLAN.md, docs/*.md   ──┐
tick/**.py, examples/*.py,        ├─► build.py ─► web/dist/*.html + style.css + app.js
tests/*.py                      ──┘              + search-index.js
```

* **The Markdown stays the single source of truth.** Nothing is written twice:
  edit a `.md`, run the build, and the site follows. There is no separate copy
  of the docs to drift.
* **Every Python file is rendered too.** A link in the prose to `tick/market.py`
  lands on the actual code with its docstrings intact, which is where a good
  deal of the reasoning lives. `source.html` lists them all.
* **Dead links are dropped, not published.** `build.py` rewrites every relative
  link into a page in the site; anything that does not resolve renders as plain
  text rather than as a link that wastes a click.
* **Search is generated at build time** into `search-index.js` — one entry per
  heading, plus each module's docstring. It is a plain `<script src>` rather
  than a `fetch`, so search works from `file://` with no server.

## Why it has no dependencies

`mdlite.py` is a small Markdown renderer and syntax highlighter, standard
library only. A real Markdown library would parse better, but then reading the
docs would require installing something first — and the whole argument of this
SDK is that it runs with what is already on the machine. It handles exactly
what these docs use: headings, fenced code, pipe tables, nested and task lists,
blockquotes, rules, and inline code, bold, italic and links.

The same goes for the page itself: no framework, no bundler, no CDN. `app.js`
is about 150 lines of plain JavaScript for search, the contents rail, copy
buttons and the theme toggle.

## Files

| Path | What |
|---|---|
| `build.py` | assembles the site: pages, nav, source rendering, search index |
| `mdlite.py` | Markdown → HTML, and the code highlighter |
| `theme/style.css` | the design — the device's own palette, light and dark |
| `theme/app.js` | search, contents rail, copy buttons, theme, mobile nav |
| `dist/` | the built site, committed so a checkout can be read immediately |

## Adding a page

Write the Markdown in `docs/`, then add one row to `PAGES` in `build.py`:

```python
('tuning.html', 'docs/tuning.md', 'Reference', 'Tuning', 'Knobs worth turning.'),
```

The nav group, the previous/next links and the search entries follow from that
row. Rebuild and the page is in the site.

## Keeping it honest

[`tests/test_web.py`](../tests/test_web.py) builds the site and checks that
every page renders, every internal link resolves to a file that exists, every
`#anchor` matches a real heading id, and no documented link was silently
dropped. Broken documentation links are a slow leak; this closes it.
