# TICK design archive

## Current direction

White FDM case, charcoal painted bezel, existing red/yellow buttons, short side crank, tape assembly, Pi Zero 2 W, 3.5-inch landscape display. Enclosure size and crank attachment are NOT verified; measurements are required before CAD. Older screw-fastened and multi-color renders below are preserved as explorations, not the current build plan.

## Proposals in progress

- [INSERT COIN: the money and leaderboard flow](insert-coin/) — arcade-style deposit and payout, and a leaderboard that climbs your row one place at a time. 480x320 mockups, two animated moves, and the flow in plain words; not built yet. [Contact sheet](insert-coin/contact-sheet.png).

## Saved images and concepts

- [Latest crank / open-back appearance study](practical-crank/assembly.png)
- [Tape-assembled knob exploration](tick-tape-build.png) and [assembly notes](TAPE-BUILD.md)
- [BOX RUN six-step storyboard](box-run-storyboard/round.png) (archived concept)
- [BOX RUN hit/miss explanation](box-run-storyboard/outcomes.png) (archived concept)
- [Original device board](tick-device-concept.png)
- [Cream Cartridge exploration](render-round-2/01-cream-cartridge.png)
- [Graphite Terminal exploration](render-round-2/02-graphite-terminal.png)
- [Four game concepts](render-round-2/04-game-concepts.png)
- [Screen composition study](screen-studies.svg)
- [Initial long-form proposal](DEVICE-CONCEPT.md) and [two-day scope](TWO-DAY-PRODUCT.md)

All completed generated images available from the conversation are now copied into this repository. Some image generation requests were interrupted before returning an output (including the separate in-hand crank view and Orange Sandwich board); there are no completed files for those. Existing prompt files record prompts where available; the interrupted multi-image batches did not retain their prompt store. The render-round-2 README describes those proposed variants even when no image finished.

## Actual software screenshots

[BOX RUN gameplay contact sheet](box-run-live/gameplay-sheet.png) and individual screens in `box-run-live/` are rendered by the implemented pygame game, not imagegen. Recreate with `cd firmware && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python capture_box.py`.

The implemented game is BOX RUN: a box on the ETH price ladder with a 20-second window clock that never stops, priced from measured live volatility and staked in demo USDC. Two archives sit beside it — `box-run-build/` is the original aim/size/confirm version, whose sizing and confirmation steps were dropped, and `rush-build/` is a crank-a-flywheel detour (still runnable with `TICK_GAME=rush`). See [firmware instructions](../firmware/README.md) for running and controls.
