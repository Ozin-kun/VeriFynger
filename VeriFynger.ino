/**
 * @file VeriFynger.ino
 * @brief Main program untuk VeriFynger ESP32 multi-sensor fingerprint system
 * @version 2.0
 * @date 2024
 *
 * System dengan 3 sensor fingerprint: FPM10A, AS608, dan HLK-ZW101
 * Komunikasi dengan Desktop App melalui MQTT
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Adafruit_Fingerprint.h>
#include <SoftwareSerial.h>
#include <ArduinoJson.h>
#include <base64.h>
#include "Config.h"

// ============================================================================
// GLOBAL OBJECTS
// ============================================================================

// WiFi & MQTT
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// LCD Display
LiquidCrystal_I2C lcd(LCD_I2C_ADDRESS, LCD_COLS, LCD_ROWS);

// Serial Ports for Fingerprint Sensors
HardwareSerial fpm10aSerial(1);                         // UART1 (GPIO 26, 27)
HardwareSerial as608Serial(2);                          // UART2 (GPIO 25, 33)
SoftwareSerial zw101Serial(ZW101_RX_PIN, ZW101_TX_PIN); // Software Serial (GPIO 32, 35)

// Fingerprint Sensor Objects
Adafruit_Fingerprint fpm10a = Adafruit_Fingerprint(&fpm10aSerial);
Adafruit_Fingerprint as608 = Adafruit_Fingerprint(&as608Serial);
Adafruit_Fingerprint zw101 = Adafruit_Fingerprint(&zw101Serial); // ✅ ZW101 ENABLED

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

// System State
SystemState currentState = STATE_STARTUP;
SystemMode currentMode = MODE_PRESENSI;
SensorType activeSensor = SENSOR_AS608; // ✅ Changed default to AS608

// Enrollment Data
struct EnrollmentData
{
    uint16_t userID;
    String userName;
    String userEmail;
    String userPosition;
    uint8_t enrollStep;
    bool isEnrolling;
} enrollData;

// Timing Variables
unsigned long lastLCDUpdate = 0;
unsigned long lastMQTTReconnect = 0;
unsigned long lastHealthCheck = 0;
unsigned long lcdMessageTimer = 0;
unsigned long relayTimer = 0;

// LCD Display State
bool showingDefaultMessage = true;
String currentLCDLine1 = "";
String currentLCDLine2 = "";

// Relay State
bool relayActive = false;

// Network Status
bool wifiConnected = false;
bool mqttConnected = false;

// Sensor Metrics Tracking
struct SensorMetrics {
    unsigned long totalScans;
    unsigned long successCount;
    unsigned long failCount;
    unsigned long totalResponseTime;  // Total waktu untuk menghitung rata-rata
    unsigned long scanCount;  // Jumlah scan untuk menghitung rata-rata
    float avgConfidence;
    unsigned long lastScanTime;
} sensorMetrics[SENSOR_COUNT];

// ============================================================================
// FUNCTION DECLARATIONS
// ============================================================================

// Setup Functions
void setupPins();
void setupSensors();
void setupLCD();
void setupWiFi();
void setupMQTT();

// Loop Functions
void handleMQTT();
void handleLCD();
void handleSensors();
void handleRelay();
void handleHealthCheck();

// MQTT Callbacks
void mqttCallback(char *topic, byte *payload, unsigned int length);
void handleModeCommand(JsonDocument &doc);
void handleEnrollCommand(JsonDocument &doc);
void handleSensorCommand(JsonDocument &doc);
void handleRelayCommand(JsonDocument &doc);

// Sensor Functions
bool initSensor(SensorType sensor);
void switchSensor(SensorType sensor);
int scanFingerprint();
bool enrollFingerprint();
void sendTemplateToMQTT(uint16_t id, uint8_t *templateData, uint16_t templateSize);

// LCD Functions
void displayLCD(String line1, String line2, unsigned long duration = 0);
void updateLCDDefault();
void displayEnrollProgress(uint8_t step);
void displaySuccess(String message);
void displayError(String message);

// Utility Functions
void publishStatus(String status, String details = "");
void publishError(String error);
void activateRelay(unsigned long duration = RELAY_DEFAULT_DURATION);
void updateLEDIndicators();
String getSensorName(SensorType sensor);
void publishSensorMetrics();
void updateSensorMetrics(SensorType sensor, bool success, unsigned long responseTime, float confidence);

// ============================================================================
// SETUP
// ============================================================================

void setup()
{
    // Initialize Serial untuk debugging - HANYA SEKALI
    Serial.begin(DEBUG_BAUD_RATE);
    delay(1000);    // Beri waktu serial untuk stabilisasi
    Serial.flush(); // Clear buffer

    DEBUG_PRINTLN("\n\n================================");
    DEBUG_PRINTLN("VeriFynger ESP32 Starting...");
    DEBUG_PRINTLN("Version: " FIRMWARE_VERSION);
    DEBUG_PRINTLN("================================\n");

    // Initialize all components
    setupPins();
    setupLCD();
    setupSensors();
    setupWiFi();
    setupMQTT();

    // Set default mode
    currentMode = MODE_PRESENSI;
    currentState = STATE_IDLE;

    // Initialize enrollment data
    enrollData.isEnrolling = false;
    enrollData.enrollStep = 0;
    
    // Initialize sensor metrics
    for (int i = 0; i < SENSOR_COUNT; i++) {
        sensorMetrics[i].totalScans = 0;
        sensorMetrics[i].successCount = 0;
        sensorMetrics[i].failCount = 0;
        sensorMetrics[i].totalResponseTime = 0;
        sensorMetrics[i].scanCount = 0;
        sensorMetrics[i].avgConfidence = 0.0;
        sensorMetrics[i].lastScanTime = 0;
    }

    // Initial LCD display
    displayLCD("Mode Presensi", "Sensor " + getSensorName(activeSensor), 3000);

    DEBUG_PRINTLN("Setup completed. System ready.");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop()
{
    // Handle MQTT connection and messages
    handleMQTT();

    // Handle LCD updates
    handleLCD();

    // Handle sensor scanning
    handleSensors();

    // Handle relay timeout
    handleRelay();

    // Handle health check
    handleHealthCheck();

    delay(LOOP_DELAY_MS);
}

// ============================================================================
// SETUP FUNCTIONS IMPLEMENTATION
// ============================================================================

void setupPins()
{
    DEBUG_PRINTLN("Setting up pins...");

    // LED Indicators
    pinMode(LED_FPM10A_PIN, OUTPUT);
    pinMode(LED_AS608_PIN, OUTPUT);
    pinMode(LED_ZW101_PIN, OUTPUT);

    // Relay Control
    pinMode(RELAY_PIN, OUTPUT);
    RELAY_OFF();

    // Button Input
    pinMode(BUTTON_PIN, INPUT_PULLUP);

    // Update LED indicators
    updateLEDIndicators();

    DEBUG_PRINTLN("Pins configured.");
}

void setupSensors()
{
    DEBUG_PRINTLN("Initializing sensors...");

    // Initialize FPM10A (UART1 - GPIO 26 RX, 27 TX)
    DEBUG_PRINTLN("Setting up FPM10A on UART1...");
    fpm10aSerial.begin(FPM10A_BAUDRATE, SERIAL_8N1, FPM10A_RX_PIN, FPM10A_TX_PIN);
    delay(200);
    fpm10aSerial.flush();

    if (fpm10a.verifyPassword())
    {
        DEBUG_PRINTLN("✓ FPM10A sensor initialized");
    }
    else
    {
        DEBUG_PRINTLN("✗ FPM10A sensor not found!");
    }

    // Initialize AS608 (UART2 - GPIO 25 RX, 33 TX)
    DEBUG_PRINTLN("Setting up AS608 on UART2...");
    as608Serial.begin(AS608_BAUDRATE, SERIAL_8N1, AS608_RX_PIN, AS608_TX_PIN);
    delay(200);
    as608Serial.flush();

    if (as608.verifyPassword())
    {
        DEBUG_PRINTLN("✓ AS608 sensor initialized");
    }
    else
    {
        DEBUG_PRINTLN("✗ AS608 sensor not found!");
    }

    // Initialize ZW101 (SoftwareSerial - GPIO 18 RX, 19 TX)
    DEBUG_PRINTLN("Setting up ZW101 on SoftwareSerial...");
    zw101Serial.begin(ZW101_BAUDRATE);
    delay(10);
    zw101.begin(ZW101_BAUDRATE);
    delay(5);

    if (zw101.verifyPassword())
    {
        DEBUG_PRINTLN("✓ ZW101 Sensor OK!");
        zw101.getParameters();
        DEBUG_PRINT("  Capacity: ");
        DEBUG_PRINTLN(zw101.capacity);
    }
    else
    {
        DEBUG_PRINTLN("✗ ZW101 Sensor Error!");
    }

    DEBUG_PRINTLN("Sensors initialization complete.\n");
    Serial.flush(); // Clear debug serial buffer
}

void setupLCD()
{
    DEBUG_PRINTLN("Initializing LCD...");

    // Initialize I2C bus
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    delay(100);

    // Scan I2C untuk detect LCD address
    byte lcdAddress = 0;
    for (byte addr = 0x20; addr < 0x40; addr++)
    {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0)
        {
            if (addr == 0x27 || addr == 0x3F)
            {
                lcdAddress = addr;
                DEBUG_PRINTF("✓ LCD found at 0x%02X\n", addr);
                break;
            }
        }
    }

    if (lcdAddress == 0)
    {
        DEBUG_PRINTLN("✗ LCD not found! Using default 0x27");
        lcdAddress = 0x27;
    }

    // Reinitialize dengan address yang benar
    lcd = LiquidCrystal_I2C(lcdAddress, LCD_COLS, LCD_ROWS);

    // Proper LCD init sequence
    lcd.init();
    delay(200);
    lcd.backlight();
    delay(200);
    lcd.clear();
    delay(200);
    lcd.home();
    delay(100);

    // Display startup message dengan padding
    lcd.setCursor(0, 0);
    lcd.print("VeriFynger 2.0  "); // Pad dengan spasi
    lcd.setCursor(0, 1);
    lcd.print("Starting...     "); // Pad dengan spasi

    delay(2000);
    DEBUG_PRINTLN("LCD initialized successfully.\n");
}

void setupWiFi()
{
    DEBUG_PRINTLN("Connecting to WiFi...");
    displayLCD("WiFi Connect", "Please wait...");

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int retry = 0;
    while (WiFi.status() != WL_CONNECTED && retry < WIFI_RETRY_MAX)
    {
        delay(1000);
        DEBUG_PRINT(".");
        retry++;
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        wifiConnected = true;
        DEBUG_PRINTLN("\n✓ WiFi connected");
        DEBUG_PRINT("IP Address: ");
        DEBUG_PRINTLN(WiFi.localIP());
        displayLCD("WiFi Connected", WiFi.localIP().toString(), 2000);
    }
    else
    {
        wifiConnected = false;
        DEBUG_PRINTLN("\n✗ WiFi connection failed!");
        displayLCD("WiFi Failed", "Check settings", 2000);
    }
}

void setupMQTT()
{
    DEBUG_PRINTLN("Setting up MQTT...");

    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setCallback(mqttCallback);
    mqttClient.setKeepAlive(60);
    mqttClient.setSocketTimeout(30);

    // Try to connect
    if (wifiConnected)
    {
        int retry = 0;
        while (!mqttClient.connected() && retry < MQTT_RETRY_MAX)
        {
            DEBUG_PRINT("Attempting MQTT connection...");
            displayLCD("MQTT Connect", "Attempt " + String(retry + 1));

            if (mqttClient.connect(MQTT_CLIENT_ID))
            {
                mqttConnected = true;
                DEBUG_PRINTLN(" connected!");

                // Subscribe to all command topics
                mqttClient.subscribe(TOPIC_CMD_MODE);
                mqttClient.subscribe(TOPIC_CMD_ENROLL);
                mqttClient.subscribe(TOPIC_CMD_SENSOR);
                mqttClient.subscribe(TOPIC_CMD_RELAY);

                DEBUG_PRINTLN("Subscribed to topics:");
                DEBUG_PRINTLN("  - " TOPIC_CMD_MODE);
                DEBUG_PRINTLN("  - " TOPIC_CMD_ENROLL);
                DEBUG_PRINTLN("  - " TOPIC_CMD_SENSOR);
                DEBUG_PRINTLN("  - " TOPIC_CMD_RELAY);

                // Publish system online status
                publishStatus("online", "System initialized");

                displayLCD("MQTT Connected", "System Ready", 2000);
                break;
            }
            else
            {
                DEBUG_PRINT(" failed, rc=");
                DEBUG_PRINTLN(mqttClient.state());
                retry++;
                delay(2000);
            }
        }

        if (!mqttClient.connected())
        {
            mqttConnected = false;
            DEBUG_PRINTLN("✗ MQTT connection failed!");
            displayLCD("MQTT Failed", "Will retry...", 2000);
        }
    }
}

// ============================================================================
// LOOP HANDLER FUNCTIONS
// ============================================================================

void handleMQTT()
{
    // Reconnect if needed
    if (wifiConnected && !mqttClient.connected())
    {
        unsigned long now = millis();
        if (now - lastMQTTReconnect > 5000)
        {
            lastMQTTReconnect = now;
            DEBUG_PRINTLN("MQTT reconnecting...");

            if (mqttClient.connect(MQTT_CLIENT_ID))
            {
                mqttConnected = true;
                mqttClient.subscribe(TOPIC_CMD_MODE);
                mqttClient.subscribe(TOPIC_CMD_ENROLL);
                mqttClient.subscribe(TOPIC_CMD_SENSOR);
                mqttClient.subscribe(TOPIC_CMD_RELAY);
                publishStatus("reconnected");
                DEBUG_PRINTLN("MQTT reconnected");
            }
        }
    }

    // Process MQTT messages
    if (mqttClient.connected())
    {
        mqttClient.loop();
    }
}

void handleLCD()
{
    unsigned long now = millis();

    // ✅ PENTING: Jangan update LCD jika sedang enrollment
    if (enrollData.isEnrolling)
    {
        return; // Skip LCD toggle saat enrollment berlangsung
    }

    // Check if we need to return to default message
    if (lcdMessageTimer > 0 && now - lcdMessageTimer > 3000)
    {
        lcdMessageTimer = 0;
        updateLCDDefault();
    }

    // Update default message periodically (every 3 seconds toggle)
    // ✅ Tambah pengecekan: hanya di STATE_IDLE dan tidak sedang enrollment
    if (currentState == STATE_IDLE && !enrollData.isEnrolling)
    {
        if (now - lastLCDUpdate > 3000)
        {
            lastLCDUpdate = now;
            showingDefaultMessage = !showingDefaultMessage;

            if (showingDefaultMessage)
            {
                // Tampilkan Mode dan Sensor
                displayLCD("Mode " + String(currentMode == MODE_PRESENSI ? "Presensi" : "Daftar"),
                           "Sensor " + getSensorName(activeSensor));
            }
            else
            {
                // Tampilkan instruksi sesuai mode
                if (currentMode == MODE_PRESENSI)
                {
                    displayLCD("Scan Finger", "For Presensi");
                }
                else
                {
                    displayLCD("Ready Enroll", "Wait Command");
                }
            }
        }
    }
}

void handleSensors()
{
    // ✅ Allow STATE_WAITING_FINGER for enrollment
    if (currentState != STATE_IDLE && currentState != STATE_WAITING_FINGER)
        return;

    // Presensi Mode: Continuously scan for fingerprint
    if (currentMode == MODE_PRESENSI && currentState == STATE_IDLE)
    {
        int result = scanFingerprint();

        if (result > 0)
        {
            // Fingerprint matched!
            DEBUG_PRINTF("Fingerprint matched! ID: %d\n", result);

            // Get confidence score from sensor
            int confidence = 95; // Default confidence
            switch (activeSensor)
            {
            case SENSOR_FPM10A:
                confidence = fpm10a.confidence;
                break;
            case SENSOR_AS608:
                confidence = as608.confidence;
                break;
            case SENSOR_ZW101:
                confidence = zw101.confidence;
                break;
            }

            // Generate hash from matched fingerprint
            String fingerprintHash = generateFingerprintHash(result, activeSensor);

            // Publish verification request to desktop (with fingerprint_hash)
            StaticJsonDocument<512> doc;
            doc["fingerprint_hash"] = fingerprintHash; // Hash: "SENSOR_ID" (e.g., "AS608_42")
            doc["match_score"] = confidence;
            doc["sensor"] = getSensorName(activeSensor);
            doc["fingerprint_id"] = result; // Raw ID (for debugging)
            doc["timestamp"] = millis();

            String payload;
            serializeJson(doc, payload);
            mqttClient.publish(TOPIC_VERIFY_REQUEST, payload.c_str());

            DEBUG_PRINTF("✅ Published attendance - Hash: %s, Score=%d, Sensor=%s\n",
                         fingerprintHash.c_str(), confidence, getSensorName(activeSensor).c_str());

            // Activate relay (unlock door) - tanpa tampilan LCD
            activateRelay();

            // Tampilkan success dengan durasi lebih lama
            displaySuccess("Match ID " + String(result));

            currentState = STATE_SUCCESS;
            delay(2000);
            currentState = STATE_IDLE;
            updateLCDDefault();
        }
        else if (result == -1)
        {
            // No match found
            displayError("No Match!");

            DEBUG_PRINTLN("❌ Fingerprint tidak dikenali");

            delay(2000);
            updateLCDDefault();
        }
    }

    // ✅ Enrollment Mode: Process enrollment steps
    if (currentMode == MODE_ENROLL && enrollData.isEnrolling)
    {
        if (enrollFingerprint())
        {
            // Enrollment successful
            DEBUG_PRINTLN("Enrollment completed successfully");
            enrollData.isEnrolling = false; // ✅ Reset flag
            enrollData.enrollStep = 0;
            currentState = STATE_IDLE;    // ✅ Reset state
            showingDefaultMessage = true; // ✅ Enable kembali toggle LCD

            displaySuccess("Enroll Success!");
            publishStatus("enroll_complete", "User ID: " + String(enrollData.userID));

            delay(2000);
            updateLCDDefault();
        }
    }
}

void handleRelay()
{
    if (relayActive && millis() > relayTimer)
    {
        RELAY_OFF();
        relayActive = false;
        DEBUG_PRINTLN("Relay deactivated (timeout)");
    }
}

void handleHealthCheck()
{
    unsigned long now = millis();

    if (now - lastHealthCheck > HEALTH_CHECK_INTERVAL)
    {
        lastHealthCheck = now;

        // Publish health status via MQTT
        if (mqttClient.connected())
        {
            StaticJsonDocument<512> doc;
            doc["uptime"] = millis() / 1000;
            doc["free_heap"] = ESP.getFreeHeap();
            doc["wifi_rssi"] = WiFi.RSSI();
            doc["mode"] = currentMode == MODE_PRESENSI ? "presensi" : "enroll";
            doc["sensor"] = getSensorName(activeSensor);

            String payload;
            serializeJson(doc, payload);
            mqttClient.publish(TOPIC_SYS_HEALTH, payload.c_str());
        }

        // Debug output yang clean
        DEBUG_PRINTF("[Health] Uptime=%lu, Heap=%d, RSSI=%d\n",
                     millis() / 1000, ESP.getFreeHeap(), WiFi.RSSI());

        // Flush serial buffer untuk prevent overflow
        Serial.flush();
    }
}

// ============================================================================
// MQTT CALLBACK HANDLER
// ============================================================================

void mqttCallback(char *topic, byte *payload, unsigned int length)
{
    DEBUG_PRINT("MQTT message received [");
    DEBUG_PRINT(topic);
    DEBUG_PRINT("]: ");

    // Convert payload to string
    String message;
    for (unsigned int i = 0; i < length; i++)
    {
        message += (char)payload[i];
    }
    DEBUG_PRINTLN(message);

    // Parse JSON
    StaticJsonDocument<1024> doc;
    DeserializationError error = deserializeJson(doc, message);

    if (error)
    {
        DEBUG_PRINT("JSON parse error: ");
        DEBUG_PRINTLN(error.c_str());
        publishError("JSON parse error");
        return;
    }

    // Route to appropriate handler
    String topicStr = String(topic);

    if (topicStr == TOPIC_CMD_MODE)
    {
        handleModeCommand(doc);
    }
    else if (topicStr == TOPIC_CMD_ENROLL)
    {
        handleEnrollCommand(doc);
    }
    else if (topicStr == TOPIC_CMD_SENSOR)
    {
        handleSensorCommand(doc);
    }
    else if (topicStr == TOPIC_CMD_RELAY)
    {
        handleRelayCommand(doc);
    }
}

void handleModeCommand(JsonDocument &doc)
{
    String mode = doc["mode"].as<String>();

    DEBUG_PRINTF("📥 Mode command received: %s\n", mode.c_str());

    if (mode == "presensi")
    {
        currentMode = MODE_PRESENSI;
        currentState = STATE_IDLE;
        enrollData.isEnrolling = false;
        enrollData.enrollStep = 0;
        showingDefaultMessage = true; // Enable LCD toggle

        displayLCD("Mode Presensi", "Sensor " + getSensorName(activeSensor), 3000);
        publishStatus("mode_changed", "presensi");

        DEBUG_PRINTLN("✅ Mode changed to PRESENSI");
    }
    else if (mode == "enroll" || mode == "daftar")
    {
        currentMode = MODE_ENROLL;
        currentState = STATE_IDLE;
        enrollData.isEnrolling = false;
        enrollData.enrollStep = 0;
        showingDefaultMessage = true; // Enable LCD toggle

        displayLCD("Mode Daftar", "Sensor " + getSensorName(activeSensor), 3000);
        publishStatus("mode_changed", "enroll");

        DEBUG_PRINTLN("✅ Mode changed to ENROLL");
    }
    else
    {
        DEBUG_PRINTF("⚠️ Unknown mode: %s\n", mode.c_str());
        publishError("Unknown mode: " + mode);
        return;
    }

    updateLCDDefault();
}

void handleEnrollCommand(JsonDocument &doc)
{
    if (currentMode != MODE_ENROLL)
    {
        publishError("Not in enrollment mode");
        DEBUG_PRINTLN("⚠️ Enroll command rejected: not in enroll mode");
        return;
    }

    if (!doc.containsKey("action"))
    {
        DEBUG_PRINTLN("⚠️ Enroll command missing 'action' field");
        publishError("Enroll command missing action");
        return;
    }

    String action = doc["action"].as<String>();
    DEBUG_PRINTF("Enroll command received: action=%s\n", action.c_str());

    if (action == "start")
    {
        // ✅ TIDAK LAGI MENERIMA user_id dari desktop
        // Fingerprint ID akan dicari otomatis oleh ESP32

        enrollData.userName = doc["name"].as<String>();
        enrollData.userEmail = doc["email"].as<String>();
        enrollData.userPosition = doc["position"].as<String>();
        enrollData.isEnrolling = true;
        enrollData.enrollStep = 0;

        // ✅ Cari slot kosong di sensor aktif
        DEBUG_PRINTF("[Enroll] Searching for available slot in %s...\n", getSensorName(activeSensor).c_str());
        uint16_t availableID = findAvailableFingerprintSlot();

        if (availableID == 0)
        {
            DEBUG_PRINTLN("[Enroll] ✗ No available slot found!");
            publishError("No available slot in sensor");
            displayError("Sensor Full!");
            enrollData.isEnrolling = false;
            return;
        }

        enrollData.userID = availableID; // Gunakan slot yang kosong

        DEBUG_PRINTF("[Enroll] ✓ Starting enrollment: %s (Auto ID: %d)\n",
                     enrollData.userName.c_str(), enrollData.userID);

        showingDefaultMessage = false;
        lcdMessageTimer = 0;

        displayLCD("Enroll Started", "Auto ID " + String(enrollData.userID), 2000);
        publishStatus("enroll_started", "Auto ID: " + String(enrollData.userID));

        currentState = STATE_WAITING_FINGER;
    }
    else if (action == "cancel")
    {
        enrollData.isEnrolling = false;
        enrollData.enrollStep = 0;
        currentState = STATE_IDLE;
        showingDefaultMessage = true;
        displayLCD("Enroll Canceled", "", 2000);
        publishStatus("enroll_canceled");
        updateLCDDefault();
    }
    else
    {
        DEBUG_PRINTF("⚠️ Unknown enroll action: %s\n", action.c_str());
        publishError("Unknown enroll action: " + action);
    }
}

void handleSensorCommand(JsonDocument &doc)
{
    // ✅ FIX: Terima sensor_id (integer), bukan sensor (string)
    if (!doc.containsKey("sensor_id"))
    {
        DEBUG_PRINTLN("⚠️ Sensor command missing 'sensor_id' field");
        publishError("Sensor command missing sensor_id");
        return;
    }

    int sensorId = doc["sensor_id"];

    DEBUG_PRINTF("📥 Sensor switch command: sensor_id=%d\n", sensorId);

    // Map sensor_id ke SensorType enum
    SensorType newSensor;
    String sensorName;
    switch (sensorId)
    {
    case 0:
        newSensor = SENSOR_FPM10A;
        sensorName = "FPM10A";
        break;
    case 1:
        newSensor = SENSOR_AS608;
        sensorName = "AS608";
        break;
    case 2:
        newSensor = SENSOR_ZW101;
        sensorName = "ZW101";
        break;
    default:
        DEBUG_PRINTF("⚠️ Unknown sensor_id: %d\n", sensorId);
        publishError("Unknown sensor_id: " + String(sensorId));
        return;
    }

    // Switch sensor and update LEDs
    switchSensor(newSensor);

    // Display on LCD
    displayLCD("Sensor Changed", sensorName, 2000);

    // Publish status response to desktop
    publishStatus("sensor_changed", sensorName);

    DEBUG_PRINTF("✅ Sensor switched to: %s\n", sensorName.c_str());

    // Update default LCD after delay
    delay(100); // Small delay to ensure MQTT message is sent
}

void handleRelayCommand(JsonDocument &doc)
{
    String action = doc["action"].as<String>();
    int duration = doc["duration"] | RELAY_DEFAULT_DURATION;

    if (action == "activate" || action == "open")
    {
        activateRelay(duration);
        publishStatus("relay_activated", "Duration: " + String(duration) + "ms");
    }
    else if (action == "deactivate" || action == "close")
    {
        RELAY_OFF();
        relayActive = false;
        publishStatus("relay_deactivated");
    }
}

// ============================================================================
// SENSOR FUNCTIONS
// ============================================================================

bool initSensor(SensorType sensor)
{
    switch (sensor)
    {
    case SENSOR_FPM10A:
        return fpm10a.verifyPassword();
    case SENSOR_AS608:
        return as608.verifyPassword();
    case SENSOR_ZW101:
        return zw101.verifyPassword();
    default:
        return false;
    }
}

void switchSensor(SensorType sensor)
{
    activeSensor = sensor;
    updateLEDIndicators();
    DEBUG_PRINTF("[Sensor] Switched to %s\n", getSensorName(sensor).c_str());
}

int scanFingerprint()
{
    int result = -2; // -2 = no finger, -1 = no match, >0 = matched ID

    switch (activeSensor)
    {
    case SENSOR_FPM10A:
    {
        uint8_t p = fpm10a.getImage();
        if (p == FINGERPRINT_OK)
        {
            p = fpm10a.image2Tz();
            if (p == FINGERPRINT_OK)
            {
                p = fpm10a.fingerFastSearch();
                if (p == FINGERPRINT_OK)
                {
                    result = fpm10a.fingerID;
                }
                else
                {
                    result = -1; // No match
                }
            }
        }
        break;
    }

    case SENSOR_AS608:
    {
        uint8_t p = as608.getImage();
        if (p == FINGERPRINT_OK)
        {
            p = as608.image2Tz();
            if (p == FINGERPRINT_OK)
            {
                p = as608.fingerFastSearch();
                if (p == FINGERPRINT_OK)
                {
                    result = as608.fingerID;
                }
                else
                {
                    result = -1; // No match
                }
            }
        }
        break;
    }

    case SENSOR_ZW101:
    {
        uint8_t p = zw101.getImage();
        if (p == FINGERPRINT_OK)
        {
            DEBUG_PRINTLN("[ZW101] Image OK");
            p = zw101.image2Tz();
            if (p == FINGERPRINT_OK)
            {
                DEBUG_PRINTLN("[ZW101] Image converted");
                p = zw101.fingerSearch();
                if (p == FINGERPRINT_OK)
                {
                    result = zw101.fingerID;
                    DEBUG_PRINTF("[ZW101] ✓ Match! ID=%d, Confidence=%d\n",
                                 zw101.fingerID, zw101.confidence);
                }
                else if (p == FINGERPRINT_NOTFOUND)
                {
                    result = -1;
                    DEBUG_PRINTLN("[ZW101] ⚠ No match");
                }
                else
                {
                    DEBUG_PRINTF("[ZW101] ✗ Search error: %d\n", p);
                }
            }
            else
            {
                DEBUG_PRINTF("[ZW101] ✗ Convert error: %d\n", p);
            }
        }
        break;
    }
    }

    return result;
}

bool enrollFingerprint()
{
    static unsigned long lastStepTime = 0;
    unsigned long now = millis();

    // Prevent too frequent calls
    if (now - lastStepTime < 500)
        return false;

    lastStepTime = now;

    bool success = false;

    switch (activeSensor)
    {
    case SENSOR_FPM10A:
    case SENSOR_AS608:
    {
        Adafruit_Fingerprint &sensor = (activeSensor == SENSOR_FPM10A) ? fpm10a : as608;

        switch (enrollData.enrollStep)
        {
        case 0: // First scan
            displayLCD("Step 1 of 3", "Place Finger");
            enrollData.enrollStep = 1;
            break;

        case 1:
        {
            uint8_t p = sensor.getImage();
            if (p == FINGERPRINT_OK)
            {
                p = sensor.image2Tz(1);
                if (p == FINGERPRINT_OK)
                {
                    displayLCD("Step 1 OK", "Remove Finger", 1000);
                    enrollData.enrollStep = 2;
                }
            }
            break;
        }

        case 2: // Wait for finger removal
            if (sensor.getImage() == FINGERPRINT_NOFINGER)
            {
                enrollData.enrollStep = 3;
            }
            break;

        case 3: // Second scan
            displayLCD("Step 2 of 3", "Same Finger");
            enrollData.enrollStep = 4;
            break;

        case 4:
        {
            uint8_t p = sensor.getImage();
            if (p == FINGERPRINT_OK)
            {
                p = sensor.image2Tz(2);
                if (p == FINGERPRINT_OK)
                {
                    displayLCD("Step 2 OK", "Processing", 1000);
                    enrollData.enrollStep = 5;
                }
            }
            break;
        }

        case 5: // Create model
        {
            uint8_t p = sensor.createModel();
            if (p == FINGERPRINT_OK)
            {
                DEBUG_PRINTF("[Enroll] Storing fingerprint at ID: %d\n", enrollData.userID);
                p = sensor.storeModel(enrollData.userID);
                if (p == FINGERPRINT_OK)
                {
                    DEBUG_PRINTF("[Enroll] ✓ Fingerprint stored successfully at ID: %d\n", enrollData.userID);

                    // Successfully stored - send dummy template for now
                    // Adafruit library doesn't easily expose raw template data
                    // We'll send enrollment confirmation with ID only
                    uint8_t dummyTemplate[512] = {0};
                    uint16_t templateSize = 512;

                    // Fill with some identifiable data
                    dummyTemplate[0] = 0xEF;
                    dummyTemplate[1] = 0x01;
                    dummyTemplate[2] = (enrollData.userID >> 8) & 0xFF;
                    dummyTemplate[3] = enrollData.userID & 0xFF;

                    // Send to MQTT (template is stored in sensor, not transferred)
                    DEBUG_PRINTF("[Enroll] Calling sendTemplateToMQTT with ID: %d\n", enrollData.userID);
                    sendTemplateToMQTT(enrollData.userID, dummyTemplate, templateSize);
                    success = true;
                }
                else
                {
                    DEBUG_PRINTF("[Enroll] ✗ Failed to store fingerprint (error: %d)\n", p);
                }
            }
            else
            {
                DEBUG_PRINTF("[Enroll] ✗ Failed to create model (error: %d)\n", p);
            }

            if (!success)
            {
                displayError("Enroll Failed");
                publishError("Enrollment failed at model creation");
                enrollData.enrollStep = 0;
                delay(2000);
            }
            break;
        }
        }
        break;
    }

    case SENSOR_ZW101:
    {
        Adafruit_Fingerprint &sensor = zw101;
        switch (enrollData.enrollStep)
        {
        case 0:
            displayEnrollProgress(1);
            enrollData.enrollStep = 1;
            currentState = STATE_WAITING_FINGER;
            DEBUG_PRINTLN("[ZW101] Step 1: Place finger");
            return false;

        case 1:
        {
            uint8_t p = sensor.getImage();
            if (p == FINGERPRINT_NOFINGER)
                return false;
            if (p != FINGERPRINT_OK)
            {
                displayError("Image Error");
                delay(2000);
                enrollData.enrollStep = 0;
                return false;
            }

            p = sensor.image2Tz(1);
            if (p == FINGERPRINT_OK)
            {
                displaySuccess("Image taken");
                delay(1000);
                enrollData.enrollStep = 2;
                return false;
            }
            displayError("Convert Error");
            delay(2000);
            enrollData.enrollStep = 0;
            return false;
        }

        case 2:
            displayLCD("Remove finger", "...", 2000);
            delay(2000);
            while (sensor.getImage() != FINGERPRINT_NOFINGER)
                delay(10);
            enrollData.enrollStep = 3;
            DEBUG_PRINTLN("[ZW101] Step 2: Finger removed");
            return false;

        case 3:
            displayEnrollProgress(2);
            enrollData.enrollStep = 4;
            currentState = STATE_WAITING_FINGER;
            DEBUG_PRINTLN("[ZW101] Step 3: Place SAME finger");
            return false;

        case 4:
        {
            uint8_t p = sensor.getImage();
            if (p == FINGERPRINT_NOFINGER)
                return false;
            if (p != FINGERPRINT_OK)
            {
                displayError("Image Error");
                delay(2000);
                enrollData.enrollStep = 2;
                return false;
            }

            p = sensor.image2Tz(2);
            if (p == FINGERPRINT_OK)
            {
                displaySuccess("Image taken");
                delay(1000);
                enrollData.enrollStep = 5;
                return false;
            }
            displayError("Convert Error");
            delay(2000);
            enrollData.enrollStep = 2;
            return false;
        }

        case 5:
            displayLCD("Creating model", "Please wait...");
            delay(500);
            {
                uint8_t p = sensor.createModel();
                if (p == FINGERPRINT_OK)
                {
                    DEBUG_PRINTLN("[ZW101] ✓ Model created");
                }
                else if (p == FINGERPRINT_ENROLLMISMATCH)
                {
                    displayError("Not match!");
                    DEBUG_PRINTLN("[ZW101] ✗ Fingerprints mismatch");
                    delay(2000);
                    enrollData.enrollStep = 0;
                    enrollData.isEnrolling = false;
                    currentState = STATE_IDLE;
                    publishError("zw101_enroll_mismatch");
                    return false;
                }
                else
                {
                    displayError("Model Error");
                    DEBUG_PRINTF("[ZW101] ✗ Create model error: %d\n", p);
                    delay(2000);
                    enrollData.enrollStep = 0;
                    enrollData.isEnrolling = false;
                    currentState = STATE_IDLE;
                    publishError("zw101_create_failed");
                    return false;
                }

                displayLCD("Storing...", "ID: " + String(enrollData.userID));
                delay(500);
                DEBUG_PRINTF("[ZW101] Storing fingerprint at ID: %d\n", enrollData.userID);
                p = sensor.storeModel(enrollData.userID);
                if (p == FINGERPRINT_OK)
                {
                    DEBUG_PRINTF("[ZW101] ✓ Fingerprint stored successfully at ID: %d\n", enrollData.userID);
                    displaySuccess("Stored!");
                    delay(2000);

                    // Send dummy template for ZW101
                    uint8_t templateBuffer[512] = {0};
                    templateBuffer[0] = 0xEF;
                    templateBuffer[1] = 0x01;
                    DEBUG_PRINTF("[ZW101] Calling sendTemplateToMQTT with ID: %d\n", enrollData.userID);
                    sendTemplateToMQTT(enrollData.userID, templateBuffer, 512);

                    enrollData.isEnrolling = false;
                    enrollData.enrollStep = 0;
                    currentState = STATE_IDLE;
                    publishStatus("enrollment_complete", "zw101");
                    return true;
                }
                DEBUG_PRINTF("[ZW101] ✗ Failed to store fingerprint (error: %d)\n", p);
                displayError("Store Error");
                DEBUG_PRINTF("[ZW101] ✗ Store error: %d\n", p);
                delay(2000);
                enrollData.enrollStep = 0;
                enrollData.isEnrolling = false;
                currentState = STATE_IDLE;
                publishError("zw101_store_failed");
                return false;
            }
        }
        return false;
    }
    }

    return success;
}

void sendTemplateToMQTT(uint16_t id, uint8_t *templateData, uint16_t templateSize)
{
    DEBUG_PRINTF("[MQTT] Sending enrollment confirmation (FP ID: %d)\n", id);
    DEBUG_PRINTF("[MQTT] enrollData.userID = %d\n", enrollData.userID);

    // Generate hash: SENSOR_ID (e.g., "AS608_5")
    String fingerprintHash = generateFingerprintHash(id, activeSensor);
    DEBUG_PRINTF("[MQTT] Generated hash: %s\n", fingerprintHash.c_str());

    // Create JSON payload
    StaticJsonDocument<1024> doc;
    doc["name"] = enrollData.userName;
    doc["email"] = enrollData.userEmail;
    doc["position"] = enrollData.userPosition;
    doc["fingerprint_hash"] = fingerprintHash; // Hash: "SENSOR_ID"
    doc["sensor"] = getSensorName(activeSensor);
    doc["fingerprint_id"] = id; // Raw ID di sensor (for debugging)
    doc["timestamp"] = millis();

    // ✅ TIDAK KIRIM user_id lagi (karena belum ada dari desktop)

    String payload;
    serializeJson(doc, payload);
    DEBUG_PRINTF("[MQTT] Payload: %s\n", payload.c_str());

    // Publish to MQTT
    bool published = mqttClient.publish(TOPIC_RES_TEMPLATE, payload.c_str());

    if (published)
    {
        DEBUG_PRINTF("[MQTT] ✅ Enrollment confirmed - Hash: %s (FP ID: %d)\n",
                     fingerprintHash.c_str(), id);
    }
    else
    {
        DEBUG_PRINTLN("[MQTT] ❌ Failed to send enrollment confirmation");
        publishError("Failed to send enrollment confirmation");
    }
}

// ============================================================================
// LCD FUNCTIONS
// ============================================================================

void displayLCD(String line1, String line2, unsigned long duration)
{
    // Clear LCD
    lcd.clear();
    delay(50);
    lcd.home();
    delay(50);

    // Prepare Line 1 dengan padding
    if (line1.length() > LCD_COLS)
    {
        line1 = line1.substring(0, LCD_COLS);
    }
    while (line1.length() < LCD_COLS)
    {
        line1 += " "; // Pad dengan spasi untuk clear sisa
    }

    // Prepare Line 2 dengan padding
    if (line2.length() > LCD_COLS)
    {
        line2 = line2.substring(0, LCD_COLS);
    }
    while (line2.length() < LCD_COLS)
    {
        line2 += " "; // Pad dengan spasi untuk clear sisa
    }

    // Print Line 1
    lcd.setCursor(0, 0);
    lcd.print(line1);
    delay(10);

    // Print Line 2
    lcd.setCursor(0, 1);
    lcd.print(line2);
    delay(10);

    currentLCDLine1 = line1;
    currentLCDLine2 = line2;

    if (duration > 0)
    {
        lcdMessageTimer = millis();
        showingDefaultMessage = false;
    }

    DEBUG_PRINTF("[LCD] %s | %s\n", line1.c_str(), line2.c_str());
}

void updateLCDDefault()
{
    showingDefaultMessage = true;

    if (currentMode == MODE_PRESENSI)
    {
        displayLCD("Mode Presensi", "Sensor " + getSensorName(activeSensor));
    }
    else
    {
        displayLCD("Mode Daftar", "Sensor " + getSensorName(activeSensor));
    }
}

void displayEnrollProgress(uint8_t step)
{
    displayLCD("Enrolling", "Step " + String(step) + " of 3", 2000);
}

void displaySuccess(String message)
{
    displayLCD("SUCCESS", message, 2000);
}

void displayError(String message)
{
    displayLCD("ERROR", message, 2000);
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

void publishStatus(String status, String details)
{
    if (!mqttClient.connected())
        return;

    StaticJsonDocument<512> doc;
    doc["status"] = status;
    doc["details"] = details;
    doc["mode"] = currentMode == MODE_PRESENSI ? "presensi" : "enroll";
    doc["sensor"] = getSensorName(activeSensor);
    doc["timestamp"] = millis();

    String payload;
    serializeJson(doc, payload);
    mqttClient.publish(TOPIC_RES_STATUS, payload.c_str());

    DEBUG_PRINTF("[Status] %s - %s\n", status.c_str(), details.c_str());
    Serial.flush();
}

void publishError(String error)
{
    if (!mqttClient.connected())
        return;

    StaticJsonDocument<256> doc;
    doc["error"] = error;
    doc["timestamp"] = millis();

    String payload;
    serializeJson(doc, payload);
    mqttClient.publish(TOPIC_RES_ERROR, payload.c_str());

    DEBUG_PRINTF("[Error] %s\n", error.c_str());
    Serial.flush();
}

void activateRelay(unsigned long duration)
{
    RELAY_ON();
    relayActive = true;
    relayTimer = millis() + duration;

    // Tidak tampilkan "Door Unlocked" - biarkan tampilan success/error tetap

    DEBUG_PRINTF("Relay activated for %lu ms\n", duration);
}

void updateLEDIndicators()
{
    // Turn off all LEDs
    LED_OFF(LED_FPM10A_PIN);
    LED_OFF(LED_AS608_PIN);
    LED_OFF(LED_ZW101_PIN);

    // Turn on active sensor LED
    switch (activeSensor)
    {
    case SENSOR_FPM10A:
        LED_ON(LED_FPM10A_PIN);
        break;
    case SENSOR_AS608:
        LED_ON(LED_AS608_PIN);
        break;
    case SENSOR_ZW101:
        LED_ON(LED_ZW101_PIN);
        break;
    }
}

String getSensorName(SensorType sensor)
{
    switch (sensor)
    {
    case SENSOR_FPM10A:
        return "FPM10A";
    case SENSOR_AS608:
        return "AS608";
    case SENSOR_ZW101:
        return "ZW101";
    default:
        return "Unknown";
    }
}

/**
 * Generate fingerprint hash: SENSOR_ID (e.g., "AS608_42")
 * This hash uniquely identifies a fingerprint on a specific sensor
 */
String generateFingerprintHash(uint16_t fingerprintId, SensorType sensor)
{
    String sensorName = getSensorName(sensor);
    return sensorName + "_" + String(fingerprintId);
}

/**
 * Update sensor metrics after scan
 */
void updateSensorMetrics(SensorType sensor, bool success, unsigned long responseTime, float confidence)
{
    SensorMetrics &metrics = sensorMetrics[sensor];
    
    metrics.totalScans++;
    if (success) {
        metrics.successCount++;
        metrics.totalResponseTime += responseTime;
        metrics.scanCount++;
        
        // Update average confidence (weighted average)
        if (metrics.avgConfidence == 0) {
            metrics.avgConfidence = confidence;
        } else {
            metrics.avgConfidence = (metrics.avgConfidence * 0.7) + (confidence * 0.3);
        }
    } else {
        metrics.failCount++;
    }
    
    metrics.lastScanTime = millis();
    
    DEBUG_PRINTF("[Metrics] %s - Total:%lu Success:%lu Fail:%lu AvgConf:%.1f%%\n",
                 getSensorName(sensor).c_str(),
                 metrics.totalScans,
                 metrics.successCount,
                 metrics.failCount,
                 metrics.avgConfidence);
}

/**
 * Publish sensor metrics to MQTT
 */
void publishSensorMetrics()
{
    if (!mqttClient.connected())
        return;
    
    StaticJsonDocument<1024> doc;
    
    // Create array for each sensor
    for (int i = 0; i < SENSOR_COUNT; i++) {
        JsonObject sensorObj = doc.createNestedObject(getSensorName((SensorType)i));
        SensorMetrics &metrics = sensorMetrics[i];
        
        sensorObj["total_scans"] = metrics.totalScans;
        sensorObj["success_count"] = metrics.successCount;
        sensorObj["fail_count"] = metrics.failCount;
        
        // Calculate average response time
        if (metrics.scanCount > 0) {
            sensorObj["avg_response_time"] = metrics.totalResponseTime / metrics.scanCount;
        } else {
            sensorObj["avg_response_time"] = 0;
        }
        
        sensorObj["avg_confidence"] = metrics.avgConfidence;
        sensorObj["last_scan_time"] = metrics.lastScanTime;
        
        // Calculate success rate
        if (metrics.totalScans > 0) {
            float successRate = (float)metrics.successCount / metrics.totalScans * 100.0;
            sensorObj["success_rate"] = successRate;
        } else {
            sensorObj["success_rate"] = 0;
        }
    }
    
    String payload;
    serializeJson(doc, payload);
    mqttClient.publish(TOPIC_SENSOR_METRICS, payload.c_str());
    
    DEBUG_PRINTLN("[Metrics] Published to MQTT");
}

/**
 * Find available (empty) fingerprint slot in active sensor
 * Returns slot ID (1-based), or 0 if sensor is full
 *
 * Strategy: Use getTemplateCount() to get total stored templates,
 * then iterate through all possible IDs to find the first empty slot.
 */
uint16_t findAvailableFingerprintSlot()
{
    Adafruit_Fingerprint *sensor;
    uint16_t maxCapacity;

    // Select active sensor
    switch (activeSensor)
    {
    case SENSOR_FPM10A:
        sensor = &fpm10a;
        maxCapacity = 100;
        break;
    case SENSOR_AS608:
        sensor = &as608;
        maxCapacity = 200;
        break;
    case SENSOR_ZW101:
        sensor = &zw101;
        maxCapacity = 50;
        break;
    default:
        DEBUG_PRINTLN("[Sensor] ✗ Invalid sensor type");
        return 0;
    }

    DEBUG_PRINTF("[Sensor] Searching available slot in %s (capacity: %d)...\n",
                 getSensorName(activeSensor).c_str(), maxCapacity);

    // Get template count from sensor
    uint8_t countResult = sensor->getTemplateCount();

    if (countResult != FINGERPRINT_OK)
    {
        DEBUG_PRINTF("[Sensor] ⚠️ Failed to get template count (error: %d), will scan all slots\n", countResult);
        // Continue with full scan if getTemplateCount fails
    }
    else
    {
        uint16_t templateCount = sensor->templateCount;
        DEBUG_PRINTF("[Sensor] Current template count: %d / %d\n", templateCount, maxCapacity);

        // Check if sensor is full
        if (templateCount >= maxCapacity)
        {
            DEBUG_PRINTLN("[Sensor] ✗ Sensor is full!");
            return 0;
        }
    }

    // Search for empty slot starting from ID 1
    // We check each slot by trying to load it
    for (uint16_t id = 1; id <= maxCapacity; id++)
    {
        // Try to load template from this slot
        uint8_t p = sensor->loadModel(id);

        DEBUG_PRINTF("[Sensor] Checking slot %d: result=%d\n", id, p);

        // Check for errors indicating empty slot
        // FINGERPRINT_PACKETRECIEVEERR = communication error (likely empty)
        // FINGERPRINT_DBRANGEFAIL = ID out of range or empty
        if (p == FINGERPRINT_PACKETRECIEVEERR || p == FINGERPRINT_DBRANGEFAIL)
        {
            DEBUG_PRINTF("[Sensor] ✓ Found empty slot: ID %d\n", id);
            return id;
        }

        // FINGERPRINT_OK means slot is occupied, continue to next
        if (p == FINGERPRINT_OK)
        {
            DEBUG_PRINTF("[Sensor] Slot %d is occupied, checking next...\n", id);
            continue;
        }

        // Add delay to prevent sensor overload
        delay(50);
    }

    DEBUG_PRINTLN("[Sensor] ✗ No available slot found - sensor is full!");
    return 0; // No empty slot found
}
