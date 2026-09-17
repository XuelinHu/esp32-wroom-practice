# ESP32 audio menu

## 1. Hardware assumption

This project assumes:

- ESP32-WROOM 38-pin development board.
- INMP441 6-pin I2S microphone.
- MAX98357A I2S amplifier and a 4 ohm or 8 ohm speaker.
- Small 4-pin I2C SSD1306 OLED, normally 128x32, address `0x3C`.

The OLED is optional. If its I2C bus is held low, the serial menu and audio tests still work.

## 2. Wiring

### INMP441

| INMP441 | ESP32 |
|---|---:|
| VCC/VDD | 3V3 |
| GND | GND |
| SCK | GPIO26 |
| WS | GPIO25 |
| SD | GPIO33 |
| L/R | GND |

### MAX98357A

| MAX98357A | ESP32 |
|---|---:|
| VIN | VIN/5V |
| GND | GND |
| BCLK | GPIO18 |
| LRC/WS | GPIO19 |
| DIN | GPIO23 |
| SD/EN | GPIO27 |

If the sixth amplifier pin is `GAIN`, do not connect it to GPIO27. Leave `GAIN` in its module-default state. If the module exposes `SD` or `SD_MODE`, connect it to GPIO27.

Connect the speaker only between `SPK+` and `SPK-`. Do not connect either speaker terminal to GND.

### OLED

| OLED marking | ESP32 |
|---|---:|
| VCC | 3V3 |
| GND | GND |
| SCK/SCL | GPIO21 |
| SDA | GPIO22 |

The actual tested wiring is `SCK -> GPIO21`, `SDA -> GPIO22`. The OLED is configured as 128x32. I2C does not reliably report the physical glass resolution, so the height is configured from the module appearance/specification.

All modules must share GND. Disconnect the amplifier and speaker while flashing firmware.

## 3. Flash MicroPython

Only do this if the board is not booting MicroPython or repeatedly reports `flash read err`. Disconnect all external modules first.

```powershell
conda run -n pyg esptool --port COM9 chip-id
conda run -n pyg esptool --port COM9 erase-flash
conda run -n pyg esptool --port COM9 --baud 460800 write-flash 0x1000 ..\ESP32_GENERIC-20250911-v1.26.1.bin
```

If automatic download mode fails: hold `BOOT`, tap `EN/RESET`, keep holding `BOOT`, then run the esptool command. Release `BOOT` after esptool connects.

Flash erase clears files on the board, but not this local `talk` folder.

## 4. Upload the project

Upload the two Python files and the web page:

```powershell
conda run -n pyg mpremote connect COM9 fs cp talk\main.py :main.py
conda run -n pyg mpremote connect COM9 fs cp talk\ssd1306.py :ssd1306.py
conda run -n pyg mpremote connect COM9 fs mkdir :web
conda run -n pyg mpremote connect COM9 fs cp talk\web\index.html :web/index.html
conda run -n pyg mpremote connect COM9 reset
conda run -n pyg mpremote connect COM9 repl
```

If `fs mkdir :web` reports that the directory already exists, continue with the next command. After reset, the board connects to the WiFi configured in `main.py`, synchronizes the clock with NTP, and prints `WIFI_CONNECTED`, `WIFI_IP`, and `WEB_URL`. The OLED shows `WIFI` and the IP address when the OLED is available. If WiFi fails, the board prints `WIFI_CONNECT_FAILED` and continues to the serial menu.

Open the printed `WEB_URL` from a computer or phone on the same WiFi. The page lists the WAV/MP3 files under `/recordings` on the ESP32 and plays them in the browser. After a finite test ends, the OLED returns to the WiFi/IP display.

The page also provides `Start recording` and `Stop recording` buttons. These control the INMP441 directly on the ESP32. Each stopped recording is saved as `/recordings/record_YYYYMMDD_HHMMSS_mmm.wav`, then appears at the top of the playback list. The web recording has a 60-second safety limit and does not initialize the MAX98357A.

Each WAV file also has a `Play on ESP32 speaker` button. This streams the WAV through the MAX98357A. The ESP32 can play WAV files directly; MP3 files are browser-only unless an MP3 decoder is added. The MAX98357A can be powered from 3V3 for a low-volume test, but use `SPK+` and `SPK-` only for the speaker connection.

The page also has `Start ABC music` and `Stop ABC` buttons. ABC music is synthesized on the ESP32 and loops until stopped. Recording, WAV playback, and ABC playback are mutually exclusive to avoid I2S memory conflicts.

The recorder uses MicroPython's tested 16-bit mono I2S mode for the single-channel INMP441 (`L/R -> GND`). It removes slow DC offset and calibrates a conservative noise gate from average background level for 0.5 seconds at the start of each web recording. Playback reads the WAV sample rate, applies 220% digital gain with clipping protection, and sends duplicated stereo frames to the MAX98357A. If the recording is still noisy, verify that `VCC/VDD` is on `3V3`, `L/R` is firmly connected to `GND`, all grounds are shared, and the microphone wires are short. Do not connect the INMP441 VCC to 5V.

`alphabet_announcement.wav` is a known-good 8 kHz mono diagnostic file that speaks the English alphabet from A through Z. If this file is also noisy, troubleshoot the MAX98357A power, speaker, ground, and I2S wiring rather than the microphone path.

The same page also has a local file selector. You can open `talk\web\index.html` directly on the computer and select local WAV/MP3 files for playback; the ESP32 list will only work when the page is opened from `WEB_URL`.

If the board is not connected to WiFi, it displays `HELLO` and `WORLD` instead.

## 5. Menu

```text
1 - OLED display test
2 - Record one phrase (no speaker playback)
3 - Speaker tone test: 880 Hz, 3 seconds
4 - ABC song: loop until Ctrl-C
q - Quit menu and mute amplifier
```

Option `1` displays a large `OLED / DISPLAY OK` message for five seconds. Option `2` only initializes the INMP441, waits for speech, allows up to 30 seconds of recording, and saves a WAV file under `/recordings`. It does not initialize the MAX98357A or play through the speaker. Option `3` isolates the amplifier and speaker. Option `4` plays the ABC melody repeatedly.

Press `Ctrl-C` at the menu to stop the program.

## 6. Save MP3 files locally

MicroPython records PCM/WAV on the ESP32. MP3 encoding is performed on the computer by the provided script, using the already-installed `ffmpeg` executable. After completing one or more option `2` recordings and returning to the menu, close the serial REPL and run:

```powershell
conda run -n pyg python talk\download_recordings.py
```

The script downloads `/recordings/*.wav` from the ESP32 and creates matching `.mp3` files in `talk\recordings`. The WAV files remain on the ESP32 until you explicitly remove them.

The web page is served by the ESP32, so it shows files stored on the ESP32. The computer-side `talk\recordings` folder is a separate local copy created by the download script.

## 7. WiFi and web output

The startup console output should look like this:

```text
WIFI_CONNECTING ssid=ChinaNet-E5y7
WIFI_CONNECTED
WIFI_IP 192.168.x.x
WEB_URL http://192.168.x.x/
WEB_SERVER_STARTED port=80
```

The IP address is assigned by the router and may change after a power cycle. Use the current `WIFI_IP` value printed by the board. The WiFi password is kept in `main.py` and is not printed.

## 8. Troubleshooting

- No menu: verify MicroPython was flashed and COM9 is not open in PyCharm/Thonny/another serial terminal.
- `flash read err`: disconnect all modules, enter BOOT mode, erase and reflash.
- `I2S_INIT_OK` or tone test works but no sound: check MAX98357A VIN/5V, common GND, `SPK+/SPK-`, and the `SD/EN` versus `GAIN` label.
- OLED not shown: power-cycle the board, verify `SCK -> GPIO21` and `SDA -> GPIO22`, and keep audio testing through the serial menu even when OLED is unavailable.
- `WIFI_CONNECT_FAILED`: check the SSID/password, make sure the router is using 2.4 GHz WiFi, and confirm the computer/phone is on the same LAN.
- Browser cannot open `WEB_URL`: keep the serial REPL closed after reset, confirm `WEB_SERVER_STARTED`, and use the exact IP printed by `WIFI_IP`.
