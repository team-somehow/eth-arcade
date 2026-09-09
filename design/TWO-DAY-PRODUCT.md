# TICK — two-day product direction

This supersedes the scope and priorities in DEVICE-CONCEPT.md. Deadline: two days. Enclosure and control caps: 3D printed. Product first; prize targeting deferred.

## Product

A tiny crypto trading arcade, styled like a pocket terminal from an alternate 1989. The screen is a miniature exchange: pixel candles, ETH-shaped cargo, block-height counters and a courier working the night shift. Physical winding is the signature interaction.

Keep the cream, charcoal and orange physical direction. Use filament colors for the finish: cream body, separate charcoal bezel, orange button caps and crank grip. Mint/amber/red live on the display. Print a small raised TICK wordmark, not fine engraved paragraphs. No paint-dependent finish, folding crank, battery development or extra controls in the critical path.

## One cartridge: BOX RUN

Recommendation for the deadline: one price-box prediction game. It gives the crank a continuous, obvious role and makes the crypto theme understandable without explanation. NERVE remains an existing prototype to reuse or revisit, not a second required deliverable.

The screen has a price trace on the left and a target box at a fixed expiry line on the right. Vertical position means price; horizontal movement means time. A ghost candle shows where the latest observed price would land. The interaction is:

1. Turn the crank to move the target box up/down relative to the current ETH price.
2. Hold B while turning to change its width. A thinner box earns more practice points; always display the points before committing.
3. Press A to lock the prediction and start a 20-second round. No purchase occurs merely by rotating.
4. During the round, the crank scrubs the already-observed trail; releasing it returns to the latest price. The committed box never moves. B returns immediately to the latest view. A has no trading action while locked.
5. At expiry, the selected observed price lands inside or outside the box. A hit stamps a pixel block onto a small tower; a miss cracks it. Show one large result and A AGAIN / B HOME.

The width modifier needs a prominent B + TURN hint and a brief first-run tutorial. If simultaneous input support takes too long, use A to advance CENTER → WIDTH → LOCK, with B back. Choose the latter for the first implementation because the current input layer lacks explicit held-button events. Two front buttons plus crank are enough.

Use practice points initially. Labels distinguish LIVE DATA, REPLAY and SIMULATED. A blockchain-shaped icon is thematic; a verified transaction is a separate implemented feature. Never imply that simulated points are tokens or settled funds. If actual trading is required, decide that before writing a settlement system: it changes the two-day scope materially.

## Print-friendly construction

Print a shallow front shell and removable rear cover; use accessible screws and available inserts or an appropriate self-tapping design. Avoid unsupported large bridges, fragile clips, hidden fasteners and cosmetic grooves that demand post-processing. Orient the visible face for the best available printer finish. Choose wall thickness, clearance and support based on the actual printer/material and a small fit coupon, not an assumed universal tolerance.

Measure the display PCB and mounting holes, Pi/header stack, wires and encoder before the first enclosure print. Use the earlier 124×112×30 mm only as a rough envelope. Position both buttons lower left and the crank shaft on the right, with clearance for the complete handle sweep. Print a faceplate and crank coupon first; hold them in both hands before committing to the shell.

Use a short rigid crank arm with a separate freely rotating grip secured by available screw/shaft hardware. Support the rotating shaft against side loads. The arm and grip can be printed; do not assume a printed bearing or encoder PCB alone is a durable mechanical support. Keep an ordinary printed knob as the fallback. A smooth knob that works is preferable to a crank that binds during the demo.

Cable power, strain relief and a serviceable rear cover are v1. Sound is optional if the speaker hardware is already available. Skip custom haptics and battery charging work.

## Two-day schedule

Hours are elapsed planning blocks, adjusted for printer time and sleep. Start physical measurements immediately; print while developing software.

- First 3 hours: freeze the screen and controls; measure parts; make fit coupon/faceplate; test panel refresh and encoder input.
- Rest of day 1: implement CENTER → WIDTH → LOCK → ROUND → RESULT; deterministic labeled demo data; start first enclosure print; assemble and test grip.
- First half of day 2: fit corrections and final print; add a real read-only crypto price source if feasible; refine text, sprite animation and result sound. Preserve working replay mode.
- Final half of day 2: stop adding features; assemble, run repeated rounds, verify reconnect/restart behavior, film the physical demo and package the code.

Definition of done: powers up into one playable crypto-themed game; every control is understandable; crank motion is immediately visible; enclosure survives repeated handling; screen reads on camera; full round works reliably; data mode is honestly labeled.

## Visual direction

Launcher: a large pixel ETH cargo crate and BOX RUN title, with TURN TO AIM / A START.

Game: dark navy exchange floor; cream price trail; mint target outline; amber time strip. Large 20s countdown. No tiny candlestick dashboard, wallet address or sponsor logos in the play area.

Result: BLOCK LANDED or OUT OF RANGE, score, a stamped block added to the tower, and restart. Avoid calling the result a mined or confirmed blockchain block unless that event actually exists.

Opening demo sentence: “This is TICK. You crank a prediction into place and watch the crypto market land inside it—or miss.”
