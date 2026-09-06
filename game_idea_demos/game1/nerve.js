/* =====================================================================
   NERVE — walking bench prototype
   Left: the 400x240 1-bit device.  Right: every number behind it.

   The whole game is one variable:
       x = SENS * (return / d)  +  wobble
   where d = 1 / leverage is the real liquidation distance.
   x <= -1 is the cliff.  x >= +1 is a safe rail (you cannot die of profit).

   The staleness mechanic: x is computed twice per frame. The screen draws
   the version built from the last tick you PAID FOR. Liquidation checks
   the version built from the real price. On a 1 Hz feed those are a full
   second apart, and the gap between them is what kills you.
   ===================================================================== */
(function () {
  'use strict';

  /* ---------------- constants ---------------- */
  var W = 400, H = 240;
  var LCD_INK = [35, 34, 30], LCD_PAPER = [183, 180, 166];
  var BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]];
  var FEEDS = [
    { name: 'BASIC',   hz: 1,  cost: 1, label: '1 Hz'  },
    { name: 'PREMIUM', hz: 10, cost: 4, label: '10 Hz' }
  ];
  var START_COINS = 1200, PACK = 600, PACK_USD = 0.30, CAP_TOTAL = 10.00;
  var WINDOW = 20;           // seconds of chart history
  var BEAM_Y = 150;          // beam baseline on the 400x240 screen

  /* ---------------- tunables ---------------- */
  var S = {
    sens: 25, vol: 0.28, kick: 420, correct: 1.5, decay: 0.55,
    collateral: 2.00, round: 60, holdMs: 1500
  };
  var PRESETS = {
    real:  { vol: 0.10, sens: 25, kick: 400 },
    tense: { vol: 0.28, sens: 25, kick: 420 },
    demo:  { vol: 0.75, sens: 30, kick: 500 }
  };
  var KNOBS = [
    { k: 'sens',       lbl: 'SENS — beam magnification', min: 5,   max: 80,   step: 1,   fmt: function (v) { return v.toFixed(0) + '×'; },        note: 'Zoom on the real liquidation distance' },
    { k: 'vol',        lbl: 'Volatility σ',              min: 0.02, max: 1.20, step: 0.01, fmt: function (v) { return v.toFixed(2) + ' %/s'; },        note: 'Real ETH sits near 0.10 %/s' },
    { k: 'kick',       lbl: 'Wobble gain',                    min: 0,   max: 900,  step: 10,  fmt: function (v) { return v.toFixed(0); },                  note: 'How hard each tick shoves you' },
    { k: 'correct',    lbl: 'Counterbalance authority',       min: 0.4, max: 4,    step: 0.1, fmt: function (v) { return v.toFixed(1) + ' /s'; },          note: 'What A and B are worth' },
    { k: 'decay',      lbl: 'Self-settle',                    min: 0,   max: 2,    step: 0.05, fmt: function (v) { return v.toFixed(2) + ' /s'; },         note: 'Wobble bleeding off on its own' },
    { k: 'collateral', lbl: 'Collateral',                     min: 0.5, max: 5,    step: 0.5, fmt: function (v) { return '$' + v.toFixed(2); },            note: 'Drawn from the cap at entry' },
    { k: 'round',      lbl: 'Round length',                   min: 15,  max: 120,  step: 5,   fmt: function (v) { return v.toFixed(0) + ' s'; },           note: 'Auto-flatten at the buzzer' },
    { k: 'holdMs',     lbl: 'Hold-A to cash out',             min: 200, max: 3000, step: 100, fmt: function (v) { return (v / 1000).toFixed(1) + ' s'; },  note: 'GAMES.md §5 specifies 3.0 s' }
  ];

  /* ---------------- state ---------------- */
  var M = {
    state: 'ready',        // ready | walk | frozen | fall | over
    price: 2430.00, entry: 0, lastTick: 0, prevTick: 0,
    lev: 1.0, wob: 0, xShown: 0, xTrue: 0,
    coins: START_COINS, capUsed: 0, ticks: 0, hbar: 0, feed: 1,
    round: 1, t: 0, tickAcc: 0, dist: 0,
    hist: [], tickHist: [],
    fallV: 0, fallY: 0, fallRot: 0, overMsg: '', overSub: '', overGood: false,
    shake: 0, holdT: 0, keyA: false, keyB: false, liqFrozen: true,
    lastPnl: 0, phase: 0, flash: 0
  };

  /* ---------------- dom ---------------- */
  var $ = function (id) { return document.getElementById(id); };
  var screen = $('screen'), sctx = screen.getContext('2d', { willReadFrequently: true });
  var chart = $('chart'), cctx = chart.getContext('2d');
  var TOK = {};

  function readTokens() {
    var cs = getComputedStyle(document.documentElement);
    ['ser-true', 'ser-paid', 'crit', 'good', 'accent', 'ink', 'ink-2', 'ink-3', 'line', 'sunk', 'surface']
      .forEach(function (n) { TOK[n] = cs.getPropertyValue('--' + n).trim(); });
  }

  /* ---------------- helpers ---------------- */
  var _sp = null;
  function gauss() {
    if (_sp !== null) { var v = _sp; _sp = null; return v; }
    var u = 0, w = 0;
    do { u = Math.random() * 2 - 1; w = Math.random() * 2 - 1; var s2 = u * u + w * w; if (s2 > 0 && s2 < 1) { var m = Math.sqrt(-2 * Math.log(s2) / s2); _sp = w * m; return u * m; } } while (true);
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function usd(v) { return (v < 0 ? '-$' : '+$') + Math.abs(v).toFixed(4); }
  function pct(v, n) { return (v * 100).toFixed(n === undefined ? 3 : n) + '%'; }
  function spct(v, n) { return (v >= 0 ? '+' : '') + (v * 100).toFixed(n === undefined ? 4 : n) + '%'; }
  function fx(v, n) { return (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(n); }

  function log(msg, cls) {
    var ol = $('log'), li = document.createElement('li');
    if (cls) li.className = cls;
    li.innerHTML = '<span class="lt">' + M.t.toFixed(1).padStart(5, ' ').replace(/ /g, ' ') + 's</span><span>' + msg + '</span>';
    ol.insertBefore(li, ol.firstChild);
    while (ol.children.length > 40) ol.removeChild(ol.lastChild);
  }

  /* =====================================================================
     MARKET + TICK BUS
     ===================================================================== */
  function stepMarket(dt) {
    var sig = S.vol / 100;
    M.price *= Math.exp(-0.5 * sig * sig * dt + sig * Math.sqrt(dt) * gauss());
    M.hist.push({ t: M.t, p: M.price });
    while (M.hist.length && M.hist[0].t < M.t - WINDOW) M.hist.shift();
  }

  function buyTick() {
    var f = FEEDS[M.feed];
    if (M.coins < f.cost) { freeze(); return; }
    M.coins -= f.cost;
    M.ticks++;
    M.hbar += f.cost / 1000;
    M.prevTick = M.lastTick;
    M.lastTick = M.price;
    if (M.prevTick > 0) {
      M.wob += S.kick * (M.lastTick - M.prevTick) / M.prevTick;
      M.shake = Math.min(1, M.shake + Math.abs((M.lastTick - M.prevTick) / M.prevTick) * 900);
    }
    M.tickHist.push({ t: M.t, p: M.lastTick });
    while (M.tickHist.length && M.tickHist[0].t < M.t - WINDOW) M.tickHist.shift();
  }

  function freeze() {
    if (M.state !== 'walk') return;
    M.state = 'frozen';
    log('OUT OF COINS — screen frozen on the last tick you paid for', 'e-pay');
  }

  /* =====================================================================
     ROUND LIFECYCLE
     ===================================================================== */
  function startRound() {
    if (M.capUsed + S.collateral > CAP_TOTAL) { log('CAP REACHED — Privy policy refuses the stake', 'e-bad'); return; }
    M.state = 'walk';
    M.entry = M.price; M.lastTick = M.price; M.prevTick = M.price;
    M.wob = 0; M.xShown = 0; M.xTrue = 0; M.t = 0; M.tickAcc = 0; M.dist = 0;
    M.fallY = 0; M.fallV = 0; M.fallRot = 0; M.shake = 0; M.holdT = 0;
    M.tickHist.length = 0; M.hist.length = 0;
    M.capUsed += S.collateral;
    log('ENTRY @ ' + M.entry.toFixed(2) + ' · ' + M.lev.toFixed(1) + '× on $' + S.collateral.toFixed(2)
      + ' · notional $' + (S.collateral * M.lev).toFixed(2));
  }

  function pnlNow(p) { if (!M.entry || !p) return 0; return S.collateral * M.lev * ((p - M.entry) / M.entry); }

  function endRound(kind) {
    var p = pnlNow(M.state === 'frozen' ? M.lastTick : M.price);
    M.lastPnl = p;
    if (kind === 'liq') {
      M.state = 'fall'; M.fallV = 0; M.fallRot = 0;
      M.overMsg = 'LIQUIDATED'; M.overSub = '−$' + S.collateral.toFixed(2) + ' COLLATERAL';
      M.overGood = false;
      log('LIQUIDATED @ ' + M.price.toFixed(2) + ' — collateral gone (−$' + S.collateral.toFixed(2) + ')', 'e-bad');
    } else {
      M.state = 'over';
      M.capUsed = Math.max(0, M.capUsed - S.collateral - Math.min(0, p));
      M.overMsg = kind === 'buzzer' ? 'ROUND OVER' : 'CASHED OUT';
      M.overSub = usd(p) + '  ·  ' + M.dist.toFixed(0) + 'M WALKED';
      M.overGood = p >= 0;
      log((kind === 'buzzer' ? 'BUZZER' : 'CASH OUT') + ' @ ' + M.price.toFixed(2) + ' — settled ' + usd(p)
        + ' on ' + M.t.toFixed(1) + 's held', p >= 0 ? 'e-good' : 'e-bad');
    }
    M.flash = 1;
  }

  function nextRound() {
    M.round++; M.state = 'ready'; M.t = 0; M.wob = 0; M.xShown = 0; M.xTrue = 0;
    M.hist.length = 0; M.tickHist.length = 0;
    $('roundNo').textContent = M.round;
  }

  function insertCoin() {
    if (M.capUsed + PACK_USD > CAP_TOTAL) { log('CAP REACHED — cannot buy more data. Flattening.', 'e-bad'); endRound('cash'); return; }
    M.coins += PACK; M.capUsed += PACK_USD; M.state = 'walk';
    log('INSERT COIN — paid $' + PACK_USD.toFixed(2) + ' for ' + PACK + ' coins (' + (PACK / 1000).toFixed(3) + ' HBAR)', 'e-pay');
  }

  /* =====================================================================
     PHYSICS
     ===================================================================== */
  function stepPhysics(dt) {
    if (M.state === 'walk') {
      if (M.keyA) M.wob -= S.correct * dt;
      if (M.keyB) M.wob += S.correct * dt;
      M.dist += 6 * dt;
      M.phase += dt * 7;
    }
    M.wob *= Math.exp(-S.decay * dt);
    M.shake *= Math.exp(-3.2 * dt);

    var d = 1 / M.lev;
    var retShown = (M.lastTick - M.entry) / M.entry;
    var retTrue = (M.price - M.entry) / M.entry;
    M.driftShown = S.sens * retShown / d;
    M.driftTrue = S.sens * retTrue / d;
    M.xShown = M.driftShown + M.wob;
    M.xTrue = M.driftTrue + M.wob;

    // the safe rail: you cannot die of profit, you lean on it
    if (M.xTrue > 1) { M.wob -= (M.xTrue - 1) * 6 * dt; }

    if (M.state === 'walk' || (M.state === 'frozen' && M.liqFrozen)) {
      if (M.xTrue <= -1) endRound('liq');
    }
    if (M.state === 'walk' && M.t >= S.round) endRound('buzzer');
  }

  /* =====================================================================
     SCREEN — 400x240, drawn in greyscale then thresholded to 1-bit
     ===================================================================== */
  function px(v) { return Math.round(v) + 0.5; }
  function txt(s, x, y, size, align) {
    sctx.font = '400 ' + size + 'px Silkscreen, ui-monospace, monospace';
    sctx.textAlign = align || 'left';
    sctx.textBaseline = 'alphabetic';
    sctx.fillText(s, x, y);
  }
  function bar(x, y, w, h, frac, filled) {
    sctx.fillStyle = '#000';
    sctx.fillRect(x, y, w, h);
    sctx.fillStyle = '#fff';
    sctx.fillRect(x + 1, y + 1, w - 2, h - 2);
    sctx.fillStyle = '#000';
    var iw = Math.round((w - 2) * clamp(frac, 0, 1));
    if (filled !== false) sctx.fillRect(x + 1, y + 1, iw, h - 2);
  }

  function drawScreen() {
    sctx.fillStyle = '#fff';
    sctx.fillRect(0, 0, W, H);
    sctx.fillStyle = '#000';
    sctx.strokeStyle = '#000';
    sctx.lineWidth = 1;

    /* ---- header ---- */
    txt('NERVE', 8, 18, 16);
    txt('×' + M.lev.toFixed(1), W - 8, 18, 16, 'right');
    if (M.state === 'walk' || M.state === 'frozen') {
      sctx.fillRect(0, 24, Math.round(W * clamp(1 - M.t / S.round, 0, 1)), 2);
    }

    /* ---- the void below the beam (this is what the dither is for) ---- */
    var g = sctx.createLinearGradient(0, BEAM_Y + 6, 0, H - 26);
    g.addColorStop(0, '#f2f2f2'); g.addColorStop(1, '#3a3a3a');
    sctx.fillStyle = g;
    sctx.fillRect(0, BEAM_Y + 6, W, H - 26 - (BEAM_Y + 6));
    // scrolling depth hatches so forward motion reads
    sctx.strokeStyle = '#9a9a9a';
    for (var i = 0; i < 14; i++) {
      var hx = ((i * 34 - (M.dist * 9) % 34) + 408) % 408 - 4;
      sctx.beginPath();
      sctx.moveTo(px(hx), BEAM_Y + 12);
      sctx.lineTo(px(hx - 16), H - 28);
      sctx.stroke();
    }
    sctx.strokeStyle = '#000';

    /* ---- ground stubs, as in the mockup ---- */
    sctx.fillStyle = '#000';
    for (var s2 = 0; s2 < 9; s2++) { sctx.fillRect(4 + s2 * 9, H - 30, 7, 2); sctx.fillRect(W - 76 + s2 * 9, H - 30, 7, 2); }

    /* ---- the beam ---- */
    var d = 1 / M.lev;
    var half = clamp(25 + 150 * d, 25, 178);
    var cx = W / 2;
    var jit = (Math.random() - 0.5) * M.shake * 5;
    sctx.lineWidth = 2;
    sctx.beginPath();
    for (var bx = cx - half; bx <= cx + half; bx += 4) {
      var wave = Math.sin((bx * 0.08) + M.t * 9) * M.shake * 2.6;
      if (bx === cx - half) sctx.moveTo(bx, BEAM_Y + wave + jit); else sctx.lineTo(bx, BEAM_Y + wave + jit);
    }
    sctx.stroke();
    sctx.lineWidth = 1;
    // beam supports
    sctx.beginPath();
    sctx.moveTo(px(cx - half), BEAM_Y + jit); sctx.lineTo(px(cx - half - 12), H - 30);
    sctx.moveTo(px(cx + half), BEAM_Y + jit); sctx.lineTo(px(cx + half + 12), H - 30);
    sctx.stroke();
    // edge ticks: the cliff (left) and the rail (right)
    sctx.fillRect(cx - half - 2, BEAM_Y - 9 + jit, 3, 9);
    sctx.fillRect(cx + half - 1, BEAM_Y - 5 + jit, 3, 5);
    txt('CLIFF', cx - half - 3, BEAM_Y - 13 + jit, 8, 'right');
    txt('RAIL', cx + half + 3, BEAM_Y - 9 + jit, 8, 'left');

    /* ---- the walker ---- */
    var wx = cx + clamp(M.xShown, -1.25, 1.12) * half;
    var wy = BEAM_Y + jit + M.fallY;
    sctx.save();
    sctx.translate(wx, wy);
    sctx.rotate(M.fallRot);
    var lean = clamp(M.wob, -1, 1) * 0.5;
    sctx.fillStyle = '#000';
    // legs
    var sw = M.state === 'walk' ? Math.sin(M.phase) * 4 : 0;
    sctx.fillRect(-3 + sw * 0.5, -9, 2, 9);
    sctx.fillRect(1 - sw * 0.5, -9, 2, 9);
    // body + head
    sctx.fillRect(-3, -21, 6, 12);
    sctx.fillRect(-3, -29, 6, 6);
    sctx.fillStyle = '#fff'; sctx.fillRect(-1, -27, 2, 2); sctx.fillStyle = '#000';
    // balance pole, tilting with wobble
    sctx.save();
    sctx.translate(0, -17); sctx.rotate(lean);
    sctx.fillRect(-26, -1, 52, 2);
    sctx.fillRect(-27, -3, 2, 6); sctx.fillRect(25, -3, 2, 6);
    sctx.restore();
    sctx.restore();

    /* ---- danger reticule when close to the cliff ---- */
    var margin = 1 + Math.min(M.xTrue, M.xShown);
    if (margin < 0.34 && (M.state === 'walk' || M.state === 'frozen')) {
      if (Math.floor(M.t * 8) % 2 === 0) {
        txt('LIQ', cx - half + 2, BEAM_Y + 22 + jit, 8, 'left');
        sctx.beginPath(); sctx.moveTo(px(cx - half), BEAM_Y + 4 + jit); sctx.lineTo(px(cx - half), BEAM_Y + 14 + jit); sctx.stroke();
      }
    }

    /* ---- prompt line ---- */
    if (M.state === 'ready') {
      txt('CRANK TO SET SIZE', cx, 46, 8, 'center');
      txt(Math.floor(M.t * 2) % 2 === 0 ? 'PRESS A TO WALK' : '', cx, 60, 16, 'center');
      txt('$' + S.collateral.toFixed(2) + ' AT ' + M.lev.toFixed(1) + 'X  =  $' + (S.collateral * M.lev).toFixed(2) + ' NOTIONAL', cx, 76, 8, 'center');
    }

    /* ---- bottom bar ---- */
    sctx.fillRect(0, H - 26, W, 1);
    var shownPnl = pnlNow(M.lastTick);
    txt('PNL ' + (shownPnl >= 0 ? '+' : '-') + '$' + Math.abs(shownPnl).toFixed(2), 6, H - 15, 8);
    txt('FEED ' + FEEDS[M.feed].label, 128, H - 15, 8);
    txt(String(M.coins), W - 6, H - 15, 8, 'right');
    bar(238, H - 21, 92, 7, M.coins / START_COINS);
    // cap strip
    bar(6, H - 9, 120, 6, M.capUsed / CAP_TOTAL);
    txt('CAP $' + M.capUsed.toFixed(2) + '/$' + CAP_TOTAL.toFixed(2), 132, H - 4, 8);
    txt(M.dist.toFixed(0) + 'M', W - 6, H - 4, 8, 'right');

    /* ---- overlays ---- */
    if (M.state === 'frozen') {
      var bw = 210, bh = 74, bxx = (W - bw) / 2, byy = 66;
      sctx.fillStyle = '#000'; sctx.fillRect(bxx - 3, byy - 3, bw + 6, bh + 6);
      sctx.fillStyle = '#fff'; sctx.fillRect(bxx, byy, bw, bh);
      sctx.fillStyle = '#000';
      txt('INSERT COIN', W / 2, byy + 26, 16, 'center');
      txt('$' + PACK_USD.toFixed(2) + '  =  ' + PACK + ' COINS', W / 2, byy + 42, 8, 'center');
      txt('A TO PAY · B TO QUIT', W / 2, byy + 60, 8, 'center');
      if (M.liqFrozen && Math.floor(M.t * 4) % 2 === 0) txt('MARKET IS STILL MOVING', W / 2, byy + 88, 8, 'center');
    }
    if (M.state === 'over' || (M.state === 'fall' && M.fallY > 90)) {
      var ow = 224, oh = 52, oxx = (W - ow) / 2, oyy = 58;
      sctx.fillStyle = '#000'; sctx.fillRect(oxx - 3, oyy - 3, ow + 6, oh + 6);
      sctx.fillStyle = '#fff'; sctx.fillRect(oxx, oyy, ow, oh);
      sctx.fillStyle = '#000';
      txt(M.overMsg, W / 2, oyy + 24, 16, 'center');
      txt(M.overSub, W / 2, oyy + 42, 8, 'center');
      txt(Math.floor(M.t * 2) % 2 === 0 ? 'SPACE FOR NEXT ROUND' : '', W / 2, oyy + 74, 8, 'center');
    }

    /* ---- hold-to-cash-out ring ---- */
    if (M.holdT > 0 && M.state === 'walk') {
      var f = clamp(M.holdT / S.holdMs, 0, 1);
      txt('CASH OUT', W / 2, 46, 8, 'center');
      bar(W / 2 - 46, 52, 92, 8, f);
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
        var t = (row[x & 3] + 0.5) * 15.9375;
        var on = lum <= t;
        d[i] = on ? LCD_INK[0] : LCD_PAPER[0];
        d[i + 1] = on ? LCD_INK[1] : LCD_PAPER[1];
        d[i + 2] = on ? LCD_INK[2] : LCD_PAPER[2];
        d[i + 3] = 255;
      }
    }
    sctx.putImageData(img, 0, 0);
  }

  /* =====================================================================
     CHART — true price vs the ticks you paid for
     ===================================================================== */
  var hover = null;
  function drawChart() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var cw = chart.clientWidth, ch = chart.clientHeight;
    if (chart.width !== cw * dpr || chart.height !== ch * dpr) {
      chart.width = cw * dpr; chart.height = ch * dpr;
    }
    cctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cctx.clearRect(0, 0, cw, ch);

    var padL = 8, padR = 62, padT = 12, padB = 20;
    var pw = cw - padL - padR, ph = ch - padT - padB;
    if (pw <= 10 || M.hist.length < 2) return;

    var d = 1 / M.lev;
    var ref = M.entry || M.price;
    var pLiq = ref * (1 + d * (-1 - M.wob) / S.sens);
    var pRail = ref * (1 + d * (1 - M.wob) / S.sens);

    var lo = Infinity, hi = -Infinity, k;
    for (k = 0; k < M.hist.length; k++) { if (M.hist[k].p < lo) lo = M.hist[k].p; if (M.hist[k].p > hi) hi = M.hist[k].p; }
    [ref, pLiq, pRail].forEach(function (v) { if (isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } });
    var pad = (hi - lo) * 0.14 || ref * 0.0005;
    lo -= pad; hi += pad;

    var t1 = M.t, t0 = t1 - WINDOW;
    var X = function (t) { return padL + (t - t0) / WINDOW * pw; };
    var Y = function (p) { return padT + (hi - p) / (hi - lo) * ph; };

    /* grid + y labels */
    cctx.font = '500 10px "IBM Plex Mono", monospace';
    cctx.textBaseline = 'middle';
    cctx.textAlign = 'left';
    for (k = 0; k <= 3; k++) {
      var gv = lo + (hi - lo) * k / 3, gy = Y(gv);
      cctx.strokeStyle = TOK.line; cctx.lineWidth = 1;
      cctx.beginPath(); cctx.moveTo(padL, Math.round(gy) + 0.5); cctx.lineTo(padL + pw, Math.round(gy) + 0.5); cctx.stroke();
      cctx.fillStyle = TOK['ink-3'];
      cctx.fillText(gv.toFixed(2), padL + pw + 7, gy);
    }

    /* entry */
    if (M.entry) {
      cctx.setLineDash([3, 3]); cctx.strokeStyle = TOK['ink-3']; cctx.lineWidth = 1;
      cctx.beginPath(); cctx.moveTo(padL, Math.round(Y(ref)) + 0.5); cctx.lineTo(padL + pw, Math.round(Y(ref)) + 0.5); cctx.stroke();
      cctx.setLineDash([]);
      cctx.fillStyle = TOK['ink-3']; cctx.textAlign = 'left';
      cctx.fillText('ENTRY', padL + 3, Y(ref) - 8);
    }

    /* cliff + rail */
    function level(p, col, label, solid) {
      var y = Y(p); if (y < padT - 2 || y > padT + ph + 2) return;
      cctx.strokeStyle = col; cctx.lineWidth = solid ? 1.5 : 1;
      if (!solid) cctx.setLineDash([2, 4]);
      cctx.beginPath(); cctx.moveTo(padL, Math.round(y) + 0.5); cctx.lineTo(padL + pw, Math.round(y) + 0.5); cctx.stroke();
      cctx.setLineDash([]);
      cctx.fillStyle = col; cctx.textAlign = 'left';
      cctx.fillText(label, padL + 3, y + (solid ? 9 : -8));
    }
    level(pRail, TOK['ink-3'], 'RAIL  x = +1', false);
    level(pLiq, TOK.crit, 'CLIFF  x = −1', true);

    /* true price */
    cctx.strokeStyle = TOK['ser-true']; cctx.lineWidth = 2;
    cctx.lineJoin = 'round'; cctx.lineCap = 'round';
    cctx.beginPath();
    for (k = 0; k < M.hist.length; k++) {
      var h = M.hist[k];
      if (k === 0) cctx.moveTo(X(h.t), Y(h.p)); else cctx.lineTo(X(h.t), Y(h.p));
    }
    cctx.stroke();

    /* ticks you paid for — stepped, because that is literally what you know */
    if (M.tickHist.length) {
      cctx.strokeStyle = TOK['ser-paid']; cctx.lineWidth = 2;
      cctx.beginPath();
      for (k = 0; k < M.tickHist.length; k++) {
        var q = M.tickHist[k];
        if (k === 0) cctx.moveTo(X(q.t), Y(q.p));
        else { cctx.lineTo(X(q.t), Y(M.tickHist[k - 1].p)); cctx.lineTo(X(q.t), Y(q.p)); }
      }
      cctx.lineTo(X(t1), Y(M.tickHist[M.tickHist.length - 1].p));
      cctx.stroke();
      // emphasized endpoint: the one number the device believes
      var last = M.tickHist[M.tickHist.length - 1];
      cctx.fillStyle = TOK.sunk; cctx.beginPath(); cctx.arc(X(t1), Y(last.p), 5.5, 0, 6.2832); cctx.fill();
      cctx.fillStyle = TOK['ser-paid']; cctx.beginPath(); cctx.arc(X(t1), Y(last.p), 4, 0, 6.2832); cctx.fill();
    }
    /* true endpoint */
    cctx.fillStyle = TOK.sunk; cctx.beginPath(); cctx.arc(X(t1), Y(M.price), 5.5, 0, 6.2832); cctx.fill();
    cctx.fillStyle = TOK['ser-true']; cctx.beginPath(); cctx.arc(X(t1), Y(M.price), 4, 0, 6.2832); cctx.fill();

    /* the blind spot, drawn as the gap it is */
    if (M.tickHist.length) {
      var lp = M.tickHist[M.tickHist.length - 1].p;
      if (Math.abs(Y(lp) - Y(M.price)) > 3) {
        cctx.strokeStyle = TOK.crit; cctx.lineWidth = 1; cctx.setLineDash([2, 2]);
        cctx.beginPath(); cctx.moveTo(X(t1), Y(lp)); cctx.lineTo(X(t1), Y(M.price)); cctx.stroke();
        cctx.setLineDash([]);
      }
    }

    /* hover crosshair */
    if (hover && hover.x > padL && hover.x < padL + pw) {
      var ht = t0 + (hover.x - padL) / pw * WINDOW;
      var near = null, bd = 1e9;
      for (k = 0; k < M.hist.length; k++) { var dd = Math.abs(M.hist[k].t - ht); if (dd < bd) { bd = dd; near = M.hist[k]; } }
      var tk = null;
      for (k = M.tickHist.length - 1; k >= 0; k--) { if (M.tickHist[k].t <= ht) { tk = M.tickHist[k]; break; } }
      if (near) {
        cctx.strokeStyle = TOK['ink-3']; cctx.lineWidth = 1; cctx.setLineDash([2, 3]);
        cctx.beginPath(); cctx.moveTo(Math.round(X(near.t)) + 0.5, padT); cctx.lineTo(Math.round(X(near.t)) + 0.5, padT + ph); cctx.stroke();
        cctx.setLineDash([]);
        var lines = [
          (near.t - t1).toFixed(2) + 's',
          'true  ' + near.p.toFixed(2),
          tk ? 'paid  ' + tk.p.toFixed(2) : 'paid  —',
          tk ? 'blind ' + ((near.p - tk.p) / tk.p * 100).toFixed(3) + '%' : ''
        ].filter(Boolean);
        var bwd = 104, bhd = lines.length * 14 + 8;
        var bxd = Math.min(X(near.t) + 8, padL + pw - bwd), byd = padT + 4;
        cctx.fillStyle = TOK.surface; cctx.strokeStyle = TOK.line; cctx.lineWidth = 1;
        cctx.fillRect(bxd, byd, bwd, bhd); cctx.strokeRect(bxd + 0.5, byd + 0.5, bwd, bhd);
        cctx.textAlign = 'left';
        lines.forEach(function (ln, ix) {
          cctx.fillStyle = ix === 1 ? TOK['ser-true'] : ix === 2 ? TOK['ser-paid'] : ix === 3 ? TOK.crit : TOK['ink-2'];
          cctx.fillText(ln, bxd + 8, byd + 13 + ix * 14);
        });
      }
    }
  }

  /* =====================================================================
     PANELS
     ===================================================================== */
  var CALC = [
    { k: 'lev',  n: 'Leverage L',        f: 'crank position' },
    { k: 'd',    n: 'Liquidation dist d', f: '1 / L' },
    { k: 'ret',  n: 'Return',            f: '(P − P₀) / P₀' },
    { k: 'dr',   n: 'Market drift',      f: 'SENS × return / d' },
    { k: 'wob',  n: 'Wobble',            f: '∫ tick kicks − your A/B' },
    { k: 'xs',   n: 'x shown — drawn', f: 'drift(paid tick) + wobble' },
    { k: 'xt',   n: 'x true — checked', f: 'drift(real price) + wobble' },
    { k: 'lag',  n: 'Blind spot',        f: 'x true − x shown', cls: 'r-lag' },
    { k: 'pnl',  n: 'PnL',               f: 'C × L × return', cls: 'r-pnl' }
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
      inp.addEventListener('input', function () {
        S[kn.k] = parseFloat(inp.value);
        $('kv-' + kn.k).textContent = kn.fmt(S[kn.k]);
      });
    });
  }
  function syncKnobs() {
    KNOBS.forEach(function (kn) {
      var inp = $('kn-' + kn.k); if (!inp) return;
      inp.value = S[kn.k];
      $('kv-' + kn.k).textContent = kn.fmt(S[kn.k]);
    });
  }

  function updatePanels() {
    var d = 1 / M.lev;
    var retShown = M.entry ? (M.lastTick - M.entry) / M.entry : 0;
    var retTrue = M.entry ? (M.price - M.entry) / M.entry : 0;
    var lag = M.xTrue - M.xShown;
    var pnl = M.entry ? pnlNow(M.state === 'frozen' ? M.lastTick : M.price) : 0;

    cells.lev.sub.textContent = '—';
    cells.lev.val.textContent = M.lev.toFixed(2) + '×';
    cells.d.sub.textContent = '1 / ' + M.lev.toFixed(2);
    cells.d.val.textContent = pct(d, 2);
    cells.ret.sub.textContent = M.entry ? '(' + M.lastTick.toFixed(2) + ' − ' + M.entry.toFixed(2) + ') / ' + M.entry.toFixed(2) : '—';
    cells.ret.val.textContent = spct(retShown);
    cells.dr.sub.textContent = S.sens.toFixed(0) + ' × ' + spct(retShown) + ' / ' + pct(d, 2);
    cells.dr.val.textContent = fx(M.driftShown || 0, 3);
    cells.wob.sub.textContent = 'decay ' + S.decay.toFixed(2) + '/s · gain ' + S.kick.toFixed(0);
    cells.wob.val.textContent = fx(M.wob, 3);
    cells.xs.sub.textContent = fx(M.driftShown || 0, 3) + ' + ' + fx(M.wob, 3);
    cells.xs.val.textContent = fx(M.xShown, 3);
    cells.xt.sub.textContent = fx(M.driftTrue || 0, 3) + ' + ' + fx(M.wob, 3);
    cells.xt.val.textContent = fx(M.xTrue, 3);
    cells.lag.sub.textContent = FEEDS[M.feed].label + ' feed · ' + (1000 / FEEDS[M.feed].hz).toFixed(0) + 'ms of unseen market';
    cells.lag.val.textContent = fx(lag, 3);
    cells.lag.tr.classList.toggle('is-bad', Math.abs(lag) > 0.12);
    cells.pnl.sub.textContent = '$' + S.collateral.toFixed(2) + ' × ' + M.lev.toFixed(2) + ' × ' + spct(retTrue);
    cells.pnl.val.textContent = usd(pnl);
    cells.pnl.val.className = 'c-val ' + (pnl >= 0 ? 'up' : 'down');

    /* calibration */
    $('calBeam').textContent = '±' + (d / S.sens * 100).toFixed(3) + '%';
    $('calLiq').textContent = '±' + (d * 100).toFixed(2) + '%';
    $('calSens').textContent = S.sens.toFixed(0) + '×';

    /* contribution split */
    var a = Math.abs(M.driftTrue || 0), b = Math.abs(M.wob), tot = a + b || 1;
    var used = clamp(Math.abs(M.xTrue), 0, 1);
    $('segDrift').style.width = (a / tot * used * 100).toFixed(1) + '%';
    $('segWob').style.width = (b / tot * used * 100).toFixed(1) + '%';
    $('shDrift').textContent = (a / tot * 100).toFixed(0) + '%';
    $('shWob').textContent = (b / tot * 100).toFixed(0) + '%';
    $('shUsed').textContent = (used * 100).toFixed(0) + '%';

    /* economy */
    $('coinVal').textContent = M.coins;
    var cb = $('coinBar');
    cb.style.width = clamp(M.coins / START_COINS, 0, 1) * 100 + '%';
    cb.classList.toggle('is-low', M.coins < START_COINS * 0.18);
    var burn = FEEDS[M.feed].hz * FEEDS[M.feed].cost;
    $('coinBurn').textContent = burn + ' coins/s — ' + (M.coins / burn).toFixed(0) + 's of sight left';
    $('capVal').textContent = '$' + M.capUsed.toFixed(2) + ' / $' + CAP_TOTAL.toFixed(2);
    $('capBar').style.width = clamp(M.capUsed / CAP_TOTAL, 0, 1) * 100 + '%';
    $('tickCount').textContent = M.ticks;
    $('hbarSpent').textContent = M.hbar.toFixed(4);

    /* chart foot */
    var lr = $('lagRead');
    if (M.tickHist.length) {
      var lp = M.tickHist[M.tickHist.length - 1].p;
      var gapPct = (M.price - lp) / lp * 100;
      lr.textContent = 'blind spot  ' + (gapPct >= 0 ? '+' : '') + gapPct.toFixed(3) + '%  ·  ' + fx(lag, 3) + ' of beam';
      lr.classList.toggle('is-bad', Math.abs(lag) > 0.12);
    } else { lr.textContent = '—'; }

    $('crankVal').textContent = '×' + M.lev.toFixed(1);
    $('crankArm').style.transform = 'translate(-50%,0) rotate(' + ((M.lev - 1) / 9 * 320) + 'deg)';
    $('padHold').style.height = (M.state === 'walk' ? clamp(M.holdT / S.holdMs, 0, 1) * 100 : 0) + '%';
    $('lgRate').textContent = FEEDS[M.feed].label;
  }

  /* =====================================================================
     LOOP
     ===================================================================== */
  var prev = performance.now();
  function frame(now) {
    var dt = Math.min((now - prev) / 1000, 0.05);
    prev = now;

    stepMarket(dt);
    if (M.state === 'walk') {
      M.t += dt;
      M.tickAcc += dt;
      var period = 1 / FEEDS[M.feed].hz;
      var guard = 0;
      while (M.tickAcc >= period && M.state === 'walk' && guard++ < 40) { M.tickAcc -= period; buyTick(); }
    } else if (M.state !== 'ready') {
      M.t += dt;
    } else { M.t += dt; }

    if (M.state === 'walk' || M.state === 'frozen') stepPhysics(dt);

    if (M.state === 'fall') {
      M.fallV += 620 * dt; M.fallY += M.fallV * dt; M.fallRot += 5 * dt;
      if (M.fallY > 160) { M.state = 'over'; }
    }
    if (M.state === 'walk' && M.keyA) { M.holdT += dt * 1000; if (M.holdT >= S.holdMs) { M.holdT = 0; endRound('cash'); } }

    drawScreen();
    drawChart();
    updatePanels();
    requestAnimationFrame(frame);
  }

  /* =====================================================================
     INPUT
     ===================================================================== */
  function crank(delta) {
    if (M.state !== 'ready' && M.state !== 'walk') return;
    M.lev = clamp(Math.round((M.lev + delta) * 10) / 10, 1, 10);
  }
  function pressA() {
    if (M.state === 'ready') { startRound(); return; }
    if (M.state === 'frozen') { insertCoin(); return; }
    if (M.state === 'over') { nextRound(); return; }
    if (M.state === 'walk') { M.keyA = true; }
  }
  function releaseA() { M.keyA = false; M.holdT = 0; }
  function pressB() {
    if (M.state === 'frozen') { endRound('cash'); return; }
    if (M.state === 'walk') M.keyB = true;
  }
  function releaseB() { M.keyB = false; }

  window.addEventListener('keydown', function (e) {
    if (e.repeat) { if (e.key === 'ArrowUp' || e.key === 'ArrowDown') e.preventDefault(); }
    var k = e.key.toLowerCase();
    if (k === 'z') { e.preventDefault(); if (!e.repeat) pressA(); }
    else if (k === 'x') { e.preventDefault(); if (!e.repeat) pressB(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); crank(0.5); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); crank(-0.5); }
    else if (e.key === ' ') {
      e.preventDefault();
      if (M.state === 'ready') startRound();
      else if (M.state === 'over') nextRound();
      else if (M.state === 'walk' || M.state === 'fall') { if (M.state === 'walk') endRound('cash'); }
    }
  });
  window.addEventListener('keyup', function (e) {
    var k = e.key.toLowerCase();
    if (k === 'z') releaseA();
    if (k === 'x') releaseB();
  });

  ['btnA', 'btnB'].forEach(function (id) {
    var el = $(id), down = id === 'btnA' ? pressA : pressB, up = id === 'btnA' ? releaseA : releaseB;
    el.addEventListener('pointerdown', function (e) { e.preventDefault(); el.setPointerCapture(e.pointerId); down(); });
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    el.addEventListener('pointerleave', up);
  });

  var dial = $('dial'), dragging = false, lastY = 0;
  dial.addEventListener('wheel', function (e) { e.preventDefault(); crank(e.deltaY < 0 ? 0.5 : -0.5); }, { passive: false });
  screen.addEventListener('wheel', function (e) { e.preventDefault(); crank(e.deltaY < 0 ? 0.5 : -0.5); }, { passive: false });
  dial.addEventListener('pointerdown', function (e) { dragging = true; lastY = e.clientY; dial.setPointerCapture(e.pointerId); });
  dial.addEventListener('pointermove', function (e) {
    if (!dragging) return;
    if (Math.abs(e.clientY - lastY) > 7) { crank(e.clientY < lastY ? 0.5 : -0.5); lastY = e.clientY; }
  });
  dial.addEventListener('pointerup', function () { dragging = false; });

  chart.addEventListener('pointermove', function (e) {
    var r = chart.getBoundingClientRect();
    hover = { x: e.clientX - r.left, y: e.clientY - r.top };
  });
  chart.addEventListener('pointerleave', function () { hover = null; });

  document.querySelectorAll('.feed').forEach(function (b) {
    b.addEventListener('click', function () {
      var f = parseInt(b.dataset.feed, 10);
      if (f === M.feed) return;
      M.feed = f;
      document.querySelectorAll('.feed').forEach(function (o) { o.classList.toggle('is-on', o === b); });
      log('FEED → ' + FEEDS[f].name + ' ' + FEEDS[f].label + ' @ ' + (FEEDS[f].cost / 1000).toFixed(3) + ' HBAR/tick', 'e-pay');
    });
  });

  document.querySelectorAll('.chip').forEach(function (c) {
    c.addEventListener('click', function () {
      var p = PRESETS[c.dataset.preset];
      Object.keys(p).forEach(function (k) { S[k] = p[k]; });
      document.querySelectorAll('.chip').forEach(function (o) { o.classList.toggle('is-on', o === c); });
      syncKnobs();
      log('PRESET → ' + c.textContent + ' (σ ' + S.vol.toFixed(2) + ' %/s, SENS ' + S.sens + ')');
    });
  });

  $('frozenLiq').addEventListener('change', function (e) { M.liqFrozen = e.target.checked; });

  $('themeBtn').addEventListener('click', function () {
    var r = document.documentElement;
    var cur = r.getAttribute('data-theme');
    var sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    r.setAttribute('data-theme', cur ? (cur === 'dark' ? 'light' : 'dark') : (sysDark ? 'light' : 'dark'));
    readTokens();
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', readTokens);

  /* =====================================================================
     BOOT
     ===================================================================== */
  buildCalc();
  buildKnobs();
  readTokens();
  log('Bench ready · PREMIUM 10 Hz selected · ' + START_COINS + ' coins · cap $' + CAP_TOTAL.toFixed(2));
  log('Crank to ×4, press A, and watch the CLIFF line on the chart come to meet you.');

  var boot = function () { prev = performance.now(); requestAnimationFrame(frame); };
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(boot).catch(boot); else boot();
})();
