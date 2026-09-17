#include <FS.h>
#include <SD.h>
#include <SPI.h>

static constexpr int SD_SCK_PIN = 7;
static constexpr int SD_MISO_PIN = 8;
static constexpr int SD_MOSI_PIN = 9;
static constexpr int SD_CS_PINS[] = {3, 21};
static constexpr uint32_t SD_FREQUENCIES[] = {4000000, 1000000, 400000};
static constexpr char TEST_PATH[] = "/glass_sd_probe.txt";

SPIClass sdSpi(FSPI);

bool testSd(int cs, uint32_t frequency) {
  SD.end();
  sdSpi.end();
  delay(150);

  for (int candidate : SD_CS_PINS) {
    pinMode(candidate, OUTPUT);
    digitalWrite(candidate, HIGH);
  }
  sdSpi.begin(SD_SCK_PIN, SD_MISO_PIN, SD_MOSI_PIN, cs);

  Serial.printf("SD_PROBE cs=%d frequency=%lu\n", cs, frequency);
  if (!SD.begin(cs, sdSpi, frequency)) {
    Serial.println("SD_MOUNT_FAILED");
    return false;
  }
  if (SD.cardType() == CARD_NONE) {
    Serial.println("SD_CARD_NONE");
    SD.end();
    return false;
  }

  const String expected = "xiao_sd_probe_ms=" + String(millis());
  File output = SD.open(TEST_PATH, FILE_WRITE);
  if (!output) {
    Serial.println("SD_OPEN_WRITE_FAILED");
    SD.end();
    return false;
  }
  output.println(expected);
  output.close();

  File input = SD.open(TEST_PATH, FILE_READ);
  if (!input) {
    Serial.println("SD_OPEN_READ_FAILED");
    SD.end();
    return false;
  }
  String actual = input.readStringUntil('\n');
  actual.trim();
  input.close();

  Serial.printf("SD_SUCCESS cs=%d frequency=%lu type=%u size_mb=%llu readback=%s\n",
                cs, frequency, SD.cardType(), SD.cardSize() / (1024ULL * 1024ULL),
                actual.c_str());
  SD.end();
  return actual == expected;
}

void setup() {
  Serial.begin(115200);
  delay(1200);
  Serial.println("SD_DIAGNOSTIC_START");

  for (uint32_t frequency : SD_FREQUENCIES) {
    for (int cs : SD_CS_PINS) {
      if (testSd(cs, frequency)) {
        Serial.println("SD_DIAGNOSTIC_PASS");
        return;
      }
    }
  }
  Serial.println("SD_DIAGNOSTIC_FAIL_ALL_CONFIGS");
}

void loop() {
  delay(1000);
}
