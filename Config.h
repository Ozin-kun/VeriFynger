/**
 * @file Config.h
 * @brief Configuration file for VeriFynger ESP32 multi-sensor fingerprint system
 * @version 2.0
 * @date 2024
 *
 * Pin assignments, sensor configurations, and system constants
 */

#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ============================================================================
// SYSTEM VERSION
// ============================================================================
#define FIRMWARE_VERSION "2.0.0"
#define HARDWARE_VERSION "1.0"

// ============================================================================
// NETWORK CONFIGURATION
// ============================================================================
#define WIFI_SSID "°!°"
#define WIFI_PASSWORD "Yahhhhhh"
#define WIFI_TIMEOUT 10000 // 10 seconds
#define WIFI_RETRY_MAX 5

#define MQTT_BROKER "test.mosquitto.org"
#define MQTT_PORT 1883
#define MQTT_CLIENT_ID "verifynger_esp32"
#define MQTT_USERNAME ""  // Optional
#define MQTT_PASSWORD ""  // Optional
#define MQTT_TIMEOUT 5000 // 5 seconds
#define MQTT_RETRY_MAX 3

// ============================================================================
// MQTT TOPICS (HARUS MATCH dengan main.py)
// ============================================================================
// Commands from Desktop to ESP32
#define TOPIC_CMD_MODE "verifynger/command/mode"     // Ganti mode (presensi/daftar)
#define TOPIC_CMD_ENROLL "verifynger/command/enroll" // Mulai enrollment
#define TOPIC_CMD_SENSOR "verifynger/command/sensor" // Ganti sensor aktif
#define TOPIC_CMD_RELAY "verifynger/command/relay"   // Kontrol relay manual

// Responses from ESP32 to Desktop
#define TOPIC_RES_TEMPLATE "verifynger/response/template" // Template hasil enrollment
#define TOPIC_RES_STATUS "verifynger/response/status"     // Status operasi
#define TOPIC_RES_ERROR "verifynger/response/error"       // Error message

// Verification (Presensi)
#define TOPIC_VERIFY_REQUEST "verifynger/verify/request"   // Request verify dari ESP32
#define TOPIC_VERIFY_RESPONSE "verifynger/verify/response" // Response dari Desktop

// System Health
#define TOPIC_SYS_HEALTH "verifynger/system/health" // Health check ESP32
#define TOPIC_SYS_CONFIG "verifynger/system/config" // Config update
#define TOPIC_SENSOR_METRICS "verifynger/sensor/metrics" // Sensor metrics data

// ============================================================================
// PIN ASSIGNMENTS - ESP32-WROOM-32D SAFE CONFIGURATION
// ============================================================================

// FPM10A Fingerprint Sensor - GPIO 26/27 (Proven working!)
#define FPM10A_RX_PIN 26 // ✅ GPIO 26 (tested, working)
#define FPM10A_TX_PIN 27 // ✅ GPIO 27 (tested, working)

// AS608 Fingerprint Sensor - GPIO 25/33 (Safe alternative pins)
#define AS608_RX_PIN 25 // ✅ GPIO 25 (safe, no conflicts)
#define AS608_TX_PIN 33 // ✅ GPIO 33 (safe, no conflicts)

// HLK-ZW101 Fingerprint Sensor - GPIO 16/17 (Using SoftwareSerial)
#define ZW101_RX_PIN 16 // ✅ GPIO 16 (U2_RXD, bidirectional)
#define ZW101_TX_PIN 17 // ✅ GPIO 17 (U2_TXD, bidirectional)

// I2C for LCD Display (16x2)
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22
#define LCD_I2C_ADDRESS 0x27     // Alamat utama LCD
#define LCD_I2C_ALT_ADDRESS 0x3F // Alamat alternatif jika 0x27 gagal

// Sensor Active Indicators (LED)
#define LED_FPM10A_PIN 13 // LED hijau untuk FPM10A aktif
#define LED_AS608_PIN 12  // LED biru untuk AS608 aktif
#define LED_ZW101_PIN 14  // LED kuning untuk ZW101 aktif (GPIO 4, safe)

// Control Pins
#define RELAY_PIN 18  // Relay untuk solenoid lock door
#define BUTTON_PIN 34 // Tactile button (input only, no pullup)

// ============================================================================
// HARDWARE SETTINGS
// ============================================================================

// Fingerprint Sensor Types
enum SensorType
{
    SENSOR_FPM10A = 0,
    SENSOR_AS608 = 1,
    SENSOR_ZW101 = 2, // ENABLED with SoftwareSerial
    SENSOR_COUNT = 3  // 3 sensor aktif (FPM10A + AS608 + ZW101)
};

// FPM10A Settings
#define FPM10A_BAUDRATE 57600
#define FPM10A_PASSWORD 0x00000000
#define FPM10A_ADDRESS 0xFFFFFFFF

// AS608 Settings
#define AS608_BAUDRATE 57600
#define AS608_PASSWORD 0x00000000
#define AS608_ADDRESS 0xFFFFFFFF

// ZW101 Settings (ENABLED with SoftwareSerial)
#define ZW101_BAUDRATE 57600
#define ZW101_PASSWORD 0x00000000
#define ZW101_ADDRESS 0xFFFFFFFF

// LCD Settings
#define LCD_ENABLED true            // Set false untuk disable LCD
#define LCD_COLS 16                 // 16 kolom
#define LCD_ROWS 2                  // 2 baris
#define LCD_BACKLIGHT_TIMEOUT 30000 // 30 detik (0 = always on)

// Relay Settings
#define RELAY_ACTIVE_HIGH true      // true = HIGH untuk aktif, false = LOW
#define RELAY_DEFAULT_DURATION 5000 // 5 detik unlock door

// Button Settings
#define BUTTON_DEBOUNCE_MS 50     // Debounce time
#define BUTTON_LONG_PRESS_MS 2000 // Long press = 2 detik

// ============================================================================
// SYSTEM CONSTANTS
// ============================================================================

// Operation Modes
enum SystemMode
{
    MODE_IDLE = 0,
    MODE_ENROLL = 1,   // Mode Daftar
    MODE_PRESENSI = 2, // Mode Presensi (default)
    MODE_ADMIN = 3     // Mode Admin (future)
};

// System States
enum SystemState
{
    STATE_STARTUP = 0,          // Booting
    STATE_INIT = 1,             // Initialization
    STATE_WIFI_CONNECT = 2,     // Connecting WiFi
    STATE_MQTT_CONNECT = 3,     // Connecting MQTT
    STATE_IDLE = 4,             // Ready, waiting
    STATE_WAITING_FINGER = 5,   // Waiting for finger scan
    STATE_PROCESSING = 6,       // Processing fingerprint
    STATE_WAITING_RESPONSE = 7, // Waiting MQTT response
    STATE_SUCCESS = 8,          // Operation success
    STATE_ERROR = 9             // Error state
};

// Timeouts (milliseconds)
#define FINGER_TIMEOUT_ENROLL 10000 // 10 detik untuk enrollment
#define FINGER_TIMEOUT_VERIFY 5000  // 5 detik untuk verifikasi
#define MQTT_RESPONSE_TIMEOUT 3000  // 3 detik timeout MQTT response
#define SENSOR_INIT_TIMEOUT 2000    // 2 detik timeout init sensor
#define SCAN_INTERVAL 500           // 500ms jeda antar scan presensi

// Retry Limits
#define MAX_FINGER_RETRY 3   // Max retry ambil fingerprint
#define MAX_TEMPLATE_RETRY 2 // Max retry create template
#define MAX_NETWORK_RETRY 5  // Max retry WiFi/MQTT

// Template Settings
#define TEMPLATE_SIZE 512       // Standard template size (bytes)
#define TEMPLATE_QUALITY_MIN 50 // Minimal kualitas fingerprint (0-100)

// Health Check
#define HEALTH_CHECK_INTERVAL 30000    // 30 detik kirim health status
#define MEMORY_WARNING_THRESHOLD 50000 // Warning jika heap < 50KB

// ============================================================================
// DEBUGGING
// ============================================================================
#define DEBUG_ENABLED true     // Set false untuk production
#define DEBUG_BAUD_RATE 115200 // Baud rate Serial Monitor
#define USE_DEBUG_SERIAL true  // Enable Serial debugging

#if DEBUG_ENABLED && USE_DEBUG_SERIAL
#define DEBUG_PRINT(x) Serial.print(x)
#define DEBUG_PRINTLN(x) Serial.println(x)
#define DEBUG_PRINTF(...) Serial.printf(__VA_ARGS__)
#else
#define DEBUG_PRINT(x)
#define DEBUG_PRINTLN(x)
#define DEBUG_PRINTF(...)
#endif

// ============================================================================
// ADVANCED SETTINGS
// ============================================================================

// Memory Management
#define JSON_BUFFER_SIZE 2048   // ArduinoJson document size
#define BASE64_BUFFER_SIZE 1024 // Base64 encoding buffer
#define SERIAL_BUFFER_SIZE 256  // Serial communication buffer

// Performance Tuning
#define LOOP_DELAY_MS 10     // Main loop delay (jangan terlalu kecil)
#define SENSOR_WARMUP_MS 100 // Sensor warmup time after init

// Safety Features
#define WATCHDOG_TIMEOUT 30000 // 30 detik watchdog timer
#define MAX_UPTIME_DAYS 30     // Auto reboot setelah 30 hari
#define AUTO_RECONNECT true    // Auto reconnect WiFi/MQTT

// LED Blink Patterns (milliseconds)
#define BLINK_FAST 100   // Fast blink (error)
#define BLINK_NORMAL 500 // Normal blink (processing)
#define BLINK_SLOW 1000  // Slow blink (idle)

// Error Codes
enum ErrorCode
{
    ERR_NONE = 0,
    ERR_SENSOR_TIMEOUT = 1,
    ERR_SENSOR_NOT_FOUND = 2,
    ERR_SENSOR_BAD_IMAGE = 3,
    ERR_SENSOR_NO_MATCH = 4,
    ERR_SENSOR_COMM_ERROR = 5,
    ERR_WIFI_DISCONNECTED = 10,
    ERR_WIFI_TIMEOUT = 11,
    ERR_MQTT_DISCONNECTED = 12,
    ERR_MQTT_TIMEOUT = 13,
    ERR_MQTT_PARSE_ERROR = 14,
    ERR_LOW_MEMORY = 20,
    ERR_RELAY_STUCK = 21,
    ERR_TEMPLATE_ENCODE_ERROR = 22,
    ERR_UNKNOWN_COMMAND = 23,
    ERR_ZW101_NOT_SUPPORTED = 30
};

// ============================================================================
// HELPER MACROS
// ============================================================================
#define ARRAY_SIZE(arr) (sizeof(arr) / sizeof(arr[0]))

// Relay control macros
#define RELAY_ON() digitalWrite(RELAY_PIN, RELAY_ACTIVE_HIGH ? HIGH : LOW)
#define RELAY_OFF() digitalWrite(RELAY_PIN, RELAY_ACTIVE_HIGH ? LOW : HIGH)

// LED control macros
#define LED_ON(pin) digitalWrite(pin, HIGH)
#define LED_OFF(pin) digitalWrite(pin, LOW)
#define LED_TOGGLE(pin) digitalWrite(pin, !digitalRead(pin))

// Memory check macro
#define CHECK_HEAP() (ESP.getFreeHeap() < MEMORY_WARNING_THRESHOLD)

// ============================================================================
// STRUCTURES
// ============================================================================

// User data structure (received from MQTT enrollment command)
struct UserData
{
    uint16_t id;        // User ID (1-127)
    char name[64];      // Nama lengkap
    char email[64];     // Email address
    char position[32];  // Jabatan/posisi
    uint32_t timestamp; // Unix timestamp enrollment
};

// Sensor status structure
struct SensorStatus
{
    bool connected;         // Sensor terdeteksi
    uint16_t templateCount; // Jumlah template tersimpan
    uint8_t lastError;      // Error code terakhir
    uint32_t lastScanTime;  // Waktu scan terakhir
};

// System status structure (untuk health check)
struct SystemStatus
{
    SystemState state;       // Current state
    SystemMode mode;         // Current mode
    SensorType activeSensor; // Sensor yang aktif
    bool relayState;         // Relay on/off
    int8_t wifiRSSI;         // WiFi signal strength
    uint32_t freeHeap;       // Free memory (bytes)
    uint32_t uptime;         // Uptime (seconds)
    float batteryVoltage;    // Battery voltage (future)
};

#endif // CONFIG_H