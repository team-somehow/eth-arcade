/* =====================================================================
   LONGSHOT — charge and release bench
   GAMES.md §3③ — "crank to charge a power bar, release A to commit"

   The real instrument is a ONE-TOUCH (knock-in) option:
       does price touch +b at any point inside T seconds?
   It pays the instant it touches and expires worthless if it never does.

   Pricing, by the reflection principle on a driftless random walk:
       a  = ln(1 + b)                barrier, in log space
       σT = σ · √T
       p  = 2 · Φ(−a / σT)           probability of EVER touching
       fair multiplier = 1 / p
   (The −σ²/2 drift term is ~5e−5 over a minute. Dropped.)

   Settlement reads the TRUE path. Your screen reads the ticks you bought.
   On a 1 Hz feed the market can spike through the barrier and back between
   two samples: you get paid for a touch you never saw.
   ===================================================================== */
(function () {
  'use strict';

  var W = 400, H = 240;
  var LCD_INK = [35, 34, 30], LCD_PAPER = [183, 180, 166];
  var BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]];
  var FEEDS = [
    { name: 'BASIC',   hz: 1,  cost: 1, label: '1 Hz'  },
    { name: 'PREMIUM', hz: 10, cost: 4, label: '10 Hz' }
  ];
  var START_COINS = 1200, PACK = 600, PACK_USD = 0.30, CAP_TOTAL = 10.00;
  var SELL_MS = 800;

  var S = { vol: 0.125, T: 60, edge: 0, stake: 1.00, meter: 0.42 };
  var PRESETS = {
    doc:  { vol: 0.125, T: 60, edge: 0 },
    real: { vol: 0.100, T: 60, edge: 3 },
    demo: { vol: 0.450, T: 40, edge: 0 }
  };
  var KNOBS = [
    { k: 'vol',   lbl: 'Volatility σ',    min: 0.02, max: 1.2,  step: 0.005, fmt: function (v) { return v.toFixed(3) + ' %/s'; }, note: '0.125 is what GAMES.md’s 6.8× implies' },
    { k: 'T',     lbl: 'Window T',        min: 10,   max: 120,  step: 5,     fmt: function (v) { return v.toFixed(0) + ' s'; },   note: 'Longer window, easier touch, thinner payout' },
    { k: 'edge',  lbl: 'House edge',      min: 0,    max: 20,   step: 0.5,   fmt: function (v) { return v.toFixed(1) + '%'; },    note: 'Shaved off the fair 1/p' },
    { k: 'stake', lbl: 'Stake per shot',  min: 0.25, max: 2.5,  step: 0.25,  fmt: function (v) { return '$' + v.toFixed(2); },    note: 'Drawn from the Privy cap on fire' },
    { k: 'meter', lbl: 'Auto-meter speed', min: 0.15, max: 1.2, step: 0.05,  fmt: function (v) { return v.toFixed(2) + ' /s'; },  note: 'Golf-swing sweep while A is held' }
  ];

  /* ---------------- state ---------------- */
  var M = {
    phase: 'charge',            // charge | flight | result
    price: 2430.00, hist: [], tickHist: [], clock: 0,
    charge: 0.45, holding: false, meterDir: 1, suppress: 0,
    b: 0, mult: 0, pEntry: 0, stake: 0,
    entry: 0, barrierPx: 0, fireClock: 0, t: 0,
    highWater: 0, shownHigh: 0,
    touched: false, touchSeen: true, touchT: 0,
    lastTick: 0, tickAcc: 0, frozen: false,
    coins: START_COINS, capUsed: 0, ticks: 0, hbar: 0, feed: 1,
    shots: 0, hits: 0, bank: 0,
    sellT: 0, autoMeter: true, trueSettle: true,
    resMsg: '', resSub: '', resGood: false, flash: 0,
    pLive: 0, valLive: 0
  };

  var $ = function (id) { return document.getElementById(id); };
  var screen = $('screen'), sctx = screen.getContext('2d', { willReadFrequently: true });
  var chart = $('chart'), cctx = chart.getContext('2d');
  var ladder = $('ladder'), lctx = ladder.getContext('2d');
  var TOK = {};
  function readTokens() {
    var cs = getComputedStyle(document.documentElement);
    ['ser-true', 'ser-paid', 'crit', 'good', 'accent', 'ink', 'ink-2', 'ink-3', 'line', 'sunk', 'surface']
      .forEach(function (n) { TOK[n] = cs.getPropertyValue('--' + n).trim(); });
  }

  /* ---------------- math ---------------- */
  var _sp = null;
  function gauss() {
    if (_sp !== null) { var v = _sp; _sp = null; return v; }
    while (true) {
      var u = Math.random() * 2 - 1, w = Math.random() * 2 - 1, s2 = u * u + w * w;
      if (s2 > 0 && s2 < 1) { var m = Math.sqrt(-2 * Math.log(s2) / s2); _sp = w * m; return u * m; }
    }
  }
  function ncdf(x) {                       // Abramowitz & Stegun 26.2.17
    var t = 1 / (1 + 0.2316419 * Math.abs(x));
    var d = 0.3989422804014327 * Math.exp(-x * x / 2);
    var p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
    return x >= 0 ? 1 - p : p;
  }
  function touchProb(a, sig, T) {          // P(ever touch level a above spot, in log space)
    if (a <= 0) return 1;
    if (T <= 0 || sig <= 0) return 0;
    return Math.min(1, 2 * ncdf(-a / (sig * Math.sqrt(T))));
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function usd(v) { return (v < 0 ? '−$' : '+$') + Math.abs(v).toFixed(2); }
  function multOf(p) { return p <= 0 ? Infinity : (1 / p) * (1 - S.edge / 100); }
  function fmtMult(m) { return !isFinite(m) || m > 9999 ? '9999×' : (m >= 100 ? m.toFixed(0) : m.toFixed(2)) + '×'; }

  function sigT() { return (S.vol / 100) * Math.sqrt(S.T); }
  function bMin() { return 0.15 * sigT(); }
  function bMax() { return 2.8 * sigT(); }
  function barrierFor(c) { return bMin() + c * (bMax() - bMin()); }

  function log(msg, cls) {
    var ol = $('log'), li = document.createElement('li');
    if (cls) li.className = cls;
    li.innerHTML = '<span class="lt">' + (M.phase === 'flight' ? M.t.toFixed(1) + 's' : '·') + '</span><span>' + msg + '</span>';
    ol.insertBefore(li, ol.firstChild);
    while (ol.children.length > 40) ol.removeChild(ol.lastChild);
  }

  /* =====================================================================
     MARKET + TICK BUS
     ===================================================================== */
  function stepMarket(dt) {
    var sig = S.vol / 100;
    M.price *= Math.exp(-0.5 * sig * sig * dt + sig * Math.sqrt(dt) * gauss());
    M.hist.push({ t: M.clock, p: M.price });
    var keep = Math.max(20, S.T) + 30;
    while (M.hist.length && M.hist[0].t < M.clock - keep) M.hist.shift();
  }

  function buyTick() {
    var f = FEEDS[M.feed];
    if (M.coins < f.cost) {
      if (!M.frozen) { M.frozen = true; log('OUT OF COINS — the flight goes dark, the option does not', 'e-pay'); }
      return;
    }
    M.coins -= f.cost; M.ticks++; M.hbar += f.cost / 1000;
    M.lastTick = M.price;
    M.tickHist.push({ t: M.t, p: M.lastTick });
    if (M.lastTick > M.shownHigh) M.shownHigh = M.lastTick;
  }

  /* =====================================================================
     ROUND
     ===================================================================== */
  function fire() {
    if (M.capUsed + S.stake > CAP_TOTAL) { log('CAP REACHED — Privy policy refuses the stake', 'e-bad'); M.holding = false; return; }
    M.b = barrierFor(M.charge);
    var a = Math.log(1 + M.b);
    M.pEntry = touchProb(a, S.vol / 100, S.T);
    M.mult = multOf(M.pEntry);
    M.stake = S.stake;
    M.entry = M.price;
    M.barrierPx = M.entry * (1 + M.b);
    M.phase = 'flight'; M.t = 0; M.fireClock = M.clock; M.tickAcc = 0;
    M.tickHist.length = 0; M.lastTick = M.entry; M.shownHigh = M.entry; M.highWater = M.entry;
    M.touched = false; M.touchSeen = true; M.frozen = false; M.sellT = 0;
    M.capUsed += M.stake; M.shots++;
    log('FIRED — barrier +' + (M.b * 100).toFixed(2) + '% @ ' + M.barrierPx.toFixed(2)
      + ' · touch odds ' + (M.pEntry * 100).toFixed(1) + '% · pays ' + fmtMult(M.mult)
      + ' on $' + M.stake.toFixed(2));
  }

  function settle(kind, amount) {
    M.phase = 'result';
    M.capUsed = Math.max(0, M.capUsed - amount);
    M.bank += amount - M.stake;
    if (kind === 'touch') {
      M.hits++;
      M.resMsg = 'TOUCHED'; M.resSub = fmtMult(M.mult) + '  ' + usd(amount - M.stake);
      M.resGood = true;
      log('TOUCHED @ ' + M.t.toFixed(1) + 's' + (M.touchSeen ? '' : ' — UNSEEN, your ' + FEEDS[M.feed].label + ' feed missed it')
        + ' · settled +$' + amount.toFixed(2) + ' (' + usd(amount - M.stake) + ')', M.touchSeen ? 'e-good' : 'e-pay');
    } else if (kind === 'sell') {
      M.resMsg = 'SOLD BACK'; M.resSub = usd(amount - M.stake);
      M.resGood = amount >= M.stake;
      log('SOLD BACK @ ' + M.t.toFixed(1) + 's for $' + amount.toFixed(2)
        + ' — odds had moved to ' + (M.pLive * 100).toFixed(1) + '% (' + usd(amount - M.stake) + ')',
        amount >= M.stake ? 'e-good' : 'e-bad');
    } else {
      M.resMsg = 'NEVER TOUCHED'; M.resSub = '−$' + M.stake.toFixed(2);
      M.resGood = false;
      log('EXPIRED — high water was +' + ((M.highWater - M.entry) / M.entry * 100).toFixed(2)
        + '%, needed +' + (M.b * 100).toFixed(2) + '% · −$' + M.stake.toFixed(2), 'e-bad');
    }
    M.flash = 1;
  }

  function nextRound() {
    M.phase = 'charge'; M.holding = false; M.t = 0; M.sellT = 0;
    M.tickHist.length = 0; M.touched = false; M.frozen = false;
  }

  function insertCoin() {
    if (M.capUsed + PACK_USD > CAP_TOTAL) { log('CAP REACHED — no more data this session', 'e-bad'); return; }
    M.coins += PACK; M.capUsed += PACK_USD; M.frozen = false;
    log('INSERT COIN — $' + PACK_USD.toFixed(2) + ' for ' + PACK + ' coins', 'e-pay');
  }

  /* =====================================================================
     STEP
     ===================================================================== */
  function step(dt) {
    M.clock += dt;
    stepMarket(dt);
    M.suppress = Math.max(0, M.suppress - dt);
    M.flash = Math.max(0, M.flash - dt * 2);

    if (M.phase === 'charge') {
      if (M.holding && M.autoMeter && M.suppress <= 0) {
        M.charge += M.meterDir * S.meter * dt;
        if (M.charge >= 1) { M.charge = 1; M.meterDir = -1; }
        if (M.charge <= 0) { M.charge = 0; M.meterDir = 1; }
      }
      var bp = barrierFor(M.charge);
      M.pLive = touchProb(Math.log(1 + bp), S.vol / 100, S.T);
      M.valLive = 0;
    }

    if (M.phase === 'flight') {
      M.t += dt;
      if (!M.frozen) {
        M.tickAcc += dt;
        var period = 1 / FEEDS[M.feed].hz, guard = 0;
        while (M.tickAcc >= period && guard++ < 40) { M.tickAcc -= period; buyTick(); if (M.frozen) break; }
      }
      if (M.price > M.highWater) M.highWater = M.price;

      /* live re-pricing: the option in your hand, decaying */
      var aRem = Math.log(M.barrierPx / M.price);
      var tRem = Math.max(0, S.T - M.t);
      M.pLive = touchProb(aRem, S.vol / 100, tRem);
      M.valLive = M.stake * M.mult * M.pLive * (1 - S.edge / 100);

      /* settlement */
      var hit = M.trueSettle ? (M.price >= M.barrierPx) : (M.lastTick >= M.barrierPx);
      if (hit && !M.touched) {
        M.touched = true; M.touchT = M.t;
        M.touchSeen = M.shownHigh >= M.barrierPx;
        settle('touch', M.stake * M.mult);
        return;
      }
      if (M.t >= S.T) { settle('expire', 0); return; }

      if (M.sellT > 0) {
        M.sellT += dt * 1000;
        if (M.sellT >= SELL_MS) { settle('sell', M.valLive); return; }
      }
    }
  }

  /* =====================================================================
     SCREEN — 400×240, greyscale then Bayer 4×4 to 1-bit
     ===================================================================== */
  function txt(s, x, y, size, align) {
    sctx.font = '400 ' + size + 'px Silkscreen, ui-monospace, monospace';
    sctx.textAlign = align || 'left'; sctx.textBaseline = 'alphabetic';
    sctx.fillText(s, x, y);
  }
  function barBox(x, y, w, h, frac) {
    sctx.fillStyle = '#000'; sctx.fillRect(x, y, w, h);
    sctx.fillStyle = '#fff'; sctx.fillRect(x + 1, y + 1, w - 2, h - 2);
    sctx.fillStyle = '#000'; sctx.fillRect(x + 1, y + 1, Math.round((w - 2) * clamp(frac, 0, 1)), h - 2);
  }

  function drawScreen() {
    sctx.fillStyle = '#fff'; sctx.fillRect(0, 0, W, H);
    sctx.fillStyle = '#000'; sctx.strokeStyle = '#000'; sctx.lineWidth = 1;

    txt('LONGSHOT', 8, 18, 16);

    if (M.phase === 'charge') {
      /* ---------- the power meter, per the mockup ---------- */
      txt('$' + S.stake.toFixed(2), W - 8, 18, 16, 'right');
      var bp = barrierFor(M.charge);
      var mv = multOf(M.pLive);

      var bx = 20, by = 76, bw = 292, bh = 28, seg = 28;
      sctx.fillStyle = '#000'; sctx.fillRect(bx - 2, by - 2, bw + 4, bh + 4);
      sctx.fillStyle = '#fff'; sctx.fillRect(bx, by, bw, bh);
      var filled = Math.round(M.charge * seg);
      for (var i = 0; i < seg; i++) {
        var cw = bw / seg, cxp = bx + i * cw;
        sctx.fillStyle = i < filled ? '#000' : '#c8c8c8';
        sctx.fillRect(cxp + 1, by + 2, cw - 2, bh - 4);
      }
      sctx.fillStyle = '#000';
      txt('+' + (bp * 100).toFixed(2) + '%', bx + bw + 10, by + 20, 16, 'left');

      txt(M.holding ? 'RELEASE TO FIRE' : 'HOLD A TO CHARGE', W / 2, 128, 8, 'center');
      txt('PAYS ' + fmtMult(mv), W / 2, 154, 16, 'center');
      txt('TOUCH ODDS ' + (M.pLive * 100).toFixed(1) + '%', W / 2, 172, 8, 'center');
      barBox(W / 2 - 70, 178, 140, 7, M.pLive);

      /* the range you can charge into, as a scale under the meter */
      txt('+' + (bMin() * 100).toFixed(2) + '%', bx, by + 46, 8, 'left');
      txt('+' + (bMax() * 100).toFixed(2) + '%', bx + bw, by + 46, 8, 'right');

    } else {
      /* ---------- flight ---------- */
      var rem = Math.max(0, S.T - M.t);
      txt(Math.floor(rem / 60) + ':' + String(Math.floor(rem % 60)).padStart(2, '0'), W - 8, 18, 16, 'right');
      sctx.fillRect(0, 24, Math.round(W * clamp(1 - M.t / S.T, 0, 1)), 2);

      var pl = 8, pr = W - 8, pt = 46, pb = 178;
      var rHi = M.b * 1.28, rLo = -M.b * 0.62;
      var Y = function (ret) { return pb - (ret - rLo) / (rHi - rLo) * (pb - pt); };
      var X = function (tt) { return pl + clamp(tt / S.T, 0, 1) * (pr - pl); };
      var R = function (p) { return (p - M.entry) / M.entry; };

      /* entry line */
      sctx.fillStyle = '#9a9a9a';
      for (var e = pl; e < pr; e += 5) sctx.fillRect(e, Math.round(Y(0)), 2, 1);
      sctx.fillStyle = '#000';

      /* barrier — the target */
      var byy = Math.round(Y(M.b));
      for (var q = pl; q < pr; q += 6) sctx.fillRect(q, byy, 4, 2);
      txt('+' + (M.b * 100).toFixed(2) + '%', pr, byy - 6, 8, 'right');
      sctx.beginPath(); sctx.moveTo(pl + 4, byy - 3); sctx.lineTo(pl + 10, byy - 3); sctx.lineTo(pl + 7, byy - 9); sctx.closePath(); sctx.fill();

      /* high water of what you have been SHOWN */
      if (M.tickHist.length) {
        var hwY = Math.round(Y(R(M.shownHigh)));
        sctx.fillStyle = '#6a6a6a';
        for (var hh = pl; hh < pr; hh += 4) sctx.fillRect(hh, hwY, 1, 1);
        sctx.fillStyle = '#000';
        txt('HIGH', pl + 2, hwY - 4, 8, 'left');
      }

      /* the trace you paid for */
      sctx.lineWidth = 2; sctx.strokeStyle = '#000';
      sctx.beginPath();
      for (var k = 0; k < M.tickHist.length; k++) {
        var pt2 = M.tickHist[k], xx = X(pt2.t), yy = clamp(Y(R(pt2.p)), pt - 6, pb + 6);
        if (k === 0) sctx.moveTo(xx, yy); else sctx.lineTo(xx, yy);
      }
      sctx.stroke();
      sctx.lineWidth = 1;
      if (M.tickHist.length) {
        var lastp = M.tickHist[M.tickHist.length - 1];
        var lx = X(lastp.t), ly = clamp(Y(R(lastp.p)), pt - 6, pb + 6);
        sctx.fillRect(lx - 3, ly - 3, 6, 6);
        sctx.fillStyle = '#fff'; sctx.fillRect(lx - 1, ly - 1, 2, 2); sctx.fillStyle = '#000';
      }

      /* remaining distance readout */
      var need = (M.barrierPx - M.price) / M.price * 100;
      txt(need > 0 ? 'NEEDS +' + need.toFixed(2) + '%' : 'IN THE MONEY', pl + 2, pt - 6, 8, 'left');
      txt('ODDS ' + (M.pLive * 100).toFixed(1) + '%', pr, pt - 6, 8, 'right');

      if (M.frozen) {
        var fw = 210, fh = 74, fx2 = (W - fw) / 2, fy = 62;
        sctx.fillStyle = '#000'; sctx.fillRect(fx2 - 3, fy - 3, fw + 6, fh + 6);
        sctx.fillStyle = '#fff'; sctx.fillRect(fx2, fy, fw, fh);
        sctx.fillStyle = '#000';
        txt('INSERT COIN', W / 2, fy + 26, 16, 'center');
        txt('$' + PACK_USD.toFixed(2) + '  =  ' + PACK + ' COINS', W / 2, fy + 42, 8, 'center');
        txt('A TO PAY · B TO RIDE BLIND', W / 2, fy + 60, 8, 'center');
      }
      if (M.sellT > 0) {
        txt('SELL BACK $' + M.valLive.toFixed(2), W / 2, pt - 22, 8, 'center');
        barBox(W / 2 - 50, pt - 18, 100, 7, M.sellT / SELL_MS);
      }
    }

    /* ---------- bottom bar ---------- */
    sctx.fillStyle = '#000';
    sctx.fillRect(0, H - 26, W, 1);
    if (M.phase === 'flight') txt('VAL $' + M.valLive.toFixed(2), 6, H - 15, 8);
    else txt('BANK ' + (M.bank >= 0 ? '+' : '−') + '$' + Math.abs(M.bank).toFixed(2), 6, H - 15, 8);
    txt('FEED ' + FEEDS[M.feed].label, 128, H - 15, 8);
    txt(String(M.coins), W - 6, H - 15, 8, 'right');
    barBox(238, H - 21, 92, 7, M.coins / START_COINS);
    barBox(6, H - 9, 120, 6, M.capUsed / CAP_TOTAL);
    txt('CAP $' + M.capUsed.toFixed(2) + '/$' + CAP_TOTAL.toFixed(2), 132, H - 4, 8);
    txt(M.shots + ' SHOTS · ' + M.hits + ' HIT', W - 6, H - 4, 8, 'right');

    /* ---------- result ---------- */
    if (M.phase === 'result') {
      if (M.resGood && M.flash > 0.55) { sctx.fillStyle = '#000'; sctx.fillRect(0, 0, W, H); }
      var ow = 250, oh = 56, ox = (W - ow) / 2, oy = 84;
      sctx.fillStyle = '#000'; sctx.fillRect(ox - 3, oy - 3, ow + 6, oh + 6);
      sctx.fillStyle = '#fff'; sctx.fillRect(ox, oy, ow, oh);
      sctx.fillStyle = '#000';
      txt(M.resMsg, W / 2, oy + 25, 16, 'center');
      txt(M.resSub, W / 2, oy + 44, 8, 'center');
      if (!M.touchSeen && M.resMsg === 'TOUCHED') txt('YOUR FEED NEVER SHOWED IT', W / 2, oy + 76, 8, 'center');
      else txt(Math.floor(M.clock * 2) % 2 === 0 ? 'A OR SPACE FOR NEXT SHOT' : '', W / 2, oy + 76, 8, 'center');
    }

    dither();
  }

  function dither() {
    var img = sctx.getImageData(0, 0, W, H), d = img.data;
    for (var y = 0; y < H; y++) {
      var row = BAYER[y & 3];
      for (var x = 0; x < W; x++) {
        var i = (y * W + x) << 2;
        var lum = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
        var on = lum <= (row[x & 3] + 0.5) * 15.9375;
        d[i] = on ? LCD_INK[0] : LCD_PAPER[0];
        d[i + 1] = on ? LCD_INK[1] : LCD_PAPER[1];
        d[i + 2] = on ? LCD_INK[2] : LCD_PAPER[2];
        d[i + 3] = 255;
      }
    }
    sctx.putImageData(img, 0, 0);
  }

  /* =====================================================================
     BENCH CHART — true path vs the ticks you bought
     ===================================================================== */
  var hover = null;
  function drawChart() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var cw = chart.clientWidth, ch = chart.clientHeight;
    if (chart.width !== cw * dpr || chart.height !== ch * dpr) { chart.width = cw * dpr; chart.height = ch * dpr; }
    cctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cctx.clearRect(0, 0, cw, ch);

    var padL = 8, padR = 62, padT = 12, padB = 18;
    var pw = cw - padL - padR, ph = ch - padT - padB;
    if (pw <= 10 || M.hist.length < 2) return;

    var flight = M.phase !== 'charge';
    var winA = flight ? M.fireClock : M.clock - 20;
    var winB = flight ? M.fireClock + S.T : M.clock;
    var ref = flight ? M.entry : M.price;
    var barPx = flight ? M.barrierPx : M.price * (1 + barrierFor(M.charge));

    var lo = Infinity, hi = -Infinity, k, h;
    for (k = 0; k < M.hist.length; k++) {
      h = M.hist[k]; if (h.t < winA || h.t > winB) continue;
      if (h.p < lo) lo = h.p; if (h.p > hi) hi = h.p;
    }
    if (!isFinite(lo)) { lo = ref; hi = ref; }
    lo = Math.min(lo, ref, barPx * 0.9995); hi = Math.max(hi, ref, barPx);
    var pad = (hi - lo) * 0.12 || ref * 0.0004; lo -= pad; hi += pad;

    var X = function (t) { return padL + clamp((t - winA) / (winB - winA), 0, 1) * pw; };
    var Y = function (p) { return padT + (hi - p) / (hi - lo) * ph; };

    cctx.font = '500 10px "IBM Plex Mono", monospace';
    cctx.textBaseline = 'middle'; cctx.textAlign = 'left';
    for (k = 0; k <= 3; k++) {
      var gv = lo + (hi - lo) * k / 3, gy = Y(gv);
      cctx.strokeStyle = TOK.line; cctx.lineWidth = 1;
      cctx.beginPath(); cctx.moveTo(padL, Math.round(gy) + 0.5); cctx.lineTo(padL + pw, Math.round(gy) + 0.5); cctx.stroke();
      cctx.fillStyle = TOK['ink-3']; cctx.fillText(gv.toFixed(2), padL + pw + 7, gy);
    }

    /* entry */
    cctx.setLineDash([3, 3]); cctx.strokeStyle = TOK['ink-3']; cctx.lineWidth = 1;
    cctx.beginPath(); cctx.moveTo(padL, Math.round(Y(ref)) + 0.5); cctx.lineTo(padL + pw, Math.round(Y(ref)) + 0.5); cctx.stroke();
    cctx.setLineDash([]);
    cctx.fillStyle = TOK['ink-3']; cctx.fillText(flight ? 'ENTRY' : 'SPOT', padL + 3, Y(ref) - 8);

    /* barrier */
    var byv = Y(barPx);
    if (byv > padT - 40) {
      cctx.strokeStyle = TOK.crit; cctx.lineWidth = 1.5;
      cctx.beginPath(); cctx.moveTo(padL, Math.round(byv) + 0.5); cctx.lineTo(padL + pw, Math.round(byv) + 0.5); cctx.stroke();
      cctx.fillStyle = TOK.crit;
      cctx.fillText((flight ? 'BARRIER  ' : 'BARRIER IF FIRED NOW  ') + '+' + ((barPx / ref - 1) * 100).toFixed(2) + '%', padL + 3, byv + 9);
    }

    /* true path */
    cctx.strokeStyle = TOK['ser-true']; cctx.lineWidth = 2; cctx.lineJoin = 'round'; cctx.lineCap = 'round';
    cctx.beginPath();
    var started = false;
    for (k = 0; k < M.hist.length; k++) {
      h = M.hist[k]; if (h.t < winA || h.t > winB) continue;
      if (!started) { cctx.moveTo(X(h.t), Y(h.p)); started = true; } else cctx.lineTo(X(h.t), Y(h.p));
    }
    cctx.stroke();

    /* the staircase you paid for */
    if (flight && M.tickHist.length) {
      cctx.strokeStyle = TOK['ser-paid']; cctx.lineWidth = 2;
      cctx.beginPath();
      for (k = 0; k < M.tickHist.length; k++) {
        var q = M.tickHist[k], qt = M.fireClock + q.t;
        if (k === 0) cctx.moveTo(X(qt), Y(q.p));
        else { cctx.lineTo(X(qt), Y(M.tickHist[k - 1].p)); cctx.lineTo(X(qt), Y(q.p)); }
      }
      cctx.stroke();
      var lastq = M.tickHist[M.tickHist.length - 1];
      var lqx = X(M.fireClock + lastq.t);
      cctx.fillStyle = TOK.sunk; cctx.beginPath(); cctx.arc(lqx, Y(lastq.p), 5.5, 0, 6.2832); cctx.fill();
      cctx.fillStyle = TOK['ser-paid']; cctx.beginPath(); cctx.arc(lqx, Y(lastq.p), 4, 0, 6.2832); cctx.fill();
    }

    /* endpoint on the true path */
    var lastTrue = M.hist[M.hist.length - 1];
    for (k = M.hist.length - 1; k >= 0; k--) { if (M.hist[k].t <= winB) { lastTrue = M.hist[k]; break; } }
    cctx.fillStyle = TOK.sunk; cctx.beginPath(); cctx.arc(X(lastTrue.t), Y(lastTrue.p), 5.5, 0, 6.2832); cctx.fill();
    cctx.fillStyle = TOK['ser-true']; cctx.beginPath(); cctx.arc(X(lastTrue.t), Y(lastTrue.p), 4, 0, 6.2832); cctx.fill();

    /* the touch */
    if (M.touched) {
      var tx = X(M.fireClock + M.touchT), ty = Y(M.barrierPx);
      cctx.strokeStyle = M.touchSeen ? TOK.good : TOK.crit; cctx.lineWidth = 2;
      cctx.beginPath(); cctx.arc(tx, ty, 7, 0, 6.2832); cctx.stroke();
      cctx.fillStyle = M.touchSeen ? TOK.good : TOK.crit; cctx.textAlign = 'center';
      cctx.fillText(M.touchSeen ? 'TOUCH' : 'UNSEEN TOUCH', clamp(tx, 44, padL + pw - 44), ty - 14);
      cctx.textAlign = 'left';
    }

    /* hover */
    if (hover && hover.x > padL && hover.x < padL + pw) {
      var ht = winA + (hover.x - padL) / pw * (winB - winA);
      var near = null, bd = 1e9;
      for (k = 0; k < M.hist.length; k++) { var dd = Math.abs(M.hist[k].t - ht); if (dd < bd) { bd = dd; near = M.hist[k]; } }
      if (near && bd < (winB - winA) / 8) {
        cctx.strokeStyle = TOK['ink-3']; cctx.lineWidth = 1; cctx.setLineDash([2, 3]);
        cctx.beginPath(); cctx.moveTo(Math.round(X(near.t)) + 0.5, padT); cctx.lineTo(Math.round(X(near.t)) + 0.5, padT + ph); cctx.stroke();
        cctx.setLineDash([]);
        var lines = ['true  ' + near.p.toFixed(2), 'to barrier  ' + ((barPx - near.p) / near.p * 100).toFixed(3) + '%'];
        var bwd = 128, bhd = lines.length * 14 + 8;
        var bxd = Math.min(X(near.t) + 8, padL + pw - bwd), byd = padT + 4;
        cctx.fillStyle = TOK.surface; cctx.strokeStyle = TOK.line;
        cctx.fillRect(bxd, byd, bwd, bhd); cctx.strokeRect(bxd + 0.5, byd + 0.5, bwd, bhd);
        lines.forEach(function (ln, ix) {
          cctx.fillStyle = ix === 0 ? TOK['ser-true'] : TOK['ink-2'];
          cctx.fillText(ln, bxd + 8, byd + 13 + ix * 14);
        });
      }
    }
  }

  /* =====================================================================
     PAYOUT LADDER — multiplier against barrier, log y
     ===================================================================== */
  function drawLadder() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var cw = ladder.clientWidth, chh = ladder.clientHeight;
    if (ladder.width !== cw * dpr || ladder.height !== chh * dpr) { ladder.width = cw * dpr; ladder.height = chh * dpr; }
    lctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lctx.clearRect(0, 0, cw, chh);

    var padL = 34, padR = 14, padT = 12, padB = 24;
    var pw = cw - padL - padR, ph = chh - padT - padB;
    if (pw <= 20) return;

    var b0 = bMin(), b1 = bMax();
    var mMax = multOf(touchProb(Math.log(1 + b1), S.vol / 100, S.T));
    var yTop = Math.log10(Math.max(mMax, 10)), yBot = 0;
    var X = function (b) { return padL + (b - b0) / (b1 - b0) * pw; };
    var Y = function (m) { return padT + (1 - (Math.log10(Math.max(m, 1)) - yBot) / (yTop - yBot)) * ph; };

    lctx.font = '500 10px "IBM Plex Mono", monospace';
    lctx.textBaseline = 'middle';

    /* log gridlines at 1, 10, 100, 1000 */
    for (var e = 0; e <= Math.ceil(yTop); e++) {
      var m = Math.pow(10, e); if (m > Math.pow(10, yTop) * 1.02) break;
      var gy = Y(m);
      lctx.strokeStyle = TOK.line; lctx.lineWidth = 1;
      lctx.beginPath(); lctx.moveTo(padL, Math.round(gy) + 0.5); lctx.lineTo(padL + pw, Math.round(gy) + 0.5); lctx.stroke();
      lctx.fillStyle = TOK['ink-3']; lctx.textAlign = 'right';
      lctx.fillText(m + '×', padL - 7, gy);
    }

    /* the region past 2σ — where the doc's "you'll never touch it" lives */
    var b2 = Math.min(b1, 2 * sigT());
    if (b2 < b1) {
      lctx.fillStyle = TOK.crit; lctx.globalAlpha = 0.08;
      lctx.fillRect(X(b2), padT, X(b1) - X(b2), ph);
      lctx.globalAlpha = 1;
      lctx.strokeStyle = TOK.crit; lctx.lineWidth = 1; lctx.setLineDash([2, 3]);
      lctx.beginPath(); lctx.moveTo(Math.round(X(b2)) + 0.5, padT); lctx.lineTo(Math.round(X(b2)) + 0.5, padT + ph); lctx.stroke();
      lctx.setLineDash([]);
      lctx.fillStyle = TOK.crit; lctx.textAlign = 'left';
      lctx.fillText('2σ — under 5% of shots land past here', X(b2) + 6, padT + 10);
    }

    /* the curve */
    lctx.strokeStyle = TOK['ser-true']; lctx.lineWidth = 2; lctx.lineJoin = 'round';
    lctx.beginPath();
    for (var i = 0; i <= 90; i++) {
      var b = b0 + (b1 - b0) * i / 90;
      var mm = multOf(touchProb(Math.log(1 + b), S.vol / 100, S.T));
      if (i === 0) lctx.moveTo(X(b), Y(mm)); else lctx.lineTo(X(b), Y(mm));
    }
    lctx.stroke();

    /* where you are right now */
    var bc = M.phase === 'charge' ? barrierFor(M.charge) : M.b;
    var mc = multOf(touchProb(Math.log(1 + bc), S.vol / 100, S.T));
    if (bc >= b0 && bc <= b1) {
      var mx = X(bc), my = Y(mc);
      lctx.strokeStyle = TOK.accent; lctx.lineWidth = 1; lctx.setLineDash([2, 3]);
      lctx.beginPath(); lctx.moveTo(Math.round(mx) + 0.5, my); lctx.lineTo(Math.round(mx) + 0.5, padT + ph); lctx.stroke();
      lctx.setLineDash([]);
      lctx.fillStyle = TOK.sunk; lctx.beginPath(); lctx.arc(mx, my, 6, 0, 6.2832); lctx.fill();
      lctx.fillStyle = TOK.accent; lctx.beginPath(); lctx.arc(mx, my, 4.2, 0, 6.2832); lctx.fill();
      lctx.fillStyle = TOK.ink; lctx.textAlign = mx > padL + pw * 0.62 ? 'right' : 'left';
      lctx.fillText('+' + (bc * 100).toFixed(2) + '%  ' + fmtMult(mc), mx + (mx > padL + pw * 0.62 ? -11 : 11), my - 1);
    }

    /* x axis */
    lctx.fillStyle = TOK['ink-3']; lctx.textAlign = 'left';
    lctx.fillText('+' + (b0 * 100).toFixed(2) + '%', padL, padT + ph + 12);
    lctx.textAlign = 'right';
    lctx.fillText('+' + (b1 * 100).toFixed(2) + '%', padL + pw, padT + ph + 12);
  }

  /* =====================================================================
     PANELS
     ===================================================================== */
  var CALC = [
    { k: 'b',    n: 'Barrier b',        f: 'crank position' },
    { k: 'a',    n: 'Log barrier a',    f: 'ln(1 + b)' },
    { k: 'sig',  n: 'σ over the window', f: 'σ · √T' },
    { k: 'z',    n: 'Standardised',     f: 'a / (σ√T)' },
    { k: 'p',    n: 'P(ever touch)',    f: '2 · Φ(−z)' },
    { k: 'fair', n: 'Fair multiplier',  f: '1 / p' },
    { k: 'off',  n: 'Offered',          f: 'fair × (1 − edge)', cls: 'r-lag' },
    { k: 'pay',  n: 'Pays if it lands', f: 'stake × offered', cls: 'r-pnl' }
  ];
  var cells = {};
  function buildCalc() {
    var tb = $('calcBody');
    CALC.forEach(function (r) {
      var tr = document.createElement('tr');
      if (r.cls) tr.className = r.cls;
      tr.innerHTML = '<td class="c-name">' + r.n + '</td><td class="c-form">' + r.f + '</td><td class="c-sub">—</td><td class="c-val">—</td>';
      tb.appendChild(tr);
      cells[r.k] = { tr: tr, sub: tr.children[2], val: tr.children[3] };
    });
  }
  function buildKnobs() {
    var host = $('knobs');
    KNOBS.forEach(function (kn) {
      var w = document.createElement('div'); w.className = 'knob';
      w.innerHTML = '<div class="knob-top"><label for="kn-' + kn.k + '">' + kn.lbl + '</label><b id="kv-' + kn.k + '"></b></div>'
        + '<input type="range" id="kn-' + kn.k + '" min="' + kn.min + '" max="' + kn.max + '" step="' + kn.step + '">'
        + '<span class="knob-n">' + kn.note + '</span>';
      host.appendChild(w);
      var inp = w.querySelector('input');
      inp.value = S[kn.k];
      $('kv-' + kn.k).textContent = kn.fmt(S[kn.k]);
      inp.addEventListener('input', function () { S[kn.k] = parseFloat(inp.value); $('kv-' + kn.k).textContent = kn.fmt(S[kn.k]); });
    });
  }
  function syncKnobs() {
    KNOBS.forEach(function (kn) {
      var inp = $('kn-' + kn.k); if (!inp) return;
      inp.value = S[kn.k]; $('kv-' + kn.k).textContent = kn.fmt(S[kn.k]);
    });
  }

  function updatePanels() {
    var charging = M.phase === 'charge';
    var b = charging ? barrierFor(M.charge) : M.b;
    var a = Math.log(1 + b);
    var sT = sigT();
    var z = a / sT;
    var p = charging ? M.pLive : M.pEntry;
    var fair = 1 / p;
    var off = charging ? multOf(p) : M.mult;
    var spot = charging ? M.price : M.entry;

    cells.b.sub.textContent = 'charge ' + (M.charge * 100).toFixed(0) + '% of ' + (bMin() * 100).toFixed(2) + '…' + (bMax() * 100).toFixed(2) + '%';
    cells.b.val.textContent = '+' + (b * 100).toFixed(3) + '%';
    cells.a.sub.textContent = 'ln(1 + ' + b.toFixed(5) + ')';
    cells.a.val.textContent = a.toFixed(5);
    cells.sig.sub.textContent = (S.vol / 100).toFixed(5) + ' × √' + S.T.toFixed(0);
    cells.sig.val.textContent = (sT * 100).toFixed(3) + '%';
    cells.z.sub.textContent = a.toFixed(5) + ' / ' + sT.toFixed(5);
    cells.z.val.textContent = z.toFixed(4);
    cells.p.sub.textContent = '2 × Φ(−' + z.toFixed(4) + ') = 2 × ' + ncdf(-z).toFixed(5);
    cells.p.val.textContent = (p * 100).toFixed(2) + '%';
    cells.fair.sub.textContent = '1 / ' + p.toFixed(5);
    cells.fair.val.textContent = fmtMult(fair);
    cells.off.sub.textContent = fmtMult(fair) + ' × (1 − ' + (S.edge / 100).toFixed(3) + ')';
    cells.off.val.textContent = fmtMult(off);
    cells.pay.sub.textContent = '$' + (charging ? S.stake : M.stake).toFixed(2) + ' × ' + fmtMult(off);
    cells.pay.val.textContent = '$' + ((charging ? S.stake : M.stake) * off).toFixed(2);
    cells.pay.val.className = 'c-val up';

    $('sBar').textContent = '+' + (b * 100).toFixed(2) + '%';
    $('sBarPx').textContent = charging ? 'spot ' + spot.toFixed(2) + ' → ' + (spot * (1 + b)).toFixed(2)
      : 'entry ' + M.entry.toFixed(2) + ' → ' + M.barrierPx.toFixed(2);
    $('sProb').textContent = (M.pLive * 100).toFixed(1) + '%';
    $('sMult').textContent = fmtMult(off);
    $('sMultN').textContent = charging ? 'locked when you release A' : 'locked at fire · odds now ' + (M.pLive * 100).toFixed(1) + '%';
    var sv = $('sVal');
    if (M.phase === 'flight') {
      sv.textContent = '$' + M.valLive.toFixed(2);
      sv.className = 'shot-v ' + (M.valLive >= M.stake ? 'up' : 'down');
    } else { sv.textContent = '—'; sv.className = 'shot-v'; }

    $('shotState').textContent = M.phase === 'charge' ? (M.holding ? 'charging — release to fire' : 'idle')
      : M.phase === 'flight' ? (M.frozen ? 'in flight, screen frozen' : 'in flight, ' + (S.T - M.t).toFixed(1) + 's left')
        : 'settled';
    $('phName').textContent = M.phase.toUpperCase();
    $('ph0').classList.toggle('is-on', M.phase !== 'result');
    $('phHint').textContent = M.phase === 'charge' ? 'hold A, crank to the barrier you want, release to fire'
      : M.phase === 'flight' ? 'hold A to sell the option back at its live value' : 'A or space for the next shot';

    var doc68 = multOf(touchProb(Math.log(1.014), S.vol / 100, 60));
    $('ladderNote').textContent = 'GAMES.md’s mockup prices +1.40% at 6.8×. At σ ' + S.vol.toFixed(3)
      + ' %/s over 60s the same barrier pays ' + fmtMult(doc68) + ' — which is how you can tell the doc’s numbers already assume roughly real ETH volatility.';

    $('coinVal').textContent = M.coins;
    var cb = $('coinBar');
    cb.style.width = clamp(M.coins / START_COINS, 0, 1) * 100 + '%';
    cb.classList.toggle('is-low', M.coins < START_COINS * 0.18);
    var burn = FEEDS[M.feed].hz * FEEDS[M.feed].cost;
    $('coinBurn').textContent = burn + ' coins/s — ' + (M.coins / burn).toFixed(0) + 's of sight left';
    $('capVal').textContent = '$' + M.capUsed.toFixed(2) + ' / $' + CAP_TOTAL.toFixed(2);
    $('capBar').style.width = clamp(M.capUsed / CAP_TOTAL, 0, 1) * 100 + '%';
    $('shotCount').textContent = M.shots;
    $('hitCount').textContent = M.hits;
    $('tickCount').textContent = M.ticks;
    $('hbarSpent').textContent = M.hbar.toFixed(4);
    $('lgRate').textContent = FEEDS[M.feed].label;

    var lr = $('lagRead');
    if (M.phase === 'flight') {
      lr.textContent = 'shown high +' + ((M.shownHigh - M.entry) / M.entry * 100).toFixed(2)
        + '%  ·  true high +' + ((M.highWater - M.entry) / M.entry * 100).toFixed(2) + '%';
      lr.classList.toggle('is-bad', M.highWater > M.shownHigh * 1.0004);
    } else { lr.textContent = 'barrier moves with the crank'; lr.classList.remove('is-bad'); }
    $('cfL').textContent = M.phase === 'charge' ? '−20s' : 'fire';
    $('cfR').textContent = M.phase === 'charge' ? 'now' : '+' + S.T.toFixed(0) + 's';

    $('crankVal').textContent = '+' + (b * 100).toFixed(2) + '%';
    $('crankArm').style.transform = 'translate(-50%,0) rotate(' + (M.charge * 320) + 'deg)';
    $('padHold').style.height = (M.phase === 'charge' && M.holding ? M.charge * 100 : M.sellT > 0 ? M.sellT / SELL_MS * 100 : 0) + '%';
  }

  /* =====================================================================
     LOOP
     ===================================================================== */
  var prev = performance.now();
  function frame(now) {
    var dt = Math.min((now - prev) / 1000, 0.05); prev = now;
    step(dt);
    drawScreen(); drawChart(); drawLadder(); updatePanels();
    requestAnimationFrame(frame);
  }

  /* =====================================================================
     INPUT
     ===================================================================== */
  function crank(delta) {
    if (M.phase !== 'charge') return;
    M.charge = clamp(M.charge + delta, 0, 1);
    M.suppress = 0.6;
  }
  function pressA() {
    if (M.phase === 'charge') { M.holding = true; M.meterDir = 1; if (M.autoMeter) M.charge = 0; }
    else if (M.phase === 'flight') { if (M.frozen) insertCoin(); else M.sellT = 0.0001; }
    else nextRound();
  }
  function releaseA() {
    if (M.phase === 'charge' && M.holding) { M.holding = false; fire(); }
    else if (M.phase === 'flight') M.sellT = 0;
  }
  function pressB() {
    if (M.phase === 'charge' && M.holding) { M.holding = false; log('CHARGE CANCELLED'); }
    else if (M.phase === 'flight' && M.frozen) { M.frozen = false; M.tickAcc = 0; log('RIDING BLIND — no more ticks, settlement still reads the true path', 'e-pay'); }
    else if (M.phase === 'result') nextRound();
  }

  window.addEventListener('keydown', function (e) {
    var k = e.key.toLowerCase();
    if (k === 'z') { e.preventDefault(); if (!e.repeat) pressA(); }
    else if (k === 'x') { e.preventDefault(); if (!e.repeat) pressB(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); crank(0.03); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); crank(-0.03); }
    else if (e.key === ' ') { e.preventDefault(); if (M.phase === 'result') nextRound(); }
  });
  window.addEventListener('keyup', function (e) {
    var k = e.key.toLowerCase();
    if (k === 'z') releaseA();
  });

  var btnA = $('btnA'), btnB = $('btnB');
  btnA.addEventListener('pointerdown', function (e) { e.preventDefault(); btnA.setPointerCapture(e.pointerId); pressA(); });
  btnA.addEventListener('pointerup', releaseA);
  btnA.addEventListener('pointercancel', releaseA);
  btnB.addEventListener('pointerdown', function (e) { e.preventDefault(); pressB(); });

  var dial = $('dial'), dragging = false, lastY = 0;
  function wheel(e) { e.preventDefault(); crank(e.deltaY < 0 ? 0.03 : -0.03); }
  dial.addEventListener('wheel', wheel, { passive: false });
  screen.addEventListener('wheel', wheel, { passive: false });
  dial.addEventListener('pointerdown', function (e) { dragging = true; lastY = e.clientY; dial.setPointerCapture(e.pointerId); });
  dial.addEventListener('pointermove', function (e) {
    if (!dragging) return;
    if (Math.abs(e.clientY - lastY) > 5) { crank(e.clientY < lastY ? 0.03 : -0.03); lastY = e.clientY; }
  });
  dial.addEventListener('pointerup', function () { dragging = false; });

  chart.addEventListener('pointermove', function (e) { var r = chart.getBoundingClientRect(); hover = { x: e.clientX - r.left }; });
  chart.addEventListener('pointerleave', function () { hover = null; });

  document.querySelectorAll('.feed').forEach(function (bn) {
    bn.addEventListener('click', function () {
      var f = parseInt(bn.dataset.feed, 10);
      if (f === M.feed) return;
      M.feed = f;
      document.querySelectorAll('.feed').forEach(function (o) { o.classList.toggle('is-on', o === bn); });
      log('FEED → ' + FEEDS[f].name + ' ' + FEEDS[f].label, 'e-pay');
    });
  });
  document.querySelectorAll('.chip').forEach(function (c) {
    c.addEventListener('click', function () {
      var pr = PRESETS[c.dataset.preset];
      Object.keys(pr).forEach(function (k) { S[k] = pr[k]; });
      document.querySelectorAll('.chip').forEach(function (o) { o.classList.toggle('is-on', o === c); });
      syncKnobs();
      log('PRESET → ' + c.textContent + ' (σ ' + S.vol.toFixed(3) + ' %/s, T ' + S.T + 's, edge ' + S.edge + '%)');
    });
  });
  $('autoMeter').addEventListener('change', function (e) { M.autoMeter = e.target.checked; });
  $('trueSettle').addEventListener('change', function (e) {
    M.trueSettle = e.target.checked;
    log(M.trueSettle ? 'SETTLEMENT → true path' : 'SETTLEMENT → your paid ticks only');
  });
  $('themeBtn').addEventListener('click', function () {
    var r = document.documentElement, cur = r.getAttribute('data-theme');
    var sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    r.setAttribute('data-theme', cur ? (cur === 'dark' ? 'light' : 'dark') : (sysDark ? 'light' : 'dark'));
    readTokens();
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', readTokens);

  /* ---------------- boot ---------------- */
  buildCalc(); buildKnobs(); readTokens();
  log('Bench ready · σ 0.125 %/s, T 60s, zero edge — the settings that reproduce the 6.8× in GAMES.md');
  log('Hold A. The meter sweeps. Release near the middle and watch the barrier line get chased.');
  var boot = function () { prev = performance.now(); requestAnimationFrame(frame); };
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(boot).catch(boot); else boot();
})();
