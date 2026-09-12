# Money and leaderboard: flow redesign

> **Superseded in part by [README.md](README.md) and the mockups beside it.**
> That later pass cut the bank face (cash out now fires straight from the
> launcher's money button), dropped the podium as a separate screen, and made
> the leaderboard move one rank per beat rather than in a single swap. The
> analysis of what is wrong today, the state table, the timings and the list of
> what the code does not track yet all still hold — read them here, but take the
> screen list from the README.

The game is done and it is fun. The two screens around it are not. This is a
design proposal for both — the money screen (`BoxGame.draw_arc_wallet`) and the
leaderboard (`screens/board.py`) — plus the flow that joins them. Nothing here
is built yet; it is written to be argued with.

---

## 1. What is wrong today

### The money screen does three jobs in one layout

```
 ┌──────────────────────────────────────────────────┐
 │ ┌──────────────┐  SEND USDC ON                   │
 │ │              │  ARC TESTNET                    │
 │ │   QR 164px   │  0x3E0Axxxxxxxxxxxxxxxxxxx      │   <- deposit job
 │ │   always     │  xxxxxxxxxxxxxx562E             │
 │ │   the hero   │                                 │
 │ │              │  WAITING FOR USDC...            │   <- status job
 │ └──────────────┘  KEEPS 0.01 OF EACH FOR GAS     │
 │                                                  │
 │  BALANCE 137.40 USDC                             │   <- bank job
 │  CASH OUT GOES TO amber-otter.tick.eth           │
 ├──────────────────────────────────────────────────┤
 │ < BACK                            CASH OUT >     │
 └──────────────────────────────────────────────────┘
```

- The QR is the largest thing on screen **even when you already have money in
  and the only thing you want is to cash out**. The screen keeps shouting "send
  USDC" at a player who is trying to leave.
- Three different truths about the same money are in three places: the address
  block (deposit), the 26-character status line (network), and the bottom two
  lines (balance / payout). None of them is clearly the headline.
- Money arriving is the best moment the device has, and it is a 6-second text
  banner.
- Cashing out is a dead end. The transaction lands, a line of text changes, and
  you are still looking at a QR code that says SEND USDC ON ARC TESTNET. No
  receipt, no summary of the run, nothing to do next.

### The leaderboard is a spreadsheet

Rows arrive, your row glows yellow, nothing ever moves. The single most
interesting fact — *you just went from 4th to 3rd* — is never shown, because the
board has no memory of where you were before.

### The flow has two dead ends

```
   HOME -> money screen -> (deposit lands) -> HOME          [ok, PLAY is focused]
   HOME -> BOX RUN -> money screen -> CASH OUT -> ...still on the QR screen
                                                  B, scroll, A to find LEADERS
```

---

## 2. The flow we want

```
        ┌────────────────────────────────────────────────────────┐
        │                                                        │
   ┌────▼─────┐  A on money button                               │
   │   HOME   ├──────────────► ┌─────────────┐                   │
   │ attract  │   (no funds)   │  CASHIER A  │  SCAN TO PLAY     │
   └────▲─────┘                │   waiting   │  big QR           │
        │                      └──────┬──────┘                   │
        │                             │ deposit lands            │
        │                      ┌──────▼──────┐                   │
        │  timeout 3s          │   ARRIVAL   │  coins rain,      │
        ├──────────────────────┤  +25.00 !!  │  balance counts   │
        │                      └──────┬──────┘                   │
        │                             │ A = PLAY NOW             │
   ┌────▼─────┐                       │                          │
   │ BOX RUN  │◄──────────────────────┘                          │
   │  (game)  │                                                  │
   └────┬─────┘                                                  │
        │ A on money button (in session)                         │
   ┌────▼─────┐                                                  │
   │CASHIER B │  THE BANK: balance is the hero, QR is a 64px     │
   │  in play │  chip marked ADD MORE. A = CASH OUT.             │
   └────┬─────┘                                                  │
        │                                                        │
   ┌────▼─────┐   three ticking steps, armoured truck drives     │
   │  PAYING  │   across the street while Arc confirms           │
   └────┬─────┘                                                  │
   ┌────▼─────┐   PAID OUT +137.40, session summary, tx          │
   │ RECEIPT  │   A = SEE YOUR RANK, or auto after 2.5s          │
   └────┬─────┘                                                  │
   ┌────▼─────────────────┐                                      │
   │ LEADERBOARD (arrival)│  opens at your OLD rank, waits for   │
   │  #4 ──────► #3  ▲    │  the scorekeeper, then MOVES you     │
   └──────────┬───────────┘                                   B  │
              └──────────────────────────────────────────────────┘
```

Two rules carry the whole thing:

1. **One screen, one job.** The money screen changes shape with the state of the
   money instead of showing all three states at once.
2. **Money moving is an event, not a status line.** Arriving and leaving both get
   their own beat, and leaving hands you straight to the leaderboard.

---

## 3. The cashier screen

Same 480x320 canvas, same palette (`ui.py`), same footer band. Which of the four
faces is drawn comes from the funding state that already exists on
`ArcFunding` — no new chain plumbing:

| face | condition (already available) |
|---|---|
| A · WAITING | `not funding.in_session and funding.last_cashout is None` |
| ARRIVAL | on the `('opened', amount, sender)` event from `funding.sync` |
| B · BANK | `funding.in_session` |
| PAYING | `self.cashing or funding.pending_cashout is not None` |
| RECEIPT | `funding.last_cashout is not None and not in_session` |

### A · WAITING — the only face where the QR is the hero

```
 ┌──────────────────────────────────────────────────┐
 │ CASHIER                             ARC TESTNET  │ 6
 │                                                  │
 │  ┌────────────────┐                              │
 │  │▓▓░▓░░▓▓▓░▓▓░▓▓▓│   SCAN TO PLAY               │ 46  24px YELLOW
 │  │▓░▓▓▓░░▓░▓░░▓░░▓│   Any amount of USDC on Arc  │ 72  13px MUTED
 │  │▓▓░░▓▓▓░▓▓▓░░▓░▓│                              │
 │  │══════scan══════│   0x3E0A 1f4c 9b22 8d7e      │ 104 15px CREAM
 │  │▓░▓░░▓▓░░▓░▓▓▓░▓│   ...  ...  ...  562E        │ 124
 │  │▓▓▓░▓░░▓▓░▓░░▓▓▓│                              │
 │  └────────────────┘   ● WAITING FOR USDC ...     │ 160 15px CREAM, pulse
 │   14,40  180x180                                 │
 │                       10.00 USDC = ONE BOX       │ 186 13px MUTED
 │      (o_o)/                                      │
 │      _|_|_   <- rider, empty bucket held out     │ 214
 │                                                  │
 │  MAX WIN 5x YOUR DEPOSIT  ·  0.01 KEPT FOR GAS   │ 250 11px MUTED
 ├──────────────────────────────────────────────────┤ 274
 │ ● < BACK                                         │
 └──────────────────────────────────────────────────┘
```

- A **scan beam** sweeps down the QR every 2s. It costs one `draw.line` and it
  makes a dead screen breathe.
- The **rider from the game stands at the bottom holding a bucket** (reuse
  `box_scene.Rider`, already imported by the launcher). This is the one screen
  in the product where our mascot has nothing to do, so let it look bored:
  taps foot, checks an imaginary watch after 15s.
- The address is split into readable quads, not two dense 22-char runs.
- The footer has no A action here. Nothing to press means nothing to press
  wrongly.
- Error state replaces the status line only: `● ARC UNREACHABLE — RETRYING` in
  RED. The QR stays valid, so do not hide it.

### ARRIVAL — 2.5 seconds, the best moment we own

Triggered by the existing `'opened'` event. Full-screen takeover.

```
 ┌──────────────────────────────────────────────────┐
 │       o     o      o        o     o              │  coins fall from the top
 │   o        o    +25.00 USDC     o        o       │  into the rider's bucket
 │        o      ╔══════════════╗       o           │  (Sparks + Floaters,
 │            o  ║   40px MINT  ║   o               │   both already exist)
 │               ╚══════════════╝                   │
 │            FROM amber-otter.tick.eth             │  or short address
 │                                                  │
 │              BALANCE  25.00 USDC                 │  counts up 0 -> 25
 │                                                  │
 │              \(^o^)/   rider cheers              │
 ├──────────────────────────────────────────────────┤
 │ ● HOME                        ◆ PLAY NOW >       │
 └──────────────────────────────────────────────────┘
```

- Sound: existing `coin` cue, then the buy arpeggio.
- **A goes straight into BOX RUN.** If nobody presses anything for 3s, fall back
  to the launcher with PLAY focused — which is exactly what the `funded` return
  value already does today. One press from wallet to playing.
- A second deposit while already in session re-plays this shorter (1.2s) and
  returns to face B rather than home.

### B · BANK — money in, the QR gets out of the way

```
 ┌──────────────────────────────────────────────────┐
 │ CASHIER                    amber-otter.tick.eth  │ 6
 │                                                  │
 │  BALANCE                             ┌────────┐  │ 40  13px MUTED
 │  ╔════════════════════╗              │▓░▓░▓░▓▓│  │
 │  ║   137.40 USDC      ║              │░▓▓░▓▓░░│  │ 56  34px CREAM
 │  ╚════════════════════╝              │▓░░▓░▓▓░│  │     (counts on open)
 │  ▲ +37.40 THIS SESSION               └────────┘  │ 96  17px MINT/RED
 │                                       ADD MORE   │ 132 11px MUTED
 │  ┌────────────────────────────────────────────┐  │
 │  │ BOXES 12   HITS 7   BEST +48.00            │  │ 158 15px
 │  │      ▁▂▅▃▇▆█▇█  balance through the run    │  │ 180 sparkline
 │  └────────────────────────────────────────────┘  │
 │                                                  │
 │  CASH OUT SENDS EVERYTHING TO YOUR WALLET  ~4s   │ 248 13px MUTED
 ├──────────────────────────────────────────────────┤
 │ ● < BACK TO PLAY              ◆ CASH OUT >       │
 └──────────────────────────────────────────────────┘
```

- The QR shrinks to a **64px chip in the corner labelled ADD MORE**. It is still
  scannable at 64px for a short EIP-681 URI, still there for a top-up, and no
  longer competing with the thing you came here to do. This single change is
  most of the fix the screen needs.
- The balance is the headline, and it **counts up from the last seen value** when
  the screen opens, so walking in after a good run feels like a good run.
- The session strip gives the run a shape. The sparkline is balance sampled after
  each settle — one list of ints, drawn as a polyline.
- `CASH OUT >` stays in the yellow A slot, where the game's buy button is. Same
  finger, different verb.

**Cap warning.** When the balance is within 10% of `wallet.cap`, the session
strip turns into `NEAR MAX WIN — CASH OUT TO KEEP PLAYING` in YELLOW. Today
that only appears as a fleeting `MAX WIN REACHED / CASH OUT` note mid-game.

### PAYING — fill the network wait with something to watch

```
 ┌──────────────────────────────────────────────────┐
 │                  CASHING OUT                     │ 24px YELLOW
 │                                                  │
 │        ✓  FINISHING THE LIVE BOX                 │ done -> MINT tick
 │        ✓  CLOSING SESSION ON ARC                 │
 │        ⣾  SENDING 137.40 USDC                    │ current -> YELLOW spin
 │           TO amber-otter.tick.eth                │
 │                                                  │
 │  ______                                          │
 │ |  $$  |o=o   armoured truck drives L->R over    │ the game's skyline and
 │ ────────────────────────────────────────────     │ street, reused
 ├──────────────────────────────────────────────────┤
 │                                                  │  no buttons: it is sending
 └──────────────────────────────────────────────────┘
```

Three steps map exactly onto states we already track: `self.cashing` (live box),
`funding.busy` + `status == 'CLOSING'`, and `pending_cashout is not None`. A step
that does not apply (no live box) is drawn already ticked. If Arc is unreachable,
the current step turns RED with `RETRYING ...` and the truck stalls and puffs —
the payout retries on its own, so do not offer a button that implies otherwise.

### RECEIPT — and the hand-off

```
 ┌──────────────────────────────────────────────────┐
 │                   PAID OUT                       │ 22px MINT
 │                 +137.40 USDC                     │ 40px MINT
 │            to amber-otter.tick.eth               │ 15px CREAM
 │  ────────────────────────────────────────────    │
 │   IN 100.00      OUT 137.40      P&L  +37.40     │ 17px
 │   12 BOXES · 7 HITS · BEST WIN +48.00            │ 13px MUTED
 │   TX 0x91ab…77c2                                 │ 11px MUTED
 │                                                  │
 │            YOUR RANK IS UPDATING ▸▸▸             │ 13px YELLOW, marching
 ├──────────────────────────────────────────────────┤
 │ ● HOME                     ◆ SEE YOUR RANK >     │
 └──────────────────────────────────────────────────┘
```

**After 2.5s it advances to the leaderboard on its own**, and A gets there
immediately. This is the requested change: withdrawal ends on the board, not on
a QR code.

`IN` is `sum(s.deposit for s in funding.sessions)` captured before the close;
`BOXES`/`HITS` are `model.rounds` / `model.hits`; `BEST WIN` is the one number we
do not track yet (see §6).

---

## 4. The leaderboard

### Standing layout (unchanged skeleton, more life)

```
 ┌──────────────────────────────────────────────────┐
 │ LEADERBOARD                  YOU  #3  +37.40     │ your rank, always visible
 │                              LIVE FROM tick.eth ●│
 │  #   PLAYER              P&L      BEST WINS PLAYS│
 │ ┌──────────────────────────────────────────────┐ │
 │ │👑1  turbo-lynx     ▐███  +812.00  +90   9  14 │ │ shimmer on #1
 │ │  2  misty-crab     ▐██   +402.50  +55   6  11 │ │
 │ │▶ 3  amber-otter    ▐█    +137.40  +48   7  12 │ │ YOUR row, yellow plate
 │ │  4  neon-yak       ▐     +101.00  +30   4   9 │ │ ▲▼ vs last read
 │ │  5  sly-moose      ▌      -12.00  +18   2   7 │ │ red bar to the LEFT
 │ └──────────────────────────────────────────────┘ │
 ├──────────────────────────────────────────────────┤
 │ ● < BACK                       ◆ REFRESH >       │
 └──────────────────────────────────────────────────┘
```

Cheap additions that make a table feel like an arcade board:

- **P&L bars** behind each row, scaled to the top absolute P&L; mint to the
  right, red to the left of a common baseline. Instant shape, no reading.
- **A crown on #1** and a slow shimmer across that plate.
- **▲2 / ▼1 chevrons** against every row that moved since the previous read, not
  only yours. Held for ~10s after a refresh, then faded.
- Your own name and rank pinned in the **header**, so you never hunt for it.
- When you are outside the visible list your row stays pinned at the bottom
  (today's `YOU_Y` behaviour, which is right) — with the rank counting rather
  than snapping when it changes.

### Arrival mode — the movement, which is the point

The board needs one thing it does not have: **memory of where you were**.

```
 before = the standings snapshot taken when the session opened
          (or the last time this player saw the board)
 after  = the first read whose tick.pnl for your name differs from before
```

Arriving from a cash-out, the board runs a small script:

**Beat 1 — the old world (0.0s).** Draw the *before* rows. Your row sits at #4.
A yellow strip under the header reads `SCORING YOUR RUN ON ENS ▸▸▸` and your
pending delta is ghosted at the right of your row: `+37.40 →`.

```
 │  3  neon-yak       ▐     +101.00                 │
 │▶ 4  amber-otter    ▐      +99.60   +37.40 →      │  ghost delta, pulsing
```

**Beat 2 — waiting (0.0s → up to 45s).** Poll ENS every **3s** instead of 20s
while a result is pending (`BoardFeed` already runs on its own thread; this is a
refresh-interval change). Rows do not update on screen during this — a read that
arrives is held back until the reveal. If 45s pass, the strip changes to
`STILL SCORING — CHECK BACK IN A MOMENT` and the board unfreezes into its normal
live behaviour; the pending reveal is kept in memory and plays whenever the score
does land, even if the player left and came back.

**Beat 3 — the move (~1.1s).** Once the new rows differ:

```
   t=0.00  your plate LIFTS: +2px, shadow, yellow border brightens
   t=0.10  your P&L number starts counting  +99.60 ──► +137.40
   t=0.15  rows tween to their new y positions, ease-out, 700ms
             yours travels UP one pitch, neon-yak travels DOWN one
   t=0.55  rank numbers roll  4 ──► 3  and  3 ──► 4
   t=0.85  your plate LANDS: 3px squash, sparks burst from under it,
             a ▲ UP 1 chevron pops beside the rank and drifts up
   t=1.10  settle. Medal colour applies if you entered the top three.
```

- **Up** gets the rising arpeggio, sparks in YELLOW/CREAM, and the row flashes
  once. Entering the **top 3** upgrades it: the medal colour sweeps in, a short
  fanfare, and a `NEW PERSONAL BEST` / `PODIUM!` floater. Reaching **#1** gets
  the crown dropping onto the plate.
- **Down** is deliberately quiet: the row slides, a muted `▼1`, no sparks, no
  sound beyond a soft thud. Losing should not be celebrated, and it should not
  be punished either.
- **No change** in rank but a better P&L: no move, the number still counts up and
  the bar grows. Something always happens.
- **New player** (no rank before): your row drops in from above the list, stamps
  down, and reads `NEW ENTRY` in yellow. This is a first-timer's first ever
  moment on the board — worth the extra case.
- **Outside the visible list**: the pinned bottom row counts `#12 → #9` with a
  ▲3 chevron. If the move brings you *into* the visible list, the pinned row
  flies up the screen into its new slot and the list opens a gap to receive it.

**Beat 4 — after.** Strip fades. Footer becomes `● HOME  /  ◆ PLAY AGAIN >`,
because the natural thing after seeing your rank is another run. `PLAY AGAIN`
goes to the cashier if the session is closed (it will be), which is face A,
which is the QR — the loop closes.

Same tween machinery runs on ordinary refreshes while the board is open: if
anyone's rank changes, the rows move rather than jump. An arcade board with
other people playing should be visibly alive.

---

## 5. What the player presses, end to end

| where | ● B (red) | ◆ A (yellow) |
|---|---|---|
| HOME · money focused | quit (2x) | cashier |
| CASHIER A · waiting | home | — |
| ARRIVAL | home | **PLAY NOW** |
| CASHIER B · bank | back to play | **CASH OUT** |
| PAYING | — | — |
| RECEIPT | home | **SEE YOUR RANK** (auto in 2.5s) |
| BOARD · arrival | home | refresh |
| BOARD · normal | home | refresh |

Launcher money button label follows the state, as it does now:
`LOAD USDC` → `CASH OUT · 137.40` (today it says `CASH OUT` with the balance
right-aligned; keeping the balance on the button is right).

---

## 6. What this needs that we do not have yet

1. **A before-snapshot.** `BoardScreen` must keep the previous `rows` and, on
   cash-out, the rank/P&L of the player at that moment. In memory is enough for
   the demo; a line in `.tick/` would survive a restart.
2. **A held reveal.** `BoardFeed` currently swaps `rows` the moment a read lands.
   Arrival mode needs the new rows parked in `pending` until the animation runs.
3. **Faster polling while pending** — 3s instead of 20s, only while waiting for a
   score. The scorekeeper writes after the escrow close, so this is usually one
   or two polls.
4. **Row layout as tweenable state** rather than `ROW_Y + i * PITCH` computed at
   draw time: each row needs a current y and a target y.
5. **Best single win** for the receipt and the bank strip: track
   `max(payout)` in `BoxGame.on_result`. One line.
6. **Balance samples** for the sparkline: append `wallet.balance` after each
   settle, cap the list at ~64.
7. **A screen router for the cashier.** Today the wallet is an overlay flag
   (`wallet_open`) inside `BoxGame`. Four faces with timed transitions want their
   own small state machine — likely `screens/cashier.py`, with `BoxGame` keeping
   only the demo loader.

Nothing above touches the escrow, the scorekeeper, or gameplay. It is all
presentation over state that already exists.

---

## 7. Open questions for you

1. **Confirm before cash out?** A press currently ends the session immediately
   and costs gas. A `CASH OUT 137.40?  ◆ YES / ● NO` card adds a dramatic beat
   and prevents an expensive misfire — but it is one more press. Default: no
   confirm, matching the current build.
2. **Auto-advance to the board after the receipt** — 2.5s as proposed, or only on
   a press? Auto is what you asked for; it does take the choice away.
3. **Demo (paper money) funding** — does it get the same four faces, or keep
   today's `+10 / +25 / +100` chooser and just borrow the ARRIVAL beat? Cheapest
   is: keep the chooser, add the arrival.
4. **45s scoring timeout** — is that the right patience before we let the board
   go back to normal and tell the player to look again later?
5. **How many rows?** `TOP = 7` today. The P&L bars and chevrons want a little
   more room; 6 rows at a slightly taller pitch would read better on the 3.5"
   panel. Worth testing on the Pi before deciding.
