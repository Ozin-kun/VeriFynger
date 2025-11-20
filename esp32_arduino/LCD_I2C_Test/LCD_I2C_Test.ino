/*********
  I2C LCD Scanner & Test

  This sketch will:
  1. Scan for I2C devices (LCD address detection)
  2. Test LCD display if found

  Common LCD I2C addresses: 0x27, 0x3F

  Wiring:
  - ESP32 SDA (GPIO 21) -> LCD SDA
  - ESP32 SCL (GPIO 22) -> LCD SCL
  - LCD VCC -> 5V
  - LCD GND -> GND
*********/

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Try common LCD addresses
#define LCD_ADDR_1 0x27
#define LCD_ADDR_2 0x3F

// LCD configuration: 16 columns, 2 rows
LiquidCrystal_I2C lcd(LCD_ADDR_1, 16, 2);

byte foundAddress = 0;
bool lcdInitialized = false;

void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n================================");
    Serial.println("I2C LCD Scanner & Test");
    Serial.println("================================");

    // Initialize I2C
    Wire.begin();

    // Scan for I2C devices
    scanI2C();

    // Try to initialize LCD if found
    if (foundAddress != 0)
    {
        initializeLCD(foundAddress);
    }
}

void loop()
{
    if (lcdInitialized)
    {
        testLCDDisplay();
    }
    else
    {
        Serial.println("\nNo LCD found. Scanning again in 5 seconds...");
        delay(5000);
        scanI2C();
        if (foundAddress != 0)
        {
            initializeLCD(foundAddress);
        }
    }
}

void scanI2C()
{
    byte error, address;
    int nDevices = 0;

    Serial.println("\n--- Scanning I2C Bus ---");

    for (address = 1; address < 127; address++)
    {
        Wire.beginTransmission(address);
        error = Wire.endTransmission();

        if (error == 0)
        {
            Serial.print("✓ I2C device found at address 0x");
            if (address < 16)
            {
                Serial.print("0");
            }
            Serial.print(address, HEX);

            // Check if it's a common LCD address
            if (address == 0x27 || address == 0x3F)
            {
                Serial.println(" <- Likely LCD!");
                foundAddress = address;
            }
            else
            {
                Serial.println();
            }

            nDevices++;
        }
        else if (error == 4)
        {
            Serial.print("✗ Unknown error at address 0x");
            if (address < 16)
            {
                Serial.print("0");
            }
            Serial.println(address, HEX);
        }
    }

    Serial.println("------------------------");
    if (nDevices == 0)
    {
        Serial.println("⚠ No I2C devices found!");
        Serial.println("\nTroubleshooting:");
        Serial.println("1. Check wiring (SDA=GPIO21, SCL=GPIO22)");
        Serial.println("2. Check power supply (VCC=5V, GND=GND)");
        Serial.println("3. Check I2C module is properly connected");
        foundAddress = 0;
    }
    else
    {
        Serial.print("✓ Found ");
        Serial.print(nDevices);
        Serial.println(" device(s)");
    }
}

void initializeLCD(byte address)
{
    Serial.println("\n--- Initializing LCD ---");
    Serial.print("Trying address 0x");
    Serial.println(address, HEX);

    // Create new LCD object with found address
    lcd = LiquidCrystal_I2C(address, 16, 2);

    // Initialize LCD with proper sequence
    lcd.init();
    delay(100); // Wait for LCD to stabilize
    lcd.backlight();
    delay(100);
    lcd.clear();
    delay(100);

    // Additional reset to ensure clean state
    lcd.home();
    delay(100);

    // Test if LCD responds with simple text
    lcd.setCursor(0, 0);
    lcd.print("LCD Init OK");
    delay(500);
    lcd.setCursor(0, 1);
    lcd.print("Addr 0x");
    lcd.print(address, HEX);

    Serial.println("✓ LCD initialized successfully!");
    Serial.println("Check LCD screen for message.");

    lcdInitialized = true;
    delay(2000);
}

void testLCDDisplay()
{
    Serial.println("\n=== LCD Display Test ===");

    // Test 1: Full screen text
    Serial.println("Test 1: Full screen text");
    lcd.clear();
    delay(100);
    lcd.setCursor(0, 0);
    lcd.print("VeriFynger");
    lcd.setCursor(0, 1);
    lcd.print("LCD OK");
    delay(3000);

    // Test 2: Character positions
    Serial.println("Test 2: Character positions");
    lcd.clear();
    delay(100);
    lcd.setCursor(0, 0);
    lcd.print("0123456789ABCDEF");
    lcd.setCursor(0, 1);
    lcd.print("Row 2 OK");
    delay(3000);

    // Test 3: Backlight control
    Serial.println("Test 3: Backlight test");
    lcd.clear();
    delay(100);
    lcd.setCursor(0, 0);
    lcd.print("Backlight Test");
    delay(1000);

    for (int i = 0; i < 3; i++)
    {
        lcd.noBacklight();
        delay(500);
        lcd.backlight();
        delay(500);
    }

    // Test 4: Counter
    Serial.println("Test 4: Counter (0-9)");
    lcd.clear();
    delay(100);
    lcd.setCursor(0, 0);
    lcd.print("Counter Test");

    for (int i = 0; i <= 9; i++)
    {
        lcd.setCursor(0, 1);
        lcd.print("Count ");
        lcd.print(i);
        lcd.print("  ");
        delay(500);
    }

    // Test 5: Simple text only (avoid special chars that may not render)
    Serial.println("Test 5: Simple text");
    lcd.clear();
    delay(100);
    lcd.setCursor(0, 0);
    lcd.print("Simple Text OK");
    lcd.setCursor(0, 1);
    lcd.print("Test Passed");
    delay(3000);

    // Test 6: Center alignment test
    Serial.println("Test 6: Center text");
    lcd.clear();
    delay(100);
    lcd.setCursor(6, 0);
    lcd.print("OK!");
    lcd.setCursor(4, 1);
    lcd.print("Centered");
    delay(3000);

    // Test complete
    Serial.println("✓ All tests completed!");
    lcd.clear();
    delay(100);
    lcd.setCursor(0, 0);
    lcd.print("All Tests OK!");
    lcd.setCursor(0, 1);
    lcd.print("Ready to use");

    Serial.println("\n=== Test Cycle Complete ===");
    Serial.println("Waiting 10 seconds before repeat...\n");
    delay(10000); // Longer delay to see results
}
