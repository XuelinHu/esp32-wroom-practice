#include <WiFi.h>
#include <esp_camera.h>
#include <ArduinoWebsockets.h>
#include <ESP_I2S.h>
#include <SPI.h>
#include <SD.h>

#include "camera_pins.h"
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

using namespace websockets;

static constexpr char CAMERA_WS_PATH[] = "/ws/camera";
static constexpr char AUDIO_WS_PATH[] = "/ws/audio";
static constexpr int PDM_CLOCK_PIN = 42;
static constexpr int PDM_DATA_PIN = 41;
static constexpr int SAMPLE_RATE = 16000;
static constexpr int AUDIO_CHUNK_MS = 20;
static constexpr size_t AUDIO_CHUNK_BYTES = SAMPLE_RATE * AUDIO_CHUNK_MS / 1000 * 2;

// Sense expansion board SD SPI. Do not use these pins for the speaker.
static constexpr int SD_SCK_PIN = 7;
static constexpr int SD_MISO_PIN = 8;
static constexpr int SD_MOSI_PIN = 9;
static constexpr int SD_CS_PINS[] = {3, 21};
static constexpr uint32_t SD_FREQUENCIES[] = {4000000, 1000000, 400000};
static constexpr int STATUS_LED_PIN = LED_BUILTIN;
bool sdReady = false;
int activeSdCs = -1;

WebsocketsClient cameraSocket;
WebsocketsClient audioSocket;
I2SClass pdmMic;
SPIClass sdSpi(FSPI);
volatile bool cameraConnected = false;
volatile bool audioConnected = false;
volatile bool listenActive = false;
uint32_t lastWifiAttempt = 0;
uint32_t lastStatusReport = 0;
uint32_t lastCameraFrame = 0;
uint32_t lastCameraConnectAttempt = 0;
uint32_t lastAudioConnectAttempt = 0;
uint32_t cameraFrameIntervalMs = 2000;
volatile uint32_t audioCapturedChunks = 0;
volatile uint32_t audioDroppedChunks = 0;
uint32_t audioSentChunks = 0;
uint32_t audioSendFailures = 0;

struct AudioChunk {
  uint16_t size;
  uint8_t data[AUDIO_CHUNK_BYTES];
};

QueueHandle_t audioQueue;

void clearAudioQueue() {
  if (audioQueue != nullptr) {
    xQueueReset(audioQueue);
  }
}

bool initCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_XGA;
  config.jpeg_quality = 14;
  config.fb_count = 2;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t result = esp_camera_init(&config);
  if (result != ESP_OK) {
    Serial.printf("CAMERA_INIT_FAILED 0x%x\n", result);
    return false;
  }
  Serial.println("CAMERA_READY JPEG XGA 1024x768");
  return true;
}

bool initPdmMic() {
  pdmMic.setPinsPdmRx(PDM_CLOCK_PIN, PDM_DATA_PIN);
  bool ready = pdmMic.begin(I2S_MODE_PDM_RX, SAMPLE_RATE,
                            I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
  Serial.println(ready ? "PDM_MIC_READY 16000Hz" : "PDM_MIC_INIT_FAILED");
  return ready;
}

bool mountSd(int cs, uint32_t frequency) {
  SD.end();
  sdSpi.end();
  for (int candidate : SD_CS_PINS) {
    pinMode(candidate, OUTPUT);
    digitalWrite(candidate, HIGH);
  }
  delay(100);
  sdSpi.begin(SD_SCK_PIN, SD_MISO_PIN, SD_MOSI_PIN, cs);
  return SD.begin(cs, sdSpi, frequency) && SD.cardType() != CARD_NONE;
}

void initSd() {
  sdReady = false;
  activeSdCs = -1;
  for (uint32_t frequency : SD_FREQUENCIES) {
    for (int cs : SD_CS_PINS) {
      Serial.printf("SD_PROBE cs=%d frequency=%lu\n", cs, frequency);
      if (mountSd(cs, frequency)) {
        sdReady = true;
        activeSdCs = cs;
        Serial.printf("SD_READY cs=%d frequency=%lu bytes=%llu\n",
                      cs, frequency, SD.totalBytes());
        return;
      }
    }
  }
  Serial.println("SD_NOT_DETECTED all supported configurations failed");
}

void reportSdTest() {
  if (!sdReady) {
    cameraSocket.send("SD_ERROR card not mounted; insert card and reset device");
    return;
  }
  const char *path = "/glass_sd_test.txt";
  String written = "glass_sd_test_ms=" + String(millis());
  File file = SD.open(path, FILE_APPEND);
  if (!file) {
    cameraSocket.send("SD_ERROR cannot open test file");
    return;
  }
  file.println(written);
  file.close();

  file = SD.open(path, FILE_READ);
  if (!file) {
    cameraSocket.send("SD_ERROR cannot read test file");
    return;
  }
  String lastLine;
  while (file.available()) {
    String line = file.readStringUntil('\n');
    if (line.length()) lastLine = line;
  }
  file.close();
  cameraSocket.send("SD_OK cs=" + String(activeSdCs) + " read=" + lastLine);
}

void updateStatusLed() {
  static bool previousActive = false;
  const bool active = listenActive;
  if (active == previousActive) {
    return;
  }
  // XIAO ESP32-S3 user LED is active-low.
  ledcWrite(STATUS_LED_PIN, active ? 0 : 255);
  previousActive = active;
  Serial.println(active ? "STATUS_LED_RECORDING_ON" : "STATUS_LED_RECORDING_OFF");
}

void setCameraResolution(const String &key) {
  framesize_t frameSize = FRAMESIZE_VGA;
  uint32_t intervalMs = 1000;
  int width = 640;
  int height = 480;

  if (key == "qvga") {
    frameSize = FRAMESIZE_QVGA;
    intervalMs = 500;
    width = 320;
    height = 240;
  } else if (key == "vga") {
    frameSize = FRAMESIZE_VGA;
  } else if (key == "svga") {
    frameSize = FRAMESIZE_SVGA;
    intervalMs = 1500;
    width = 800;
    height = 600;
  } else if (key == "xga") {
    frameSize = FRAMESIZE_XGA;
    intervalMs = 2000;
    width = 1024;
    height = 768;
  } else if (key == "hd") {
    frameSize = FRAMESIZE_HD;
    intervalMs = 2500;
    width = 1280;
    height = 720;
  } else if (key == "uxga") {
    frameSize = FRAMESIZE_UXGA;
    intervalMs = 3500;
    width = 1600;
    height = 1200;
  } else if (key == "qxga") {
    frameSize = FRAMESIZE_QXGA;
    intervalMs = 5000;
    width = 2048;
    height = 1536;
  } else {
    cameraSocket.send("CAMERA_SIZE_ERROR unsupported resolution");
    return;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (!sensor || sensor->set_framesize(sensor, frameSize) != 0) {
    cameraSocket.send("CAMERA_SIZE_ERROR sensor rejected resolution");
    return;
  }
  cameraFrameIntervalMs = intervalMs;
  cameraSocket.send("CAMERA_SIZE_OK key=" + key + " size=" + String(width) + "x" +
                    String(height) + " interval_ms=" + String(intervalMs));
}

void sendCameraFrame() {
  if (!cameraConnected || millis() - lastCameraFrame < cameraFrameIntervalMs) {
    return;
  }
  lastCameraFrame = millis();
  camera_fb_t *frame = esp_camera_fb_get();
  if (!frame) {
    return;
  }
  bool sent = cameraSocket.sendBinary((const char *)frame->buf, frame->len);
  esp_camera_fb_return(frame);
  if (!sent) {
    cameraSocket.close();
    cameraConnected = false;
  }
}

void captureAudioTask(void *) {
  for (;;) {
    if (!audioConnected || !listenActive) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }
    AudioChunk chunk = {.size = AUDIO_CHUNK_BYTES};
    size_t offset = 0;
    while (offset < sizeof(chunk.data)) {
      int sample = pdmMic.read();
      if (sample < 0) {
        vTaskDelay(pdMS_TO_TICKS(1));
        continue;
      }
      chunk.data[offset++] = sample & 0xff;
      chunk.data[offset++] = (sample >> 8) & 0xff;
    }
    audioCapturedChunks++;
    if (xQueueSend(audioQueue, &chunk, 0) != pdPASS) {
      audioDroppedChunks++;
      AudioChunk discarded;
      xQueueReceive(audioQueue, &discarded, 0);
      xQueueSend(audioQueue, &chunk, 0);
    }
  }
}

void sendQueuedAudio() {
  if (!audioConnected || !listenActive) {
    clearAudioQueue();
    return;
  }
  static uint8_t batch[AUDIO_CHUNK_BYTES * 10];
  AudioChunk chunk;
  size_t total = 0;
  while (total + AUDIO_CHUNK_BYTES <= sizeof(batch) &&
         xQueueReceive(audioQueue, &chunk, 0) == pdPASS) {
    memcpy(batch + total, chunk.data, chunk.size);
    total += chunk.size;
  }
  if (total) {
    if (!audioSocket.sendBinary((const char *)batch, total)) {
      audioSendFailures++;
      audioSocket.close();
      audioConnected = false;
    } else {
      audioSentChunks += total / AUDIO_CHUNK_BYTES;
    }
  }
}

void beginWifi() {
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  delay(200);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWifiAttempt = millis();
  Serial.println("WIFI_CONNECTING");
}

void reportTargetWifi() {
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  delay(200);
  WiFi.mode(WIFI_STA);
  delay(300);
  const int networkCount = WiFi.scanNetworks();
  bool found = false;
  for (int i = 0; i < networkCount; ++i) {
    if (WiFi.SSID(i) == WIFI_SSID) {
      found = true;
      Serial.printf("WIFI_TARGET_FOUND channel=%d rssi=%d\n", WiFi.channel(i), WiFi.RSSI(i));
      break;
    }
  }
  if (!found) {
    Serial.printf("WIFI_TARGET_NOT_FOUND scanned=%d\n", networkCount);
  }
  WiFi.scanDelete();
}

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("GLASSES_STARTING");
  ledcAttach(STATUS_LED_PIN, 5000, 8);
  ledcWrite(STATUS_LED_PIN, 255);
  beginWifi();
  initSd();
  if (!initCamera() || !initPdmMic()) {
    Serial.println("FATAL_INIT_FAILURE");
    while (true) delay(1000);
  }
  cameraSocket.onEvent([](WebsocketsEvent event, String) {
    if (event == WebsocketsEvent::ConnectionOpened) {
      cameraConnected = true;
      Serial.println("WS_CAMERA_CONNECTED");
    } else if (event == WebsocketsEvent::ConnectionClosed) {
      cameraConnected = false;
      Serial.println("WS_CAMERA_DISCONNECTED");
    }
  });
  cameraSocket.onMessage([](WebsocketsMessage message) {
    if (message.data() == "sd_test") {
      reportSdTest();
    } else if (message.data().startsWith("camera_size:")) {
      setCameraResolution(message.data().substring(12));
    }
  });
  audioSocket.onEvent([](WebsocketsEvent event, String) {
    if (event == WebsocketsEvent::ConnectionOpened) {
      audioConnected = true;
      Serial.println("WS_AUDIO_CONNECTED");
    } else if (event == WebsocketsEvent::ConnectionClosed) {
      audioConnected = false;
      listenActive = false;
      clearAudioQueue();
      Serial.println("WS_AUDIO_DISCONNECTED");
    }
  });
  audioQueue = xQueueCreate(128, sizeof(AudioChunk));
  audioSocket.onMessage([](WebsocketsMessage message) {
    const String command = message.data();
    if (command == "LISTEN_START") {
      clearAudioQueue();
      if (audioSocket.send("START")) {
        listenActive = true;
        Serial.println("AUDIO_LISTEN_STARTED");
      }
    } else if (command == "LISTEN_STOP") {
      listenActive = false;
      clearAudioQueue();
      audioSocket.send("STOP");
      Serial.println("AUDIO_LISTEN_STOPPED");
    } else if (command == "RESET" || command == "RESTART") {
      listenActive = false;
      clearAudioQueue();
      Serial.println("AUDIO_LISTEN_RESET");
    }
  });
  xTaskCreatePinnedToCore(captureAudioTask, "pdm_capture", 4096, nullptr, 2, nullptr, 0);
}

void loop() {
  updateStatusLed();
  if (millis() - lastStatusReport >= 5000) {
    lastStatusReport = millis();
    Serial.printf("STATUS wifi=%d ip=%s camera_ws=%d audio_ws=%d listening=%d pcm=%lu sent=%lu drop=%lu fail=%lu\n",
                  WiFi.status(), WiFi.localIP().toString().c_str(), cameraConnected, audioConnected,
                  listenActive, audioCapturedChunks, audioSentChunks, audioDroppedChunks, audioSendFailures);
  }

  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiAttempt >= 10000) {
      Serial.println("WIFI_RETRY");
      reportTargetWifi();
      beginWifi();
    }
    delay(500);
    return;
  }
  if (!cameraConnected && millis() - lastCameraConnectAttempt >= 2000) {
    lastCameraConnectAttempt = millis();
    cameraSocket.close();
    Serial.printf("WS_CAMERA_CONNECT=%d\n",
                  cameraSocket.connect(SERVER_HOST, SERVER_PORT, CAMERA_WS_PATH));
  }
  if (!audioConnected && millis() - lastAudioConnectAttempt >= 2000) {
    lastAudioConnectAttempt = millis();
    audioSocket.close();
    Serial.printf("WS_AUDIO_CONNECT=%d\n",
                  audioSocket.connect(SERVER_HOST, SERVER_PORT, AUDIO_WS_PATH));
  }
  cameraSocket.poll();
  audioSocket.poll();
  sendQueuedAudio();
  sendCameraFrame();
  cameraSocket.poll();
  audioSocket.poll();
  delay(1);
}
