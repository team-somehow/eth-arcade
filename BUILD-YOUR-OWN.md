# Build your own ETH Arcade

This guide follows the handheld described on the landing page: a Raspberry Pi
Zero W, a wired 3.5-inch 480 × 320 landscape display, a right-side KY-040 knob,
red and yellow buttons, a rear speaker, and a battery inside a two-part printed
press-fit shell. It runs **Box Run with ten-second rounds and paper USDC**.
The Graph, Arc testnet, and ENS integrations can be added after the device works.

**Go straight to:** [display wiring](#4-prepare-the-pi-and-display) ·
[controls and wiring order](#5-wire-and-check-the-controls) ·
[speaker and power](#6-add-the-rear-speaker-and-battery) ·
[CAD downloads and print instructions](design/cad/README.md).

## 1. Understand what is ready

The game, input readers, enclosure source, and printable shell files are in this
repository. There is not yet a fully specified, verified Pi Zero W assembly:

| Part | What the repository supplies | What you must verify |
|---|---|---|
| Shell | 104 × 110 × 40 mm body and lid; 2.5 mm walls; 3 mm fillets; nominal 5 mm overlap and 0.3 mm clearance | Fit of your actual boards, connectors, switches, and printer tolerances |
| Pi | Landing page specifies Zero W / 512 MB | OS compatibility, GPIO access, and performance on that board |
| Display | Wiring for a Waveshare 3.5inch RPi LCD (F), ST7796S, with backlight moved to GPIO12 | Driver setup on your OS and board, rotation, and redraw speed |
| Power | Battery and charging circuit shown in the landing-page model | Exact cell, protection, charger, regulated supply, switch, and mounting |
| Sound | Synthesized cues and music in firmware; grille in lid | Audio interface, amplifier, speaker, and available space |

The CAD's mock Pi is still **85 × 56 mm**, and comments describe a USB-C cable
exit. Do not use that mock board as a Zero W mounting template. The shell has
flat internal faces, not a completed set of component mounts. Battery and audio
electronics are also not specified by a tested wiring diagram. Resolve these
items on the bench before committing to the final enclosure.

## 2. Gather the parts

Use this as a parts checklist, then measure the exact components you have.
It is not a supplier-specific shopping list or a guaranteed price quote.

| Quantity | Part | Fit or connection requirement |
|---|---|---|
| 1 | Raspberry Pi Zero W with a populated 40-pin header | The board named on the landing page; retain access to power and microSD |
| 1 | microSD card with a Pi Zero W-compatible Raspberry Pi OS image | Use an OS/Python combination capable of running the repository; Python 3.11+ for the SDK |
| 1 | 3.5-inch IPS display and cable | Reference: Waveshare RPi LCD (F), native 320 × 480, rotated to landscape |
| 1 | KY-040 encoder and fitting knob | Side opening is nominally 12 mm square; check shaft and board clearance |
| 2 | Momentary switches, one red and one yellow | Nominal 13 mm square openings, 26 mm between centres; two switch leads each |
| 1 set | Speaker plus compatible audio output and amplifier | Mount behind the lid grille; confirm electrical ratings and depth |
| 1 set | Li-ion battery, protection/charging and regulated 5 V power system | Match cell chemistry, charge current, load capability, and connector polarity |
| 1 each | Printed body and lid | Files linked below |
| As needed | Insulated wires, connectors, insulating sheet, adhesive mounts and strain relief | Keep exposed contacts off adjacent boards and the battery |

You will also need a computer, a microSD writer, calipers, a soldering iron,
a multimeter, and access to an FDM printer. Start with an external regulated
power supply; add the battery once display, controls, and sound work.

## 3. Run the actual game on a computer first

From the repository root, on macOS or another desktop where pip pygame works:

```sh
cd firmware
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
TICK_GAME=box TICK_ASSET=eth TICK_FUNDING=demo TICK_MARKET_SOURCE=sim TICK_STAKE_USDC=10 python main.py
```

On Linux, the display bootstrap can switch to system Python; use the system
pygame installation described in the Pi step below if that happens.

Select PLAY. Hold Up/Down to move the box, press Enter or Space to buy, and
press Backspace to return. Escape exits. Buying fixes the box for that window;
pressing again adds stake to the same box. The clock keeps rolling every ten
seconds. At the bell, only the settlement price inside the box wins.

Use the native firmware for the full Box Run experience shown on the device.
The [browser demo](site/src/game/engine.ts) is a separate implementation with
simulated prices and paper money. The SDK's Ladder example is another starting
point, rather than the complete Box Run launcher and presentation.

## 4. Prepare the Pi and display

Flash the compatible OS image, configure Wi-Fi and a login, boot the Pi, and
copy or clone this repository onto it. On Raspberry Pi OS, install the system
display and GPIO dependencies:

```sh
sudo apt update
sudo apt install python3-pygame python3-gpiozero python3-lgpio
```

Use system `python3` for paper play on the panel. A pip pygame wheel can lack
KMSDRM support; the firmware deliberately switches to system Python in that
case. The Arc/QR libraries in `requirements.txt` are optional for this stage.

Wire and configure the display using [hardware.md](hardware.md), matching your
exact panel. That document records a prior Pi 5 installation; its overlay
fragment is a reference to adapt and verify, not a tested Zero W OS image.
Get a stable image on the display before debugging the game.

The documented reference wiring is:

| Display signal | BCM GPIO / supply | Physical header pin |
|---|---|---|
| VCC / GND | 5 V / ground | 4 / 6 |
| MISO / MOSI / SCLK | 9 / 10 / 11 | 21 / 19 / 23 |
| LCD_CS / LCD_DC / LCD_RST | 8 / 22 / 27 | 24 / 15 / 13 |
| LCD_BL | **12** | **32** |
| TP_SDA / TP_SCL | 2 / 3 | 3 / 5 |
| TP_INT / TP_RST | 4 / 17 | 7 / 11 |

The landing page calls the display connection a 26-pin interface. That does
**not** mean all connections fit on the first 26 Pi header pins: this wiring
moves the backlight to physical pin 32, and the controls also use later pins.
Check cable orientation and continuity before applying power. Do not assume
an unmodified display cable already includes the GPIO12 backlight change.

### Connect the display cable

1. Unplug external power and disconnect the battery. Locate physical pin 1
   using the Pi board's pin-1 marking or board documentation. Count physical
   positions from that end: odd pins are in one row, even pins in the other.
   The tables describe the Pi header, **not** the numbering of the connector
   on the display. Viewing the back of a connector mirrors its layout.
2. Identify each display lead by its signal name or cable continuity, not wire
   colour. Connect VCC to physical pin 4 and GND to physical pin 6. The panel
   supply is 5 V; that does not make its signal pins 5 V tolerant.
3. Connect the three SPI leads: MISO → pin 21, MOSI → pin 19, SCLK → pin 23.
   Connect CS → pin 24, DC → pin 15, and RESET → pin 13.
4. Route the backlight lead to **physical pin 32 / GPIO12**. In this build it
   must not remain connected to physical pin 12 / GPIO18 as well. Use a
   breakout or individually routed leads if the stock cable cannot provide
   the documented mapping.
5. Connect the touch leads: SDA → pin 3, SCL → pin 5, INT → pin 7, RESET →
   pin 11. Keep the LCD reset and touch reset labels distinct.
6. With power still disconnected, check continuity from each display signal
   to its intended Pi pin and check for accidental solder bridges. Configure
   the matching display overlay, then power up and verify the panel before
   adding the controls. Disconnect power again before changing any wiring.

The display needs a cable connection so the Pi header remains accessible to
the controls. A full-size header breakout can make the shared connections
easier to assemble; include its height and cables in your enclosure fit check.

## 5. Wire and check the controls

Disconnect power while wiring. These are **BCM GPIO numbers** with physical
header positions listed separately. Power the encoder logic from **3.3 V**.

| Part / lead | BCM GPIO / supply | Physical header pin |
|---|---|---|
| Encoder VCC | 3.3 V | 1 or 17 |
| Encoder GND | Ground | 9, or another ground |
| Encoder CLK | 21 | 40 |
| Encoder DT | 20 | 38 |
| Encoder SW | 16 | 36 |
| Red switch | 13 → switch → ground | 33 → switch → 34 or 39 |
| Yellow switch | 26 → switch → ground | 37 → switch → 34 or 39 |

The switches use internal pull-ups; each press connects its GPIO to ground.
The encoder click is A; holding it for about 0.65 seconds and releasing is B.
Yellow is A, red is B. Sources: [encoder.py](firmware/encoder.py) and
[buttons.py](firmware/buttons.py).

### Connect one control at a time

1. Mount the encoder so its shaft exits the right wall, leaving its solder
   joints accessible. Read the module labels: KY-040 boards can arrange their
   terminals differently. Connect `+` / VCC → physical pin 1 and GND → pin 9.
2. Connect CLK → pin 40, DT → pin 38, and SW → pin 36. Insulate the joints and
   leave enough slack to remove the case lid without pulling on them.
3. Connect one red-switch contact to pin 33 and the other to ground pin 34.
   Connect one yellow-switch contact to pin 37 and the other to ground pin 39.
   The two contacts of an ordinary unlit switch have no polarity. If your
   switch has extra LED terminals, identify the actual switch contacts with
   continuity testing; the firmware wiring here does not power the LED.
4. Check that each switch is open at rest and closes to ground when pressed.
   If a switch has four legs, identify the switched pair with the meter;
   two legs may already be connected internally.
5. Check against this control harness sketch, then power up and test. Stop the
   game and disconnect power before correcting a connection.

```text
Pi physical pin                  Control terminal
 1  (3.3 V) -------------------- encoder VCC / +
 9  (GND) ---------------------- encoder GND
40  (GPIO21) ------------------- encoder CLK
38  (GPIO20) ------------------- encoder DT
36  (GPIO16) ------------------- encoder SW

33  (GPIO13) -------- [ red switch ] -------- 34 (GND)
37  (GPIO26) -------- [yellow switch] ------- 39 (GND)
```

All listed ground pins share the Pi's ground. Use proper branches or a
distribution connector if multiple wires need the same ground connection;
do not force two loose connectors onto one header pin. Keep the knob and
switch wiring clear of the lid's press-fit lip.

Run from the Pi's local desktop session, with the same demo settings:

```sh
cd firmware
TICK_GAME=box TICK_ASSET=eth TICK_FUNDING=demo TICK_MARKET_SOURCE=sim TICK_STAKE_USDC=10 python3 main.py
```

Without a desktop, use a local console and set
`SDL_VIDEO_KMSDRM_DEVICE_INDEX` to the actual panel's DRM card index. The code's
fallback is `2`, inherited from the Pi 5; determine your index from `/sys/class/drm`
and the connected display instead of assuming it applies. Use `TICK_ROTATE=90`
or `270` if automatic portrait-to-landscape rotation is wrong.

Check slow detents, fast turns, both buttons, and short/long encoder clicks.
The game remains playable by keyboard when GPIO initialization fails, so a
working screen alone does not prove that the controls opened. Check the
system GPIO libraries and pin ownership if turning the knob has no effect.

## 6. Add the rear speaker and battery

Choose and bench-test an audio path before making its mount. The repository
does not supply a complete Zero W speaker circuit. An audio interface with
a compatible amplifier can drive the rear speaker; a bare speaker cannot be
connected directly to a GPIO pin. Confirm the chosen interface works through
the OS sound output, then check the game's detent clicks and music.

The device notes identify an I²S pin conflict: that audio path needs GPIO21,
which is already encoder CLK. If you choose I²S, resolve the entire pin map
and update the encoder reader before connecting it. Preserve the documented
pin map by using an audio path that does not claim those pins. Account for
its adapters, amplifier, and cables when checking the shell fit.

For portable power, the intended functional chain is:

```text
charging input → cell-compatible charger / power management ↔ protected Li-ion cell
                                  ↓
                       regulated 5 V → Pi and display
```

Implement this with a specified power system whose documentation covers your
cell and combined load. A charging board alone does not establish a regulated
5 V supply or safe operation while charging. If charging during play is
required, use a system designed for that power-path behavior. Check output
voltage and polarity before connecting the Pi, then test display and audio
under load. Do not connect a raw cell to the Pi's 5 V input or parallel two
power sources without a power system designed for it.

Leave space for insulated battery mounting without compression, wire strain
relief, and access to the charge connector. Shut down the OS before cutting
power. Battery runtime and charging behavior remain measurements for your
chosen assembly; the repository supplies no verified figures.

## 7. Print and assemble the landing-page shell

Use these files, rather than the older tape-build appearance studies:

**[Open the CAD download and printing page](design/cad/README.md)** for a
file-by-file checklist, previews, print quantities, and export commands.

- [3D OpenSCAD source](design/cad/tick-case-3d.scad)
- [Body STL](design/cad/tick-body.stl) and [lid STL](design/cad/tick-lid.stl)
- [Body 3MF](design/cad/tick-body.3mf) and [lid 3MF](design/cad/tick-lid.3mf)
- [Exploded view](design/cad/exploded.png) and [section view](design/cad/section.png)
- [Optional loose locator brackets](design/cad/tick-bracket-l-x4.stl)

Measure the display PCB and visible area, switch bodies, encoder shaft, Pi,
battery, speaker, and plugged-in connectors. The CAD assumes a 92 × 60 mm
screen module and a 79 × 49 mm visible opening. Adjust the named constants
and connector opening to your measured parts. The body/lid are the two shell
parts; the loose brackets are optional additional prints for internal mounts.

If you edit the model, regenerate the meshes from the repository root with
OpenSCAD installed:

```sh
openscad -o design/cad/tick-body.stl -D 'VIEW="print_body"' design/cad/tick-case-3d.scad
openscad -o design/cad/tick-lid.stl -D 'VIEW="print_lid"' design/cad/tick-case-3d.scad
```

The source provides front-face-down body and back-face-down lid orientations,
intended to print without supports. Check the slicer preview and start with
a fit sample of the tongue/socket and control openings. The nominal 0.3 mm
clearance is a CAD parameter, not a proven fit for every printer/material.

Dry-fit the display behind the front window, buttons through the front, and
encoder through the right wall. Add insulated mounts or glued locator
brackets so button presses and knob loads cannot shift the boards. Mount the
speaker behind the grille and arrange Pi, power electronics, and cell around
the actual cables. Keep the lid's tongue area clear. Test everything with the
case open, then press the lid into place without trapping wires or loading
the display or battery. The shell closure needs no screws; it does not itself
secure the components inside.

## 8. Match the landing-page play mode

In `firmware/`, copy `.env.example` to `.env` if you have no local settings yet,
and edit these entries:

```dotenv
TICK_GAME=box
TICK_ASSET=eth
TICK_FUNDING=demo
TICK_MARKET_SOURCE=coinbase
TICK_STAKE_USDC=10
```

Run `python3 main.py` from that directory. Coinbase is the implemented read-only
feed polled at 5 Hz; it requires network access. Use `sim` for offline play.
The simulated feed runs at 20 Hz, and Substreams is block-driven, so the
landing page's 5 Hz figure does not describe every adapter.

Set the stake explicitly: the example `.env` uses `0.5`, while the code's
default is `10`. Also avoid assuming the packaged `.deb` has the landing-page
money settings: it defaults to Arc testnet and a `0.001` stake. Source launch
with the configuration above gives paper play.

In [box_model.py](firmware/games/box_model.py), the ten-second window scales
the reference geometry by `sqrt(10 / 20)`. At $2,500 ETH, the resulting box
height is about $1.41, each step $0.18, and reach ±$2.12. These scale with
price. Quotes react to measured volatility, with a 1.05× floor and 25× cap;
the landing page's 1.5× / 5× / 25× ladder is illustrative.

## 9. Add the integrated backend, if wanted

The base handheld does not need keys or a contract deployment. To reproduce
the landing page's infrastructure demonstration as well, add these in order:

1. **The Graph price pipeline:** follow [substreams/README.md](substreams/README.md)
   to configure keys and pools, compile the Rust module, and run `relay.py` on
   a laptop/server. Set `TICK_MARKET_SOURCE=substreams` and
   `SUBSTREAMS_BASE_URL=http://<relay-machine-address>:8787` on the Pi. Use the
   server's LAN address, not `localhost`, when it is a different machine.
   Verify `/stream` delivers fresh data; keep credentials on the relay host.
2. **Arc testnet settlement:** follow [contracts/README.md](contracts/README.md)
   and the [firmware money instructions](firmware/README.md#money) for the
   escrow setup, house reserve, Python dependencies, and device funding.
   Change to `TICK_FUNDING=arc-testnet` and a small stake such as `0.001` only
   when deliberately testing this flow. Fund from a wallet you control and
   verify cash-out back to that wallet. Preserve the device key and session
   state in `firmware/.tick/` across restarts.
3. **ENS identity and leaderboard:** follow [ens/README.md](ens/README.md) to
   configure the Sepolia registry/resolver and run the scorekeeper that watches
   Arc events. Verify a closed session appears in ENS and on LEADERS. Enabling
   Arc funding alone does not provision the scorekeeper. The launcher can
   start it automatically when the required keys and Python dependencies are
   already present; see [keeper.py](firmware/keeper.py). Run one scorekeeper
   for the deployment. If it runs on a separate host, set `TICK_SCOREKEEPER=0`
   on the handheld.

The integrated demonstration uses Arc testnet and ENSv2 on Sepolia. Rounds
run off-chain, and the device reports the final balance; the escrow enforces
session payment rules rather than independently verifying each game round.

## 10. Check the completed build

- The display fills a 480 × 320 landscape canvas with legible text.
- Each detent moves the box; yellow buys; red returns; encoder clicks work.
- Buying locks the box, additional presses add stake, and the ten-second clock
  rolls continuously. A hit pays and a miss loses the stake.
- Disconnecting a live feed blocks stale-price bets; a window with no valid
  post-bell price is voided and refunded after the settlement timeout.
- You hear entry/exit swoops, pitched countdown, win/miss cues, and the changing
  music beds through the rear speaker.
- The closed case leaves controls free, supports their loads, and does not
  pinch wiring or press on the cell. Test portable power and charging using
  the chosen power system's instructions.
- If using the backend, verify deposit → play → cash-out → ENS update, then
  restart and confirm the stored device identity/session state is retained.

Software regression checks can be run from `firmware/` in an environment with
its dependencies installed:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover -s tests -v
```

Those tests do not certify electrical assembly, physical fit, or Pi Zero W
frame rate. Measure those on the finished device before calling it complete.

To make your own game afterward, start with the [SDK installation](sdk/README.md#install)
and [game-writing tutorial](sdk/docs/writing-a-game.md). The SDK supplies the
price, timing, wallet, input, and sound building blocks advertised on the page.
