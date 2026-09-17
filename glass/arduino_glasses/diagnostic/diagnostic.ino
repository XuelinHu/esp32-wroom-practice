#include <ESP_I2S.h>

constexpr int PDM_CLOCK_PIN = 42;
constexpr int PDM_DATA_PIN = 41;
constexpr int SAMPLE_RATE = 16000;

I2SClass pdmMic;
uint32_t sampleCount = 0;
int16_t minSample = INT16_MAX;
int16_t maxSample = INT16_MIN;
uint32_t lastReport = 0;

void setup() {
  Serial.begin(115200);
  delay(1500);
  pdmMic.setPinsPdmRx(PDM_CLOCK_PIN, PDM_DATA_PIN);
  bool ready = pdmMic.begin(I2S_MODE_PDM_RX, SAMPLE_RATE,
                            I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
  Serial.printf("PDM_DIAGNOSTIC_READY=%d\n", ready);
}

void loop() {
  int sample = pdmMic.read();
  if (sample >= 0) {
    int16_t pcm = static_cast<int16_t>(sample);
    sampleCount++;
    minSample = min(minSample, pcm);
    maxSample = max(maxSample, pcm);
  }
  if (millis() - lastReport >= 1000) {
    Serial.printf("PDM_SAMPLES=%lu MIN=%d MAX=%d\n", sampleCount, minSample, maxSample);
    sampleCount = 0;
    minSample = INT16_MAX;
    maxSample = INT16_MIN;
    lastReport = millis();
  }
}
