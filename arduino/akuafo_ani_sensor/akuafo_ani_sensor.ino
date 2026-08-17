/*
 * Akuafo Ani — ESP32 Soil Sensor Node v2.0
 *
 * Hardware:
 *   ESP32 DevKit | SN-3002 7-in-1 RS485 Modbus soil sensor | MAX485 module
 *
 * Wiring:
 *   MAX485 RO  → GPIO26   MAX485 DI ← GPIO27
 *   MAX485 RE  → GPIO13   MAX485 DE ← GPIO14
 *   Sensor A+/B- → MAX485 A/B terminals (12 V supply for sensor)
 *
 * Libraries (Sketch → Manage Libraries):
 *   ArduinoJson by Benoit Blanchon
 *
 * Board   : ESP32 Dev Module
 * Partition: Huge APP (3MB No OTA)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── WiFi / API config ─────────────────────────────────────────────────────
#define WIFI_SSID       "YOUR_WIFI_NAME"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"
#define PREDICT_URL     "https://akuafo-ani.onrender.com/api/predict"
#define OWM_KEY         "YOUR_OPENWEATHERMAP_API_KEY"

// Fixed farm coordinates for OWM rainfall lookup
#define LOCATION_LAT    5.6037
#define LOCATION_LNG   -0.1870

#define READ_INTERVAL   300000UL   // 5 minutes between readings

// ── RS485 / sensor config ─────────────────────────────────────────────────
#define RS485_RX_PIN  26   // MAX485 RO → ESP32 RX
#define RS485_TX_PIN  27   // ESP32 TX  → MAX485 DI
#define RS485_RE_PIN  13
#define RS485_DE_PIN  14
#define SENSOR_ID     0x01
#define BAUD_RATE     4800

HardwareSerial RS485Serial(2);
unsigned long lastRead = 0;


// ── RS485 direction control ───────────────────────────────────────────────

void rs485Transmit() {
  digitalWrite(RS485_RE_PIN, HIGH);
  digitalWrite(RS485_DE_PIN, HIGH);
}

void rs485Receive() {
  digitalWrite(RS485_DE_PIN, LOW);
  digitalWrite(RS485_RE_PIN, LOW);
}


// ── Modbus CRC16 ──────────────────────────────────────────────────────────

uint16_t modbusCRC(uint8_t *buffer, uint8_t length) {
  uint16_t crc = 0xFFFF;
  for (uint8_t pos = 0; pos < length; pos++) {
    crc ^= buffer[pos];
    for (uint8_t i = 0; i < 8; i++) {
      if (crc & 0x0001) { crc >>= 1; crc ^= 0xA001; }
      else               { crc >>= 1; }
    }
  }
  return crc;
}


// ── Read 7 registers from soil sensor ────────────────────────────────────
// Registers: [0] Moisture  [1] Temperature  [2] EC
//            [3] pH        [4] N  [5] P  [6] K

bool readSoilSensor(uint16_t *values) {

  uint8_t request[8];
  request[0] = SENSOR_ID;
  request[1] = 0x03;
  request[2] = 0x00;
  request[3] = 0x00;
  request[4] = 0x00;
  request[5] = 0x07;

  uint16_t crc = modbusCRC(request, 6);
  request[6] = crc & 0xFF;
  request[7] = (crc >> 8) & 0xFF;

  // Flush stale bytes
  while (RS485Serial.available()) RS485Serial.read();

  rs485Transmit();
  delayMicroseconds(100);
  RS485Serial.write(request, 8);
  RS485Serial.flush();
  delayMicroseconds(100);
  rs485Receive();

  // Read 19-byte response
  uint8_t response[19];
  uint8_t index = 0;
  unsigned long startTime = millis();

  while (millis() - startTime < 1000) {
    if (RS485Serial.available()) {
      response[index++] = RS485Serial.read();
      if (index >= 19) break;
    }
  }

  if (index != 19) {
    Serial.print(F("ERROR: Expected 19 bytes, received "));
    Serial.println(index);
    return false;
  }

  // Print raw bytes
  Serial.print(F("RX: "));
  for (uint8_t i = 0; i < index; i++) {
    if (response[i] < 0x10) Serial.print('0');
    Serial.print(response[i], HEX);
    Serial.print(' ');
  }
  Serial.println();

  if (response[0] != SENSOR_ID) { Serial.println(F("ERROR: Wrong sensor ID"));      return false; }
  if (response[1] != 0x03)      { Serial.println(F("ERROR: Invalid function code")); return false; }
  if (response[2] != 14)        { Serial.println(F("ERROR: Invalid byte count"));    return false; }

  uint16_t receivedCRC   = response[17] | ((uint16_t)response[18] << 8);
  uint16_t calculatedCRC = modbusCRC(response, 17);
  if (receivedCRC != calculatedCRC) {
    Serial.println(F("ERROR: CRC mismatch"));
    return false;
  }

  for (uint8_t i = 0; i < 7; i++) {
    values[i] = ((uint16_t)response[3 + i*2] << 8) | response[4 + i*2];
  }
  return true;
}


// ── WiFi connect ──────────────────────────────────────────────────────────

bool wifiConnect() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(500); Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WiFi] Connected — IP: %s\n", WiFi.localIP().toString().c_str());
    return true;
  }
  Serial.println(F("[WiFi] Failed — will retry next cycle"));
  return false;
}


// ── Rainfall from OpenWeatherMap ──────────────────────────────────────────

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


// ── POST sensor values to Akuafo Ani app ─────────────────────────────────

void postToApp(float moisture, float temperature, float ec,
               float pH, uint16_t N, uint16_t P, uint16_t K,
               float rain) {

  if (!wifiConnect()) return;

  // Build JSON body
  // Note: app FIELDS = [N, P, K, temperature, humidity, ph, rainfall]
  // "humidity" in the model = soil moisture from the sensor
  StaticJsonDocument<192> body;
  body["N"]           = N;
  body["P"]           = P;
  body["K"]           = K;
  body["temperature"] = temperature;
  body["humidity"]    = moisture;   // sensor moisture → app humidity field
  body["ph"]          = pH;
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

  // ── Print result ─────────────────────────────────────────────────────
  Serial.println(F("\n===== AKUAFO ANI RESULT ====="));

  if (doc["no_match"].as<bool>()) {
    Serial.println(F("STATUS : NO MATCHING CROP"));
    Serial.println(doc["message"] | "");
    if (doc.containsKey("advice") && doc["advice"] != "")
      Serial.println(doc["advice"].as<const char*>());
  } else {
    int rank = 1;
    char line[80];
    for (JsonObject rec : doc["recommendations"].as<JsonArray>()) {
      snprintf(line, sizeof(line), "#%d %-22s %.0f%%",
        rank++,
        rec["crop"].as<const char*>(),
        rec["confidence"].as<float>() * 100.0f);
      Serial.println(line);
    }
    Serial.println(F("-- Improvement Tips --"));
    for (const char* tip : doc["improvement_tips"].as<JsonArray>()) {
      Serial.print(F("  * ")); Serial.println(tip);
    }
  }
  Serial.println(F("=============================\n"));
}


// ── Setup ─────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);

  pinMode(RS485_RE_PIN, OUTPUT);
  pinMode(RS485_DE_PIN, OUTPUT);
  rs485Receive();

  RS485Serial.begin(BAUD_RATE, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);

  Serial.println();
  Serial.println(F("=============================="));
  Serial.println(F(" SN-3002 7-IN-1 SOIL SENSOR"));
  Serial.println(F(" Akuafo Ani Node v2.0"));
  Serial.println(F("=============================="));
  Serial.println(F("Baud: 4800  |  Slave ID: 1"));
  Serial.println();

  Serial.println(F("[Boot] Waiting 5s for sensor warm-up..."));
  delay(5000);

  wifiConnect();
  delay(1000);
  Serial.println(F("[Boot] Ready.\n"));
}


// ── Main loop ─────────────────────────────────────────────────────────────

void loop() {
  // Run immediately on first boot, then every READ_INTERVAL
  if (lastRead && millis() - lastRead < READ_INTERVAL) return;
  lastRead = millis();

  Serial.println(F("\n[Cycle] ---- New Reading ----"));

  uint16_t values[7];

  if (!readSoilSensor(values)) {
    Serial.println(F("[Sensor] Retrying in 5s..."));
    delay(5000);
    if (!readSoilSensor(values)) {
      Serial.println(F("[Sensor] Failed twice. Check RS485 wiring and 12V supply."));
      return;
    }
  }

  // ── Convert raw register values ───────────────────────────────────────
  float    moisture    = values[0] / 10.0f;
  float    temperature = (int16_t)values[1] / 10.0f;  // signed for negatives
  float    ec          = (float)values[2];
  float    pH          = values[3] / 10.0f;
  uint16_t nitrogen    = values[4];
  uint16_t phosphorus  = values[5];
  uint16_t potassium   = values[6];

  // ── Print to Serial Monitor ───────────────────────────────────────────
  Serial.println();
  Serial.println(F("--------------------------------"));
  Serial.print(F("Soil Moisture : ")); Serial.print(moisture, 1);    Serial.println(F(" %"));
  Serial.print(F("Temperature   : ")); Serial.print(temperature, 1); Serial.println(F(" degC"));
  Serial.print(F("EC            : ")); Serial.print(ec, 0);          Serial.println(F(" uS/cm"));
  Serial.print(F("pH            : ")); Serial.println(pH, 1);
  Serial.print(F("Nitrogen      : ")); Serial.print(nitrogen);       Serial.println(F(" mg/kg"));
  Serial.print(F("Phosphorus    : ")); Serial.print(phosphorus);     Serial.println(F(" mg/kg"));
  Serial.print(F("Potassium     : ")); Serial.print(potassium);      Serial.println(F(" mg/kg"));
  Serial.println(F("--------------------------------"));

  // ── Get rainfall then send to app ─────────────────────────────────────
  float rain = 0.0f;
  if (wifiConnect()) rain = fetchRain();

  postToApp(moisture, temperature, ec, pH, nitrogen, phosphorus, potassium, rain);
}
