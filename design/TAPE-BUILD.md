# TICK — practical tape-assembled prototype

This replaces the screw-fastened enclosure proposal for the two-day build. The accompanying render is an appearance concept; it does not establish component fit or provide printable CAD.

## Simplify the object

- One open printed tray, with flat walls and gently chamfered corners.
- One flat front panel with a rectangular display window and two button holes.
- One flat removable rear cover, attached with short replaceable tape strips.
- A short rotary knob on the right side. Defer the projecting crank until its shaft attachment and support are proven.
- External cable power through an oversized edge notch. No battery packaging or charging work.

Use whatever filament is already available. Cream face / orange tray / dark tape is the visual direction, but a single-color print with neatly trimmed tape also works. All panels are separate pieces; no multi-color printer is required.

## What holds each part

| Part | Practical retention concept | Must check |
|---|---|---|
| Display | Broad internal ledges support the assembly; small retaining pieces or tape attach to suitable non-active frame/PCB margins | No pressure on glass, touch surface, ribbon or exposed components |
| Pi | Insulating support under suitable board edges; accessible connectors | Keep metal contacts isolated, chips uncovered, and tape away from hot components |
| Button switches | A support shelf behind each switch carries pressing force; retain switch body against shelf | Actual switch dimensions and travel; tape alone must not take the repeated press load |
| Encoder | A shaped cradle supports the body with a strap/tape retaining it | Body geometry, wire clearance, shaft length, and resistance to rotation |
| Knob | Short lightweight cap matched to the actual shaft | Shaft profile and fit coupon; no forced fit onto unknown hardware |
| Panels | Panels rest on ledges; short external tape strips keep them seated | Tape must not obstruct screen, controls, cable or ventilation |

Tape retains parts against physical supports; it should not be the only structure resisting button or knob forces. If suitable internal supports cannot be printed in time, use a larger enclosure with accessible foam/card insulating spacers and verify they do not obstruct cooling or damage connectors. Test adhesive on a spare printed patch before choosing strip length.

No screw holes, threaded inserts, magnets, folding hinge or tight sliding lid are required. A lift-off cover avoids spending time tuning sliding tolerances. Use short tape tabs that can be replaced after opening, rather than wrapping the whole device shut.

## Fit before finish

Do not use a fixed outer dimension from an earlier render. Measure or obtain the actual parts first:

1. Display PCB width, height and complete depth, including connectors; active screen position relative to the board.
2. Pi assembly height including its header and attached plugs.
3. Button body dimensions, cap diameter and travel.
4. Encoder body dimensions, shaft diameter/profile, protrusion and wiring.
5. Cable paths with real connectors inserted and relaxed bends.

Lay the parts on paper at full scale. Prefer side-by-side board placement if stacking squeezes cables; allow the shell to become wider/deeper. Print the front window/button layout and encoder cradle as small fit checks before printing a full tray. Add assembly clearance based on those checks rather than promising an arbitrary tolerance.

The board layout inside the render is illustrative. It must not be copied as a verified electronics mounting arrangement.

## Controls and look

Two front buttons, A/B, both at lower left; short right-side knob. Home is reached through B from menus, so there is no third physical button to source. During an active round, B follows the game's explicit state rules rather than silently abandoning a pending operation.

Keep BOX RUN as the first screen: a large ETH price trace, one target box and countdown. Crank-like winding becomes knob rotation with the same software input. The knob is the practical v1 control; a crank can be added later after the mechanism is tested.

Use two neat dark tape tabs on blank face margins below the display as a visible intentional detail. Rear cover tabs can be less decorative. Prioritize a clean screen window, straight tape edges and reliable controls over hidden assembly.

## Two-day assembly check

Before filming: repeat button presses and knob reversals, inspect internal movement, confirm wires are not trapped, run the display/game long enough to check heat and adhesive movement, and reopen the cover once to ensure service access. Check screen readability and touch without pressing on the glass. This is a bench-tested hackathon prototype, not a rugged consumer enclosure.
