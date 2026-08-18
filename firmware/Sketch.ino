enum Screen {
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

enum Expression {
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

Expression defaultExpression = HAPPY;
Expression currentExpression = HAPPY;

unsigned long expressionStartTime = 0;
unsigned long expressionDuration = 0;

bool expressionTimerActive = false;

const char* getScreenName(Screen screen)
{
  switch(screen)
  {
    case FACE: return "FACE";
    case WEATHER: return "WEATHER";
    case SPOTIFY: return "SPOTIFY";
    case TODO_SCREEN: return "TODO";
    case CLOCK: return "CLOCK";
    case GAMES: return "GAMES";
    case CHANCE: return "CHANCE";
    case ANIMATION: return "ANIMATION";
    case SETTINGS: return "SETTINGS";
    case SYSTEM_INFORMATION: return "SYSTEM_INFORMATION";
    case NOTIFICATION_SCREEN: return "NOTIFICATION_SCREEN";
    case LOW_BATTERY_SCREEN: return "LOW_BATTERY_SCREEN";
  }

  return "UNKNOWN";
}

const char* getExpressionName(Expression expression)
{
  switch(expression)
  {
    case IDLE: return "IDLE";
    case HAPPY: return "HAPPY";
    case SAD: return "SAD";
    case CONCERNED: return "CONCERNED";
    case ANGRY: return "ANGRY";
    case SURPRISED: return "SURPRISED";
    case SLEEPY: return "SLEEPY";
    case SLEEPING: return "SLEEPING";
    case HYPED: return "HYPED";
    case DETECTIVE: return "DETECTIVE";
    case MUSIC_ENJOYING: return "MUSIC_ENJOYING";
    case LISTENING: return "LISTENING";
    case THINKING: return "THINKING";
    case TALKING: return "TALKING";
    case LOW_BATTERY: return "LOW_BATTERY";
    case CONFUSED: return "CONFUSED";
  }

  return "UNKNOWN";
}

void printCurrentState()
{
  Serial.print("Screen: ");
  Serial.print(getScreenName(currentScreen));

  Serial.print(" | Expression: ");
  Serial.println(getExpressionName(currentExpression));
}

void setExpression(Expression expression, unsigned long durationMs)
{
  currentExpression = expression;

  expressionStartTime = millis();
  expressionDuration = durationMs;

  expressionTimerActive = true;

  printCurrentState();
}

void printHelp()
{
  Serial.println("");
  Serial.println("=== BMO DEBUG COMMANDS ===");

  Serial.println("");
  Serial.println("Navigation");
  Serial.println("r = Next Screen");
  Serial.println("l = Previous Screen");
  Serial.println("Screens");
  Serial.println("f = FACE");
  Serial.println("w = WEATHER");
  Serial.println("s = SPOTIFY");

  Serial.println("");

  Serial.println("Expressions");
  Serial.println("h = HAPPY");
  Serial.println("a = ANGRY");
  Serial.println("t = THINKING");
  Serial.println("c = CONFUSED");
  Serial.println("i = IDLE");

  Serial.println("");

  Serial.println("? = HELP");
}

void nextScreen()
{
  switch(currentScreen)
  {
    case FACE:
      currentScreen = WEATHER;
      break;

    case WEATHER:
      currentScreen = SPOTIFY;
      break;

    case SPOTIFY:
      currentScreen = TODO_SCREEN;
      break;

    case TODO_SCREEN:
      currentScreen = CLOCK;
      break;

    case CLOCK:
      currentScreen = GAMES;
      break;

    case GAMES:
      currentScreen = CHANCE;
      break;

    case CHANCE:
      currentScreen = ANIMATION;
      break;

    case ANIMATION:
      currentScreen = SETTINGS;
      break;

    case SETTINGS:
      currentScreen = SYSTEM_INFORMATION;
      break;

    case SYSTEM_INFORMATION:
      currentScreen = NOTIFICATION_SCREEN;
      break;

    case NOTIFICATION_SCREEN:
      currentScreen = LOW_BATTERY_SCREEN;
      break;

    case LOW_BATTERY_SCREEN:
      currentScreen = FACE;
      break;
  }

  printCurrentState();
}

void previousScreen()
{
  switch(currentScreen)
  {
    case FACE:
      currentScreen = LOW_BATTERY_SCREEN;
      break;

    case WEATHER:
      currentScreen = FACE;
      break;

    case SPOTIFY:
      currentScreen = WEATHER;
      break;

    case TODO_SCREEN:
      currentScreen = SPOTIFY;
      break;

    case CLOCK:
      currentScreen = TODO_SCREEN;
      break;

    case GAMES:
      currentScreen = CLOCK;
      break;

    case CHANCE:
      currentScreen = GAMES;
      break;

    case ANIMATION:
      currentScreen = CHANCE;
      break;

    case SETTINGS:
      currentScreen = ANIMATION;
      break;

    case SYSTEM_INFORMATION:
      currentScreen = SETTINGS;
      break;

    case NOTIFICATION_SCREEN:
      currentScreen = SYSTEM_INFORMATION;
      break;

    case LOW_BATTERY_SCREEN:
      currentScreen = NOTIFICATION_SCREEN;
      break;
  }

  printCurrentState();
}

void setup()
{
  Serial.begin(115200);

  Serial.println("BMO Booting...");
  printHelp();
  printCurrentState();
}

void loop()
{
  // Expression timeout handling

  if(expressionTimerActive)
  {
    if(millis() - expressionStartTime >= expressionDuration)
    {
      currentExpression = defaultExpression;
      expressionTimerActive = false;

      Serial.println("Expression timeout.");
      printCurrentState();
    }
  }

  // Serial commands

  if(Serial.available())
  {
    char cmd = Serial.read();

    switch(cmd)
    {
      // Screens

      case 'r':
            nextScreen();
      return;

      case 'l':
             previousScreen();
      return;
      
      case 'f':
        currentScreen = FACE;
        break;

      case 'w':
        currentScreen = WEATHER;
        break;

      case 's':
        currentScreen = SPOTIFY;
        break;

      // Expressions

      case 'h':
        setExpression(HAPPY, 10000);
        return;

      case 'a':
        setExpression(ANGRY, 15000);
        return;

      case 't':
        setExpression(THINKING, 5000);
        return;

      case 'c':
        setExpression(CONFUSED, 10000);
        return;

      case 'i':
        currentExpression = IDLE;
        expressionTimerActive = false;
        break;

      case '?':
        printHelp();
        return;
    }

    printCurrentState();
  }
}

    printCurrentState();
  }
}

