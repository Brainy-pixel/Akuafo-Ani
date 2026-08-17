/*
 * Akuafo Ani — ESP32 Soil Sensor Node v1.4
 *
 * Hardware:
 *   ESP32 DevKit | RS485 7-in-1 Modbus soil sensor | MAX485 module
 *
 * Wiring:
 *   MAX485 DI (TX) → GPIO27    MAX485 RO (RX) → GPIO26
 *   MAX485 DE      → GPIO14    MAX485 RE      → GPIO13
 *   Sensor A+/B-   → MAX485 A/B terminals (12 V supply for sensor)
 *
 * Libraries (Sketch → Include Library → Manage Libraries):
 *   ArduinoJson by Benoit Blanchon
 *
 * Board: ESP32 Dev Module
 * Partition: Huge APP (3MB No OTA)
 */

#include <HardwareSerial.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── CONFIG ────────────────────────────────────────────────────────────────
#define WIFI_SSID     "YOUR_WIFI_NAME"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define PREDICT_URL   "https://akuafo-ani.onrender.com/api/predict"
#define OWM_KEY       "YOUR_OPENWEATHERMAP_API_KEY"

// Fixed farm location for OWM rainfall lookup
#define LOCATION_LAT   5.6037
#define LOCATION_LNG  -0.1870

#define READ_INTERVAL  300000UL   // 5 minutes between readings
#define RS485_BAUD     4800
#define SENSOR_ADDR    0x01

// ── PINS ──────────────────────────────────────────────────────────────────
#define RS485_TX  27   // ESP32 TX → MAX485 DI
#define RS485_RX  26   // ESP32 RX ← MAX485 RO
#define RE        13   // MAX485 RE (Receiver Enable, active LOW)
#define DE        14   // MAX485 DE (Driver Enable, active HIGH)

HardwareSerial RS485Serial(2);
unsigned long lastRead = 0;

struct Soil { float h, t, ec, ph, n, p, k; bool ok; };

// ── RS485 direction helpers ───────────────────────────────────────────────
inline void txMode() {
  digitalWrite(DE, HIGH);   // enable driver
  digitalWrite(RE, HIGH);   // disable receiver (avoid echo)
}

inline void rxMode() {
  digitalWrite(DE, LOW);    // disable driver
  digitalWrite(RE, LOW);    // enable receiver
}

// ── CRC-16/Modbus ─────────────────────────────────────────────────────────
uint16_t crc16(const uint8_t* d, uint8_t len) {
  uint16_t c = 0xFFFF;
  while (len--) {
    c ^= *d++;
    for (uint8_t i = 0; i < 8; i++)
      c = (c & 1) ? (c >> 1) ^ 0xA001 : c >> 1;
  }
  return c;
}

// ── Print helpers ─────────────────────────────────────────────────────────
void printHexByte(uint8_t b) {
  if (b < 0x10) Serial.print('0');
  Serial.print(b, HEX);
  Serial.print(' ');
}

void printHexMsg(const uint8_t* buf, uint8_t len) {
  for (uint8_t i = 0; i < len; i++) printHexByte(buf[i]);
  Serial.println();
}

// ── Read 7 registers from soil sensor ────────────────────────────────────
//
// Modbus response frame (19 bytes):
//   [0]    Device address  0x01
//   [1]    Function code   0x03
//   [2]    Byte count      0x0E (14 data bytes = 7 registers × 2)
//   [3-4]  Register 0  humidity    ×0.1 %
//   [5-6]  Register 1  temperature ×0.1 °C
//   [7-8]  Register 2  EC          μS/cm
//   [9-10] Register 3  pH          ×0.1
//   [11-12]Register 4  N           mg/kg
//   [13-14]Register 5  P           mg/kg
//   [15-16]Register 6  K           mg/kg
//   [17-18]CRC-16 (lo, hi)
//
// Fix: collect up to 24 raw bytes, then SCAN for the valid frame header
// (0x01, 0x03, 0x0E) to skip any direction-change glitch bytes.
// ─────────────────────────────────────────────────────────────────────────
Soil readSensor() {
  Soil s = {};
  const uint8_t FRAME_LEN = 19;   // expected Modbus response size

  // Build request
  uint8_t req[8] = { SENSOR_ADDR, 0x03, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00 };
  uint16_t c = crc16(req, 6);
  req[6] = c & 0xFF;
  req[7] = c >> 8;

  // Flush stale bytes
  while (RS485Serial.available()) RS485Serial.read();

  // ── TX ──
  txMode();
  delay(10);
  Serial.print(F("TX: ")); printHexMsg(req, sizeof(req));
  RS485Serial.write(req, sizeof(req));
  RS485Serial.flush();

  // Let the 485 bus settle after direction switch (avoids glitch byte)
  delay(20);
  rxMode();

  // ── RX: collect up to 24 bytes within 1000 ms ──
  const uint8_t BUFLEN = 24;
  uint8_t buf[BUFLEN];
  uint8_t total = 0;
  uint32_t t0 = millis();

  while (total < BUFLEN && millis() - t0 < 1000) {
    if (RS485Serial.available()) {
      buf[total++] = RS485Serial.read();
    }
  }

  Serial.print(F("RX raw (")); Serial.print(total); Serial.print(F(" bytes): "));
  printHexMsg(buf, total);
  Serial.println(F("--------------------------------"));

  if (total < FRAME_LEN) {
    Serial.printf("[RS485] Only %d/%d bytes — check wiring/12V supply\n", total, FRAME_LEN);
    return s;
  }

  // ── Scan for valid frame header: 0x01  0x03  0x0E ──
  int8_t frameStart = -1;
  for (uint8_t i = 0; i <= total - FRAME_LEN; i++) {
    if (buf[i] == 0x01 && buf[i+1] == 0x03 && buf[i+2] == 0x0E) {
      frameStart = (int8_t)i;
      break;
    }
  }

  if (frameStart < 0) {
    Serial.println(F("[RS485] Valid frame header not found in response"));
    return s;
  }

  if (frameStart > 0) {
    Serial.printf("[RS485] Skipped %d glitch byte(s) before frame\n", frameStart);
  }

  const uint8_t* f = buf + frameStart;

  // Validate CRC
  uint16_t rxCRC = (uint16_t)f[FRAME_LEN-1] << 8 | f[FRAME_LEN-2];
  if (rxCRC != crc16(f, FRAME_LEN-2)) {
    Serial.println(F("[RS485] CRC mismatch"));
    return s;
  }

  // Decode registers
  uint16_t r[7];
  for (uint8_t i = 0; i < 7; i++)
    r[i] = (uint16_t)f[3 + i*2] << 8 | f[4 + i*2];

  s.h  = r[0] * 0.1f;
  s.t  = r[1] * 0.1f;
  s.ec = (float)r[2];
  s.ph = r[3] * 0.1f;
  s.n  = (float)r[4];
  s.p  = (float)r[5];
  s.k  = (float)r[6];
  s.ok = true;
  return s;
}

// ── Rainfall via OpenWeatherMap ───────────────────────────────────────────
float fetchRain() {
  char url[224];
  snprintf(url, sizeof(url),
    "https://api.openweathermap.org/data/2.5/weather?lat=%.4f&lon=%.4f&appid=%s&units=metric",
    (float)LOCATION_LAT, (float)LOCATION_LNG, OWM_KEY);

  HTTPClient h;
  h.begin(url);
  int code = h.GET();
  if (code != 200) {
    Serial.printf("[OWM] HTTP %d\n", code);
    h.end();
    return 0.0f;
  }

  StaticJsonDocument<1024> doc;
  deserializeJson(doc, h.getString());
  h.end();

  float rain = doc["rain"]["1h"] | 0.0f;
  Serial.printf("[OWM] Location: %s  Rain 1h: %.1f mm\n",
    doc["name"].as<const char*>(), rain);
  return rain;
}

// ── WiFi connect ──────────────────────────────────────────────────────────
bool wifiConnect() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WiFi] Connected — IP: %s\n", WiFi.localIP().toString().c_str());
    return true;
  }
  Serial.println(F("[WiFi] Failed — will retry next cycle"));
  return false;
}

// ── POST to Akuafo Ani API ────────────────────────────────────────────────
void postAPI(const Soil& s, float rain) {
  if (!wifiConnect()) return;

  StaticJsonDocument<192> body;
  body["N"]           = s.n;
  body["P"]           = s.p;
  body["K"]           = s.k;
  body["temperature"] = s.t;
  body["humidity"]    = s.h;
  body["ph"]          = s.ph;
  body["rainfall"]    = rain;

  char js[192];
  serializeJson(body, js, sizeof(js));
  Serial.printf("[API] POST → %s\n", js);

  HTTPClient h;
  h.begin(PREDICT_URL);
  h.addHeader(F("Content-Type"), F("application/json"));
  int code = h.POST(js);

  if (code != 200) {
    Serial.printf("[API] HTTP %d\n", code);
    h.end();
    return;
  }

  StaticJsonDocument<3072> doc;
  deserializeJson(doc, h.getString());
  h.end();

  Serial.println(F("\n===== AKUAFO ANI RESULT ====="));

  if (doc["no_match"].as<bool>()) {
    Serial.println(F("STATUS : NO MATCH"));
    Serial.println(doc["message"] | "");
    if (doc["advice"] && doc["advice"] != "") {
      Serial.println(doc["advice"].as<const char*>());
    }
  } else {
    int rank = 1;
    char line[80];
    for (JsonObject r : doc["recommendations"].as<JsonArray>()) {
      snprintf(line, sizeof(line), "#%d %-20s %.0f%%",
        rank++,
        r["crop"].as<const char*>(),
        r["confidence"].as<float>() * 100.0f);
      Serial.println(line);
    }
    Serial.println(F("\n-- Improvement Tips --"));
    for (const char* tip : doc["improvement_tips"].as<JsonArray>()) {
      Serial.print(F("  * "));
      Serial.println(tip);
    }
  }

  Serial.printf("\n-- Soil Readings --\n"
    "N: %.1f mg/kg  P: %.1f mg/kg  K: %.1f mg/kg\n"
    "pH: %.2f  Temp: %.1f C  Humidity: %.1f%%  EC: %.0f uS/cm  Rain: %.1f mm\n",
    s.n, s.p, s.k, s.ph, s.t, s.h, s.ec, rain);
  Serial.println(F("=============================\n"));
}

// ── SETUP ─────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println(F("=============================="));
  Serial.println(F("  Akuafo Ani — Sensor Node"));
  Serial.println(F("=============================="));
  Serial.printf("DI / TX : GPIO %d\n", RS485_TX);
  Serial.printf("RO / RX : GPIO %d\n", RS485_RX);
  Serial.printf("DE      : GPIO %d\n", DE);
  Serial.printf("RE      : GPIO %d\n", RE);
  Serial.println();

  pinMode(DE, OUTPUT);
  pinMode(RE, OUTPUT);
  rxMode();

  RS485Serial.begin(RS485_BAUD, SERIAL_8N1, RS485_RX, RS485_TX);
  Serial.println(F("[Boot] RS485 ready"));

  // Give sensor time to power up before first read
  Serial.println(F("[Boot] Waiting 5s for sensor warm-up..."));
  delay(5000);

  wifiConnect();
  delay(1000);
  Serial.println(F("[Boot] Starting first reading...\n"));
}

// ── LOOP ──────────────────────────────────────────────────────────────────
void loop() {
  if (lastRead && millis() - lastRead < READ_INTERVAL) return;
  lastRead = millis();

  Serial.println(F("\n[Cycle] ---- New Reading ----"));

  // 1. Get rainfall from OWM
  float rain = 0.0f;
  if (wifiConnect()) rain = fetchRain();

  // 2. Read soil sensor
  Soil s = readSensor();
  if (!s.ok) {
    Serial.println(F("[Sensor] Retrying in 5s..."));
    delay(5000);
    s = readSensor();
  }
  if (!s.ok) {
    Serial.println(F("[Sensor] Failed twice. Check RS485 wiring and 12V supply."));
    return;
  }

  Serial.printf("[Soil] N=%.1f P=%.1f K=%.1f pH=%.2f T=%.1f RH=%.1f EC=%.0f\n",
    s.n, s.p, s.k, s.ph, s.t, s.h, s.ec);

  // 3. POST to Akuafo Ani
  postAPI(s, rain);
}
