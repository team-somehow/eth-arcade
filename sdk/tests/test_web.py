"""The docs site builds, and nothing in it points at nothing.

Broken links in documentation are a slow leak: each one costs a reader a click
to discover that the thing they wanted is not there. These tests are cheap and
they close it.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'web'))

import build as site            # noqa: E402
import mdlite                   # noqa: E402


class TestMarkdown(unittest.TestCase):
    def test_headings_become_the_anchors_links_already_use(self):
        self.assertEqual(mdlite.slug('### `tick.hud` and `tick.ui`'), 'tickhud-and-tickui')
        self.assertEqual(mdlite.slug('Part 1 - First principles'), 'part-1-first-principles')

    def test_code_spans_win_over_every_other_inline_rule(self):
        out = mdlite.inline('use `**kwargs` and **bold**')
        self.assertIn('<code>**kwargs</code>', out)
        self.assertIn('<strong>bold</strong>', out)

    def test_html_in_the_source_is_escaped(self):
        self.assertIn('&lt;script&gt;', mdlite.inline('<script>alert(1)</script>'))

    def test_a_table_becomes_a_table(self):
        out = mdlite.render('| a | b |\n|---|---|\n| 1 | 2 |\n').html
        self.assertIn('<th>a</th>', out)
        self.assertIn('<td>2</td>', out)

    def test_a_nested_list_nests(self):
        out = mdlite.render('- one\n  - deeper\n- two\n').html
        self.assertIn('<ul><li>one<ul><li>deeper</li></ul></li>', out)

    def test_a_fenced_block_is_not_parsed_as_markdown(self):
        out = mdlite.render('```python\n# **not bold**\n```\n').html
        self.assertNotIn('<strong>', out)
        self.assertIn('t-com', out)

    def test_a_task_list_gets_boxes(self):
        out = mdlite.render('- [ ] todo\n- [x] done\n').html
        self.assertEqual(out.count('class="task"'), 2)
        self.assertIn('&#10003;', out)


class TestSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dist = site.build()
        cls.pages = sorted(cls.dist.glob('*.html'))

    def test_every_documented_page_is_built(self):
        for name, _, _, _, _ in site.PAGES:
            self.assertTrue((self.dist / name).exists(), name)
        self.assertTrue((self.dist / 'source.html').exists())
        self.assertTrue((self.dist / 'style.css').exists())
        self.assertTrue((self.dist / 'app.js').exists())
        self.assertTrue((self.dist / 'search-index.js').exists())

    def test_every_page_is_a_whole_html_document(self):
        for page in self.pages:
            text = page.read_text()
            with self.subTest(page=page.name):
                self.assertTrue(text.startswith('<!doctype html>'))
                self.assertIn('<meta charset="utf-8">', text)
                self.assertIn('name="viewport"', text)
                self.assertIn('</html>', text)

    def test_no_internal_link_points_at_a_missing_file(self):
        missing = []
        for page in self.pages:
            for href in set(re.findall(r'href="([^"#]*)(?:#[^"]*)?"', page.read_text())):
                if not href or href.startswith(('http', 'data:', 'mailto:')):
                    continue
                if not (self.dist / href).exists():
                    missing.append(f'{page.name} -> {href}')
        self.assertEqual(missing, [])

    def test_every_anchor_matches_a_real_heading(self):
        ids = {p.name: set(re.findall(r'id="([^"]+)"', p.read_text())) for p in self.pages}
        broken = []
        for page in self.pages:
            for target, anchor in set(re.findall(r'href="([^"]*)#([^"]+)"', page.read_text())):
                where = target or page.name
                if where.startswith(('http', 'data:')):
                    continue
                if anchor not in ids.get(where, set()):
                    broken.append(f'{page.name} -> {where}#{anchor}')
        self.assertEqual(broken, [])

    def test_no_link_in_the_markdown_was_silently_dropped(self):
        files = site.source_files()
        sources = {str(p.relative_to(site.ROOT)): site.source_page(p.relative_to(site.ROOT))
                   for p in files}
        docs = {source: name for name, source, *_ in site.PAGES}
        dropped = []
        for _name, source, *_rest in site.PAGES:
            markdown = (site.ROOT / source).read_text()
            rewrite = site.build_link_map((site.ROOT / source).parent, docs, sources)
            for label, href in re.findall(r'\[([^\]]+)\]\(([^)\s]+)\)', markdown):
                if rewrite(href) is None:
                    dropped.append(f'{source}: [{label}]({href})')
        self.assertEqual(dropped, [])

    def test_the_search_index_covers_every_page(self):
        index = (self.dist / 'search-index.js').read_text()
        for name, _, _, label, _ in site.PAGES:
            self.assertIn(f'"{name}"', index, name)
        self.assertGreater(index.count('"u":'), 100)


if __name__ == '__main__':
    unittest.main()
