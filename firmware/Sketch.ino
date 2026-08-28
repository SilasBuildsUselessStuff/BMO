#define LGFX_USE_V1

#include <Arduino.h>
#include <LovyanGFX.hpp>
#include <SPI.h>
#include <SD.h>
#include <driver/i2c.h>

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
  3,
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
    case MODE_THINKING:
      // Temporary THINKING animation until a dedicated folder exists.
      return &lookIdleAnimation;

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
// DRAW PNG
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
    setupComplete = false;

    showError(
      "FRAME ERROR",
      "Could not draw PC expression."
    );
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
// SERIAL COMMAND HANDLING
// ============================================================

void processSerialLine(char* line)
{
  if (line[0] == '\0')
  {
    return;
  }

  Serial.print("Command received: ");
  Serial.println(line);

  if (strcmp(line, "PING") == 0)
  {
    Serial.println("PONG");
    return;
  }

  static const char expressionPrefix[] = "EXPRESSION:";

  if (
    strncmp(
      line,
      expressionPrefix,
      strlen(expressionPrefix)
    ) == 0
  )
  {
    const char* expressionName =
      line + strlen(expressionPrefix);

    setExpressionFromName(expressionName);
    return;
  }

  if (line[0] == '{')
  {
    // The Companion App already sends structured screen JSON.
    // Parsing and WEATHER rendering will be added in the next firmware step.
    Serial.println(
      "SCREEN_DATA received; JSON renderer not implemented yet."
    );
    return;
  }

  Serial.print("Unknown command: ");
  Serial.println(line);
}

void updateSerialInput()
{
  while (Serial.available() > 0)
  {
    char incoming = static_cast<char>(Serial.read());

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
      else
      {
        serialLineBuffer[serialLineLength] = '\0';
        processSerialLine(serialLineBuffer);
      }

      serialLineLength = 0;
      serialLineOverflow = false;
      continue;
    }

    if (serialLineOverflow)
    {
      continue;
    }

    if (
      serialLineLength <
      SERIAL_LINE_BUFFER_SIZE - 1
    )
    {
      serialLineBuffer[serialLineLength] = incoming;
      serialLineLength++;
    }
    else
    {
      serialLineOverflow = true;
    }
  }
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
  Serial.setRxBufferSize(2048);
  Serial.begin(115200);

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
  // Serial remains available even when an asset error is visible.
  updateSerialInput();

  if (!setupComplete)
  {
    delay(10);
    return;
  }

  handleTouch();
  updateBehaviorTimers();
  updateRandomEvents();
  updateAnimation();

  delay(1);
}
