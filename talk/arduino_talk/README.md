# ESP32 Arduino audio controller

This is the Arduino C++ rewrite of the `talk` MicroPython application. It targets
an ESP32-WROOM 38-pin development board and uses the currently installed Arduino
ESP32 Core `3.3.11`.

## Features

- INMP441 recording through native ESP32 I2S0, saved as PCM16 mono WAV.
- MAX98357A WAV playback and looping ABC melody through native ESP32 I2S1.
- SSD1306 128x64 display with automatic multi-frame blinking plus happy, angry, crying, and neutral expressions.
- Four continuous-rotation servo drive with hold-to-move web controls and safety timeout.
- WiFi web page embedded in the firmware.
- LittleFS recording list, browser playback, upload, delete, and speaker playback.
- Single-recording storage: a new recording removes the previous `record_*.wav` first.
- Serial menu and HTTP APIs use the same implementation paths.
- Recording, WAV playback, and ABC playback are mutually exclusive.

## Wiring

Disconnect every peripheral while uploading firmware. Reconnect one module at a
time after the bare ESP32 boots successfully.

### INMP441

| INMP441 | ESP32 | Voltage / purpose |
|---|---:|---|
| VDD/VCC | 3V3 | 3.3V only; never 5V |
| GND | GND | Common ground |
| SCK | GPIO26 | I2S bit clock |
| WS | GPIO25 | I2S word select |
| SD | GPIO33 | I2S microphone data |
| L/R | GND | Select left channel |

All six INMP441 pins must be connected. Firmware samples both I2S slots during
startup and automatically selects the channel carrying microphone data. The first
eight blocks are discarded to remove the I2S startup transient. The web status
shows the selected channel and live peak level.

### MAX98357A

| MAX98357A | ESP32 | Voltage / purpose |
|---|---:|---|
| VIN | 3V3 initially | Low-power test supply |
| GND | GND | Common ground |
| BCLK | GPIO18 | I2S bit clock |
| LRC/WS | GPIO19 | I2S word select |
| DIN | GPIO23 | I2S speaker data |
| SD/EN | GPIO27 | Amplifier enable |
| GAIN | Unconnected initially | Optional hardware gain selection |

Connect the speaker only between `SPK+` and `SPK-`. Neither speaker terminal goes
to GND. `GAIN` and `SD/EN` are different pins. After basic operation is stable,
connecting the actual `GAIN` pin directly to GND selects a higher hardware gain on
common MAX98357A modules. Power off before changing it.

Because this board previously lost Flash communication when peripherals were
connected, do not reconnect 5V until every pin label and ground connection has been
verified. A separate stable amplifier supply must share GND with the ESP32.

### OLED 1: 24x16 mm module

| OLED | ESP32 | Voltage / purpose |
|---|---:|---|
| VCC | 3V3 | OLED supply |
| GND | GND | Common ground |
| SDA | GPIO22 | I2C data |
| SCL/SCK | GPIO21 | I2C clock |

The physical size does not identify the pixel resolution. The current configuration
assumes `SSD1306 128x64`, address `0x3C`. It continues running when the display is
not detected. If the panel is actually 128x32, change `OLED1_HEIGHT` from `64` to
`32` in `hardware_config.h`.

### Four 360-degree servos

| Position | Signal GPIO | Power |
|---|---:|---|
| Front left | GPIO13 | External regulated 5V |
| Front right | GPIO14 | External regulated 5V |
| Rear left | GPIO16 | External regulated 5V |
| Rear right | GPIO17 | External regulated 5V |

Connect all servo brown/black wires to the external supply negative terminal and
ESP32 GND. Do not power four servos from ESP32 3V3 or the board 5V pin. The web
direction buttons must be held; releasing a button stops all motors. Firmware also
stops them after 1.2 seconds without a refreshed command.

## Optimized pin grouping

The pin layout is organized by module so signal wires stay on one side of the
38-pin board as much as possible:

| Board area | Module | Pins |
|---|---|---|
| Left upper header | INMP441 | GPIO33, GPIO25, GPIO26 |
| Right upper header | OLED 1 | GPIO21, GPIO22 |
| Right/left bridge | MAX98357A | GPIO23, GPIO19, GPIO18, GPIO27 |
| Lower headers | Four servos | GPIO13, GPIO14, GPIO16, GPIO17 |

GPIO0, GPIO2, GPIO5, GPIO12 and the internal Flash pins are deliberately avoided.
The OLED uses `SDA=22/SCL=21`.
MAX98357A `SD/EN` remains on GPIO27 to avoid a pin conflict.

## Build

The Arduino CLI and required libraries are installed locally. Build from the
repository root:

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32:FlashFreq=40,FlashMode=dio,PartitionScheme=default" talk\arduino_talk
```

The project needs these libraries:

- ESP32 Core built-ins: WiFi, WebServer, LittleFS, Wire, ESP_I2S.
- Adafruit SSD1306, Adafruit GFX, and Adafruit BusIO.

WiFi credentials are in the ignored local `secrets.h`. Use
`secrets.example.h` as the template on another computer.

## Upload

Keep all peripherals disconnected, put the ESP32 on COM9, then run:

```powershell
arduino-cli upload -p COM9 --fqbn "esp32:esp32:esp32:UploadSpeed=115200,FlashFreq=40,FlashMode=dio,PartitionScheme=default" talk\arduino_talk
```

If automatic download mode fails, hold `BOOT`, tap `EN`, start the command, and
release `BOOT` after the connection begins.

Open the serial monitor at 115200 baud:

```powershell
arduino-cli monitor -p COM9 -c baudrate=115200
```

The startup log prints `WIFI_CONNECTED`, the current IP, and `WEB_URL`.

## First run

1. Boot the bare ESP32 and verify the serial menu and WiFi.
2. Power off, connect OLED 1, then verify `/api/displays/status`.
3. Use the web expression buttons to test blink, happy, angry, and crying.
4. Power off, connect the INMP441, and make a short recording.
5. Power off, connect the MAX98357A at 3.3V and test ABC.
6. Upload `talk/alphabet_announcement.wav` from the web page, then use the A-Z test.

LittleFS is formatted automatically on first Arduino boot. Files previously stored
by MicroPython are not expected to survive the firmware/partition change.

## Serial menu

```text
1 - OLED test
2 - Start recording
3 - Play alphabet_announcement.wav
4 - Start ABC melody
0 - Stop recording/playback
s - Print JSON status
```

HTTP routes are documented in [API.md](API.md).
The complete optimized power and signal layout is in [WIRING.md](WIRING.md).
