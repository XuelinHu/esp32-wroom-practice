# XIAO ESP32-S3 Sense: voice and camera

glass is the standalone project for the XIAO ESP32-S3 Sense board.

It starts a WiFi web server after boot and provides:

- OV2640/OV3660 automatic camera detection through the bundled native camera module.
- OV3660 RGB565 capture rendered as a browser Canvas live view.
- Onboard PDM microphone recording to 16 kHz, 16-bit mono WAV.
- Browser playback of recordings stored on the board.
- Camera status and resolution controls.
- MicroSD mount, file listing, and read/write self-test in the web page.

The project-specific firmware includes a native `pdm_mic` module for the
onboard XIAO Sense microphone. The public precompiled firmware does not contain
this module, so upload the updated `voice_recorder.py` only after flashing the
custom firmware built from `firmware-src`.

## Firmware

Use the board-specific image included in this directory:

    glass\firmware\micropython-camera-xiao-esp32s3-v1.27.0.bin

This image is built for XIAO ESP32-S3 and includes the OV3660 camera driver. It uses the board's fixed camera pin mapping and the newer object-based MicroPython camera API. On the tested OV3660 module, direct JPEG capture fails in the native driver, while RGB565 capture works. The web page therefore requests RGB565 frames and renders them in Canvas.

If MicroPython is already installed, do not erase the flash just to upload this project. The first-time flash command is:

    & "C:\Users\De\.conda\envs\pyg\Scripts\esptool.exe" --port COM11 --baud 460800 write-flash 0 "glass\firmware\micropython-camera-xiao-esp32s3-v1.27.0.bin"

## Upload

Upload these files to the board filesystem:

    glass\boot.py -> /boot.py
    glass\main.py -> /main.py
    glass\camera_setup.py -> /camera_setup.py
    glass\voice_recorder.py -> /voice_recorder.py
    glass\http_server.py -> /http_server.py
    glass\web\index.html -> /web/index.html

After reset, the serial output contains the assigned IP address:

    WIFI_CONNECTED
    WIFI_IP 192.168.x.x
    WEB_URL http://192.168.x.x/

Open WEB_URL on a device connected to the same WiFi network.

The default stream size is 160x120 to keep the raw frame transfer reliable. A stronger 2.4 GHz WiFi signal is needed for a higher refresh rate.

## Camera Resolution

The OV3660 sensor supports up to 2048x1536. The current MicroPython camera driver is verified for RGB565 capture at 160x120 and 320x240. Higher raw frames are unsuitable for this board's browser stream because they exceed the practical WiFi transfer budget.

## MicroSD

Insert a FAT32 microSD card in the Sense expansion board and use `检测 SD 卡` followed by `读写自检` in the web page. The Sense SPI wiring is GPIO7 (SCK), GPIO8 (MISO), GPIO9 (MOSI), and GPIO3 (CS) on recent board documentation. When mounted, new recordings use `/sd/recordings`; otherwise they stay in `/recordings` on internal flash.

## WiFi

The default values copied from talk are configured in main.py:

    WIFI_SSID = "ChinaNet-E5y7"
    WIFI_PASSWORD = "zadyx5cc"

The password is never printed by the firmware.
