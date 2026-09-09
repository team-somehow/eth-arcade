# TICK design archive

## Current direction

White FDM case, charcoal painted bezel, existing red/yellow buttons, short side crank, tape assembly, Pi Zero 2 W, 3.5-inch landscape display. Enclosure size and crank attachment are NOT verified; measurements are required before CAD. Older screw-fastened and multi-color renders below are preserved as explorations, not the current build plan.

## Saved images and concepts

- [Latest crank / open-back appearance study](practical-crank/assembly.png)
- [Tape-assembled knob exploration](tick-tape-build.png) and [assembly notes](TAPE-BUILD.md)
- [BOX RUN six-step storyboard](box-run-storyboard/round.png)
- [BOX RUN hit/miss explanation](box-run-storyboard/outcomes.png)
- [Original device board](tick-device-concept.png)
- [Cream Cartridge exploration](render-round-2/01-cream-cartridge.png)
- [Graphite Terminal exploration](render-round-2/02-graphite-terminal.png)
- [Four game concepts](render-round-2/04-game-concepts.png)
- [Screen composition study](screen-studies.svg)
- [Initial long-form proposal](DEVICE-CONCEPT.md) and [two-day scope](TWO-DAY-PRODUCT.md)

All completed generated images available from the conversation are now copied into this repository. Some image generation requests were interrupted before returning an output (including the separate in-hand crank view and Orange Sandwich board); there are no completed files for those. Existing prompt files record prompts where available; the interrupted multi-image batches did not retain their prompt store. The render-round-2 README describes those proposed variants even when no image finished.

## Actual software screenshots

[Gameplay contact sheet](box-run-build/gameplay-sheet.png) and individual screens in `box-run-build/` are rendered by the implemented pygame game, not imagegen. Recreate with `cd firmware && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python capture_box_run.py`.

The first implemented game is BOX RUN with simulated prices and practice credits. See [firmware instructions](../firmware/README.md) for running and arrow-only controls.
