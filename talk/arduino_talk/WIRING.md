# Optimized wiring diagram

This layout uses the working 24x16 mm OLED. The broken 27x11 mm OLED is removed.

## Power rails

```text
ESP32 3V3 ----- 3.3V rail ----- INMP441 VDD
                     +--------- OLED 1 VCC

Stable 5V + --- 5V rail ------- MAX98357A VIN
                     +--------- 4x servo red wire

ESP32 GND ----- GND rail ------- INMP441 GND
External 5V - ------+  +-------- OLED 1 GND
                       +-------- MAX98357A GND
                       +-------- 4x servo brown/black wire
```

Use one common GND rail. Never connect 5V to ESP32 `3V3`, INMP441 VDD, OLED VCC,
or an ESP32 GPIO. During the first test, MAX98357A may use 3V3 at low volume.
For final speaker testing, use a stable regulated 5V amplifier supply and connect
its negative terminal to the common GND rail.

## Signal wiring

```text
INMP441                         ESP32
  SCK  ----------------------- GPIO26
  WS   ----------------------- GPIO25
  SD   ----------------------- GPIO33
  L/R  ----------------------- GND

OLED 1: 24x16 mm               ESP32 I2C controller 0
  SDA  ----------------------- GPIO22
  SCL/SCK -------------------- GPIO21

MAX98357A                       ESP32
  DIN  ----------------------- GPIO23
  LRC  ----------------------- GPIO19
  BCLK ----------------------- GPIO18
  SD   ----------------------- GPIO27
  GAIN ----------------------- unconnected initially

360-degree servos               ESP32
  Front-left signal ---------- GPIO13
  Front-right signal --------- GPIO14
  Rear-left signal ----------- GPIO16
  Rear-right signal ---------- GPIO17
  All red wires -------------- external regulated 5V +
  All brown/black wires ------- common GND
```

## 四个 360 度舵机供电

四个舵机不要接 ESP32 的 `3V3`，也不要从开发板 `5V/VIN` 引脚同时取电。
请使用独立稳压 5V 电源，额定电流至少覆盖四个舵机的堵转电流总和；不知道型号时，
可先选择 5V/5A 或更高规格。外部电源负极必须连接 ESP32 `GND`，但外部 5V
正极不要接 ESP32 `3V3`。

建议在舵机供电母线附近并联一个 `1000-2200 uF` 电解电容，注意正负极。
360 度舵机只能控制方向和速度，不能控制到某个角度。若停止命令后仍缓慢转动，
在 `arduino_talk.ino` 中微调 `SERVO_NEUTRAL_US`，常见范围约为 1470-1530 us。

## Grouping by header area

```text
LEFT UPPER                         RIGHT UPPER
GPIO33  INMP441 SD                 GPIO23  MAX98357A DIN
GPIO25  INMP441 WS                 GPIO22  OLED 1 SDA
GPIO26  INMP441 SCK                GPIO21  OLED 1 SCL/SCK
GPIO27  MAX98357A SD               GND     common GND rail
                                   GPIO19  MAX98357A LRC
LEFT LOWER                         GPIO18  MAX98357A BCLK
GPIO13  front-left servo           GPIO14  front-right servo
GPIO16  rear-left servo            GPIO17  rear-right servo
```

The exact printed order can vary between 38-pin ESP32 board vendors. Follow the
GPIO labels printed on the board rather than counting physical pins.

## Safe connection order

1. Upload firmware with every peripheral disconnected.
2. Power off and connect OLED 1 only; verify the primary display is online.
3. Power off and add INMP441; make a short recording.
4. Power off and add MAX98357A at low volume.
5. Use the final regulated 5V amplifier supply only after every signal is verified.
6. Keep the wheels off the ground for the first servo direction test.

## INMP441 排查顺序

1. 断开 MAX98357A 和全部舵机，只保留 ESP32、OLED 和 INMP441。
2. 测量 INMP441 `VDD-GND`，应稳定在约 3.3V；确认 `L/R` 直接接 GND。
3. 逐根核对：`SCK=GPIO26`、`WS=GPIO25`、`SD=GPIO33`，并检查焊点和杜邦线通断。
4. 确认麦克风金属壳上的拾音孔没有被胶、泡棉或安装板遮住。
5. 在模块 VDD 和 GND 附近并联 0.1uF 陶瓷去耦电容后再录音。
6. 对着麦克风从约 20cm 处说话，观察网页的 peak 是否明显随声音变化。

当前固件已经能识别左声道并取得非零 I2S 数据，说明时钟、数据线和驱动并非完全失效。
如果断开功放和舵机后仍必须贴近 3cm 才能听清，最有效的确认方法是换一块已知正常的
INMP441，保持同一组线和同一份固件做对照测试。
