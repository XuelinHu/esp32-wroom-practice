# Arduino glasses firmware

This replaces the MicroPython device firmware with an Arduino implementation
based on the reference project's transport design:

- OV3660 JPEG QVGA to `ws://<laptop>:8002/ws/camera`
- Sense onboard PDM microphone, GPIO42/41, 16 kHz PCM16 to `/ws/audio`
- SD detection on GPIO7/8/9 with CS GPIO3

It intentionally does not use the reference project's speaker pins GPIO7/8/9,
because those pins are reserved for the Sense SD card. Reserve GPIO4/5/6 for a
future MAX98357A I2S amplifier.

Before compiling, copy `secrets.example.h` to `secrets.h`, enter the existing
2.4 GHz Wi-Fi credentials, and keep `SERVER_HOST` set to the laptop IPv4
address. Install the ESP32 board package and `ArduinoWebsockets` library in
Arduino IDE, choose `XIAO_ESP32S3`, then upload to COM12.
