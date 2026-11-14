/*
 * ============================================================================
 * TAHAP 1: KODE TES SENSOR & RELAY OFFLINE (TANPA WI-FI DULU)
 * Tim: "Denger Azan Kok Lanjut Pidato"
 *
 * Gunakan kode ini pertama kali saat colok kabel USB ke laptop untuk:
 * 1. Mengecek apakah Sensor Suhu & Kelembapan Udara (DHT22) terbaca.
 * 2. Mencatat angka mentah (ADC) Sensor Tanah saat kering & saat dicelup air.
 * 3. Mengetes bunyi "Cetek" pada Relay (ketik '1' di Serial Monitor = NYALA,
 *    ketik '0' = MATI).
 * ============================================================================
 */

#include <DHT.h>

#if defined(ESP8266)
  #define PIN_SOIL  A0
  #define PIN_DHT   D4   // Pin D4 (GPIO2) di Board Biru D1
  #define PIN_RELAY D5   // Pin D5 (GPIO14) di Board Biru D1
  int ADC_KERING = 820;  // Sesuaikan nanti dengan angka di Serial Monitor saat sensor kering
  int ADC_BASAH  = 390;  // Sesuaikan nanti saat sensor dicelup air
#elif defined(ESP32)
  #define PIN_SOIL  36   // Pin A0 / VP
  #define PIN_DHT   4
  #define PIN_RELAY 5
  int ADC_KERING = 3100;
  int ADC_BASAH  = 1450;
#else
  #define PIN_SOIL  A0
  #define PIN_DHT   4
  #define PIN_RELAY 5
  int ADC_KERING = 820;
  int ADC_BASAH  = 390;
#endif

#define DHTTYPE DHT22
DHT dht(PIN_DHT, DHTTYPE);

// Relay aktif LOW (LOW = Lampu Relay Nyala / Pompa Hidup, HIGH = Mati)
#define RELAY_ON  LOW
#define RELAY_OFF HIGH

bool statusPompa = false;
unsigned long lastRead = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, RELAY_OFF);
  dht.begin();

  Serial.println("\n=======================================================");
  Serial.println("TES HARDWARE SMART CHILI IRRIGATION (MODE OFFLINE)");
  Serial.println("Ketik '1' lalu Enter di Serial Monitor -> Relay NYALA");
  Serial.println("Ketik '0' lalu Enter di Serial Monitor -> Relay MATI");
  Serial.println("=======================================================");
}

void loop() {
  // 1. Cek perintah dari Serial Monitor untuk tes Relay manual
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == '1') {
      statusPompa = true;
      digitalWrite(PIN_RELAY, RELAY_ON);
      Serial.println(">>> [TES MANUAL] RELAY / POMPA DINYALAKAN! (Harus bunyi 'Cetek') <<<");
    } else if (cmd == '0') {
      statusPompa = false;
      digitalWrite(PIN_RELAY, RELAY_OFF);
      Serial.println(">>> [TES MANUAL] RELAY / POMPA DIMATIKAN! <<<");
    }
  }

  // 2. Baca sensor setiap 2 detik
  if (millis() - lastRead >= 2000) {
    lastRead = millis();

    int rawSoil = analogRead(PIN_SOIL);
    float soilPct = map(rawSoil, ADC_KERING, ADC_BASAH, 0, 100);
    if (soilPct < 0) soilPct = 0;
    if (soilPct > 100) soilPct = 100;

    float temp = dht.readTemperature();
    float rh   = dht.readHumidity();

    Serial.print("[SENSOR] ");
    Serial.print("Tanah Mentah (ADC): ");
    Serial.print(rawSoil);
    Serial.print(" (");
    Serial.print(soilPct, 1);
    Serial.print("%)  |  ");

    if (isnan(temp) || isnan(rh)) {
      Serial.print("DHT22: Belum terbaca (cek kabel D4 / + / -)  |  ");
    } else {
      Serial.print("Suhu: ");
      Serial.print(temp, 1);
      Serial.print(" °C  |  Udara: ");
      Serial.print(rh, 1);
      Serial.print(" %  |  ");
    }

    Serial.print("Relay: ");
    Serial.println(statusPompa ? "MENYALA" : "MATI");
  }
}
