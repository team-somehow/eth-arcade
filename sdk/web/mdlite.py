"""Just enough Markdown to render these docs, with no dependencies.

A full Markdown library would be a better parser and a worse decision: the docs
site would then need a package installed before anyone could read it, and the
whole point of this SDK is that it runs on a Pi with the standard library.

What it handles, because it is what the docs use: ATX headings, fenced code
with a language, pipe tables, ordered and unordered lists (nested, and task
lists), blockquotes, horizontal rules, paragraphs, and inline code, bold,
italic and links.

Order matters in the inline pass. Code spans are pulled out **first** and put
back **last**, so `**not bold**` inside backticks stays literal -- which the
API reference depends on in about forty places.
"""
from __future__ import annotations

import html
import re

# ---------------------------------------------------------------- slugs ----
_SLUG_DROP = re.compile(r'[^\w\s-]')
_SLUG_SPACE = re.compile(r'[\s_]+')


def slug(text: str) -> str:
    """A heading id, matching the anchors GitHub-style links already use.

    `### tick.hud and tick.ui` -> `tickhud-and-tickui`: punctuation vanishes
    rather than becoming a separator, which is why the dot disappears.
    """
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = _SLUG_DROP.sub('', text.lower())
    text = _SLUG_SPACE.sub('-', text.strip())
    # Collapse runs of dashes, so "Part 1 - First principles" is
    # part-1-first-principles rather than part-1---first-principles. The
    # anchors and the links that point at them are generated together here, so
    # they agree whatever the rule is; this one just reads better in a URL.
    return re.sub(r'-{2,}', '-', text).strip('-')


# ------------------------------------------------------------ highlight ----
KEYWORDS = {
    'python': ('and as assert async await break class continue def del elif else except '
               'finally for from global if import in is lambda None nonlocal not or pass '
               'raise return self True False try while with yield').split(),
    'bash': ('cd echo export for do done if then fi else pip python python3 source sudo '
             'cat curl git make mkdir rm set while').split(),
    'graphql': 'query mutation fragment on first where'.split(),
}
# Commands worth colouring as the subject of a shell line.
TOOLS = ('tick', 'python', 'python3', 'pip', 'pytest', 'cargo', 'substreams', 'forge', 'git')


def _span(kind: str, text: str) -> str:
    return f'<span class="t-{kind}">{html.escape(text)}</span>'


def highlight(code: str, language: str) -> str:
    """Colour a code block. Escapes as it goes, so callers pass raw text."""
    language = (language or '').lower()
    if language in ('python', 'py'):
        return _highlight_python(code)
    if language in ('bash', 'sh', 'shell', 'console'):
        return _highlight_shell(code)
    if language == 'json':
        return _highlight_json(code)
    if language == 'graphql':
        return _highlight_generic(code, KEYWORDS['graphql'], '#')
    return html.escape(code)


def _highlight_python(code: str) -> str:
    out: list[str] = []
    # Strings, comments, decorators, numbers, names -- one pass, first match wins.
    pattern = re.compile(
        r'(?P<str>"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\n]*"|\'[^\'\n]*\')'
        r'|(?P<comment>#[^\n]*)'
        r'|(?P<num>\b\d[\w_.]*\b)'
        r'|(?P<name>\b[A-Za-z_]\w*\b)')
    last = 0
    for match in pattern.finditer(code):
        out.append(html.escape(code[last:match.start()]))
        last = match.end()
        text = match.group()
        if match.lastgroup == 'name':
            if text in KEYWORDS['python']:
                out.append(_span('key', text))
            elif code[match.end():match.end() + 1] == '(':
                out.append(_span('fn', text))
            elif text[:1].isupper():
                out.append(_span('type', text))
            else:
                out.append(html.escape(text))
        elif match.lastgroup == 'str' and text[:3] in ('"""', "'''"):
            # A docstring is prose that happens to be a string. Most of the
            # reasoning in this SDK lives in one, so it gets a colour that
            # reads as text rather than as a literal.
            out.append(_span('doc', text))
        else:
            out.append(_span({'str': 'str', 'comment': 'com', 'num': 'num'}[match.lastgroup], text))
    out.append(html.escape(code[last:]))
    return ''.join(out)


def _highlight_shell(code: str) -> str:
    lines = []
    for line in code.split('\n'):
        stripped = line.lstrip()
        if stripped.startswith('#'):
            lines.append(_span('com', line))
            continue
        comment = ''
        # A trailing comment, but not a '#' inside quotes.
        hit = re.search(r'\s+#(?![!{])', line)
        if hit and line.count('"', 0, hit.start()) % 2 == 0:
            line, comment = line[:hit.start()], _span('com', line[hit.start():])
        words = re.split(r'(\s+)', line)
        done = []
        first = True
        for word in words:
            if not word.strip():
                done.append(word)
                continue
            if first and word.split('=')[0] in TOOLS:
                done.append(_span('fn', word))
            elif first and re.fullmatch(r'[A-Z][A-Z0-9_]*=.*', word):
                key, _, value = word.partition('=')
                done.append(_span('type', key) + '=' + html.escape(value))
            elif word.startswith('-'):
                done.append(_span('key', word))
            elif word.startswith(('"', "'")):
                done.append(_span('str', word))
            else:
                done.append(html.escape(word))
            first = False
        lines.append(''.join(done) + comment)
    return '\n'.join(lines)


def _highlight_json(code: str) -> str:
    pattern = re.compile(r'(?P<key>"[^"]*")(?P<colon>\s*:)|(?P<str>"[^"]*")'
                         r'|(?P<num>\b-?\d[\d.eE+-]*\b)|(?P<lit>\btrue\b|\bfalse\b|\bnull\b)')
    out, last = [], 0
    for match in pattern.finditer(code):
        out.append(html.escape(code[last:match.start()]))
        last = match.end()
        if match.lastgroup == 'colon' or match.group('key'):
            out.append(_span('type', match.group('key')) + html.escape(match.group('colon')))
        elif match.group('str'):
            out.append(_span('str', match.group('str')))
        elif match.group('num'):
            out.append(_span('num', match.group('num')))
        else:
            out.append(_span('key', match.group('lit')))
    out.append(html.escape(code[last:]))
    return ''.join(out)


def _highlight_generic(code: str, keywords, comment_mark: str) -> str:
    out = []
    for line in code.split('\n'):
        if line.lstrip().startswith(comment_mark):
            out.append(_span('com', line))
            continue
        pieces = re.split(r'(\W+)', line)
        out.append(''.join(_span('key', p) if p in keywords else html.escape(p) for p in pieces))
    return '\n'.join(out)


# --------------------------------------------------------------- inline ----
_CODE = re.compile(r'`([^`]+)`')
_LINK = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')
_BOLD = re.compile(r'\*\*([^*]+)\*\*')
_ITALIC = re.compile(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])')
_AUTOLINK = re.compile(r'(?<![\w">(])(https?://[^\s<>)\]]+)')


def inline(text: str, link_map=None) -> str:
    """Inline Markdown to HTML. `link_map` rewrites hrefs (see build.py)."""
    spans: list[str] = []

    def stash(match):
        spans.append(f'<code>{html.escape(match.group(1))}</code>')
        return f'\x00{len(spans) - 1}\x00'

    text = _CODE.sub(stash, text)
    text = html.escape(text)

    def link(match):
        label, href = match.group(1), match.group(2)
        if link_map:
            href = link_map(href)
            if href is None:
                return label
        external = href.startswith('http')
        extra = ' target="_blank" rel="noopener"' if external else ''
        return f'<a href="{href}"{extra}>{label}</a>'

    # The label may hold a stashed code span, so match on the escaped text.
    text = _LINK.sub(link, text)
    text = _AUTOLINK.sub(r'<a href="\1" target="_blank" rel="noopener">\1</a>', text)
    text = _BOLD.sub(r'<strong>\1</strong>', text)
    text = _ITALIC.sub(r'<em>\1</em>', text)
    return re.sub(r'\x00(\d+)\x00', lambda m: spans[int(m.group(1))], text)


# ---------------------------------------------------------------- blocks ---
_FENCE = re.compile(r'^```(\w*)\s*$')
_HEADING = re.compile(r'^(#{1,6})\s+(.*)$')
_BULLET = re.compile(r'^(\s*)([-*+])\s+(.*)$')
_NUMBER = re.compile(r'^(\s*)(\d+)\.\s+(.*)$')
_TASK = re.compile(r'^\[([ xX])\]\s+(.*)$')
_RULE = re.compile(r'^(-{3,}|\*{3,}|_{3,})$')


class Document:
    """Rendered HTML plus the headings, which become the page's contents list."""

    def __init__(self, html_text: str, headings: list[tuple[int, str, str]], text: str) -> None:
        self.html = html_text
        self.headings = headings      # (level, title, id)
        self.text = text              # plain text, for the search index

    @property
    def title(self) -> str:
        for level, title, _ in self.headings:
            if level == 1:
                return title
        return ''


def render(source: str, link_map=None) -> Document:
    lines = source.split('\n')
    out: list[str] = []
    headings: list[tuple[int, str, str]] = []
    plain: list[str] = []
    seen: dict[str, int] = {}
    index = 0

    def anchor(title: str) -> str:
        base = slug(title)
        seen[base] = seen.get(base, 0) + 1
        return base if seen[base] == 1 else f'{base}-{seen[base]}'

    while index < len(lines):
        line = lines[index]

        fence = _FENCE.match(line)
        if fence:
            language = fence.group(1)
            index += 1
            body = []
            while index < len(lines) and not lines[index].startswith('```'):
                body.append(lines[index])
                index += 1
            index += 1
            code = '\n'.join(body)
            label = f'<span class="lang">{html.escape(language)}</span>' if language else ''
            out.append(f'<div class="code">{label}'
                       f'<button class="copy" type="button" aria-label="Copy">copy</button>'
                       f'<pre><code>{highlight(code, language)}</code></pre></div>')
            continue

        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            ident = anchor(title)
            headings.append((level, re.sub(r'[`*]', '', title), ident))
            plain.append(title)
            out.append(f'<h{level} id="{ident}">{inline(title, link_map)}'
                       f'<a class="anchor" href="#{ident}" aria-label="Link">#</a></h{level}>')
            index += 1
            continue

        if _RULE.match(line.strip()) and line.strip():
            out.append('<hr>')
            index += 1
            continue

        if line.lstrip().startswith('|') and index + 1 < len(lines) \
                and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[index + 1]):
            table, index = _table(lines, index, link_map)
            out.append(table)
            continue

        if line.startswith('>'):
            body = []
            while index < len(lines) and lines[index].startswith('>'):
                body.append(lines[index].lstrip('>').strip())
                index += 1
            plain.append(' '.join(body))
            out.append(f'<blockquote>{inline(" ".join(body), link_map)}</blockquote>')
            continue

        if _BULLET.match(line) or _NUMBER.match(line):
            block, index = _list(lines, index, link_map, plain)
            out.append(block)
            continue

        if not line.strip():
            index += 1
            continue

        body = []
        while index < len(lines) and lines[index].strip() \
                and not _FENCE.match(lines[index]) and not _HEADING.match(lines[index]) \
                and not _BULLET.match(lines[index]) and not _NUMBER.match(lines[index]) \
                and not _RULE.match(lines[index].strip()):
            body.append(lines[index].strip())
            index += 1
        paragraph = ' '.join(body)
        plain.append(paragraph)
        out.append(f'<p>{inline(paragraph, link_map)}</p>')

    return Document('\n'.join(out), headings, ' '.join(plain))


def _table(lines, index, link_map):
    def cells(row):
        return [c.strip() for c in row.strip().strip('|').split('|')]

    head = cells(lines[index])
    aligns = []
    for spec in cells(lines[index + 1]):
        aligns.append('right' if spec.endswith(':') and not spec.startswith(':')
                      else 'center' if spec.startswith(':') and spec.endswith(':') else '')
    index += 2
    rows = []
    while index < len(lines) and lines[index].lstrip().startswith('|'):
        rows.append(cells(lines[index]))
        index += 1

    def cell(tag, text, align):
        style = f' style="text-align:{align}"' if align else ''
        return f'<{tag}{style}>{inline(text, link_map)}</{tag}>'

    out = ['<div class="table"><table><thead><tr>']
    out += [cell('th', text, aligns[i] if i < len(aligns) else '') for i, text in enumerate(head)]
    out.append('</tr></thead><tbody>')
    for row in rows:
        out.append('<tr>')
        out += [cell('td', text, aligns[i] if i < len(aligns) else '') for i, text in enumerate(row)]
        out.append('</tr>')
    out.append('</tbody></table></div>')
    return ''.join(out), index


def _list(lines, index, link_map, plain, depth=0):
    """One list, and any list nested under it. Indent is two spaces per level."""
    ordered = bool(_NUMBER.match(lines[index]))
    items: list[str] = []
    while index < len(lines):
        match = _NUMBER.match(lines[index]) or _BULLET.match(lines[index])
        if not match:
            break
        indent = len(match.group(1))
        if indent < depth:
            break
        if indent > depth:
            nested, index = _list(lines, index, link_map, plain, indent)
            if items:
                items[-1] += nested
            continue
        text = match.group(3)
        index += 1
        # A wrapped item: following lines indented further, with no marker.
        while index < len(lines) and lines[index].strip() \
                and not _NUMBER.match(lines[index]) and not _BULLET.match(lines[index]) \
                and lines[index].startswith(' ' * (depth + 1)):
            text += ' ' + lines[index].strip()
            index += 1
        plain.append(text)
        task = _TASK.match(text)
        if task:
            done = task.group(1).lower() == 'x'
            box = '<span class="box">%s</span>' % ('&#10003;' if done else '&nbsp;')
            items.append(f'<li class="task">{box}{inline(task.group(2), link_map)}')
        else:
            items.append(f'<li>{inline(text, link_map)}')
    tag = 'ol' if ordered else 'ul'
    return f'<{tag}>' + ''.join(item + '</li>' for item in items) + f'</{tag}>', index
