# ETH Arcade — 3:40 demo film, first cut

Draft pending your answers about the physical device, friends, available timelapses, personal motivation, and whether the integrated testnet flow is running today.

The story: two monitors become one handheld; a friend plays; a session becomes a payout and an ENS record; then the viewer learns they can build the next game.

## Opening choices

**Recommended — visual contrast:** “Two monitors. Twelve charts. Still bored. So we built this.” Use twelve charts only if twelve are actually shown; otherwise say “Too many charts.”

**More personal:** “I wanted to feel the market. Apparently, I needed a knob.” Close-up turn; hard cut into the game.

**Most instantly understandable:** “What if this…” [charts] “…played like this?” [handheld and a friend leaning in].

Avoid opening with sponsor names or a dashboard tour. Reveal the product by second 10. Say “market-powered arcade,” not “a better way to make money trading.”

## Timecoded shooting script

| Time | Spoken words | Picture, cuts, sound |
|---|---|---|
| 0:00–0:12 | **“Two monitors. Too many charts. Still bored. So we built this.”** | 0–2s wide: you between two monitors. 2–4s chart close-up. 4–6s mouse clicking. 6–8s your expression. Hand reaches forward. Match-cut that hand onto the yellow button. On “this,” reveal ETH Arcade. Dry mouse clicks become the actual button click; music enters. |
| 0:12–0:26 | **“ETH Arcade. A handheld for market-powered games. One knob. Two buttons. And an ETH chart you can actually play.”** | Hero shot in your hands. Macro: knob, buttons, screen. Friend takes it. On-screen words arrive one at a time: TURN / PLACE / PLAY. Product name clearly visible once. Use physical device footage where available; label a 3D render as a render. |
| 0:26–0:46 | **“This is Box Run. That rider follows the price. Turn the knob to place your box. Press yellow to lock it. When the bell rings, price inside: hit. Outside: miss.”** | Real gameplay capture occupies most of the frame. Three punch-ins: rider → cursor → lock. Then show one uninterrupted resolution sequence so the viewer understands the rule. Let the last countdown and bell sound through. Label SIMULATED FEED / DEMO USDC if that is the footage source. |
| 0:46–1:02 | **“Move farther from the price and the odds change. Three hits in a row? The rider catches fire.”** Then one genuine friend reaction. | Split moment: hand turns / quoted odds change. Show an actual hat trick if captured; otherwise use a normal hit and omit the hat-trick sentence. Cut to a friend after the bell. Keep their reaction to 2–3 seconds. Don’t manufacture a winning outcome for the reaction. |
| 1:02–1:18 | **Personal line to confirm:** “I wanted to take something that lives behind a screen and make it something you can hold, hear, and pass to a friend. So we built the hardware, the game, and the tools.” | 3–4 authentic build clips: coding timelapse, case assembly, wiring, testing. Finish on two people passing the device. Use real earlier footage where available; newly filmed work is fine, but don’t present it as an earlier milestone. No made-up build duration. |
| 1:18–1:46 | **“The price comes through The Graph. We use one standardized query across supported DEX subgraphs, then compose Pinax’s Uniswap v3 and v4 Substreams. The same pipeline runs on Arbitrum and Base. Those live pool prices feed the game’s market and odds.”** | THE GRAPH label persists for this beat. 4s: standardized query, highlight token order/decimals. 5s: two imports in the manifest. 5s: two running streams with chain names and current block times. 5s: architecture crop, data → relay → game. 9s: price changing on the actual device/SDK feed with hand on knob. Use live Graph-backed capture for the integration claim, not the browser’s simulated feed. |
| 1:46–2:14 | **“Now, insert coin. Except the coin is USDC on Arc. Scan, send, and the machine credits your session. The escrow reserves the house’s side too. You play off-chain; one close pays the session back to your wallet. And a stuck session has a timeout refund.”** | CIRCLE / ARC TESTNET label. QR scan → actual funding event → coin-drop animation → play → cash-out. Show the matching transaction and recipient for 5 seconds. Brief diagram overlay: FUND → RESERVE → PLAY → PAY OUT. If cutting out waiting time, visibly mark “wait shortened.” Never imply funding, gameplay, and settlement all happened in the length of the edit. |
| 2:14–2:48 | **“Then your name moves. ENSv2 gives each player a name under tick.eth. Your results live in its text records. The scorekeeper can update scores; you can edit your profile, but not your score. The leaderboard reads those records through ENS. That’s a player record other apps can read, not just a name painted on a screen.”** | ENSv2 / SEPOLIA label. Receipt → leaderboard “scoring” state → actual result update. Punch in on the same player’s name. Cut to the resolver’s actual stats record and Arc transaction link. Three-column graphic: PLAYER / PROFILE; SCOREKEEPER / STATS; TEAM / ADMIN. Then show the real record-grant code or transaction. Keep text legible for 4–5 seconds. Don’t promise a rank climb: use the actual result, including a drop. |
| 2:48–3:19 | **“And Box Run is only one idea. We turned these building blocks into a Python SDK. Prices, timing, odds, wallets, controls, and sound are already there. Scaffold a game. Change the rules and the drawing. Run it. Coinflip is one example. What would you build?”** | Docs at /docs/ → `tick new mygame` → a genuine small edit → run the generated game → Coinflip example. Label “edit sped up” when compressing work. Show the terminal command and the resulting game together; don’t substitute an unrelated capture. Cut back to friend for one genuine sentence if strong footage exists; otherwise stay on the working example. |
| 3:19–3:40 | **“We started with a chart. We ended with a machine you can pass around—and tools to make the next game. This is ETH Arcade. Play Box Run. Build yours.”** | 3s timelapse payoff: case closes. 3s friend receives device. 3s real click and grin. 4s clean hero. Last 8s hold the end card with the final verified site URL, /docs/, GitHub QR/link, and all three sponsor names. Music resolves on a button click. |

Timing includes breaths, gameplay sound, friends, and readable proof. Deliver the spoken material crisply; do not stretch every line to fill its slot. If a section runs long, remove a sentence before speeding up the voice. Target about 400–450 narrated words, plus very short reactions.

## Pace that feels fast without losing the demo

- Hook: 1–2 second cuts. Body: mostly 2–4 seconds. Change angle, crop, subject, or visual evidence with each new thought.
- Hold one gameplay resolution and several proof screens longer. Constant one-second cuts would hide the very functionality judges need to see.
- Carry narration across cuts. Use the knob click, confirmation sound, coin drop, bell, and cash-out as transition sounds. Avoid adding a generic whoosh to every edit.
- Use only a few transitions: hard cut, a hand-position match cut, and a punch-in. No elaborate effects needed.
- Duck music clearly under speech and game sound. Give the opening two seconds dry room sound before the track begins.
- Keep captions to one or two short lines, away from game balances, the timer, and the player name. Sponsor titles stay up while their actual integration is visible.
- Every 20–30 seconds, change the kind of picture: face → screen → hands → timelapse → evidence → friend.

## Friends: direct the situation, not the endorsement

Give a friend one instruction: “Play three rounds, then tell me what surprised you.” Film continuously from before the first press until after the bell. Ask one follow-up: “Explain it to the next person in one sentence.”

Possible useful moments are “Wait, I get it,” “Your turn,” or “I moved it too far”—only use them if someone actually says them. A puzzled beat followed by understanding is more convincing than three people saying “amazing.” Two brief reactions total are enough. Get their permission to include their face and voice.

## Film now: efficient capture order

1. **Capture the integrated proof first.** A working feed and a complete session matter more than cinematic B-roll. Record funding through payout and the ENS update continuously as a master. Capture the corresponding wallet, transaction, and resolver views. Edit them later.
2. **Record clean gameplay directly.** Get aim, lock, actual resolution, one miss, and a hat trick only if it occurs. Capture game audio separately from room noise if possible.
3. **Film the friends while they are fresh.** One wide shot with face and device, one over-shoulder angle, then hand/button pickups. Don’t ask them to repeat a supposedly spontaneous reaction.
4. **Film the two-monitor hook.** Locked wide shot, face close-up, chart inserts, mouse, matching hand movement onto device. Use a clean workspace without personal account data.
5. **Film hardware inserts.** Turn the knob, press each button, rear speaker, internals, case closing, pass between hands. 5–8 seconds of each gives editing room.
6. **Capture SDK proof.** Prepare the environment beforehand. Record scaffolding, one small visual/rule change, and the actual resulting game. Keep the Python package/CLI names `tick` intact.
7. **Record narration last.** One section per take, two takes each. Record ten seconds of room tone. Speak to one person rather than presenting to a hall.

If only one camera is available, shoot the session wide first with a simultaneous screen recording. Afterwards capture neutral hand close-ups; don’t use pickups to falsely show a specific transaction or game result.

Use landscape framing for the hackathon film. Hold exposure/focus on the device screen; test for flicker and adjust shutter/frame rate until it disappears. A stable phone and a soft desk light are enough. Record at a readable resolution; use direct game capture for tiny text rather than relying entirely on filming the display.

## Accuracy checks from the current repository

- New firmware includes `MoneyScreen` and the animated `BoardScreen`: insert coin, arrival, cash-out, receipt, scoring state, and rank movement. Their availability in a live setup still needs your confirmation.
- `design/insert-coin/*` contains explicitly labeled proposed mockups. Use actual running firmware for proof; the mockup amounts, player names, and ranks are not evidence of a real transaction.
- The browser game is simulated. Do not intercut its ticker as if it proves a live Graph integration. Label the source whenever it changes.
- Current Arc deployment is testnet. The device flow pays gas in USDC; don’t say it is gasless. A positive session P&L is not a claim that the player made a net profit after funding fees and gas.
- ENS uses one shared PermissionedResolver with scoped permissions and a team administrator. Don’t claim each player has a separate resolver or that the system has no privileged operator. The scorekeeper is not an AI agent.
- The code currently contains standalone firmware `BoxGame`/`BoxModel` classes alongside the SDK. “We turned these building blocks into a Python SDK” is a safer architecture description than claiming this firmware directly imports the `tick.Game` package.
- The example SDK game may use simulated prices; show that label. Prove extensibility with a real scaffold/run, not typing over a prerecorded unrelated window.
- Public domain and repository visibility should be verified before the end card. Local Firebase configuration is not proof that deployment is live.

## Fallback if the integrated flow cannot be recorded today

Keep the physical gameplay, friends, SDK demonstration, and site walkthrough. For sponsor proof, use an authentic previous recording or historical transaction with a visible “recorded testnet session” label. Never animate mock values into an explorer-like view. Without a working provider-backed recording, the Graph segment should explain the implementation and show source, but the submission still needs live integration evidence to meet the supplied requirement.
