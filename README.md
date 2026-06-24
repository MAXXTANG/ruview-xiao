# RuView on Seeed XIAO (ESP32‑S3 / C6 / C5) + SSD1306 OLED

WiFi **CSI** human‑sensing firmware (presence, breathing, heart‑rate, multi‑person)
running on the three **Seeed Studio XIAO** ESP32 boards, with an on‑board
**0.96″ SSD1306 OLED** (Seeed XIAO Expansion Board) showing live vitals.

This repo is a small set of **additions and fixes** on top of
[**ruvnet/RuView**](https://github.com/ruvnet/RuView) (the `esp32-csi-node`
firmware, MIT). It is **not** a re-host of the upstream tree — it contains only
the files we added, a patch for the few upstream files we changed, the
host-side tools, and ready-to-flash binaries. All credit for the sensing
firmware goes to upstream; see [LICENSE](LICENSE) (MIT, © rUv).

## Status

| Board | Chip | WiFi | Flash / PSRAM | OLED I²C (D4/D5) | Status |
|-------|------|------|---------------|------------------|--------|
| XIAO ESP32‑S3 | Xtensa dual‑core | 2.4 GHz | 8 MB / 8 MB | GPIO5 / GPIO6 | ✅ working |
| XIAO ESP32‑C6 | RISC‑V single‑core | WiFi 6 2.4 GHz | 4 MB / – | GPIO22 / GPIO23 | ✅ working |
| XIAO ESP32‑C5 | RISC‑V single‑core | WiFi 6 **dual‑band** | 8 MB / – | GPIO23 / GPIO24 | ✅ working (needed two C5‑specific fixes, below) |

All three build from the **same source tree** via `idf.py set-target`.

## Quick flash (no build needed)

Prebuilt binaries are in [`prebuilt/`](prebuilt/). Install `esptool` (`pip install esptool`), then:

```bash
# pick your board dir: prebuilt/s3 | prebuilt/c6 | prebuilt/c5
./tools/flash.sh s3 /dev/cu.usbmodemXXXX        # S3 / C6
./tools/flash.sh c5 /dev/cu.usbmodemXXXX        # C5 (uses DOUT@40MHz — see notes)
```

Then provision WiFi + the aggregator target (uses upstream `provision.py`):

```bash
python provision.py --port /dev/cu.usbmodemXXXX --chip esp32s3 \
  --ssid "YourWiFi" --password "secret" --target-ip <your-PC-ip> --edge-tier 2
```

The node streams UDP to `<your-PC-ip>:5005`. Watch it on your computer:

```bash
python tools/udp_receiver.py            # decodes the 32-byte vitals packet (magic 0xC5110002)
```

> ⚠️ ESP32 boards are **2.4 GHz** (S3) / dual-band (C5) — use a 2.4 GHz SSID.
> The SX1262/LoRa and other XIAO add-ons are unused by RuView (it senses on the
> chip's own WiFi radio).

## What's in this repo

```
firmware/main/oled_ssd1306.{c,h}   # standalone SSD1306 OLED task (per-target I²C pins)
firmware/main/cjk_font.h           # optional 16×16 Traditional-Chinese glyph table
firmware/sdkconfig.defaults.esp32c5# C5 target overlay (flash mode/freq, no 802.15.4, …)
patches/0001-*.patch               # our changes to 4 upstream files (main.c, edge_processing.c, CMakeLists.txt, sdkconfig.defaults)
tools/udp_receiver.py              # host-side vitals decoder
tools/gen_cjk_font.py              # regenerate cjk_font.h from a system CJK font
tools/flash.sh                     # esptool wrapper per target
prebuilt/{s3,c6,c5}/               # bootloader + partition-table + ota_data + app
```

## Build from source

```bash
# 1. Clone upstream firmware at the tag these patches were made against
git clone --branch v0.8.2-esp32 https://github.com/ruvnet/RuView.git
cd RuView/firmware/esp32-csi-node

# 2. Add our new files
cp /path/to/ruview-xiao/firmware/main/oled_ssd1306.{c,h} main/
cp /path/to/ruview-xiao/firmware/main/cjk_font.h         main/
cp /path/to/ruview-xiao/firmware/sdkconfig.defaults.esp32c5 .

# 3. Apply our patch to the upstream files (run from the RuView repo root)
cd ../.. && git apply /path/to/ruview-xiao/patches/0001-*.patch && cd firmware/esp32-csi-node

# 4. Build (ESP-IDF v5.4/v5.5)
idf.py set-target esp32s3   # or esp32c6 / esp32c5
idf.py build
```

## Our changes, explained

**New: SSD1306 OLED task** (`oled_ssd1306.c`) — a self-contained I²C task that
polls `edge_get_vitals()` and renders presence / breathing / heart-rate /
person-count. Independent of the upstream RM67162 QSPI/LVGL display path (which
we leave off via `CONFIG_DISPLAY_ENABLE=n` so it doesn't grab `I2C_NUM_0` with
the legacy driver and conflict with our `i2c_master` bus). I²C pins are chosen
per target from the XIAO Arduino variants (S3 5/6, C6 22/23, C5 23/24).

**Fix: DSP task stack 8 KB → 16 KB** (`edge_processing.c`) — headroom; the
pipeline already used ~6.5–7.5 KB.

### The two ESP32‑C5 fixes (the interesting part)

The C5 is newer and was not supported upstream. Two distinct bugs:

1. **ROM boot loop — `SPI flash busy detected(0x1f)` / `TG0_WDT`.**
   This XIAO‑C5's Puya flash will not ROM‑boot at the IDF‑default **80 MHz**.
   Fix: **DOUT mode @ 40 MHz**, baked into `sdkconfig.defaults.esp32c5`
   (`CONFIG_ESPTOOLPY_FLASHMODE_DOUT` + `FLASHFREQ_40M`).

2. **`CPU_LOCKUP` (Illegal instruction) ~3 s after boot.**
   The double‑fault hid the backtrace, so we enabled
   `CONFIG_ESP_PANIC_HANDLER_IRAM` to make the panic handler print, then
   `addr2line` on `MEPC` gave:
   `app_main → mmwave_sensor_init → uart_set_pin → gpio_func_sel`.
   The optional mmWave sensor probe defaults its UART to **TX=17 / RX=18** —
   which on the C5 are the **SPI flash pins** (MSPI `MISO=17`, `WP=18`).
   Reconfiguring the flash data lines as UART corrupts code‑fetch → illegal
   instruction. On S3/C6 those GPIOs are ordinary, so it only bites the C5.
   Fix: `main.c` **skips the mmWave probe on C5** (no mmWave sensor is wired).

> Flashing a C5 that's stuck in a crash‑loop: auto‑reset can't catch it. Use
> `esptool ... --before default-reset` and retry a few times (the USB‑JTAG
> reset eventually wins), or unplug → hold **BOOT** → replug → release.

## Credit

Built on [ruvnet/RuView](https://github.com/ruvnet/RuView) — WiFi CSI spatial
intelligence (MIT). This repo only adds XIAO board support, the SSD1306 OLED
task, and the C5 port fixes.
