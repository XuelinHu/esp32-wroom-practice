#pragma once

// Left-side cluster: INMP441 microphone.
static constexpr int MIC_BCLK = 26;
static constexpr int MIC_WS = 25;
static constexpr int MIC_SD = 33;

// Right-side cluster: MAX98357A amplifier.
static constexpr int AMP_BCLK = 18;
static constexpr int AMP_LRC = 19;
static constexpr int AMP_DIN = 23;
static constexpr int AMP_SD = 27;

// OLED 1, 24x16 mm physical module: detailed display on I2C controller 0.
static constexpr int OLED1_SDA = 22;
static constexpr int OLED1_SCL = 21;
static constexpr uint8_t OLED1_ADDRESS = 0x3C;
static constexpr int OLED1_WIDTH = 128;
static constexpr int OLED1_HEIGHT = 64;

// Four continuous-rotation servos. Power them from an external regulated 5V rail.
static constexpr int SERVO_FRONT_LEFT = 13;
static constexpr int SERVO_FRONT_RIGHT = 14;
static constexpr int SERVO_REAR_LEFT = 16;
static constexpr int SERVO_REAR_RIGHT = 17;

// Right-side servos are mirrored on a typical four-wheel chassis.
static constexpr bool SERVO_FRONT_LEFT_REVERSED = false;
static constexpr bool SERVO_FRONT_RIGHT_REVERSED = true;
static constexpr bool SERVO_REAR_LEFT_REVERSED = false;
static constexpr bool SERVO_REAR_RIGHT_REVERSED = true;
