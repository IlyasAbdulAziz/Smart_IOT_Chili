/*
 * ============================================================================
 * SMART AGRICULTURE: AUTOMATIC CHILI PLANT IRRIGATION SYSTEM
 * Tim: "Denger Azan Kok Lanjut Pidato"
 *
 * Fitur Firmware:
 * 1. Otomatis kompatibel untuk board berbasis ESP8266 (WeMos D1 R1/R2)
 *    maupun ESP32 (D1 R32 / DevKit).
 * 2. Membaca Capacitive Soil Moisture Sensor v2.0 (Pin Analog A0)
 *    dan Sensor Suhu & Kelembapan Udara DHT22.
 * 3. Mengirim data JSON ke Server Django (`POST /api/sensor/`) setiap 3 detik
 *    dan menerima balasan perintah Pompa (`pump: true/false`).
 * 4. Dilengkapi Safety Cut-Off mandiri bila koneksi Wi-Fi terputus.
 * ============================================================================
 */

#if defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266HTTPClient.h>
  #include <WiFiClient.h>
  #define PIN_SOIL A0
  #define PIN_DHT  D4   // GPIO2 pada WeMos D1
  #define PIN_RELAY D5  // GPIO14 pada WeMos D1
  // Nilai kalibrasi ADC 10-bit (0-1023) untuk Capacitive Soil Moisture v2.0
  int ADC_KERING = 820; // Nilai saat sensor kering di udara (0%)
  int ADC_BASAH  = 390; // Nilai saat sensor dicelup air (100%)
#elif defined(ESP32)
  #include <WiFi.h>
  #include <HTTPClient.h>
  #include <WiFiClient.h>
  #define PIN_SOIL 36   // Pin VP / A0 pada ESP32
  #define PIN_DHT  4    // GPIO4
  #define PIN_RELAY 5   // GPIO5
  // Nilai kalibrasi ADC 12-bit (0-4095) untuk Capacitive Soil Moisture v2.0
  int ADC_KERING = 3100;
  int ADC_BASAH  = 1450;
#endif

#include <DHT.h>

// ---------------- KONFIGURASI WI-FI & SERVER DJANGO ----------------
const char* WIFI_SSID     = "ARKAUL";
const char* WIFI_PASSWORD = "ISI_PASSWORD_WIFI"; // Diganti placeholder agar password aman saat di-push ke GitHub

// IPv4 Wi-Fi Laptop kamu saat ini: 192.168.18.205
const char* SERVER_URL    = "http://192.168.18.205:8000/api/sensor/";

// Relay Module 2-Channel umumnya Active LOW (LOW = Menyala, HIGH = Mati)
#define RELAY_ON  LOW
#define RELAY_OFF HIGH

#define DHTTYPE DHT22
DHT dht(PIN_DHT, DHTTYPE);

unsigned long lastSendMs = 0;
const unsigned long SEND_INTERVAL_MS = 2500; // Kirim tiap 2,5 detik

void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, RELAY_OFF); // Pastikan pompa mati saat baru nyala

  dht.begin();

  Serial.println("\n=============================================");
  Serial.println("Smart Chili Irrigation - Connecting to Wi-Fi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 30) {
    delay(500);
    Serial.print(".");
    retry++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Terhubung ke Wi-Fi! IP ESP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("Belum terhubung ke Wi-Fi, akan terus mencoba di loop...");
  }
}

float readSoilMoisturePercent() {
  long total = 0;
  for (int i = 0; i < 10; i++) {
    total += analogRead(PIN_SOIL);
    delay(5);
  }
  int raw = total / 10;
  float pct = map(raw, ADC_KERING, ADC_BASAH, 0, 100);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  Serial.printf("[ADC Tanah Mentah: %d -> %.1f%%] ", raw, pct);
  return pct;
}

void loop() {
  if (millis() - lastSendMs < SEND_INTERVAL_MS) {
    return;
  }
  lastSendMs = millis();

  float soil = readSoilMoisturePercent();
  float temp = dht.readTemperature();
  float rh   = dht.readHumidity();

  // Jika DHT22 belum terbaca sempurna, gunakan nilai aman sementara
  if (isnan(temp)) temp = 28.0;
  if (isnan(rh))   rh   = 70.0;

  Serial.printf("Sensor -> Tanah: %.1f%% | Suhu: %.1f C | Udara: %.1f%%\n", soil, temp, rh);

  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;

    http.begin(client, SERVER_URL);
    http.addHeader("Content-Type", "application/json");

    String jsonPayload = "{\"soil\":" + String(soil, 1) +
                         ",\"temp\":" + String(temp, 1) +
                         ",\"rh\":" + String(rh, 1) + "}";

    int httpCode = http.POST(jsonPayload);
    if (httpCode > 0) {
      String response = http.getString();
      Serial.println("Balasan Server Django: " + response);

      // Cek apakah server memerintahkan pompa menyala ("pump": true)
      if (response.indexOf("\"pump\": true") >= 0 || response.indexOf("\"pump\":true") >= 0) {
        digitalWrite(PIN_RELAY, RELAY_ON);
        Serial.println(">>> STATUS POMPA: MENYALA <<<");
      } else {
        digitalWrite(PIN_RELAY, RELAY_OFF);
        Serial.println(">>> STATUS POMPA: MATI <<<");
      }
    } else {
      Serial.printf("Gagal kirim ke Django (HTTP Error: %s). Safety: Matikan pompa.\n",
                    http.errorToString(httpCode).c_str());
      digitalWrite(PIN_RELAY, RELAY_OFF);
    }
    http.end();
  } else {
    Serial.println("Wi-Fi Putus! Safety Cut-Off mematikan pompa.");
    digitalWrite(PIN_RELAY, RELAY_OFF);
    WiFi.reconnect();
  }
}
