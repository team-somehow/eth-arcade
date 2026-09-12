/* TICK SDK docs: search, contents highlighting, copy buttons, theme.
   No framework and no build step — the whole site is files you can open. */
(function () {
  'use strict';

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };

  /* ------------------------------------------------------------- theme -- */
  var root = document.documentElement;
  var themeButton = $('#theme');
  if (themeButton) {
    themeButton.addEventListener('click', function () {
      var next = root.dataset.theme === 'light' ? 'dark' : 'light';
      root.dataset.theme = next;
      try { localStorage.setItem('tick-theme', next); } catch (e) {}
    });
  }

  /* -------------------------------------------------------------- menu -- */
  var menuButton = $('#menu'), side = $('#side');
  if (menuButton && side) {
    menuButton.addEventListener('click', function () { side.classList.toggle('open'); });
    $$('a', side).forEach(function (a) {
      a.addEventListener('click', function () { side.classList.remove('open'); });
    });
  }

  /* -------------------------------------------------------------- copy -- */
  $$('.copy').forEach(function (button) {
    button.addEventListener('click', function () {
      var code = $('code', button.parentNode) || $('code', button.parentNode.parentNode);
      if (!code) return;
      var write = navigator.clipboard && navigator.clipboard.writeText
        ? navigator.clipboard.writeText(code.innerText)
        : Promise.reject();
      write.then(function () {
        button.textContent = 'copied';
        button.classList.add('done');
        setTimeout(function () {
          button.textContent = 'copy';
          button.classList.remove('done');
        }, 1200);
      }, function () { button.textContent = 'select it'; });
    });
  });

  /* ---------------------------------------------------- contents rail -- */
  var links = $$('.toc a');
  if (links.length) {
    var targets = links.map(function (a) {
      return document.getElementById(decodeURIComponent(a.hash.slice(1)));
    }).filter(Boolean);
    var mark = function () {
      var best = 0;
      targets.forEach(function (node, i) {
        if (node.getBoundingClientRect().top < 120) best = i;
      });
      links.forEach(function (a, i) { a.classList.toggle('on', i === best); });
    };
    var waiting = false;
    window.addEventListener('scroll', function () {
      if (waiting) return;
      waiting = true;
      requestAnimationFrame(function () { mark(); waiting = false; });
    }, { passive: true });
    mark();
  }

  /* ------------------------------------------------------------ search -- */
  var box = $('#q'), panel = $('#results');
  var docs = window.DOCS || [];
  if (!box || !panel) return;

  var escapeHtml = function (text) {
    return text.replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  };

  /* Score a row against the words typed. Every word must appear somewhere,
     so "quiet market" does not match a page that only says "market". */
  function score(row, words) {
    var title = row.t.toLowerCase(), page = row.p.toLowerCase(), body = row.x.toLowerCase();
    var total = 0;
    for (var i = 0; i < words.length; i++) {
      var word = words[i];
      var inTitle = title.indexOf(word), inBody = body.indexOf(word);
      if (inTitle < 0 && inBody < 0 && page.indexOf(word) < 0) return 0;
      if (title === word) total += 60;
      else if (inTitle === 0) total += 40;
      else if (inTitle > 0) total += 24;
      if (inBody >= 0) total += 6;
      if (page.indexOf(word) >= 0) total += 4;
    }
    return total;
  }

  function snippet(text, words) {
    if (!text) return '';
    var lower = text.toLowerCase(), at = -1;
    for (var i = 0; i < words.length && at < 0; i++) at = lower.indexOf(words[i]);
    var from = Math.max(0, at - 42);
    var cut = text.slice(from, from + 150);
    var out = escapeHtml((from ? '…' : '') + cut + (from + 150 < text.length ? '…' : ''));
    words.forEach(function (word) {
      if (!word) return;
      out = out.replace(new RegExp('(' + word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'),
                        '<mark>$1</mark>');
    });
    return out;
  }

  var picked = -1;

  function run() {
    var query = box.value.trim().toLowerCase();
    if (query.length < 2) { panel.hidden = true; panel.innerHTML = ''; picked = -1; return; }
    var words = query.split(/\s+/);
    var hits = [];
    for (var i = 0; i < docs.length; i++) {
      var points = score(docs[i], words);
      if (points) hits.push({ row: docs[i], points: points });
    }
    hits.sort(function (a, b) { return b.points - a.points; });
    hits = hits.slice(0, 12);
    if (!hits.length) {
      panel.innerHTML = '<div class="none">Nothing for “' + escapeHtml(query) + '”.</div>';
    } else {
      panel.innerHTML = hits.map(function (hit, i) {
        var row = hit.row;
        var href = row.u + (row.a ? '#' + row.a : '');
        return '<a href="' + href + '"' + (i === 0 ? ' class="on"' : '') + '>' +
          '<div class="where">' + escapeHtml(row.p) + '</div>' +
          '<div class="what">' + escapeHtml(row.t) + '</div>' +
          '<div class="snip">' + snippet(row.x, words) + '</div></a>';
      }).join('');
      picked = 0;
    }
    panel.hidden = false;
  }

  function move(step) {
    var items = $$('a', panel);
    if (!items.length) return;
    items[picked] && items[picked].classList.remove('on');
    picked = (picked + step + items.length) % items.length;
    items[picked].classList.add('on');
    items[picked].scrollIntoView({ block: 'nearest' });
  }

  box.addEventListener('input', run);
  box.addEventListener('focus', run);
  box.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowDown') { event.preventDefault(); move(1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); move(-1); }
    else if (event.key === 'Enter') {
      var items = $$('a', panel);
      if (items[picked]) { event.preventDefault(); window.location.href = items[picked].href; }
    } else if (event.key === 'Escape') { box.blur(); panel.hidden = true; }
  });
  document.addEventListener('click', function (event) {
    if (!panel.contains(event.target) && event.target !== box) panel.hidden = true;
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === '/' && document.activeElement !== box) {
      event.preventDefault();
      box.focus();
      box.select();
    }
  });
})();
