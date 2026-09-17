#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <LittleFS.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP_I2S.h>
#include <algorithm>
#include <vector>
#include <time.h>

#include "secrets.h"
#include "hardware_config.h"
#include "web_page.h"

static constexpr uint32_t RECORD_RATE = 16000;
static constexpr uint32_t TONE_RATE = 16000;
static constexpr uint32_t MAX_RECORD_SECONDS = 45;
static constexpr int MIC_DIGITAL_GAIN = 2;
static constexpr int MIC_NOISE_GATE = 80;
static constexpr int PLAYBACK_GAIN_PERCENT = 220;
static constexpr char RECORD_DIR[] = "/recordings";
static constexpr uint32_t SERVO_PWM_FREQUENCY = 50;
static constexpr uint8_t SERVO_PWM_RESOLUTION = 16;
static constexpr uint16_t SERVO_NEUTRAL_US = 1500;
static constexpr uint16_t SERVO_MIN_DELTA_US = 120;
static constexpr uint16_t SERVO_MAX_DELTA_US = 450;
static constexpr uint32_t SERVO_COMMAND_TIMEOUT_MS = 1200;
static constexpr size_t RECORD_STORAGE_RESERVE_BYTES = 96 * 1024;
static constexpr int SERVO_PINS[] = {
  SERVO_FRONT_LEFT, SERVO_FRONT_RIGHT, SERVO_REAR_LEFT, SERVO_REAR_RIGHT
};
static constexpr bool SERVO_REVERSED[] = {
  SERVO_FRONT_LEFT_REVERSED, SERVO_FRONT_RIGHT_REVERSED,
  SERVO_REAR_LEFT_REVERSED, SERVO_REAR_RIGHT_REVERSED
};

WebServer server(80);
Adafruit_SSD1306 oledPrimary(OLED1_WIDTH, OLED1_HEIGHT, &Wire, -1);
I2SClass micI2S(I2S_NUM_0);
I2SClass ampI2S(I2S_NUM_1);
SemaphoreHandle_t stateMutex;
SemaphoreHandle_t oledMutex;
SemaphoreHandle_t logMutex;

enum class AudioMode : uint8_t { IDLE, RECORDING, PLAYING, ABC };
enum class OledExpression : uint8_t { NEUTRAL, HAPPY, ANGRY, CRYING };
enum class ServoMotion : uint8_t { STOPPED, FORWARD, BACKWARD, LEFT, RIGHT };

AudioMode audioMode = AudioMode::IDLE;
volatile bool stopRequested = false;
bool recordingLaunchPending = false;
uint32_t recordingLaunchAtMs = 0;
size_t audioBytes = 0;
uint16_t micLivePeak = 0;
uint16_t lastRecordPeak = 0;
uint16_t lastRecordMean = 0;
String micSelectedChannel = "unknown";
String activeFile;
String lastRecord;
String audioError;
bool oledPrimaryReady = false;
File uploadFile;
bool uploadOk = false;
String uploadName;
String uploadError;
OledExpression oledExpression = OledExpression::NEUTRAL;
bool oledBlinkActive = false;
bool oledNeedsRedraw = true;
uint8_t oledBlinkClosure = 0;
uint32_t oledBlinkStartedMs = 0;
uint32_t oledNextAutoBlinkMs = 0;
uint32_t oledLastFrameMs = 0;
uint32_t oledMessageUntilMs = 0;
bool servosReady = false;
ServoMotion servoMotion = ServoMotion::STOPPED;
uint8_t servoSpeed = 45;
uint32_t servoCommandDeadlineMs = 0;
static constexpr size_t EVENT_LOG_CAPACITY = 16;
String eventLog[EVENT_LOG_CAPACITY];
size_t eventLogStart = 0;
size_t eventLogCount = 0;

struct __attribute__((packed)) WavHeader {
  char riff[4];
  uint32_t fileSize;
  char wave[4];
  char fmt[4];
  uint32_t fmtSize;
  uint16_t audioFormat;
  uint16_t channels;
  uint32_t sampleRate;
  uint32_t byteRate;
  uint16_t blockAlign;
  uint16_t bitsPerSample;
  char data[4];
  uint32_t dataSize;
};

static_assert(sizeof(WavHeader) == 44, "WAV header must be 44 bytes");

const char *modeName(AudioMode mode) {
  switch (mode) {
    case AudioMode::RECORDING: return "recording";
    case AudioMode::PLAYING: return "playing";
    case AudioMode::ABC: return "abc";
    default: return "idle";
  }
}

String jsonEscape(const String &value) {
  String result;
  result.reserve(value.length() + 8);
  for (size_t i = 0; i < value.length(); ++i) {
    const char ch = value[i];
    if (ch == '"' || ch == '\\') {
      result += '\\';
      result += ch;
    } else if (ch == '\n') {
      result += "\\n";
    } else if (static_cast<uint8_t>(ch) >= 0x20) {
      result += ch;
    }
  }
  return result;
}

void sendJson(int status, const String &body) {
  server.sendHeader("Cache-Control", "no-store");
  server.send(status, "application/json; charset=utf-8", body);
}

String errorJson(const String &error) {
  return "{\"ok\":false,\"error\":\"" + jsonEscape(error) + "\"}";
}

String currentTimeText() {
  struct tm info = {};
  if (!getLocalTime(&info, 20)) return String(millis() / 1000) + "s";
  char value[24];
  snprintf(value, sizeof(value), "%04d-%02d-%02d %02d:%02d:%02d",
           info.tm_year + 1900, info.tm_mon + 1, info.tm_mday,
           info.tm_hour, info.tm_min, info.tm_sec);
  return String(value);
}

void appendEvent(const String &message) {
  const String entry = currentTimeText() + "  " + message;
  Serial.println(entry);
  if (logMutex == nullptr || xSemaphoreTake(logMutex, pdMS_TO_TICKS(100)) != pdTRUE) return;
  if (eventLogCount < EVENT_LOG_CAPACITY) {
    eventLog[(eventLogStart + eventLogCount) % EVENT_LOG_CAPACITY] = entry;
    ++eventLogCount;
  } else {
    eventLog[eventLogStart] = entry;
    eventLogStart = (eventLogStart + 1) % EVENT_LOG_CAPACITY;
  }
  xSemaphoreGive(logMutex);
}

const char *servoMotionName(ServoMotion motion) {
  switch (motion) {
    case ServoMotion::FORWARD: return "forward";
    case ServoMotion::BACKWARD: return "backward";
    case ServoMotion::LEFT: return "left";
    case ServoMotion::RIGHT: return "right";
    default: return "stopped";
  }
}

uint32_t servoDutyFromPulse(uint16_t pulseUs) {
  return (static_cast<uint32_t>(pulseUs) * 65535UL + 10000UL) / 20000UL;
}

void writeServo(size_t index, int direction, uint8_t speed) {
  if (index >= 4) return;
  if (SERVO_REVERSED[index]) direction = -direction;
  uint16_t pulseUs = SERVO_NEUTRAL_US;
  if (direction != 0) {
    const uint16_t delta = SERVO_MIN_DELTA_US +
                           (SERVO_MAX_DELTA_US - SERVO_MIN_DELTA_US) * speed / 100;
    pulseUs = static_cast<uint16_t>(SERVO_NEUTRAL_US + direction * delta);
  }
  ledcWrite(SERVO_PINS[index], servoDutyFromPulse(pulseUs));
}

void applyServoMotion(ServoMotion motion, uint8_t speed) {
  int directions[4] = {0, 0, 0, 0};
  if (motion == ServoMotion::FORWARD) {
    directions[0] = directions[1] = directions[2] = directions[3] = 1;
  } else if (motion == ServoMotion::BACKWARD) {
    directions[0] = directions[1] = directions[2] = directions[3] = -1;
  } else if (motion == ServoMotion::LEFT) {
    directions[0] = directions[2] = -1;
    directions[1] = directions[3] = 1;
  } else if (motion == ServoMotion::RIGHT) {
    directions[0] = directions[2] = 1;
    directions[1] = directions[3] = -1;
  }
  for (size_t i = 0; i < 4; ++i) writeServo(i, directions[i], speed);
}

void stopServos(bool timedOut = false) {
  const bool wasMoving = servoMotion != ServoMotion::STOPPED;
  servoMotion = ServoMotion::STOPPED;
  servoCommandDeadlineMs = 0;
  applyServoMotion(servoMotion, 0);
  if (wasMoving) appendEvent(timedOut ? "SERVO_SAFETY_STOP" : "SERVO_STOPPED");
}

bool commandServos(const String &direction, int requestedSpeed) {
  ServoMotion requested = ServoMotion::STOPPED;
  if (direction == "forward") requested = ServoMotion::FORWARD;
  else if (direction == "backward") requested = ServoMotion::BACKWARD;
  else if (direction == "left") requested = ServoMotion::LEFT;
  else if (direction == "right") requested = ServoMotion::RIGHT;
  else if (direction != "stop") return false;

  if (requested == ServoMotion::STOPPED) {
    stopServos(false);
    return true;
  }
  const ServoMotion previous = servoMotion;
  servoSpeed = static_cast<uint8_t>(constrain(requestedSpeed, 1, 100));
  servoMotion = requested;
  applyServoMotion(requested, servoSpeed);
  servoCommandDeadlineMs = millis() + SERVO_COMMAND_TIMEOUT_MS;
  if (requested != previous) {
    appendEvent("SERVO_MOVE " + direction + " speed=" + String(servoSpeed));
  }
  return true;
}

void initServos() {
  servosReady = true;
  for (size_t i = 0; i < 4; ++i) {
    if (!ledcAttachChannel(SERVO_PINS[i], SERVO_PWM_FREQUENCY,
                           SERVO_PWM_RESOLUTION, static_cast<uint8_t>(i))) {
      servosReady = false;
    }
  }
  applyServoMotion(ServoMotion::STOPPED, 0);
  appendEvent(servosReady ? "SERVOS_READY" : "SERVOS_INIT_FAILED");
}

String eventLogJson() {
  String json = "[";
  if (xSemaphoreTake(logMutex, portMAX_DELAY) == pdTRUE) {
    for (size_t i = 0; i < eventLogCount; ++i) {
      if (i) json += ',';
      const size_t index = (eventLogStart + i) % EVENT_LOG_CAPACITY;
      json += "\"" + jsonEscape(eventLog[index]) + "\"";
    }
    xSemaphoreGive(logMutex);
  }
  json += ']';
  return json;
}

bool validWavName(const String &name) {
  if (name.length() < 5 || name.length() > 80 || name.indexOf('/') >= 0 ||
      name.indexOf('\\') >= 0 || name.indexOf("..") >= 0) {
    return false;
  }
  String lower = name;
  lower.toLowerCase();
  return lower.endsWith(".wav");
}

bool recordedWavName(const String &name) {
  if (!validWavName(name)) return false;
  String lower = name;
  lower.toLowerCase();
  return lower.startsWith("record_");
}

String recordingPath(const String &name) {
  return String(RECORD_DIR) + "/" + name;
}

bool removePreviousRecordings() {
  std::vector<String> paths;
  File directory = LittleFS.open(RECORD_DIR);
  if (directory && directory.isDirectory()) {
    File file = directory.openNextFile();
    while (file) {
      if (!file.isDirectory()) {
        String path = file.name();
        const int slash = path.lastIndexOf('/');
        const String name = slash >= 0 ? path.substring(slash + 1) : path;
        if (recordedWavName(name)) paths.push_back(recordingPath(name));
      }
      file.close();
      file = directory.openNextFile();
    }
    directory.close();
  }

  bool removedAll = true;
  size_t removedCount = 0;
  for (const String &path : paths) {
    if (LittleFS.remove(path)) ++removedCount;
    else removedAll = false;
  }
  if (removedCount > 0) appendEvent("OLD_RECORDINGS_REMOVED count=" + String(removedCount));
  return removedAll;
}

void showOled(const String &line1, const String &line2 = "") {
  if (!oledPrimaryReady || xSemaphoreTake(oledMutex, pdMS_TO_TICKS(100)) != pdTRUE) return;
  oledMessageUntilMs = millis() + 2000;
  oledPrimary.clearDisplay();
  oledPrimary.setTextColor(SSD1306_WHITE);
  oledPrimary.setTextSize(2);
  oledPrimary.setCursor(0, 0);
  oledPrimary.println(line1);
  if (line2.length()) {
    oledPrimary.setTextSize(1);
    oledPrimary.setCursor(0, 28);
    oledPrimary.print(line2);
  }
  oledPrimary.display();
  xSemaphoreGive(oledMutex);
}

const char *expressionName(OledExpression expression) {
  switch (expression) {
    case OledExpression::HAPPY: return "happy";
    case OledExpression::ANGRY: return "angry";
    case OledExpression::CRYING: return "crying";
    default: return "neutral";
  }
}

void drawOpenEye(int x, int y) {
  oledPrimary.fillRoundRect(x - 8, y - 8, 16, 16, 5, SSD1306_WHITE);
  oledPrimary.fillCircle(x, y, 3, SSD1306_BLACK);
}

void drawBlinkingEyes(uint8_t closure) {
  if (closure >= 2) {
    oledPrimary.drawLine(38, 27, 54, 27, SSD1306_WHITE);
    oledPrimary.drawLine(74, 27, 90, 27, SSD1306_WHITE);
  } else {
    oledPrimary.fillRoundRect(38, 23, 16, 7, 3, SSD1306_WHITE);
    oledPrimary.fillRoundRect(74, 23, 16, 7, 3, SSD1306_WHITE);
    oledPrimary.fillCircle(46, 27, 2, SSD1306_BLACK);
    oledPrimary.fillCircle(82, 27, 2, SSD1306_BLACK);
  }
}

void drawExpression(uint8_t blinkClosure = 0) {
  if (!oledPrimaryReady || xSemaphoreTake(oledMutex, pdMS_TO_TICKS(100)) != pdTRUE) return;
  oledPrimary.clearDisplay();
  oledPrimary.drawRoundRect(20, 1, 88, 62, 18, SSD1306_WHITE);

  if (blinkClosure > 0) {
    drawBlinkingEyes(blinkClosure);
  } else if (oledExpression == OledExpression::HAPPY) {
    oledPrimary.drawLine(38, 28, 46, 21, SSD1306_WHITE);
    oledPrimary.drawLine(46, 21, 54, 28, SSD1306_WHITE);
    oledPrimary.drawLine(74, 28, 82, 21, SSD1306_WHITE);
    oledPrimary.drawLine(82, 21, 90, 28, SSD1306_WHITE);
  } else {
    drawOpenEye(46, 26);
    drawOpenEye(82, 26);
  }

  if (oledExpression == OledExpression::HAPPY) {
    oledPrimary.drawLine(48, 43, 56, 50, SSD1306_WHITE);
    oledPrimary.drawLine(56, 50, 72, 50, SSD1306_WHITE);
    oledPrimary.drawLine(72, 50, 80, 43, SSD1306_WHITE);
  } else if (oledExpression == OledExpression::ANGRY) {
    oledPrimary.drawLine(36, 15, 54, 21, SSD1306_WHITE);
    oledPrimary.drawLine(74, 21, 92, 15, SSD1306_WHITE);
    oledPrimary.drawLine(50, 52, 58, 45, SSD1306_WHITE);
    oledPrimary.drawLine(58, 45, 70, 45, SSD1306_WHITE);
    oledPrimary.drawLine(70, 45, 78, 52, SSD1306_WHITE);
  } else if (oledExpression == OledExpression::CRYING) {
    oledPrimary.drawLine(52, 49, 76, 49, SSD1306_WHITE);
    const int tearOffset = (millis() / 120) % 13;
    oledPrimary.fillCircle(38, 32 + tearOffset, 2, SSD1306_WHITE);
    oledPrimary.fillCircle(90, 38 + ((tearOffset + 6) % 13), 2, SSD1306_WHITE);
  } else {
    oledPrimary.drawLine(52, 48, 76, 48, SSD1306_WHITE);
  }
  oledPrimary.display();
  xSemaphoreGive(oledMutex);
}

bool requestExpression(const String &name) {
  if (!oledPrimaryReady) return false;
  if (name == "blink") {
    oledBlinkActive = true;
    oledBlinkStartedMs = millis();
    oledBlinkClosure = 0;
  } else if (name == "neutral") {
    oledExpression = OledExpression::NEUTRAL;
  } else if (name == "happy") {
    oledExpression = OledExpression::HAPPY;
  } else if (name == "angry") {
    oledExpression = OledExpression::ANGRY;
  } else if (name == "crying") {
    oledExpression = OledExpression::CRYING;
  } else {
    return false;
  }
  oledMessageUntilMs = 0;
  oledNeedsRedraw = true;
  oledNextAutoBlinkMs = millis() + random(2500, 5001);
  appendEvent("OLED_EXPRESSION " + name);
  return true;
}

void updateOledAnimation() {
  if (!oledPrimaryReady || static_cast<int32_t>(millis() - oledMessageUntilMs) < 0) return;
  if (!oledBlinkActive && static_cast<int32_t>(millis() - oledNextAutoBlinkMs) >= 0) {
    oledBlinkActive = true;
    oledBlinkStartedMs = millis();
    oledBlinkClosure = 0;
  }
  if (oledBlinkActive) {
    const uint32_t elapsed = millis() - oledBlinkStartedMs;
    uint8_t closure = 0;
    if (elapsed >= 70 && elapsed < 130) closure = 1;
    else if (elapsed >= 130 && elapsed < 260) closure = 2;
    else if (elapsed >= 260 && elapsed < 330) closure = 1;
    if (closure != oledBlinkClosure || oledNeedsRedraw) {
      drawExpression(closure);
      oledBlinkClosure = closure;
      oledNeedsRedraw = false;
    }
    if (elapsed >= 380) {
      oledBlinkActive = false;
      oledNeedsRedraw = true;
      oledNextAutoBlinkMs = millis() + random(2500, 5001);
    }
    return;
  }
  if (oledExpression == OledExpression::CRYING && millis() - oledLastFrameMs >= 120) {
    oledNeedsRedraw = true;
    oledLastFrameMs = millis();
  }
  if (oledNeedsRedraw) {
    drawExpression(false);
    oledNeedsRedraw = false;
  }
}

bool initOled() {
  Wire.begin(OLED1_SDA, OLED1_SCL, 100000);

  auto findOledAddress = [](TwoWire &bus, uint8_t preferred) -> uint8_t {
    const uint8_t addresses[] = {preferred, static_cast<uint8_t>(preferred == 0x3C ? 0x3D : 0x3C)};
    for (const uint8_t address : addresses) {
      bus.beginTransmission(address);
      if (bus.endTransmission() == 0) return address;
    }
    return 0;
  };

  const uint8_t primaryAddress = findOledAddress(Wire, OLED1_ADDRESS);
  if (primaryAddress != 0 &&
      oledPrimary.begin(SSD1306_SWITCHCAPVCC, primaryAddress, false, false)) {
    oledPrimaryReady = true;
    Serial.printf("OLED1_READY %dx%d address=0x%02X sda=%d scl=%d\n",
                  OLED1_WIDTH, OLED1_HEIGHT, primaryAddress, OLED1_SDA, OLED1_SCL);
  } else {
    Serial.printf("OLED1_NOT_FOUND addresses=0x3C/0x3D sda=%d scl=%d\n",
                  OLED1_SDA, OLED1_SCL);
  }

  if (oledPrimaryReady) {
    oledNextAutoBlinkMs = millis() + 2200;
    showOled("HELLO", "Arduino ESP32");
  }
  return oledPrimaryReady;
}

bool reserveAudio(AudioMode requested, const String &file = "") {
  if (servoMotion != ServoMotion::STOPPED) stopServos(false);
  bool reserved = false;
  xSemaphoreTake(stateMutex, portMAX_DELAY);
  if (audioMode == AudioMode::IDLE) {
    audioMode = requested;
    stopRequested = false;
    audioBytes = 0;
    micLivePeak = 0;
    activeFile = file;
    audioError = "";
    if (requested == AudioMode::RECORDING) {
      micSelectedChannel = "probing";
      lastRecord = "";
      lastRecordPeak = 0;
      lastRecordMean = 0;
    }
    reserved = true;
  }
  xSemaphoreGive(stateMutex);
  return reserved;
}

void finishAudio(const String &error = "") {
  xSemaphoreTake(stateMutex, portMAX_DELAY);
  audioError = error;
  audioMode = AudioMode::IDLE;
  stopRequested = false;
  micLivePeak = 0;
  xSemaphoreGive(stateMutex);
}

String statusJson() {
  xSemaphoreTake(stateMutex, portMAX_DELAY);
  const bool active = audioMode != AudioMode::IDLE;
  String result = "{\"ok\":true,\"mode\":\"" + String(modeName(audioMode)) +
                  "\",\"active\":" + String(active ? "true" : "false") +
                  ",\"bytes\":" + String(audioBytes) +
                  ",\"active_file\":\"" + jsonEscape(activeFile) +
                  "\",\"path\":\"" + jsonEscape(activeFile.length() ? recordingPath(activeFile) : "") +
                  "\",\"last_record\":\"" + jsonEscape(lastRecord) +
                  "\",\"error\":\"" + jsonEscape(audioError) +
                  "\",\"oled_primary_ready\":" + String(oledPrimaryReady ? "true" : "false") +
                  ",\"oled_expression\":\"" + expressionName(oledExpression) +
                  "\",\"mic_peak\":" + String(micLivePeak) +
                  ",\"mic_channel\":\"" + jsonEscape(micSelectedChannel) +
                  "\",\"last_record_peak\":" + String(lastRecordPeak) +
                  ",\"last_record_mean\":" + String(lastRecordMean) +
                  ",\"servos_ready\":" + String(servosReady ? "true" : "false") +
                  ",\"servo_motion\":\"" + servoMotionName(servoMotion) +
                  "\",\"servo_speed\":" + String(servoSpeed) + "}";
  xSemaphoreGive(stateMutex);
  return result;
}

String makeRecordName() {
  struct tm info = {};
  if (getLocalTime(&info, 200)) {
    char name[40];
    snprintf(name, sizeof(name), "record_%04d%02d%02d_%02d%02d%02d.wav",
             info.tm_year + 1900, info.tm_mon + 1, info.tm_mday,
             info.tm_hour, info.tm_min, info.tm_sec);
    return String(name);
  }
  return "record_boot_" + String(millis()) + ".wav";
}

WavHeader makeWavHeader(uint32_t sampleRate, uint16_t channels, uint32_t dataSize) {
  WavHeader header = {};
  memcpy(header.riff, "RIFF", 4);
  header.fileSize = 36 + dataSize;
  memcpy(header.wave, "WAVE", 4);
  memcpy(header.fmt, "fmt ", 4);
  header.fmtSize = 16;
  header.audioFormat = 1;
  header.channels = channels;
  header.sampleRate = sampleRate;
  header.bitsPerSample = 16;
  header.blockAlign = channels * 2;
  header.byteRate = sampleRate * header.blockAlign;
  memcpy(header.data, "data", 4);
  header.dataSize = dataSize;
  return header;
}

int16_t amplifiedSample(int32_t sample, int percent) {
  sample = sample * percent / 100;
  if (sample > 32767) return 32767;
  if (sample < -32768) return -32768;
  return static_cast<int16_t>(sample);
}

void recordTask(void *) {
  const String name = makeRecordName();
  const String path = recordingPath(name);
  File wav;
  String error;
  int32_t dc[2] = {0, 0};
  uint32_t dataSize = 0;
  uint16_t recordPeak = 0;
  uint64_t magnitudeTotal = 0;
  uint32_t sampleTotal = 0;
  uint64_t channelEnergy[2] = {0, 0};
  uint8_t channelProbeBlocks = 0;
  uint8_t selectedChannel = 0;
  int16_t stereoSamples[512];
  int16_t samples[256];

  xSemaphoreTake(stateMutex, portMAX_DELAY);
  activeFile = name;
  xSemaphoreGive(stateMutex);
  showOled("RECORD", name.substring(0, 20));
  if (!removePreviousRecordings()) {
    error = "previous_record_delete_failed";
  }
  bool ready = false;
  if (!error.length()) {
    micI2S.setPins(MIC_BCLK, MIC_WS, -1, MIC_SD);
    ready = micI2S.begin(I2S_MODE_STD, RECORD_RATE,
                         I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO,
                         I2S_STD_SLOT_BOTH);
    if (ready) {
      ready = micI2S.configureRX(RECORD_RATE, I2S_DATA_BIT_WIDTH_32BIT,
                                 I2S_SLOT_MODE_STEREO,
                                 I2S_RX_TRANSFORM_32_TO_16,
                                 I2S_STD_SLOT_BOTH);
    }
    if (!ready) error = "microphone_i2s_init_failed";
  }
  if (!error.length()) {
    wav = LittleFS.open(path, "w+");
    if (!wav) {
      error = "record_file_open_failed";
    }
  }

  if (!error.length()) {
    const size_t freeBytes = LittleFS.totalBytes() - LittleFS.usedBytes();
    const size_t configuredMax = RECORD_RATE * 2UL * MAX_RECORD_SECONDS;
    const size_t maxBytes = std::min(
      configuredMax,
      freeBytes > RECORD_STORAGE_RESERVE_BYTES ? freeBytes - RECORD_STORAGE_RESERVE_BYTES : 0U
    );
    if (maxBytes < sizeof(samples)) {
      error = "record_storage_full";
    } else {
      WavHeader emptyHeader = makeWavHeader(RECORD_RATE, 1, 0);
      if (wav.write(reinterpret_cast<const uint8_t *>(&emptyHeader), sizeof(emptyHeader)) !=
          sizeof(emptyHeader)) {
        error = "record_header_write_failed";
      }
    }

    if (!error.length()) {
      Serial.printf("RECORD_STARTED path=%s max=%u\n", path.c_str(), static_cast<unsigned>(maxBytes));
      appendEvent("RECORD_STARTED " + name);
    }

    while (!error.length() && !stopRequested && dataSize + sizeof(samples) <= maxBytes) {
      const size_t bytesRead = micI2S.readBytes(reinterpret_cast<char *>(stereoSamples), sizeof(stereoSamples));
      if (bytesRead == 0) {
        error = "microphone_read_failed";
        break;
      }
      const size_t frameCount = bytesRead / (sizeof(int16_t) * 2);
      if (frameCount == 0) continue;
      uint64_t blockEnergy[2] = {0, 0};
      for (size_t i = 0; i < frameCount; ++i) {
        const int16_t left = stereoSamples[i * 2];
        const int16_t right = stereoSamples[i * 2 + 1];
        blockEnergy[0] += left < 0 ? -static_cast<int32_t>(left) : left;
        blockEnergy[1] += right < 0 ? -static_cast<int32_t>(right) : right;
      }
      if (channelProbeBlocks < 8) {
        for (size_t i = 0; i < frameCount; ++i) {
          for (size_t channel = 0; channel < 2; ++channel) {
            const int32_t input = stereoSamples[i * 2 + channel];
            dc[channel] += (input - dc[channel]) >> 4;
          }
        }
        channelEnergy[0] += blockEnergy[0];
        channelEnergy[1] += blockEnergy[1];
        ++channelProbeBlocks;
        selectedChannel = channelEnergy[1] > channelEnergy[0] ? 1 : 0;
        if (channelProbeBlocks == 8) {
          xSemaphoreTake(stateMutex, portMAX_DELAY);
          micSelectedChannel = selectedChannel == 0 ? "left" : "right";
          xSemaphoreGive(stateMutex);
          appendEvent("MIC_CHANNEL " + micSelectedChannel + " left=" + String(channelEnergy[0]) +
                      " right=" + String(channelEnergy[1]));
        }
        continue;
      }
      uint16_t blockPeak = 0;
      for (size_t i = 0; i < frameCount; ++i) {
        const int32_t input = stereoSamples[i * 2 + selectedChannel];
        dc[selectedChannel] += (input - dc[selectedChannel]) >> 6;
        int32_t centered = input - dc[selectedChannel];
        const int32_t rawMagnitude = abs(centered);
        if (rawMagnitude <= MIC_NOISE_GATE) {
          centered = 0;
        } else {
          centered = centered < 0 ? -(rawMagnitude - MIC_NOISE_GATE) : rawMagnitude - MIC_NOISE_GATE;
        }
        const int16_t processed = amplifiedSample(centered, MIC_DIGITAL_GAIN * 100);
        samples[i] = processed;
        const uint16_t magnitude = static_cast<uint16_t>(processed < 0 ? -static_cast<int32_t>(processed) : processed);
        blockPeak = std::max(blockPeak, magnitude);
        recordPeak = std::max(recordPeak, magnitude);
        magnitudeTotal += magnitude;
        ++sampleTotal;
      }
      const size_t outputBytes = frameCount * sizeof(int16_t);
      if (wav.write(reinterpret_cast<uint8_t *>(samples), outputBytes) != outputBytes) {
        error = "record_file_write_failed";
        break;
      }
      dataSize += outputBytes;
      xSemaphoreTake(stateMutex, portMAX_DELAY);
      audioBytes = dataSize;
      micLivePeak = blockPeak;
      activeFile = name;
      xSemaphoreGive(stateMutex);
    }

    if (!error.length() && dataSize > 0) {
      WavHeader header = makeWavHeader(RECORD_RATE, 1, dataSize);
      if (!wav.seek(0) ||
          wav.write(reinterpret_cast<const uint8_t *>(&header), sizeof(header)) != sizeof(header)) {
        error = "record_finalize_failed";
      }
    }
    wav.flush();
    wav.close();
    if (!error.length() && dataSize > 0) {
      File saved = LittleFS.open(path, "r");
      const size_t expectedSize = sizeof(WavHeader) + dataSize;
      const size_t actualSize = saved ? saved.size() : 0;
      if (saved) saved.close();
      if (actualSize != expectedSize) {
        Serial.printf("RECORD_SIZE_MISMATCH expected=%u actual=%u\n",
                      static_cast<unsigned>(expectedSize), static_cast<unsigned>(actualSize));
        error = "record_storage_commit_failed";
      }
    }
    if (!error.length() && dataSize > 0) {
      xSemaphoreTake(stateMutex, portMAX_DELAY);
      lastRecord = name;
      lastRecordPeak = recordPeak;
      lastRecordMean = sampleTotal > 0 ? static_cast<uint16_t>(magnitudeTotal / sampleTotal) : 0;
      xSemaphoreGive(stateMutex);
      Serial.printf("RECORD_SAVED path=%s bytes=%u peak=%u mean=%u\n", path.c_str(),
                    static_cast<unsigned>(dataSize), recordPeak, lastRecordMean);
      appendEvent("RECORD_SAVED " + name + " bytes=" + String(dataSize) +
                  " peak=" + String(recordPeak) + " mean=" + String(lastRecordMean) +
                  " channel=" + micSelectedChannel);
    } else {
      LittleFS.remove(path);
      if (!error.length()) error = "record_no_audio_data";
    }
  }

  if (wav) wav.close();
  micI2S.end();
  if (error.length()) appendEvent("RECORD_FAILED " + error);
  showOled(error.length() ? "REC ERR" : "SAVED", error.length() ? error : name);
  finishAudio(error);
  vTaskDelete(nullptr);
}

bool readWavHeader(File &wav, WavHeader &header) {
  uint8_t riffHeader[12];
  if (!wav.seek(0) || wav.read(riffHeader, sizeof(riffHeader)) != sizeof(riffHeader) ||
      memcmp(riffHeader, "RIFF", 4) != 0 || memcmp(riffHeader + 8, "WAVE", 4) != 0) {
    return false;
  }

  auto readLe16 = [](const uint8_t *data) -> uint16_t {
    return static_cast<uint16_t>(data[0]) |
           (static_cast<uint16_t>(data[1]) << 8);
  };
  auto readLe32 = [](const uint8_t *data) -> uint32_t {
    return static_cast<uint32_t>(data[0]) |
           (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) |
           (static_cast<uint32_t>(data[3]) << 24);
  };

  bool foundFormat = false;
  memset(&header, 0, sizeof(header));
  memcpy(header.riff, "RIFF", 4);
  memcpy(header.wave, "WAVE", 4);

  while (wav.position() + 8 <= wav.size()) {
    uint8_t chunkHeader[8];
    if (wav.read(chunkHeader, sizeof(chunkHeader)) != sizeof(chunkHeader)) return false;
    const uint32_t chunkSize = readLe32(chunkHeader + 4);
    const size_t chunkDataPosition = wav.position();

    if (memcmp(chunkHeader, "fmt ", 4) == 0) {
      if (chunkSize < 16 || chunkDataPosition + chunkSize > wav.size()) return false;
      uint8_t format[16];
      if (wav.read(format, sizeof(format)) != sizeof(format)) return false;
      header.audioFormat = readLe16(format);
      header.channels = readLe16(format + 2);
      header.sampleRate = readLe32(format + 4);
      header.byteRate = readLe32(format + 8);
      header.blockAlign = readLe16(format + 12);
      header.bitsPerSample = readLe16(format + 14);
      foundFormat = true;
    } else if (memcmp(chunkHeader, "data", 4) == 0 && foundFormat) {
      memcpy(header.data, "data", 4);
      header.dataSize = std::min(chunkSize, static_cast<uint32_t>(wav.size() - wav.position()));
      return header.audioFormat == 1 && header.bitsPerSample == 16 &&
             (header.channels == 1 || header.channels == 2) &&
             header.sampleRate >= 8000 && header.sampleRate <= 48000;
    }

    const size_t nextChunk = chunkDataPosition + chunkSize + (chunkSize & 1U);
    if (nextChunk > wav.size() || !wav.seek(nextChunk)) return false;
  }
  return false;
}

bool beginAmplifier(uint32_t rate) {
  pinMode(AMP_SD, OUTPUT);
  digitalWrite(AMP_SD, LOW);
  ampI2S.setPins(AMP_BCLK, AMP_LRC, AMP_DIN);
  if (!ampI2S.begin(I2S_MODE_STD, rate, I2S_DATA_BIT_WIDTH_16BIT,
                    I2S_SLOT_MODE_STEREO, I2S_STD_SLOT_BOTH)) {
    return false;
  }
  digitalWrite(AMP_SD, HIGH);
  return true;
}

void endAmplifier() {
  delay(30);
  digitalWrite(AMP_SD, LOW);
  ampI2S.end();
}

void playbackTask(void *) {
  String name;
  xSemaphoreTake(stateMutex, portMAX_DELAY);
  name = activeFile;
  xSemaphoreGive(stateMutex);
  const String path = recordingPath(name);
  File wav = LittleFS.open(path, "r");
  WavHeader header = {};
  String error;

  if (!wav) {
    error = "file_not_found";
  } else if (!readWavHeader(wav, header)) {
    error = "unsupported_wav_use_pcm16_mono_or_stereo";
  } else if (!beginAmplifier(header.sampleRate)) {
    error = "amplifier_i2s_init_failed";
  }

  if (!error.length()) {
    showOled("PLAY", name.substring(0, 20));
    Serial.printf("PLAY_STARTED name=%s rate=%u channels=%u gain=%d%%\n",
                  name.c_str(), header.sampleRate, header.channels, PLAYBACK_GAIN_PERCENT);
    appendEvent("PLAY_STARTED " + name);
    int16_t input[512];
    int16_t output[1024];
    uint32_t remaining = header.dataSize;
    while (!stopRequested && remaining > 0) {
      const size_t wanted = std::min(static_cast<size_t>(remaining), sizeof(input));
      const size_t bytesRead = wav.read(reinterpret_cast<uint8_t *>(input), wanted);
      if (bytesRead == 0) break;
      remaining -= bytesRead;
      const size_t sampleCount = bytesRead / sizeof(int16_t);
      size_t outputCount = 0;
      if (header.channels == 1) {
        for (size_t i = 0; i < sampleCount; ++i) {
          const int16_t value = amplifiedSample(input[i], PLAYBACK_GAIN_PERCENT);
          output[outputCount++] = value;
          output[outputCount++] = value;
        }
      } else {
        for (size_t i = 0; i < sampleCount; ++i) {
          output[outputCount++] = amplifiedSample(input[i], PLAYBACK_GAIN_PERCENT);
        }
      }
      if (ampI2S.write(output, outputCount * sizeof(int16_t)) == 0) {
        error = "amplifier_write_failed";
        break;
      }
    }
    Serial.printf("PLAY_FINISHED name=%s error=%s\n", name.c_str(), error.c_str());
    appendEvent(error.length() ? "PLAY_FAILED " + error : "PLAY_FINISHED " + name);
    endAmplifier();
  }

  if (wav) wav.close();
  if (error.length()) {
    digitalWrite(AMP_SD, LOW);
    ampI2S.end();
  }
  showOled(error.length() ? "PLAY ERR" : "DONE", error.length() ? error : name);
  finishAudio(error);
  vTaskDelete(nullptr);
}

void writeTone(uint32_t frequency, uint32_t durationMs) {
  int16_t stereo[256 * 2];
  const uint32_t totalSamples = TONE_RATE * durationMs / 1000;
  uint32_t sent = 0;
  float phase = 0.0f;
  const float step = 2.0f * PI * frequency / TONE_RATE;
  while (!stopRequested && sent < totalSamples) {
    const size_t count = std::min(static_cast<uint32_t>(256), totalSamples - sent);
    for (size_t i = 0; i < count; ++i) {
      const int16_t sample = static_cast<int16_t>(sinf(phase) * 11000);
      phase += step;
      stereo[i * 2] = sample;
      stereo[i * 2 + 1] = sample;
    }
    ampI2S.write(stereo, count * 4);
    sent += count;
  }
}

void abcTask(void *) {
  String error;
  if (!beginAmplifier(TONE_RATE)) {
    error = "amplifier_i2s_init_failed";
  } else {
    showOled("ABC", "Press stop");
    static const uint16_t frequencies[] = {
      262, 262, 392, 392, 440, 440, 392,
      349, 349, 330, 330, 294, 294, 262
    };
    static const uint8_t beats[] = {1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 2};
    Serial.println("ABC_STARTED");
    appendEvent("ABC_STARTED");
    while (!stopRequested) {
      for (size_t i = 0; i < sizeof(frequencies) / sizeof(frequencies[0]) && !stopRequested; ++i) {
        writeTone(frequencies[i], beats[i] * 420);
        delay(25);
      }
      delay(100);
    }
    endAmplifier();
    Serial.println("ABC_STOPPED");
    appendEvent("ABC_STOPPED");
  }
  showOled(error.length() ? "ABC ERR" : "DONE", error);
  finishAudio(error);
  vTaskDelete(nullptr);
}

bool startRecording() {
  if (!reserveAudio(AudioMode::RECORDING)) return false;
  recordingLaunchPending = true;
  recordingLaunchAtMs = millis() + 150;
  return true;
}

void launchPendingRecording() {
  if (!recordingLaunchPending || static_cast<int32_t>(millis() - recordingLaunchAtMs) < 0) return;
  recordingLaunchPending = false;
  if (stopRequested) {
    finishAudio("record_cancelled_before_start");
    return;
  }
  if (xTaskCreatePinnedToCore(recordTask, "record", 8192, nullptr, 2, nullptr, 0) != pdPASS) {
    finishAudio("record_task_create_failed");
  }
}

bool startPlayback(const String &name) {
  if (!validWavName(name) || !LittleFS.exists(recordingPath(name))) return false;
  if (!reserveAudio(AudioMode::PLAYING, name)) return false;
  if (xTaskCreatePinnedToCore(playbackTask, "playback", 6144, nullptr, 2, nullptr, 0) != pdPASS) {
    finishAudio("playback_task_create_failed");
    return false;
  }
  return true;
}

bool startAbc() {
  if (!reserveAudio(AudioMode::ABC, "ABC melody")) return false;
  if (xTaskCreatePinnedToCore(abcTask, "abc", 4096, nullptr, 2, nullptr, 0) != pdPASS) {
    finishAudio("abc_task_create_failed");
    return false;
  }
  return true;
}

void requestStop() {
  stopRequested = true;
}

void cleanupEmptyRecordings() {
  std::vector<String> paths;
  File directory = LittleFS.open(RECORD_DIR);
  if (directory && directory.isDirectory()) {
    File file = directory.openNextFile();
    while (file) {
      if (!file.isDirectory() && file.size() <= sizeof(WavHeader)) {
        String path = file.name();
        const int slash = path.lastIndexOf('/');
        const String name = slash >= 0 ? path.substring(slash + 1) : path;
        if (validWavName(name)) paths.push_back(recordingPath(name));
      }
      file.close();
      file = directory.openNextFile();
    }
    directory.close();
  }
  for (const String &path : paths) {
    if (LittleFS.remove(path)) appendEvent("REMOVED_EMPTY_RECORDING " + path);
  }
}

String listRecordingsJson() {
  std::vector<String> names;
  File directory = LittleFS.open(RECORD_DIR);
  if (directory && directory.isDirectory()) {
    File file = directory.openNextFile();
    while (file) {
      if (!file.isDirectory()) {
        String path = file.name();
        const int slash = path.lastIndexOf('/');
        String name = slash >= 0 ? path.substring(slash + 1) : path;
        if (validWavName(name)) names.push_back(name);
      }
      file.close();
      file = directory.openNextFile();
    }
    directory.close();
  }
  std::sort(names.begin(), names.end(), [](const String &a, const String &b) { return a > b; });
  String json = "[";
  for (size_t i = 0; i < names.size(); ++i) {
    if (i) json += ',';
    json += "\"" + jsonEscape(names[i]) + "\"";
  }
  json += ']';
  return json;
}

void handleUploadData() {
  HTTPUpload &upload = server.upload();
  if (upload.status == UPLOAD_FILE_START) {
    uploadOk = false;
    uploadError = "";
    uploadName = upload.filename;
    if (!validWavName(uploadName)) {
      uploadError = "invalid_wav_filename";
      return;
    }
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    const bool busy = audioMode != AudioMode::IDLE;
    xSemaphoreGive(stateMutex);
    if (busy) {
      uploadError = "audio_busy";
      return;
    }
    uploadFile = LittleFS.open(recordingPath(uploadName), "w");
    if (!uploadFile) uploadError = "upload_file_open_failed";
  } else if (upload.status == UPLOAD_FILE_WRITE) {
    if (uploadFile && !uploadError.length() &&
        uploadFile.write(upload.buf, upload.currentSize) != upload.currentSize) {
      uploadError = "upload_write_failed";
    }
  } else if (upload.status == UPLOAD_FILE_END) {
    if (uploadFile) uploadFile.close();
    if (uploadError.length()) {
      if (validWavName(uploadName)) LittleFS.remove(recordingPath(uploadName));
    } else {
      uploadOk = true;
      Serial.printf("UPLOAD_SAVED name=%s bytes=%u\n", uploadName.c_str(), upload.totalSize);
    }
  } else if (upload.status == UPLOAD_FILE_ABORTED) {
    if (uploadFile) uploadFile.close();
    if (validWavName(uploadName)) LittleFS.remove(recordingPath(uploadName));
    uploadError = "upload_aborted";
  }
}

void registerRoutes() {
  server.on("/", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    server.send_P(200, "text/html; charset=utf-8", WEB_PAGE);
  });
  server.on("/api/status", HTTP_GET, []() { sendJson(200, statusJson()); });
  server.on("/api/logs", HTTP_GET, []() { sendJson(200, eventLogJson()); });
  server.on("/api/displays/status", HTTP_GET, []() {
    sendJson(200, "{\"ok\":true,\"primary\":" + String(oledPrimaryReady ? "true" : "false") + "}");
  });
  server.on("/api/list", HTTP_GET, []() { sendJson(200, listRecordingsJson()); });
  server.on("/api/servo/status", HTTP_GET, []() { sendJson(200, statusJson()); });
  server.on("/api/servo/move", HTTP_POST, []() {
    if (!servosReady) {
      sendJson(503, errorJson("servos_not_ready"));
      return;
    }
    const String direction = server.arg("direction");
    const int speed = server.hasArg("speed") ? server.arg("speed").toInt() : servoSpeed;
    if (!commandServos(direction, speed)) {
      sendJson(400, errorJson("invalid_servo_direction"));
    } else {
      sendJson(200, "{\"ok\":true,\"motion\":\"" + String(servoMotionName(servoMotion)) +
                    "\",\"speed\":" + String(servoSpeed) + "}");
    }
  });

  server.on("/api/record/start", HTTP_POST, []() {
    if (!startRecording()) sendJson(409, errorJson("audio_busy_or_start_failed"));
    else sendJson(200, statusJson());
  });
  server.on("/api/record/stop", HTTP_POST, []() {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    const bool recording = audioMode == AudioMode::RECORDING;
    xSemaphoreGive(stateMutex);
    if (!recording) sendJson(409, errorJson("not_recording"));
    else {
      requestStop();
      appendEvent("RECORD_STOP_REQUESTED");
      sendJson(202, "{\"ok\":true,\"state\":\"stopping\"}");
    }
  });
  server.on("/api/record/status", HTTP_GET, []() { sendJson(200, statusJson()); });

  server.on("/api/play/start", HTTP_POST, []() {
    const String name = server.arg("name");
    if (!validWavName(name) || !LittleFS.exists(recordingPath(name))) {
      sendJson(404, errorJson("file_not_found"));
    } else if (!startPlayback(name)) {
      sendJson(409, errorJson("audio_busy_or_start_failed"));
    } else {
      sendJson(200, statusJson());
    }
  });
  server.on("/api/play/stop", HTTP_POST, []() {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    const bool playing = audioMode == AudioMode::PLAYING || audioMode == AudioMode::ABC;
    xSemaphoreGive(stateMutex);
    if (!playing) sendJson(409, errorJson("not_playing"));
    else { requestStop(); sendJson(200, "{\"ok\":true}"); }
  });
  server.on("/api/play/status", HTTP_GET, []() { sendJson(200, statusJson()); });

  server.on("/api/abc/start", HTTP_POST, []() {
    if (!startAbc()) sendJson(409, errorJson("audio_busy_or_start_failed"));
    else sendJson(200, statusJson());
  });
  server.on("/api/abc/stop", HTTP_POST, []() {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    const bool abc = audioMode == AudioMode::ABC;
    xSemaphoreGive(stateMutex);
    if (!abc) sendJson(409, errorJson("abc_not_playing"));
    else { requestStop(); sendJson(200, "{\"ok\":true}"); }
  });
  server.on("/api/abc/status", HTTP_GET, []() { sendJson(200, statusJson()); });

  server.on("/api/oled/test", HTTP_POST, []() {
    if (!oledPrimaryReady) {
      sendJson(503, errorJson("no_oled_detected"));
    } else {
      requestExpression("blink");
      sendJson(200, "{\"ok\":true,\"primary\":true}");
    }
  });
  server.on("/api/oled/expression", HTTP_POST, []() {
    if (!oledPrimaryReady) {
      sendJson(503, errorJson("no_oled_detected"));
    } else if (!requestExpression(server.arg("name"))) {
      sendJson(400, errorJson("invalid_expression"));
    } else {
      sendJson(200, "{\"ok\":true,\"expression\":\"" +
                    String(expressionName(oledExpression)) + "\"}");
    }
  });

  server.on("/api/delete", HTTP_POST, []() {
    const String name = server.arg("name");
    if (!validWavName(name)) sendJson(400, errorJson("invalid_filename"));
    else if (!LittleFS.remove(recordingPath(name))) sendJson(404, errorJson("file_not_found"));
    else sendJson(200, "{\"ok\":true}");
  });

  server.on("/api/upload", HTTP_POST, []() {
    if (uploadOk) {
      sendJson(200, "{\"ok\":true,\"name\":\"" + jsonEscape(uploadName) + "\"}");
    } else {
      sendJson(400, errorJson(uploadError.length() ? uploadError : "upload_failed"));
    }
  }, handleUploadData);

  server.onNotFound([]() {
    const String uri = server.uri();
    const String legacyPrefix = "/api/play/start/";
    if (server.method() == HTTP_POST && uri.startsWith(legacyPrefix)) {
      const String name = uri.substring(legacyPrefix.length());
      if (!validWavName(name) || !LittleFS.exists(recordingPath(name))) {
        sendJson(404, errorJson("file_not_found"));
      } else if (!startPlayback(name)) {
        sendJson(409, errorJson("audio_busy_or_start_failed"));
      } else {
        sendJson(200, statusJson());
      }
      return;
    }
    const String filePrefix = "/recordings/";
    if (server.method() == HTTP_GET && uri.startsWith(filePrefix)) {
      const String name = uri.substring(filePrefix.length());
      if (!validWavName(name)) {
        server.send(403, "text/plain", "Forbidden");
        return;
      }
      File file = LittleFS.open(recordingPath(name), "r");
      if (!file) {
        server.send(404, "text/plain", "Not found");
        return;
      }
      server.streamFile(file, "audio/wav");
      file.close();
      return;
    }
    server.send(404, "text/plain", "Not found");
  });
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("WIFI_CONNECTING ssid=%s\n", WIFI_SSID);
  const uint32_t deadline = millis() + 20000;
  while (WiFi.status() != WL_CONNECTED && static_cast<int32_t>(deadline - millis()) > 0) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WIFI_CONNECTED ip=%s\n", WiFi.localIP().toString().c_str());
    configTime(8 * 3600, 0, "pool.ntp.org", "ntp.aliyun.com");
    appendEvent("WIFI_CONNECTED ip=" + WiFi.localIP().toString());
    requestExpression("happy");
  } else {
    Serial.println("WIFI_CONNECT_FAILED");
    showOled("NO WIFI", "Serial menu OK");
  }
}

void printMenu() {
  Serial.println("\n=== ESP32 ARDUINO AUDIO ===");
  Serial.println("1 - OLED test");
  Serial.println("2 - Start recording");
  Serial.println("3 - Play alphabet_announcement.wav");
  Serial.println("4 - Start ABC melody");
  Serial.println("0 - Stop recording/playback");
  Serial.println("s - Print status");
}

void handleSerialMenu() {
  if (!Serial.available()) return;
  const char choice = Serial.read();
  while (Serial.available()) Serial.read();
  switch (choice) {
    case '1':
      if (oledPrimaryReady) requestExpression("blink");
      else Serial.println("NO_OLED_DETECTED");
      break;
    case '2':
      Serial.println(startRecording() ? "RECORD_START_REQUESTED" : "AUDIO_BUSY");
      break;
    case '3':
      Serial.println(startPlayback("alphabet_announcement.wav") ? "PLAY_START_REQUESTED" : "FILE_MISSING_OR_BUSY");
      break;
    case '4':
      Serial.println(startAbc() ? "ABC_START_REQUESTED" : "AUDIO_BUSY");
      break;
    case '0':
      requestStop();
      Serial.println("STOP_REQUESTED");
      break;
    case 's':
      Serial.println(statusJson());
      break;
    default:
      printMenu();
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("ARDUINO_TALK_STARTING");
  pinMode(AMP_SD, OUTPUT);
  digitalWrite(AMP_SD, LOW);
  stateMutex = xSemaphoreCreateMutex();
  oledMutex = xSemaphoreCreateMutex();
  logMutex = xSemaphoreCreateMutex();
  appendEvent("ARDUINO_TALK_STARTING");
  initServos();

  if (!LittleFS.begin(true)) {
    Serial.println("LITTLEFS_MOUNT_FAILED");
  } else {
    LittleFS.mkdir(RECORD_DIR);
    cleanupEmptyRecordings();
    Serial.printf("LITTLEFS_READY total=%u used=%u\n",
                  static_cast<unsigned>(LittleFS.totalBytes()),
                  static_cast<unsigned>(LittleFS.usedBytes()));
  }

  initOled();
  connectWifi();
  registerRoutes();
  server.begin();
  Serial.println("HTTP_SERVER_READY port=80");
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WEB_URL http://%s/\n", WiFi.localIP().toString().c_str());
  }
  printMenu();
}

void loop() {
  server.handleClient();
  launchPendingRecording();
  handleSerialMenu();
  if (servoMotion != ServoMotion::STOPPED &&
      static_cast<int32_t>(millis() - servoCommandDeadlineMs) >= 0) {
    stopServos(true);
  }
  xSemaphoreTake(stateMutex, portMAX_DELAY);
  const bool idle = audioMode == AudioMode::IDLE;
  xSemaphoreGive(stateMutex);
  if (idle) updateOledAnimation();
  delay(2);
}
