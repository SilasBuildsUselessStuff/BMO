#define LGFX_USE_V1

#include <Arduino.h>
#include <ArduinoJson.h>
#include <LovyanGFX.hpp>
#include <SPI.h>
#include <SD.h>
#include <driver/i2c.h>
#include <math.h>

// ============================================================
// DISPLAY CONFIGURATION
// Board: ESP32-3248S035C
// Display: ST7796
// Landscape resolution: 480 x 320
// ============================================================

class LGFX : public lgfx::LGFX_Device
{
  lgfx::Panel_ST7796 panel;
  lgfx::Bus_SPI bus;
  lgfx::Light_PWM backlight;
  lgfx::Touch_GT911 touch;

public:
  LGFX()
  {
    // Display SPI bus
    {
      auto cfg = bus.config();

      cfg.spi_host = HSPI_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = 80000000;
      cfg.freq_read = 40000000;
      cfg.spi_3wire = true;
      cfg.use_lock = true;
      cfg.dma_channel = SPI_DMA_CH_AUTO;

      cfg.pin_sclk = 14;
      cfg.pin_mosi = 13;
      cfg.pin_miso = 12;
      cfg.pin_dc = 2;

      bus.config(cfg);
      panel.setBus(&bus);
    }

    // ST7796 panel
    {
      auto cfg = panel.config();

      cfg.pin_cs = 15;
      cfg.pin_rst = -1;
      cfg.pin_busy = -1;

      cfg.panel_width = 320;
      cfg.panel_height = 480;

      cfg.offset_x = 0;
      cfg.offset_y = 0;
      cfg.offset_rotation = 0;

      cfg.dummy_read_pixel = 8;
      cfg.dummy_read_bits = 1;

      cfg.readable = true;
      cfg.invert = false;
      cfg.rgb_order = false;
      cfg.dlen_16bit = false;
      cfg.bus_shared = true;

      panel.config(cfg);
    }

    // Backlight
    {
      auto cfg = backlight.config();

      cfg.pin_bl = 27;
      cfg.invert = false;
      cfg.freq = 1200;
      cfg.pwm_channel = 7;

      backlight.config(cfg);
      panel.setLight(&backlight);
    }

    // GT911 touch controller
    {
      auto cfg = touch.config();

      cfg.pin_int = GPIO_NUM_36;
      cfg.pin_sda = GPIO_NUM_33;
      cfg.pin_scl = GPIO_NUM_32;

      cfg.i2c_addr = 0x5D;
      cfg.i2c_port = I2C_NUM_0;
      cfg.freq = 800000;

      cfg.x_min = 14;
      cfg.x_max = 310;
      cfg.y_min = 5;
      cfg.y_max = 448;

      cfg.offset_rotation = 0;
      cfg.bus_shared = false;

      touch.config(cfg);
      panel.setTouch(&touch);
    }

    setPanel(&panel);
  }
};

// ============================================================
// HARDWARE
// ============================================================

LGFX display;
SPIClass SDSPI(VSPI);

// ============================================================
// SD CARD
// ============================================================

static constexpr int SD_CS = 5;
static constexpr int SD_SCLK = 18;
static constexpr int SD_MISO = 19;
static constexpr int SD_MOSI = 23;

// ============================================================
// BMO STATE
// ============================================================

enum Screen
{
  FACE,
  WEATHER,
  SPOTIFY,
  TODO_SCREEN,
  CLOCK,
  GAMES,
  CHANCE,
  ANIMATION,
  SETTINGS,
  SYSTEM_INFORMATION,
  NOTIFICATION_SCREEN,
  LOW_BATTERY_SCREEN
};

enum Expression
{
  IDLE,
  HAPPY,
  SAD,
  CONCERNED,
  ANGRY,
  SURPRISED,
  SLEEPY,
  SLEEPING,
  HYPED,
  DETECTIVE,
  MUSIC_ENJOYING,
  LISTENING,
  THINKING,
  TALKING,
  LOW_BATTERY,
  CONFUSED
};

Screen currentScreen = FACE;
Expression currentExpression = IDLE;

// True while the Windows Companion App controls the expression.
bool pcExpressionActive = false;

// ============================================================
// ANIMATION DEFINITION
//
// highestFrame is inclusive.
// Example:
// /assets/idle/idle0000.png
// ============================================================

struct Animation
{
  const char* folder;
  const char* filePrefix;
  int firstFrame;
  int highestFrame;
  unsigned long frameDurationMs;
  bool pingPong;
};

// Autonomous animations
Animation bootingAnimation = {
  "/assets/booting",
  "booting",
  0,
  9,
  350,
  false
};

Animation idleAnimation = {
  "/assets/idle",
  "idle",
  0,
  8,
  50,
  true
};

Animation blinkIdleAnimation = {
  "/assets/blinkidle",
  "blinkidle",
  0,
  2,
  50,
  false
};

Animation lookIdleAnimation = {
  "/assets/lookidle",
  "lookidle",
  0,
  14,
  50,
  false
};

Animation surprisedAnimation = {
  "/assets/surprised",
  "surprised",
  0,
  1,
  50,
  false
};

Animation smileAnimation = {
  "/assets/smile",
  "smile",
  0,
  8,
  50,
  true
};

Animation blinkSmileAnimation = {
  "/assets/blinksmile",
  "blinksmile",
  0,
  5,
  50,
  false
};

Animation lookSmileAnimation = {
  "/assets/looksmile",
  "looksmile",
  0,
  20,
  50,
  false
};

Animation tiredAnimation = {
  "/assets/tired",
  "tired",
  0,
  9,
  100,
  true
};

Animation sleepingAnimation = {
  "/assets/sleeping",
  "sleeping",
  0,
  16,
  120,
  true
};

// Companion App expression animations
Animation listeningAnimation = {
  "/assets/listening",
  "listening",
  0,
  13,
  80,
  true
};

Animation thinkingAnimation = {
  "/assets/thinking",
  "thinking",
  0,
  7,
  80,
  true
};

Animation talkingAnimation = {
  "/assets/talking",
  "talking",
  0,
  8,
  80,
  true
};

Animation musicAnimation = {
  "/assets/music",
  "music",
  0,
  8,
  80,
  true
};

// Available for a later screensaver feature.
Animation ballBounceAnimation = {
  "/assets/screensaver",
  "ballbounce",
  0,
  17,
  80,
  true
};

// ============================================================
// BEHAVIOR TIMINGS
// ============================================================

static constexpr unsigned long SMILE_DURATION_MS = 60000UL;
static constexpr unsigned long IDLE_TO_TIRED_MS = 120000UL;
static constexpr unsigned long TIRED_TO_SLEEPING_MS = 60000UL;
static constexpr unsigned long TOUCH_DEBOUNCE_MS = 250UL;
static constexpr unsigned long WEATHER_SCREEN_DURATION_MS = 12000UL;

// ============================================================
// ANIMATION MODES
// ============================================================

enum AnimationMode
{
  MODE_BOOTING,

  // Autonomous modes
  MODE_IDLE,
  MODE_BLINK_IDLE,
  MODE_LOOK_IDLE,
  MODE_SURPRISED,
  MODE_SMILE,
  MODE_BLINK_SMILE,
  MODE_LOOK_SMILE,
  MODE_TIRED,
  MODE_SLEEPING,

  // Companion App controlled modes
  MODE_PC_IDLE,
  MODE_PC_HAPPY,
  MODE_PC_SURPRISED,
  MODE_PC_SLEEPY,
  MODE_PC_SLEEPING,
  MODE_LISTENING,
  MODE_THINKING,
  MODE_TALKING,
  MODE_MUSIC
};

AnimationMode currentMode = MODE_BOOTING;

// ============================================================
// FRAME STATE
// ============================================================

int currentFrame = 0;
int frameDirection = 1;

unsigned long lastFrameAt = 0;

// ============================================================
// EVENT TIMERS
// ============================================================

unsigned long nextBlinkAt = 0;
unsigned long nextLookAt = 0;

unsigned long smileUntil = 0;
unsigned long lastInteractionAt = 0;
unsigned long tiredStartedAt = 0;

unsigned long lastTouchAt = 0;

bool previousTouchState = false;
bool setupComplete = false;

// ============================================================
// SERIAL RECEIVE BUFFER
// ============================================================

static constexpr size_t SERIAL_LINE_BUFFER_SIZE = 1536;

char serialLineBuffer[SERIAL_LINE_BUFFER_SIZE];
size_t serialLineLength = 0;
bool serialLineOverflow = false;

// ============================================================
// STRUCTURED WEATHER SCREEN DATA
// ============================================================

struct WeatherScreenData
{
  bool valid = false;
  bool forecast = false;

  char location[128] = "";
  char condition[48] = "";
  char dayLabel[32] = "";
  char date[24] = "";
  char observedAt[32] = "";

  int weatherCode = -1;

  float temperatureC = NAN;
  float apparentTemperatureC = NAN;

  float temperatureMinC = NAN;
  float temperatureMaxC = NAN;

  int precipitationProbabilityPercent = -1;
  float precipitationMm = NAN;
  float windSpeedKmh = NAN;
};

WeatherScreenData weatherScreenData;

bool weatherScreenPending = false;
bool weatherScreenActive = false;

unsigned long weatherScreenStartedAt = 0;

// ============================================================
// NAMES
// ============================================================

const char* getScreenName(Screen screen)
{
  switch (screen)
  {
    case FACE:
      return "FACE";

    case WEATHER:
      return "WEATHER";

    case SPOTIFY:
      return "SPOTIFY";

    case TODO_SCREEN:
      return "TODO";

    case CLOCK:
      return "CLOCK";

    case GAMES:
      return "GAMES";

    case CHANCE:
      return "CHANCE";

    case ANIMATION:
      return "ANIMATION";

    case SETTINGS:
      return "SETTINGS";

    case SYSTEM_INFORMATION:
      return "SYSTEM_INFORMATION";

    case NOTIFICATION_SCREEN:
      return "NOTIFICATION_SCREEN";

    case LOW_BATTERY_SCREEN:
      return "LOW_BATTERY_SCREEN";
  }

  return "UNKNOWN";
}

const char* getExpressionName(Expression expression)
{
  switch (expression)
  {
    case IDLE:
      return "IDLE";

    case HAPPY:
      return "HAPPY";

    case SAD:
      return "SAD";

    case CONCERNED:
      return "CONCERNED";

    case ANGRY:
      return "ANGRY";

    case SURPRISED:
      return "SURPRISED";

    case SLEEPY:
      return "SLEEPY";

    case SLEEPING:
      return "SLEEPING";

    case HYPED:
      return "HYPED";

    case DETECTIVE:
      return "DETECTIVE";

    case MUSIC_ENJOYING:
      return "MUSIC_ENJOYING";

    case LISTENING:
      return "LISTENING";

    case THINKING:
      return "THINKING";

    case TALKING:
      return "TALKING";

    case LOW_BATTERY:
      return "LOW_BATTERY";

    case CONFUSED:
      return "CONFUSED";
  }

  return "UNKNOWN";
}

void printCurrentState()
{
  Serial.print("STATE Screen: ");
  Serial.print(getScreenName(currentScreen));

  Serial.print(" | Expression: ");
  Serial.print(getExpressionName(currentExpression));

  Serial.print(" | PC control: ");
  Serial.println(pcExpressionActive ? "yes" : "no");
}

// ============================================================
// ERROR SCREEN
// ============================================================

void showError(
  const char* title,
  const char* message
)
{
  display.fillScreen(
    display.color565(20, 20, 20)
  );

  display.setTextSize(2);

  display.setTextColor(
    display.color565(255, 80, 80)
  );

  display.setCursor(20, 30);
  display.println(title);

  display.setTextColor(
    display.color565(255, 255, 255)
  );

  display.setCursor(20, 75);
  display.println(message);

  display.setCursor(20, 120);
  display.println("Check Serial Monitor.");
}

// ============================================================
// GET CURRENT ANIMATION
// ============================================================

Animation* getCurrentAnimation()
{
  switch (currentMode)
  {
    case MODE_BOOTING:
      return &bootingAnimation;

    case MODE_IDLE:
    case MODE_PC_IDLE:
      return &idleAnimation;

    case MODE_BLINK_IDLE:
      return &blinkIdleAnimation;

    case MODE_LOOK_IDLE:
      return &lookIdleAnimation;

    case MODE_THINKING:
      return &thinkingAnimation;

    case MODE_SURPRISED:
    case MODE_PC_SURPRISED:
      return &surprisedAnimation;

    case MODE_SMILE:
    case MODE_PC_HAPPY:
      return &smileAnimation;

    case MODE_BLINK_SMILE:
      return &blinkSmileAnimation;

    case MODE_LOOK_SMILE:
      return &lookSmileAnimation;

    case MODE_TIRED:
    case MODE_PC_SLEEPY:
      return &tiredAnimation;

    case MODE_SLEEPING:
    case MODE_PC_SLEEPING:
      return &sleepingAnimation;

    case MODE_LISTENING:
      return &listeningAnimation;

    case MODE_TALKING:
      return &talkingAnimation;

    case MODE_MUSIC:
      return &musicAnimation;
  }

  return &idleAnimation;
}

// ============================================================
// FRAME PATH
// ============================================================

void buildFramePath(
  const Animation& animation,
  int frameNumber,
  char* outputPath,
  size_t outputPathSize
)
{
  snprintf(
    outputPath,
    outputPathSize,
    "%s/%s%04d.png",
    animation.folder,
    animation.filePrefix,
    frameNumber
  );
}

// ============================================================
// DRAW PNG FRAME FROM SD
// ============================================================

bool drawPngFrame(const char* path)
{
  File pngFile = SD.open(path, FILE_READ);

  if (!pngFile)
  {
    Serial.print("FRAME NOT FOUND: ");
    Serial.println(path);
    return false;
  }

  size_t pngSize = pngFile.size();

  if (pngSize == 0)
  {
    Serial.print("FRAME IS EMPTY: ");
    Serial.println(path);

    pngFile.close();
    return false;
  }

  // The entire compressed PNG must fit into one contiguous memory block
  // with this installed LovyanGFX version.
  size_t freeHeap = ESP.getFreeHeap();
  size_t largestBlock = ESP.getMaxAllocHeap();

  Serial.print("PNG size: ");
  Serial.print(pngSize);

  Serial.print(" | Free heap: ");
  Serial.print(freeHeap);

  Serial.print(" | Largest block: ");
  Serial.println(largestBlock);

  if (pngSize > largestBlock)
  {
    Serial.print("PNG TOO LARGE FOR CONTIGUOUS HEAP: ");
    Serial.println(path);

    pngFile.close();
    return false;
  }

  uint8_t* pngBuffer =
    static_cast<uint8_t*>(malloc(pngSize));

  if (pngBuffer == nullptr)
  {
    Serial.print("FRAME MEMORY FAILED: ");
    Serial.println(path);

    Serial.print("Required bytes: ");
    Serial.println(pngSize);

    Serial.print("Free heap: ");
    Serial.println(ESP.getFreeHeap());

    Serial.print("Largest block: ");
    Serial.println(ESP.getMaxAllocHeap());

    pngFile.close();
    return false;
  }

  size_t bytesRead = pngFile.read(
    pngBuffer,
    pngSize
  );

  pngFile.close();

  if (bytesRead != pngSize)
  {
    Serial.print("FRAME READ INCOMPLETE: ");
    Serial.println(path);

    Serial.print("Expected bytes: ");
    Serial.println(pngSize);

    Serial.print("Read bytes: ");
    Serial.println(bytesRead);

    free(pngBuffer);
    return false;
  }

  bool drawResult = display.drawPng(
    pngBuffer,
    pngSize,
    0,
    0
  );

  free(pngBuffer);

  if (!drawResult)
  {
    Serial.print("FRAME DECODE FAILED: ");
    Serial.println(path);
    return false;
  }

  return true;
}

// ============================================================
// DRAW CURRENT ANIMATION FRAME
// ============================================================

bool drawCurrentFrame()
{
  Animation* animation = getCurrentAnimation();

  char framePath[96];

  buildFramePath(
    *animation,
    currentFrame,
    framePath,
    sizeof(framePath)
  );

  Serial.print("Drawing: ");
  Serial.println(framePath);

  return drawPngFrame(framePath);
}

// ============================================================
// VERIFY ANIMATION
// ============================================================

bool verifyAnimation(const Animation& animation)
{
  char firstPath[96];
  char lastPath[96];

  buildFramePath(
    animation,
    animation.firstFrame,
    firstPath,
    sizeof(firstPath)
  );

  buildFramePath(
    animation,
    animation.highestFrame,
    lastPath,
    sizeof(lastPath)
  );

  File firstFile = SD.open(firstPath, FILE_READ);

  if (!firstFile)
  {
    Serial.print("FIRST FRAME MISSING: ");
    Serial.println(firstPath);
    return false;
  }

  firstFile.close();

  File lastFile = SD.open(lastPath, FILE_READ);

  if (!lastFile)
  {
    Serial.print("LAST FRAME MISSING: ");
    Serial.println(lastPath);
    return false;
  }

  lastFile.close();

  Serial.print("Animation verified: ");
  Serial.print(animation.filePrefix);
  Serial.print(" | Frames ");
  Serial.print(animation.firstFrame);
  Serial.print(" to ");
  Serial.println(animation.highestFrame);

  return true;
}

// ============================================================
// EVENT SCHEDULING
// ============================================================

void scheduleNextBlink()
{
  nextBlinkAt =
    millis() + random(5000, 10001);
}

void scheduleNextLook()
{
  nextLookAt =
    millis() + random(10000, 20001);
}

void scheduleIdleEventsIfNeeded()
{
  if (nextBlinkAt == 0)
  {
    scheduleNextBlink();
  }

  if (nextLookAt == 0)
  {
    scheduleNextLook();
  }
}

void scheduleSmileEventsIfNeeded()
{
  if (nextBlinkAt == 0)
  {
    scheduleNextBlink();
  }

  if (nextLookAt == 0)
  {
    scheduleNextLook();
  }
}

// ============================================================
// MODE HELPERS
// ============================================================

void initializeModeFrame(AnimationMode mode)
{
  currentMode = mode;

  Animation* animation = getCurrentAnimation();

  currentFrame = animation->firstFrame;
  frameDirection = 1;
  lastFrameAt = millis();
}

bool isPcLoopingMode(AnimationMode mode)
{
  switch (mode)
  {
    case MODE_PC_IDLE:
    case MODE_PC_HAPPY:
    case MODE_PC_SURPRISED:
    case MODE_PC_SLEEPY:
    case MODE_PC_SLEEPING:
    case MODE_LISTENING:
    case MODE_THINKING:
    case MODE_TALKING:
    case MODE_MUSIC:
      return true;

    default:
      return false;
  }
}

// ============================================================
// AUTONOMOUS MODES
// ============================================================

void startBooting()
{
  pcExpressionActive = false;
  currentExpression = IDLE;

  initializeModeFrame(MODE_BOOTING);

  Serial.println("Animation: BOOTING");
}

void startFreshIdle()
{
  pcExpressionActive = false;
  currentScreen = FACE;
  currentExpression = IDLE;

  initializeModeFrame(MODE_IDLE);

  nextBlinkAt = 0;
  nextLookAt = 0;

  scheduleIdleEventsIfNeeded();

  Serial.println("Animation: IDLE");
}

void resumeIdle()
{
  currentExpression = IDLE;

  initializeModeFrame(MODE_IDLE);
  scheduleIdleEventsIfNeeded();

  Serial.println("Animation: IDLE");
}

void startBlinkIdle()
{
  currentExpression = IDLE;

  initializeModeFrame(MODE_BLINK_IDLE);
  nextBlinkAt = 0;

  Serial.println("Animation: BLINK IDLE");
}

void startLookIdle()
{
  currentExpression = IDLE;

  initializeModeFrame(MODE_LOOK_IDLE);
  nextLookAt = 0;

  Serial.println("Animation: LOOK IDLE");
}

void startSurprised()
{
  currentExpression = SURPRISED;

  initializeModeFrame(MODE_SURPRISED);

  nextBlinkAt = 0;
  nextLookAt = 0;

  Serial.println("Animation: SURPRISED");
}

void startSmileSession()
{
  currentExpression = HAPPY;

  initializeModeFrame(MODE_SMILE);

  smileUntil = millis() + SMILE_DURATION_MS;

  nextBlinkAt = 0;
  nextLookAt = 0;

  scheduleSmileEventsIfNeeded();

  Serial.println("Animation: SMILE");
}

void resumeSmile()
{
  currentExpression = HAPPY;

  initializeModeFrame(MODE_SMILE);
  scheduleSmileEventsIfNeeded();

  Serial.println("Animation: SMILE");
}

void startBlinkSmile()
{
  currentExpression = HAPPY;

  initializeModeFrame(MODE_BLINK_SMILE);
  nextBlinkAt = 0;

  Serial.println("Animation: BLINK SMILE");
}

void startLookSmile()
{
  currentExpression = HAPPY;

  initializeModeFrame(MODE_LOOK_SMILE);
  nextLookAt = 0;

  Serial.println("Animation: LOOK SMILE");
}

void startTired()
{
  currentExpression = SLEEPY;

  initializeModeFrame(MODE_TIRED);

  tiredStartedAt = millis();

  nextBlinkAt = 0;
  nextLookAt = 0;

  Serial.println("Animation: TIRED");
}

void startSleeping()
{
  currentExpression = SLEEPING;

  initializeModeFrame(MODE_SLEEPING);

  nextBlinkAt = 0;
  nextLookAt = 0;

  Serial.println("Animation: SLEEPING");
}

// ============================================================
// WEATHER SCREEN HELPERS
// ============================================================

void makeDisplaySafe(
  const char* source,
  char* destination,
  size_t destinationSize
)
{
  if (
    source == nullptr ||
    destination == nullptr ||
    destinationSize == 0
  )
  {
    return;
  }

  size_t sourceIndex = 0;
  size_t destinationIndex = 0;

  while (
    source[sourceIndex] != '\0' &&
    destinationIndex < destinationSize - 1
  )
  {
    uint8_t first =
      static_cast<uint8_t>(source[sourceIndex]);

    // Convert common German UTF-8 characters for the built-in font.
    if (
      first == 0xC3 &&
      source[sourceIndex + 1] != '\0'
    )
    {
      uint8_t second = static_cast<uint8_t>(
        source[sourceIndex + 1]
      );

      const char* replacement = nullptr;

      switch (second)
      {
        case 0xA4:
          replacement = "ae";
          break;

        case 0xB6:
          replacement = "oe";
          break;

        case 0xBC:
          replacement = "ue";
          break;

        case 0x84:
          replacement = "Ae";
          break;

        case 0x96:
          replacement = "Oe";
          break;

        case 0x9C:
          replacement = "Ue";
          break;

        case 0x9F:
          replacement = "ss";
          break;
      }

      if (replacement != nullptr)
      {
        for (
          size_t index = 0;
          replacement[index] != '\0' &&
          destinationIndex < destinationSize - 1;
          index++
        )
        {
          destination[destinationIndex++] =
            replacement[index];
        }

        sourceIndex += 2;
        continue;
      }
    }

    // Copy ordinary ASCII. Replace unsupported UTF-8 bytes with '?'.
    if (first < 128)
    {
      destination[destinationIndex++] =
        source[sourceIndex];
    }
    else
    {
      destination[destinationIndex++] = '?';
    }

    sourceIndex++;
  }

  destination[destinationIndex] = '\0';
}

// ============================================================
// SIMPLE WEATHER ICONS
// ============================================================

void drawSunIcon(
  int centerX,
  int centerY,
  uint16_t color
)
{
  display.fillCircle(
    centerX,
    centerY,
    28,
    color
  );

  for (int angle = 0; angle < 360; angle += 45)
  {
    float radians = angle * DEG_TO_RAD;

    int innerX =
      centerX + static_cast<int>(38 * cos(radians));
    int innerY =
      centerY + static_cast<int>(38 * sin(radians));

    int outerX =
      centerX + static_cast<int>(52 * cos(radians));
    int outerY =
      centerY + static_cast<int>(52 * sin(radians));

    display.drawLine(
      innerX,
      innerY,
      outerX,
      outerY,
      color
    );

    display.drawLine(
      innerX + 1,
      innerY,
      outerX + 1,
      outerY,
      color
    );
  }
}

void drawCloudIcon(
  int centerX,
  int centerY,
  uint16_t color
)
{
  display.fillCircle(
    centerX - 28,
    centerY + 4,
    24,
    color
  );

  display.fillCircle(
    centerX,
    centerY - 12,
    32,
    color
  );

  display.fillCircle(
    centerX + 32,
    centerY + 5,
    23,
    color
  );

  display.fillRoundRect(
    centerX - 52,
    centerY,
    104,
    35,
    14,
    color
  );
}

void drawRainIcon(
  int centerX,
  int centerY,
  uint16_t cloudColor,
  uint16_t rainColor
)
{
  drawCloudIcon(
    centerX,
    centerY - 20,
    cloudColor
  );

  for (int offset = -30; offset <= 30; offset += 20)
  {
    display.drawLine(
      centerX + offset,
      centerY + 30,
      centerX + offset - 7,
      centerY + 48,
      rainColor
    );

    display.drawLine(
      centerX + offset + 1,
      centerY + 30,
      centerX + offset - 6,
      centerY + 48,
      rainColor
    );
  }
}

void drawSnowIcon(
  int centerX,
  int centerY,
  uint16_t cloudColor,
  uint16_t snowColor
)
{
  drawCloudIcon(
    centerX,
    centerY - 20,
    cloudColor
  );

  for (int offset = -28; offset <= 28; offset += 28)
  {
    int snowX = centerX + offset;
    int snowY = centerY + 40;

    display.drawLine(
      snowX - 6,
      snowY,
      snowX + 6,
      snowY,
      snowColor
    );

    display.drawLine(
      snowX,
      snowY - 6,
      snowX,
      snowY + 6,
      snowColor
    );

    display.drawLine(
      snowX - 4,
      snowY - 4,
      snowX + 4,
      snowY + 4,
      snowColor
    );

    display.drawLine(
      snowX + 4,
      snowY - 4,
      snowX - 4,
      snowY + 4,
      snowColor
    );
  }
}

void drawFogIcon(
  int centerX,
  int centerY,
  uint16_t color
)
{
  drawCloudIcon(
    centerX,
    centerY - 30,
    color
  );

  for (int offset = 20; offset <= 55; offset += 12)
  {
    display.drawLine(
      centerX - 52,
      centerY + offset,
      centerX + 52,
      centerY + offset,
      color
    );
  }
}

void drawThunderIcon(
  int centerX,
  int centerY,
  uint16_t cloudColor,
  uint16_t lightningColor
)
{
  drawCloudIcon(
    centerX,
    centerY - 25,
    cloudColor
  );

  display.fillTriangle(
    centerX + 4,
    centerY + 12,
    centerX - 15,
    centerY + 48,
    centerX + 2,
    centerY + 43,
    lightningColor
  );

  display.fillTriangle(
    centerX + 2,
    centerY + 43,
    centerX + 19,
    centerY + 35,
    centerX - 8,
    centerY + 68,
    lightningColor
  );
}

void drawWeatherIcon(
  int weatherCode,
  int centerX,
  int centerY
)
{
  uint16_t sunColor =
    display.color565(255, 210, 45);

  uint16_t cloudColor =
    display.color565(225, 235, 240);

  uint16_t rainColor =
    display.color565(75, 180, 255);

  uint16_t snowColor =
    display.color565(245, 250, 255);

  uint16_t lightningColor =
    display.color565(255, 230, 40);

  if (weatherCode == 0 || weatherCode == 1)
  {
    drawSunIcon(
      centerX,
      centerY,
      sunColor
    );
  }
  else if (weatherCode == 2)
  {
    drawSunIcon(
      centerX - 25,
      centerY - 22,
      sunColor
    );

    drawCloudIcon(
      centerX + 10,
      centerY + 5,
      cloudColor
    );
  }
  else if (
    weatherCode == 45 ||
    weatherCode == 48
  )
  {
    drawFogIcon(
      centerX,
      centerY,
      cloudColor
    );
  }
  else if (
    weatherCode >= 51 &&
    weatherCode <= 67
  )
  {
    drawRainIcon(
      centerX,
      centerY,
      cloudColor,
      rainColor
    );
  }
  else if (
    weatherCode >= 71 &&
    weatherCode <= 77
  )
  {
    drawSnowIcon(
      centerX,
      centerY,
      cloudColor,
      snowColor
    );
  }
  else if (
    weatherCode >= 80 &&
    weatherCode <= 82
  )
  {
    drawRainIcon(
      centerX,
      centerY,
      cloudColor,
      rainColor
    );
  }
  else if (
    weatherCode == 85 ||
    weatherCode == 86
  )
  {
    drawSnowIcon(
      centerX,
      centerY,
      cloudColor,
      snowColor
    );
  }
  else if (weatherCode >= 95)
  {
    drawThunderIcon(
      centerX,
      centerY,
      cloudColor,
      lightningColor
    );
  }
  else
  {
    drawCloudIcon(
      centerX,
      centerY,
      cloudColor
    );
  }
}

// ============================================================
// RENDER WEATHER SCREEN
// ============================================================

void renderWeatherScreen()
{
  const uint16_t backgroundColor =
    display.color565(20, 55, 85);

  const uint16_t headerColor =
    display.color565(35, 125, 165);

  const uint16_t panelColor =
    display.color565(28, 75, 105);

  const uint16_t textColor =
    display.color565(255, 255, 255);

  const uint16_t secondaryTextColor =
    display.color565(190, 225, 240);

  const uint16_t accentColor =
    display.color565(255, 220, 80);

  display.fillScreen(backgroundColor);

  // Header
  display.fillRect(
    0,
    0,
    480,
    52,
    headerColor
  );

  display.setTextColor(textColor);
  display.setTextSize(2);
  display.setCursor(16, 16);

  if (weatherScreenData.forecast)
  {
    if (weatherScreenData.dayLabel[0] != '\0')
    {
      display.print("FORECAST: ");
      display.print(weatherScreenData.dayLabel);
    }
    else
    {
      display.print("WEATHER FORECAST");
    }
  }
  else
  {
    display.print("CURRENT WEATHER");
  }

  // Main information panel
  display.fillRoundRect(
    12,
    65,
    285,
    205,
    14,
    panelColor
  );

  char safeLocation[128];

  makeDisplaySafe(
    weatherScreenData.location,
    safeLocation,
    sizeof(safeLocation)
  );

  display.setTextColor(secondaryTextColor);

  if (strlen(safeLocation) > 34)
  {
    display.setTextSize(1);
  }
  else
  {
    display.setTextSize(2);
  }

  display.setCursor(25, 82);
  display.print(safeLocation);

  display.setTextColor(textColor);

  if (weatherScreenData.forecast)
  {
    display.setTextSize(3);
    display.setCursor(25, 120);

    if (
      !isnan(weatherScreenData.temperatureMinC) &&
      !isnan(weatherScreenData.temperatureMaxC)
    )
    {
      display.print(
        weatherScreenData.temperatureMinC,
        1
      );

      display.print(" - ");

      display.print(
        weatherScreenData.temperatureMaxC,
        1
      );

      display.print(" C");
    }
    else
    {
      display.print("-- C");
    }
  }
  else
  {
    display.setTextSize(5);
    display.setCursor(25, 115);

    if (!isnan(weatherScreenData.temperatureC))
    {
      display.print(
        weatherScreenData.temperatureC,
        1
      );

      display.print(" C");
    }
    else
    {
      display.print("-- C");
    }
  }

  char safeCondition[64];

  makeDisplaySafe(
    weatherScreenData.condition,
    safeCondition,
    sizeof(safeCondition)
  );

  display.setTextColor(accentColor);
  display.setTextSize(2);
  display.setCursor(25, 180);
  display.print(safeCondition);

  display.setTextColor(secondaryTextColor);
  display.setTextSize(1);

  if (weatherScreenData.forecast)
  {
    display.setCursor(25, 220);

    if (
      weatherScreenData.precipitationProbabilityPercent >= 0
    )
    {
      display.print("Rain chance: ");
      display.print(
        weatherScreenData.precipitationProbabilityPercent
      );
      display.print("%");
    }

    display.setCursor(25, 242);

    if (!isnan(weatherScreenData.windSpeedKmh))
    {
      display.print("Max wind: ");
      display.print(
        weatherScreenData.windSpeedKmh,
        1
      );
      display.print(" km/h");
    }
  }
  else
  {
    display.setCursor(25, 220);

    if (!isnan(weatherScreenData.apparentTemperatureC))
    {
      display.print("Feels like: ");
      display.print(
        weatherScreenData.apparentTemperatureC,
        1
      );
      display.print(" C");
    }

    display.setCursor(25, 242);

    if (!isnan(weatherScreenData.windSpeedKmh))
    {
      display.print("Wind: ");
      display.print(
        weatherScreenData.windSpeedKmh,
        1
      );
      display.print(" km/h");
    }
  }

  // Weather icon area
  drawWeatherIcon(
    weatherScreenData.weatherCode,
    385,
    145
  );

  // Footer
  display.drawFastHLine(
    0,
    286,
    480,
    headerColor
  );

  display.setTextColor(secondaryTextColor);
  display.setTextSize(1);
  display.setCursor(16, 299);

  if (
    weatherScreenData.forecast &&
    weatherScreenData.date[0] != '\0'
  )
  {
    display.print(weatherScreenData.date);
  }
  else if (weatherScreenData.observedAt[0] != '\0')
  {
    display.print("Observed: ");
    display.print(weatherScreenData.observedAt);
  }

  display.setCursor(356, 299);
  display.print("Tap to close");
}

// ============================================================
// WEATHER SCREEN LIFECYCLE
// ============================================================

void showWeatherScreen()
{
  if (!weatherScreenData.valid)
  {
    Serial.println(
      "WEATHER ERROR: No valid weather data is stored."
    );
    return;
  }

  weatherScreenPending = false;
  weatherScreenActive = true;
  weatherScreenStartedAt = millis();

  pcExpressionActive = false;
  currentScreen = WEATHER;
  currentExpression = IDLE;

  Serial.println("Showing physical WEATHER screen.");
  printCurrentState();

  renderWeatherScreen();
}

void dismissWeatherScreen()
{
  if (!weatherScreenActive)
  {
    return;
  }

  Serial.println("Closing physical WEATHER screen.");

  weatherScreenActive = false;
  weatherScreenPending = false;

  lastInteractionAt = millis();
  startFreshIdle();

  if (!drawCurrentFrame())
  {
    Serial.println(
      "Could not draw idle frame after weather screen."
    );
  }
}

void updateWeatherScreen()
{
  if (!weatherScreenActive)
  {
    return;
  }

  if (
    millis() - weatherScreenStartedAt >=
    WEATHER_SCREEN_DURATION_MS
  )
  {
    Serial.println("WEATHER screen timeout.");
    dismissWeatherScreen();
  }
}

// ============================================================
// PC-CONTROLLED EXPRESSIONS
// ============================================================

void startPcExpression(
  Expression expression,
  AnimationMode mode
)
{
  pcExpressionActive = true;
  currentScreen = FACE;
  currentExpression = expression;

  nextBlinkAt = 0;
  nextLookAt = 0;

  initializeModeFrame(mode);

  Serial.print("PC expression: ");
  Serial.println(getExpressionName(expression));

  printCurrentState();

  if (!drawCurrentFrame())
  {
    Serial.println(
      "Runtime frame failed; keeping display system active."
    );

    // Skip the failed frame on the next animation update instead of
    // permanently stopping the complete display system.
  }
}

void releasePcExpressionToIdle()
{
  Serial.println("PC expression released to autonomous IDLE.");

  lastInteractionAt = millis();
  startFreshIdle();
  printCurrentState();

  if (!drawCurrentFrame())
  {
    setupComplete = false;

    showError(
      "FRAME ERROR",
      "Could not return to idle."
    );
  }
}

void setExpressionFromName(const char* expressionName)
{
  if (strcmp(expressionName, "IDLE") == 0)
  {
    releasePcExpressionToIdle();
  }
  else if (
    strcmp(expressionName, "HAPPY") == 0 ||
    strcmp(expressionName, "HYPED") == 0
  )
  {
    startPcExpression(HAPPY, MODE_PC_HAPPY);
  }
  else if (strcmp(expressionName, "SURPRISED") == 0)
  {
    startPcExpression(SURPRISED, MODE_PC_SURPRISED);
  }
  else if (strcmp(expressionName, "SLEEPY") == 0)
  {
    startPcExpression(SLEEPY, MODE_PC_SLEEPY);
  }
  else if (strcmp(expressionName, "SLEEPING") == 0)
  {
    startPcExpression(SLEEPING, MODE_PC_SLEEPING);
  }
  else if (strcmp(expressionName, "LISTENING") == 0)
  {
    startPcExpression(LISTENING, MODE_LISTENING);
  }
  else if (strcmp(expressionName, "THINKING") == 0)
  {
    // Uses lookidle until a dedicated thinking animation exists.
    startPcExpression(THINKING, MODE_THINKING);
  }
  else if (strcmp(expressionName, "TALKING") == 0)
  {
    startPcExpression(TALKING, MODE_TALKING);
  }
  else if (strcmp(expressionName, "MUSIC_ENJOYING") == 0)
  {
    startPcExpression(MUSIC_ENJOYING, MODE_MUSIC);
  }
  else
  {
    // Expressions without dedicated assets currently use a protected idle
    // animation. They still remain under PC control, so autonomous events
    // cannot interrupt them.
    Serial.print("No dedicated animation for expression: ");
    Serial.println(expressionName);

    startPcExpression(IDLE, MODE_PC_IDLE);
  }
}

// ============================================================
// STRUCTURED SCREEN JSON
// ============================================================

float readJsonFloat(
  JsonVariantConst value,
  float fallback = NAN
)
{
  if (value.isNull())
  {
    return fallback;
  }

  return value.as<float>();
}

int readJsonInteger(
  JsonVariantConst value,
  int fallback = -1
)
{
  if (value.isNull())
  {
    return fallback;
  }

  return value.as<int>();
}

bool processScreenDataJson(const char* jsonText)
{
  JsonDocument document;

  DeserializationError error = deserializeJson(
    document,
    jsonText
  );

  if (error)
  {
    Serial.print("JSON ERROR: ");
    Serial.println(error.c_str());
    return false;
  }

  const char* type =
    document["type"] | "";

  const char* screen =
    document["screen"] | "";

  if (strcmp(type, "screen_data") != 0)
  {
    Serial.print("JSON ignored: unsupported type [");
    Serial.print(type);
    Serial.println("]");
    return false;
  }

  if (strcmp(screen, "WEATHER") != 0)
  {
    Serial.print("JSON ignored: unsupported screen [");
    Serial.print(screen);
    Serial.println("]");
    return false;
  }

  JsonObjectConst data =
    document["data"].as<JsonObjectConst>();

  if (data.isNull())
  {
    Serial.println(
      "WEATHER JSON ERROR: Missing data object."
    );
    return false;
  }

  WeatherScreenData incoming;

  const char* mode =
    data["mode"] | "current";

  incoming.forecast =
    strcmp(mode, "forecast") == 0;

  strlcpy(
    incoming.location,
    data["location"] | "Unknown location",
    sizeof(incoming.location)
  );

  strlcpy(
    incoming.condition,
    data["condition"] | "unknown conditions",
    sizeof(incoming.condition)
  );

  strlcpy(
    incoming.dayLabel,
    data["day_label"] | "",
    sizeof(incoming.dayLabel)
  );

  strlcpy(
    incoming.date,
    data["date"] | "",
    sizeof(incoming.date)
  );

  strlcpy(
    incoming.observedAt,
    data["observed_at"] | "",
    sizeof(incoming.observedAt)
  );

  incoming.weatherCode = readJsonInteger(
    data["weather_code"]
  );

  incoming.temperatureC = readJsonFloat(
    data["temperature_c"]
  );

  incoming.apparentTemperatureC = readJsonFloat(
    data["apparent_temperature_c"]
  );

  incoming.temperatureMinC = readJsonFloat(
    data["temperature_min_c"]
  );

  incoming.temperatureMaxC = readJsonFloat(
    data["temperature_max_c"]
  );

  incoming.precipitationProbabilityPercent =
    readJsonInteger(
      data["precipitation_probability_percent"]
    );

  // Current weather uses precipitation_mm. Forecast data uses
  // precipitation_sum_mm.
  if (!data["precipitation_mm"].isNull())
  {
    incoming.precipitationMm = readJsonFloat(
      data["precipitation_mm"]
    );
  }
  else
  {
    incoming.precipitationMm = readJsonFloat(
      data["precipitation_sum_mm"]
    );
  }

  // Current weather and forecast payloads use different wind keys.
  if (!data["wind_speed_kmh"].isNull())
  {
    incoming.windSpeedKmh = readJsonFloat(
      data["wind_speed_kmh"]
    );
  }
  else
  {
    incoming.windSpeedKmh = readJsonFloat(
      data["wind_speed_max_kmh"]
    );
  }

  incoming.valid = true;

  weatherScreenData = incoming;
  weatherScreenPending = true;

  Serial.println("WEATHER JSON stored successfully.");

  Serial.print("Weather mode: ");
  Serial.println(
    weatherScreenData.forecast
      ? "forecast"
      : "current"
  );

  Serial.print("Weather location: ");
  Serial.println(weatherScreenData.location);

  Serial.print("Weather condition: ");
  Serial.println(weatherScreenData.condition);

  Serial.print("Weather code: ");
  Serial.println(weatherScreenData.weatherCode);

  return true;
}

// ============================================================
// SERIAL COMMAND HANDLING
// ============================================================

void processSerialLine(char* line)
{
  String rawCommand = String(line);
  rawCommand.trim();

  if (rawCommand.length() == 0)
  {
    return;
  }

  // JSON is case-sensitive and must be handled before uppercasing ordinary
  // serial commands.
  if (rawCommand.startsWith("{"))
  {
    Serial.println("Structured JSON received.");

    processScreenDataJson(
      rawCommand.c_str()
    );

    return;
  }

  String command = rawCommand;
  command.toUpperCase();

  // Normalize optional whitespace after EXPRESSION:.
  static const String expressionPrefix =
    "EXPRESSION:";

  if (command.startsWith(expressionPrefix))
  {
    String expressionName =
      command.substring(
        expressionPrefix.length()
      );

    expressionName.trim();

    command =
      expressionPrefix + expressionName;
  }

  // ============================================================
// NON-BLOCKING SERIAL INPUT
// ============================================================

void updateSerialInput()
{
  while (Serial.available() > 0)
  {
    char incoming =
      static_cast<char>(Serial.read());

    // Ignore carriage returns. Newline completes the command.
    if (incoming == '\r')
    {
      continue;
    }

    if (incoming == '\n')
    {
      if (serialLineOverflow)
      {
        Serial.println(
          "SERIAL ERROR: Incoming line exceeded buffer."
        );
      }
      else if (serialLineLength > 0)
      {
        serialLineBuffer[serialLineLength] = '\0';

        processSerialLine(
          serialLineBuffer
        );
      }

      // Prepare the buffer for the next message.
      serialLineLength = 0;
      serialLineOverflow = false;

      continue;
    }

    // Ignore the remaining characters of an oversized line until its
    // terminating newline arrives.
    if (serialLineOverflow)
    {
      continue;
    }

    if (
      serialLineLength <
      SERIAL_LINE_BUFFER_SIZE - 1
    )
    {
      serialLineBuffer[serialLineLength] =
        incoming;

      serialLineLength++;
    }
    else
    {
      serialLineOverflow = true;
    }
  }
}

  Serial.print("Normalized command: [");
  Serial.print(command);
  Serial.println("]");

  if (command == "PING")
  {
    Serial.println("PONG");
    return;
  }

  if (command == "EXPRESSION:IDLE")
  {
    Serial.println("Matched command: IDLE");

    // A weather payload arrives before TALKING. Show it only after speech
    // finishes and Python returns BMO to IDLE.
    if (
      weatherScreenPending &&
      weatherScreenData.valid
    )
    {
      showWeatherScreen();
    }
    else
    {
      releasePcExpressionToIdle();
    }

    return;
  }

  if (command == "EXPRESSION:HAPPY")
  {
    Serial.println("Matched command: HAPPY");
    startPcExpression(
      HAPPY,
      MODE_PC_HAPPY
    );
    return;
  }

  if (command == "EXPRESSION:HYPED")
  {
    Serial.println("Matched command: HYPED");
    startPcExpression(
      HYPED,
      MODE_PC_HAPPY
    );
    return;
  }

  if (command == "EXPRESSION:SURPRISED")
  {
    Serial.println("Matched command: SURPRISED");
    startPcExpression(
      SURPRISED,
      MODE_PC_SURPRISED
    );
    return;
  }

  if (command == "EXPRESSION:SLEEPY")
  {
    Serial.println("Matched command: SLEEPY");
    startPcExpression(
      SLEEPY,
      MODE_PC_SLEEPY
    );
    return;
  }

  if (command == "EXPRESSION:SLEEPING")
  {
    Serial.println("Matched command: SLEEPING");
    startPcExpression(
      SLEEPING,
      MODE_PC_SLEEPING
    );
    return;
  }

  if (command == "EXPRESSION:LISTENING")
  {
    Serial.println("Matched command: LISTENING");

    weatherScreenActive = false;

    startPcExpression(
      LISTENING,
      MODE_LISTENING
    );
    return;
  }

  if (command == "EXPRESSION:THINKING")
  {
    Serial.println("Matched command: THINKING");

    weatherScreenActive = false;

    startPcExpression(
      THINKING,
      MODE_THINKING
    );
    return;
  }

  if (command == "EXPRESSION:TALKING")
  {
    Serial.println("Matched command: TALKING");

    weatherScreenActive = false;

    startPcExpression(
      TALKING,
      MODE_TALKING
    );
    return;
  }

  if (command == "EXPRESSION:MUSIC_ENJOYING")
  {
    Serial.println("Matched command: MUSIC_ENJOYING");

    weatherScreenActive = false;

    startPcExpression(
      MUSIC_ENJOYING,
      MODE_MUSIC
    );
    return;
  }

  Serial.print("Unknown command: [");
  Serial.print(command);
  Serial.println("]");
}

// ============================================================
// TOUCH
// ============================================================

void handleTouch()
{
  uint16_t touchX = 0;
  uint16_t touchY = 0;

  bool touched = display.getTouch(
    &touchX,
    &touchY
  );

  unsigned long now = millis();

  bool newTouch =
    touched &&
    !previousTouchState &&
    now - lastTouchAt >= TOUCH_DEBOUNCE_MS;

  previousTouchState = touched;

  if (!newTouch)
  {
    return;
  }

  lastTouchAt = now;

  Serial.print("Touch: ");
  Serial.print(touchX);
  Serial.print(", ");
  Serial.println(touchY);

  // Touch dismisses a structured information screen immediately.
  if (weatherScreenActive)
  {
    Serial.println("Touch action: close WEATHER screen.");
    dismissWeatherScreen();
    return;
  }
  
  // Do not let touch interrupt LISTENING, THINKING, or TALKING.
  if (pcExpressionActive)
  {
    Serial.println(
      "Touch ignored while PC expression is active."
    );
    return;
  }

  if (currentMode == MODE_BOOTING)
  {
    return;
  }

  lastInteractionAt = now;
  startSurprised();

  if (!drawCurrentFrame())
  {
    setupComplete = false;

    showError(
      "FRAME ERROR",
      "Could not draw surprise frame."
    );
  }
}

// ============================================================
// ANIMATION ADVANCEMENT
// ============================================================

void advancePingPongAnimation(
  Animation* animation
)
{
  if (
    animation->highestFrame <=
    animation->firstFrame
  )
  {
    currentFrame = animation->firstFrame;
    return;
  }

  currentFrame += frameDirection;

  if (currentFrame >= animation->highestFrame)
  {
    currentFrame = animation->highestFrame;
    frameDirection = -1;
  }
  else if (currentFrame <= animation->firstFrame)
  {
    currentFrame = animation->firstFrame;
    frameDirection = 1;
  }
}

void advanceRepeatingAnimation(
  Animation* animation
)
{
  if (animation->pingPong)
  {
    advancePingPongAnimation(animation);
    return;
  }

  currentFrame++;

  if (currentFrame > animation->highestFrame)
  {
    currentFrame = animation->firstFrame;
  }
}

void advanceAnimation()
{
  Animation* animation = getCurrentAnimation();

  // Companion App modes loop until another serial command arrives.
  if (isPcLoopingMode(currentMode))
  {
    advanceRepeatingAnimation(animation);
    return;
  }

  // Boot plays once.
  if (currentMode == MODE_BOOTING)
  {
    currentFrame++;

    if (currentFrame > animation->highestFrame)
    {
      lastInteractionAt = millis();
      startFreshIdle();
    }

    return;
  }

  // Autonomous idle events play once.
  if (currentMode == MODE_BLINK_IDLE)
  {
    currentFrame++;

    if (currentFrame > animation->highestFrame)
    {
      resumeIdle();
    }

    return;
  }

  if (currentMode == MODE_LOOK_IDLE)
  {
    currentFrame++;

    if (currentFrame > animation->highestFrame)
    {
      resumeIdle();
    }

    return;
  }

  // Surprise plays once, then starts a smile session.
  if (currentMode == MODE_SURPRISED)
  {
    currentFrame++;

    if (currentFrame > animation->highestFrame)
    {
      startSmileSession();
    }

    return;
  }

  // Smile events play once.
  if (currentMode == MODE_BLINK_SMILE)
  {
    currentFrame++;

    if (currentFrame > animation->highestFrame)
    {
      resumeSmile();
    }

    return;
  }

  if (currentMode == MODE_LOOK_SMILE)
  {
    currentFrame++;

    if (currentFrame > animation->highestFrame)
    {
      resumeSmile();
    }

    return;
  }

  // Permanent autonomous modes ping-pong.
  if (
    currentMode == MODE_IDLE ||
    currentMode == MODE_SMILE ||
    currentMode == MODE_TIRED ||
    currentMode == MODE_SLEEPING
  )
  {
    advancePingPongAnimation(animation);
  }
}

// ============================================================
// AUTONOMOUS BEHAVIOR
// ============================================================

void updateBehaviorTimers()
{
  if (pcExpressionActive)
  {
    return;
  }

  unsigned long now = millis();

  if (
    currentMode == MODE_SMILE &&
    now >= smileUntil
  )
  {
    Serial.println("Smile session finished.");
    startFreshIdle();
    return;
  }

  if (
    currentMode == MODE_IDLE &&
    now - lastInteractionAt >= IDLE_TO_TIRED_MS
  )
  {
    startTired();
    return;
  }

  if (
    currentMode == MODE_TIRED &&
    now - tiredStartedAt >= TIRED_TO_SLEEPING_MS
  )
  {
    startSleeping();
  }
}

void updateRandomEvents()
{
  if (pcExpressionActive)
  {
    return;
  }

  unsigned long now = millis();

  if (currentMode == MODE_IDLE)
  {
    if (now >= nextLookAt)
    {
      startLookIdle();

      if (!drawCurrentFrame())
      {
        setupComplete = false;

        showError(
          "FRAME ERROR",
          "Could not draw look frame."
        );
      }

      return;
    }

    if (now >= nextBlinkAt)
    {
      startBlinkIdle();

      if (!drawCurrentFrame())
      {
        setupComplete = false;

        showError(
          "FRAME ERROR",
          "Could not draw blink frame."
        );
      }

      return;
    }
  }

  if (currentMode == MODE_SMILE)
  {
    if (now >= nextLookAt)
    {
      startLookSmile();

      if (!drawCurrentFrame())
      {
        setupComplete = false;

        showError(
          "FRAME ERROR",
          "Could not draw smile look frame."
        );
      }

      return;
    }

    if (now >= nextBlinkAt)
    {
      startBlinkSmile();

      if (!drawCurrentFrame())
      {
        setupComplete = false;

        showError(
          "FRAME ERROR",
          "Could not draw smile blink frame."
        );
      }
    }
  }
}

// ============================================================
// ANIMATION PLAYER
// ============================================================

void updateAnimation()
{
  unsigned long now = millis();

  Animation* animation = getCurrentAnimation();

  if (
    now - lastFrameAt <
    animation->frameDurationMs
  )
  {
    return;
  }

  lastFrameAt = now;

  advanceAnimation();

  if (!drawCurrentFrame())
  {
    setupComplete = false;

    showError(
      "FRAME ERROR",
      "Could not draw animation frame."
    );
  }
}

// ============================================================
// SETUP
// ============================================================

void setup()
{
  // Increase RX space for future structured JSON messages.
  Serial.begin(115200); 
  Serial.setRxBufferSize(2048);


  delay(2000);

  Serial.println();
  Serial.println("=== BMO COMPANION DISPLAY ===");

  // Display
  display.init();
  display.setRotation(1);
  display.setBrightness(180);
  display.setColorDepth(16);
  display.setSwapBytes(true);

  display.fillScreen(
    display.color565(0, 0, 0)
  );

  Serial.print("Display size: ");
  Serial.print(display.width());
  Serial.print(" x ");
  Serial.println(display.height());

  // SD card
  pinMode(SD_CS, OUTPUT);
  digitalWrite(SD_CS, HIGH);

  SDSPI.begin(
    SD_SCLK,
    SD_MISO,
    SD_MOSI,
    SD_CS
  );

  SDSPI.setFrequency(1000000);

  if (!SD.begin(SD_CS, SDSPI))
  {
    Serial.println("SD INITIALIZATION FAILED");

    showError(
      "SD ERROR",
      "Could not initialize SD card."
    );

    return;
  }

  Serial.println("SD initialized.");

  // Verify all currently used assets.
  bool animationsValid = true;

  animationsValid &= verifyAnimation(bootingAnimation);
  animationsValid &= verifyAnimation(idleAnimation);
  animationsValid &= verifyAnimation(blinkIdleAnimation);
  animationsValid &= verifyAnimation(lookIdleAnimation);
  animationsValid &= verifyAnimation(surprisedAnimation);
  animationsValid &= verifyAnimation(smileAnimation);
  animationsValid &= verifyAnimation(blinkSmileAnimation);
  animationsValid &= verifyAnimation(lookSmileAnimation);
  animationsValid &= verifyAnimation(tiredAnimation);
  animationsValid &= verifyAnimation(sleepingAnimation);
  animationsValid &= verifyAnimation(listeningAnimation);
  animationsValid &= verifyAnimation(thinkingAnimation);
  animationsValid &= verifyAnimation(talkingAnimation);
  animationsValid &= verifyAnimation(musicAnimation);
  animationsValid &= verifyAnimation(ballBounceAnimation);

  if (!animationsValid)
  {
    showError(
      "ASSET ERROR",
      "Animation frames are missing."
    );

    return;
  }

  Serial.println("All animations verified.");

  randomSeed(esp_random());

  lastInteractionAt = millis();
  startBooting();

  if (!drawCurrentFrame())
  {
    showError(
      "FRAME ERROR",
      "Could not draw first boot frame."
    );

    return;
  }

  setupComplete = true;

  Serial.println("BMO display system running.");
  Serial.println("Serial protocol ready.");
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop()
{
  // Serial remains available in every display state.
  updateSerialInput();

  if (!setupComplete)
  {
    delay(10);
    return;
  }

  handleTouch();

  // Structured information screens temporarily pause face animations.
  if (weatherScreenActive)
  {
    updateWeatherScreen();
    delay(1);
    return;
  }

  updateBehaviorTimers();
  updateRandomEvents();
  updateAnimation();

  delay(1);
}
