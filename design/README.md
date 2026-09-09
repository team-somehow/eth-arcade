# TICK design archive

## Current direction

White FDM case, charcoal painted bezel, existing red/yellow buttons, short side crank, tape assembly, Pi Zero 2 W, 3.5-inch landscape display. Enclosure size and crank attachment are NOT verified; measurements are required before CAD. Older screw-fastened and multi-color renders below are preserved as explorations, not the current build plan.

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

[RUSH gameplay contact sheet](rush-build/gameplay-sheet.png) and individual screens in `rush-build/` are rendered by the implemented pygame game, not imagegen. Recreate with `cd firmware && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python capture_rush.py`.

The implemented game is RUSH: one continuous crank drives a leveraged paper ride on a read-only price feed, staked in demo USDC. The earlier BOX RUN screens in `box-run-build/` are kept as an archive — its aim/size/confirm flow was dropped because it broke the crank. See [firmware instructions](../firmware/README.md) for running and controls.
