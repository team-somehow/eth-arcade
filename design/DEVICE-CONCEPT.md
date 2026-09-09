# TICK — a pocket market arcade

Design proposal • 9 September 2026 • Working name, not cleared branding.

**Pitch:** Turn a physical crank to play with markets. Two buttons, one tiny screen, and a visible receipt for the onchain action.

The strongest submission is one memorable physical interaction, one excellent game, and one verifiable financial flow. Build NERVE as the hero using the existing sketch, with LONGSHOT as the second cartridge only after the hero works on the actual device. A wide catalogue would weaken the demo.

## What exists and what is proposed

The repository has a pygame launcher at 480×320, a GPIO rotary encoder, and browser sketches of NERVE and LONGSHOT at 400×240. Both sketches generate market movements locally; sponsor names in their logs are not evidence of integrations. Their mathematical models are game prototypes, not production trading engines.

`hardware.md` describes a Waveshare LCD (F) and Pi 5. This proposal targets the user's Pi Zero 2 W. Treat the recorded wiring as a starting point to verify, not an already-tested Zero configuration. The display model still needs confirmation.

## Physical object

Choose a warm cream shell, charcoal bezel, persimmon-orange A button and crank grip. Mint is the screen's success color; amber is attention. This looks like a cherished pocket instrument and makes the moving orange crank easy to see on camera. Avoid glossy finishes, tiny decorative text and thin scanlines.

Provisional envelope: **124 W × 112 H × 30 D mm**, excluding crank. These are packaging targets, not fabrication dimensions. Measure the panel PCB, connectors, cable bends and mechanical stack before CAD. A 3.5-inch 3:2 active area is approximately 74×49 mm; its board may be substantially larger.

| Part | Proposed design | Reason |
|---|---|---|
| Display | Landscape, centered in upper face; matte charcoal surround | Large scene, readable while cranking |
| A/B | Two 15–17 mm caps, about 23 mm center spacing, together at lower left | Left thumb operates both while right hand cranks |
| Home | One small recessed button lower right | Avoid accidental exits; no overloaded A/B hold gestures |
| Crank | Right side, roughly 20–22 mm throw, free-spinning grip | Recognizable silhouette and satisfying winding action |
| Rear | Rounded palm surfaces, service screws, cable strain relief | Comfortable hold and repairability |
| Audio | Small speaker with short bottom slots; amplifier module | Clicks and reward tones reinforce touch |
| Power | Cable-powered first build; rear cable exit | Keeps the first enclosure achievable |

Use a bearing-supported shaft or supported crank bracket so side loads do not bear directly on the encoder module. A basic detented encoder is fine for the first knob prototype; test before using it as a fast crank. Prototype an open arm before attempting a folding hinge. Verify the complete sweep with real fingers: no collision with enclosure, tabletop, cable or left hand. Support the shell with the left palm; test with both small and large hands. Offer a reversed rotation setting.

**Do not add a D-pad or separate knob in v1.** The crank handles menu selection and game adjustment. More controls add wiring, visual clutter and learning time. Make an interchangeable knob cap for development, with the crank as the final hero control.

Optional GPIO proposal, subject to checking the actual overlays: A=GPIO5, B=GPIO6, Home=GPIO13, active-low buttons to ground with pull-ups. Keep existing encoder GPIO21/20/16. These do not overlap the panel pins recorded in `hardware.md`; audio or later peripherals can change that. Keep encoder logic at 3.3V. Drive speakers/haptics through appropriate modules, not directly from a GPIO. Do not finalize a battery or charging design until packaging and power draw are measured.

## The controls must tell the truth

Global: turn to select, A to enter/confirm, B to back/cancel, Home to return to launcher after resolving any active round. During play, returning home must not silently cancel a pending financial operation.

Cranking changes a preview immediately. Financial changes require a clearly labeled confirmation; never send one transaction per encoder edge. Show the accepted value separately while an operation is pending. Every screen has two persistent A/B hints, and the launcher teaches the crank with a short looping animation.

The current encoder converts motion into throttled menu UP/DOWN events. Add a separate signed rotation-delta input for games, plus explicit button-down/up states. Never reuse the menu's queued navigation as a gameplay motion signal: the character could keep moving after the player stops turning. Timestamp inputs, cap unreasonable deltas, and test reversals under fast spinning.

## Game lineup

| Game | Physical interaction | Why it works | Priority |
|---|---|---|---|
| NERVE | Crank sets intensity before a round; A/B balance during play | A tiny courier on a beam is legible and expressive immediately | Hero |
| LONGSHOT | Hold A and wind to aim; release to lock a preview; A confirms | Slingshot-like ritual with a visible target and payoff | Second |
| BOX RUN | Crank moves a price box; A fixes center then width; B resets | Clear interpretation of “box trading”: predict a price range at expiry | Alternative to LONGSHOT |
| MARKET MAKER | Crank positions a band; A changes width; B collects a practice result | Turns liquidity-range management into a tactile puzzle | Later |
| SWAP SHOP | Crank selects quantity; A reviews quote then confirms; B cancels | A useful trading utility and straightforward real financial-flow demo | Optional integration fallback |

### NERVE: preserve the fun, repair the metaphor

The existing game mixes price exposure with player-controlled wobble. A/B cannot magically prevent a real leveraged position from liquidating. For the hackathon, recommend **a clearly labeled practice game driven by market data**, with actual onchain payment for access/data and a verifiable receipt. The game score and payment are separate facts.

Round: select practice intensity → confirm → play for 30 seconds → show score → show receipt. A/B move the courier's balance; market returns animate gusts; intensity narrows the beam. Use a clear practice score, not fictional dollar profit. The crane/beam world should feature a tiny courier, blocks, warning lamps and one expressive fall animation.

If real positions become essential, scope a different mode: crank previews exposure, A submits a change, B requests a reduction/close, and the beam displays actual venue risk. Remove manual balance that changes liquidation. Use venue-confirmed position, fees, margin and liquidation data; the current approximate `1/leverage` model is insufficient. Do not advertise this mode until an execution venue is integrated and tested.

### LONGSHOT and BOX RUN

Keep both as practice predictions initially. LONGSHOT asks whether a defined observed price crosses a threshold during a specified interval. BOX RUN asks whether the expiry price lands in a chosen range. These are different settlement rules. In a real-money version, terms must define the source, timestamps, sampling, boundary equality, stale-feed behavior, payout funding and disputes. A sampled oracle cannot establish every unsampled market touch; label it as observed crossings at the specified samples.

Do not call the sketch's simulated multipliers executable quotes. For the hero demo, a deterministic replay gives a reliable dramatic sequence, with a persistent REPLAY label. Live mode must actually consume live data and show its age. Stop new commitments on stale data; never let visual animation imply fresh prices.

## Screen design at 480×320

Use a full-color pixel world with clean UI text. Reserve roughly 28 px for status and 36 px for controls; let the main scene own the rest. Main numbers should be 28–36 px, primary labels 18–22 px, secondary labels at least 16 px, validated on the physical panel. Touch targets should be about 48 px or larger where possible. Use words and shapes alongside colors.

Three core screens are illustrated in `screen-studies.svg`: cartridge selection, NERVE practice, and receipt. These are exact 480×320 composition studies, not running firmware. The product rendering is an aesthetic concept, not a dimensioned engineering drawing.

Do not stretch 400×240 game canvases into 480×320: their aspect ratios differ. Recompose the scene to the native screen. Nearest-neighbor scaling should apply to sprite artwork; UI text needs its own native-resolution rendering.

States: BOOT → HOME → REVIEW → PLAY → RESULT → RECEIPT. Financial operations separately track READY → SUBMITTING → PENDING → CONFIRMED/FAILED. A confirmed chime plays only after actual confirmation. Repeated taps and retries must not create duplicate purchases.

## Architecture and feasibility

Keep pygame on the Pi. Port only the selected game's mechanics, using a renderer-independent state model. Avoid adding a browser kiosk until a device benchmark justifies it. The Zero 2 W has a quad-core CPU and 512 MB RAM; budget conservatively ([official product specifications](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)).

```text
Buttons / encoder / touch
          ↓
Input adapter → game state → pygame renderer → SPI display
                    ↕ asynchronous messages
              authenticated backend
               ↙             ↘
       market-data adapter   wallet / payment adapter
                                  ↓
                          actual chain receipt
```

Network work never blocks the frame loop. The Pi receives minimal game/feed state; the backend handles authenticated payment intents and deduplication. Pair by a short-lived QR session on the phone. Restrict authorized spend, recipient, expiry and replay; enforce those limits in the backend/wallet controls rather than trusting the device UI. Do not put a master wallet secret on the Pi image.

The repository requests a 48 MHz SPI bus. At 480×320×16 bits, 30 complete frames/s would require about 73.7 Mbit/s before overhead. So 30 displayed full-screen updates/s cannot be assumed at that bus rate. Benchmark actual transfer behavior first: target responsive controls, small dirty regions and modest animation; verify whether the driver benefits from partial updates. Fall back to 15–20 displayed updates/s if necessary while keeping input responsive. Avoid full-screen camera shake, which invalidates most pixels.

## Sponsor strategy

I found the [official ETHOnline 2026 prize list](https://ethglobal.com/events/ethonline2026/prizes). Provisional fit: Hedera's x402 track requires a live gated service through Blocky402 and a real paid request. Privy's financial-flow track requires a wallet and a functional flow; login alone is insufficient. Arc is an alternative for meaningful USDC finance. Confirm chain/provider compatibility before combining them. Pick one primary integration, then one complementary sponsor only if time permits.

Proposed hero flow: authorize a bounded session → purchase a round/data entitlement → play NERVE → open the real payment receipt. Payment unlocks actual service delivery. One purchase per round is easier to demonstrate than pretending to settle every animation tick. Resolve pricing and facilitator support in an early integration spike.

Before submitting, verify event eligibility for pre-existing code and disclose the starter work. The existing repo is a useful base, not proof that all of it was built during the event.

## Build sequence and exit criteria

Timing is provisional until the deadline and team size are known. Work in this order:

1. **Hardware spike — half day.** Boot actual Zero with display/touch; measure refresh, input latency and crank edge loss. Print a full-scale paper faceplate and make a cardboard grip/crank mockup. Exit: two people can play without changing grip awkwardly.
2. **Vertical slice — one day.** Port one NERVE round, add proper input events, launcher, result and sounds. Exit: complete 20 rounds without crash or stuck input, at readable brightness.
3. **Integration spike — one day.** Deliver one real authorized payment and actual purchased service, then receipt. Exit: verify transaction independently; handle rejection, timeout and duplicate button presses.
4. **Enclosure and polish — one day plus fabrication lead time.** Fit boards, strain relief and supported crank; sand/finish shell, add simple labels. Exit: 30-minute session without loose mechanism or thermal/power faults.
5. **Demo rehearsal — half day.** Film, verify submission evidence, prepare explicitly labeled replay and connection recovery. Add second game only if all previous exits pass.

If time collapses, cut battery, folding crank, haptics, second game and extra sponsors. Preserve the physical crank, hero game and one real payment flow. Do not order a full enclosure before measuring the exact display assembly.

## Camera and judging plan

Opening line: **“We built a pocket market arcade. Turn the crank, play a round, and see exactly what the device paid for.”**

- 0–10s: macro of crank and audible button press, then full device in hands.
- 10–30s: select NERVE, show the bounded purchase and begin play.
- 30–60s: one complete round, large visual tension, satisfying result.
- 60–80s: real receipt and the corresponding explorer/backend evidence.
- 80–110s: simple architecture and why programmable payment matters.
- Final seconds: another person picks it up and understands the controls.

Film from front-right so the crank remains visible. Use diffuse light, lock exposure/focus and test shutter settings against screen flicker. Use large sprite motion, short tones, stable UI and minimal glare. Capture a direct screen recording alongside the physical shot, but show the actual device working. Never present replay as live or pending as confirmed.

Success measures: understandable interaction within 10 seconds; complete playable round within 30 seconds; visible button feedback targeted under 100 ms and measured; no stuck input; no duplicate purchases; one independently verifiable transaction; legible screen in the final camera framing.

## Remaining decisions

Confirm sponsor priorities, deadline/team, exact display model, fabrication access and whether genuine trading positions are essential. Default recommendation: physical NERVE practice arcade with real paid data/access. Keep the proposed trading modes in the design, but earn the live-finance claim with an actual supported integration.
