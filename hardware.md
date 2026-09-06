# Hardware

Pin map for this handheld: [Waveshare 3.5inch RPi LCD (F)](https://www.waveshare.com/wiki/3.5inch_RPi_LCD_(F)) plus a KY-040-style rotary encoder on a Raspberry Pi 5.

All GPIO numbers below are **BCM**. Board pins are the 40-pin header positions.

## Display — 3.5inch RPi LCD (F)

- Panel: IPS, native **320×480** (firmware runs landscape **480×320**)
- LCD controller: **ST7796S** over **SPI0**
- Touch controller: **GT911** (Goodix) over **I2C**, overlay `goodix` at `0x5d`
- Power: **5V** panel supply, **3.3V** logic

Wiring matches the Waveshare cable pinout, with one change: **backlight is on GPIO12 instead of GPIO18**.

| Function | BCM | Board pin | Notes |
|----------|-----|-----------|--------|
| VCC | 5V | 4 | Panel supply |
| GND | GND | 6 | |
| MISO | 9 | 21 | SPI0_MISO |
| MOSI | 10 | 19 | SPI0_MOSI |
| SCLK | 11 | 23 | SPI0_SCLK |
| LCD_CS | 8 | 24 | SPI0_CE0 |
| LCD_DC | 22 | 15 | Data / command |
| LCD_RST | 27 | 13 | Reset |
| LCD_BL | **12** | **32** | **Moved from Waveshare default GPIO18 / pin 12** |
| TP_SDA | 2 | 3 | I2C1 SDA |
| TP_SCL | 3 | 5 | I2C1 SCL |
| TP_INT | 4 | 7 | Touch interrupt |
| TP_RST | 17 | 11 | Touch reset |

### Diff vs Waveshare wiki

| Signal | Waveshare default | This device |
|--------|-------------------|-------------|
| LCD_BL | GPIO18 (board pin 12) | **GPIO12 (board pin 32)** |

Everything else matches [Method 2: Connect Raspberry Pi through Cable](https://www.waveshare.com/wiki/3.5inch_RPi_LCD_(F)#Method_2:_Connect_Raspberry_Pi_through_Cable).

### Matching `/boot/firmware/config.txt` fragment

```text
dtparam=spi=on
dtoverlay=mipi-dbi-spi,speed=48000000
dtparam=compatible=st7796s\0panel-mipi-dbi-spi
dtparam=width=320,height=480,width-mm=49,height-mm=79
dtparam=reset-gpio=27,dc-gpio=22,backlight-gpio=12
dtoverlay=goodix,addr=0x5d
```


## Rotary encoder

Typical KY-040-style module. Logic at **3.3V only** (do not power from 5V).

| Encoder pin | BCM | Board pin | Role in firmware |
|-------------|-----|-----------|------------------|
| VCC | 3.3V | 1 or 17 | Module power |
| GND | GND | 9 (or any GND) | Ground |
| SW | 16 | 36 | Push button — short = A, hold ≈0.65s = B |
| DT | 20 | 38 | Quadrature B |
| CLK | 21 | 40 | Quadrature A |

Firmware mapping (`firmware/encoder.py`):

| Input | Action |
|-------|--------|
| Turn | Navigate UP / DOWN |
| Short click | A (launch / select) |
| Hold click | B (back / quit) |
