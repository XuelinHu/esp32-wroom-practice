# Glass wiring

## Camera

The XIAO Sense camera expansion board uses its built-in OV3660 camera and the bundled camera connector. No camera jumper wires are needed.

## External INMP441

The default glass voice input uses an external INMP441 because the board microphone is PDM while the current MicroPython binding exposes standard I2S.

| INMP441 | XIAO ESP32-S3 | Signal |
|---|---:|---|
| VCC/VDD | 3V3 | 3.3 V only |
| GND | GND | common ground |
| SCK | GPIO4 | I2S bit clock |
| WS | GPIO5 | I2S word select |
| SD | GPIO6 | I2S data |
| L/R | GND | left channel |

GPIO4, GPIO5 and GPIO6 are selected because they do not overlap the XIAO Sense camera pins. If your microphone is wired differently, change MIC_BCLK, MIC_WS and MIC_SD in voice_recorder.py.

## Onboard microphone limitation

The XIAO Sense expansion board's onboard microphone uses PDM on GPIO42/GPIO41. The current MicroPython I2S constructor only accepts sck, ws and sd; it has no PDM input option. Do not connect the onboard PDM microphone to the three-wire INMP441 configuration. A native firmware rebuild is needed to support it.

## Power and flashing

Disconnect the external microphone while changing firmware or entering download mode if it affects boot. Keep all grounds common and never power the INMP441 from 5 V.
