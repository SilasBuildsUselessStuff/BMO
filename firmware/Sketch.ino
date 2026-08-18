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
Expression currentExpression = IDLE;

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

void printHelp()
{
  Serial.println("");
  Serial.println("=== BMO DEBUG COMMANDS ===");
  Serial.println("Screens:");
  Serial.println("f = Face");
  Serial.println("w = Weather");
  Serial.println("s = Spotify");
  Serial.println("");

  Serial.println("Expressions:");
  Serial.println("h = Happy");
  Serial.println("a = Angry");
  Serial.println("t = Thinking");
  Serial.println("c = Confused");
  Serial.println("i = Idle");
  Serial.println("");
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
  if (Serial.available())
  {
    char cmd = Serial.read();

    switch(cmd)
    {
      // Screens

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
        currentExpression = HAPPY;
        break;

      case 'a':
        currentExpression = ANGRY;
        break;

      case 't':
        currentExpression = THINKING;
        break;

      case 'c':
        currentExpression = CONFUSED;
        break;

      case 'i':
        currentExpression = IDLE;
        break;

      case '?':
        printHelp();
        break;
    }

    printCurrentState();
  }
}
