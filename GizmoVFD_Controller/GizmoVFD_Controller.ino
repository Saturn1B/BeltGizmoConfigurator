#include <EEPROM.h>

// ======================================================
// MAX6921 CONTROL PINS
// ======================================================

#define DIN   11
#define CLK   13
#define LOAD  10
#define BLANK 9

// ======================================================
// EEPROM LAYOUT
// ======================================================

#define EEPROM_TEXT_ADDR   0
#define EEPROM_TEXT_LEN    64

#define EEPROM_SPEED_ADDR  80

#define EEPROM_MAGIC 0xBEEF

// ======================================================
// CONFIG VARIABLES
// ======================================================

struct DisplayConfig {

  char text[64];

  uint16_t scrollSpeed;

  uint8_t scrollSpacing;

  bool forceScroll;

  uint8_t animationMode;

  uint8_t segmentMap[8];

  uint8_t gridMap[8];
};

DisplayConfig config;

struct EEPROMData {

  uint16_t magic;

  DisplayConfig cfg;
};

EEPROMData ee;

// ======================================================
// LOGICAL SEGMENT IDS
// ======================================================

enum {

  SEG_E,
  SEG_D,
  SEG_C,
  SEG_DP,

  SEG_A,
  SEG_G,
  SEG_F,
  SEG_B
};

uint32_t segMask(uint8_t logicalSegment)
{
  return (1UL << config.segmentMap[logicalSegment]);
}

// ======================================================
// DISPLAY VARIABLES
// ======================================================

uint32_t displayBuf[8];

String scrollMessage = "";

int scrollIndex = 0;

unsigned long lastScrollMs = 0;

const uint16_t refreshPerDigitUs = 1200;

// ======================================================
// ANIMATION STATE
// ======================================================

enum AnimationStepType {

  STEP_STATIC,
  STEP_SCROLL,
  STEP_BLINK,
  STEP_HOLD
};

struct AnimationStep {

  uint8_t type;

  char text[64];

  uint16_t duration;

  uint16_t speed;
};

struct AnimationState {

  uint8_t currentStep = 0;

  unsigned long stepStartTime = 0;

  unsigned long lastFrameTime = 0;

  uint16_t frameIndex = 0;

  bool blinkState = false;
};

AnimationState anim;

#define MAX_ANIMATION_STEPS 8

AnimationStep animationSteps[MAX_ANIMATION_STEPS];

uint8_t animationStepCount = 0;

String getFrame() {

  if (animationStepCount == 0) {
    return "        ";
  }

  AnimationStep &step =
    animationSteps[anim.currentStep];

  // =================================================
  // STATIC
  // =================================================

  if (step.type == STEP_STATIC) {

    String s = step.text;

    s.toUpperCase();

    while (s.length() < 8) {
      s += " ";
    }

    return s;
  }

  // =================================================
  // SCROLL
  // =================================================

  if (step.type == STEP_SCROLL) {

    String msg = step.text;

    msg.toUpperCase();

    for (int i = 0; i < config.scrollSpacing; i++) {
      msg += " ";
    }

    int len = msg.length();

    String window = "";

    for (int i = 0; i < 8; i++) {

      int idx =
        (anim.frameIndex + i) % len;

      window += msg.charAt(idx);
    }

    return window;
  }

  // =================================================
  // BLINK
  // =================================================

  if (step.type == STEP_BLINK) {

    if (anim.blinkState) {

      String s = step.text;

      s.toUpperCase();

      while (s.length() < 8) {
        s += " ";
      }

      return s;
    }

    return "        ";
  }

  // =================================================
  // HOLD
  // =================================================

  if (step.type == STEP_HOLD) {

    String s = step.text;

    s.toUpperCase();

    while (s.length() < 8) {
      s += " ";
    }

    return s;
  }

  return "        ";
}

// ======================================================
// SERIAL
// ======================================================

String serialBuffer = "";

// ======================================================
// EEPROM SAVE / LOAD
// ======================================================

void saveConfig() {

  ee.magic = EEPROM_MAGIC;

  ee.cfg = config;

  EEPROM.put(0, ee);
}

void loadConfig() {

  EEPROM.get(0, ee);

  if (ee.magic != EEPROM_MAGIC) {

    setDefaultConfig();

    saveConfig();

    return;
  }

  config = ee.cfg;
}

void setDefaultConfig() {

  strcpy(config.text, "NO_GHOST");

  config.scrollSpeed = 250;

  config.scrollSpacing = 8;

  config.forceScroll = false;

  config.animationMode = 0;

  // Segment mapping

  config.segmentMap[0] = 0; // E
  config.segmentMap[1] = 1; // D
  config.segmentMap[2] = 2; // C
  config.segmentMap[3] = 3; // DP
  config.segmentMap[4] = 5; // A
  config.segmentMap[5] = 6; // G
  config.segmentMap[6] = 7; // F
  config.segmentMap[7] = 8; // B

  // Grid mapping

  for (int i = 0; i < 8; i++) {
    config.gridMap[i] = 10 + i;
  }
}

// ======================================================
// MAX6921 SEND
// ======================================================

void send20(uint32_t data) {

  digitalWrite(LOAD, LOW);

  for (int i = 19; i >= 0; i--) {

    digitalWrite(CLK, LOW);

    digitalWrite(DIN, (data >> i) & 1);

    digitalWrite(CLK, HIGH);
  }

  digitalWrite(LOAD, HIGH);
}

// ======================================================
// SERIAL COMMANDS
// ======================================================

bool parseMapString(
    String data,
    uint8_t *dest,
    int count
) {

  uint8_t temp[8];

  int index = 0;

  while (data.length() > 0 && index < count) {

    int comma = data.indexOf(',');

    String token;

    if (comma == -1) {

      token = data;
      data = "";

    } else {

      token = data.substring(0, comma);
      data = data.substring(comma + 1);
    }

    token.trim();

    if (token.length() == 0) {
      return false;
    }

    int value = token.toInt();

    if (value < 0 || value > 19) {
      return false;
    }

    temp[index++] = value;
  }

  // Must receive EXACT amount

  if (index != count) {
    return false;
  }

  // Copy only after validation

  for (int i = 0; i < count; i++) {
    dest[i] = temp[i];
  }

  return true;
}

void handleCommand(String cmd) {

  cmd.trim();

  // ---------------- TEXT ----------------

  if (cmd.startsWith("TEXT=")) {

    String s = cmd.substring(5);

    s.toUpperCase();

    s.toCharArray(config.text, 64);

    prepareMessage();

    buildDefaultAnimation();

    Serial.println("OK TEXT");
  }

  // ---------------- SPEED ----------------

  else if (cmd.startsWith("SPEED=")) {

    config.scrollSpeed = cmd.substring(6).toInt();

    prepareMessage();

    buildDefaultAnimation();

    Serial.println("OK SPEED");
  }

  // ---------------- SPACING ----------------

  else if (cmd.startsWith("SPACING=")) {

    config.scrollSpacing = cmd.substring(8).toInt();

    prepareMessage();

    buildDefaultAnimation();

    Serial.println("OK SPACING");
  }

  // ---------------- FORCE SCROLL ----------------

  else if (cmd.startsWith("FORCESCROLL=")) {

  config.forceScroll = cmd.substring(12).toInt();

  prepareMessage();

  buildDefaultAnimation();

  Serial.println("OK FORCE");
  }

  // ---------------- ANIMATION ----------------

  else if (cmd.startsWith("ANIM=")) {

    config.animationMode = cmd.substring(5).toInt();

    prepareMessage();

    buildDefaultAnimation();

    Serial.println("OK ANIM");
  }

  // ---------------- SEGMENT MAP ----------------

  else if (cmd.startsWith("SEGMAP=")) {

    String data = cmd.substring(7);

    if (parseMapString(data,
                      config.segmentMap,
                      8)) {

      Serial.println("OK SEGMAP");

    } else {

      Serial.println("ERR SEGMAP");
    }
  }

  // ---------------- GRID MAP ----------------

  else if (cmd.startsWith("GRIDMAP=")) {

    String data = cmd.substring(8);

    if (parseMapString(data,
                      config.gridMap,
                      8)) {

      Serial.println("OK GRIDMAP");

    } else {

      Serial.println("ERR GRIDMAP");
    }
  }

  // ---------------- SAVE ----------------

  else if (cmd == "SAVE") {

    saveConfig();

    Serial.println("OK SAVED");
  }

  // ---------------- GET CONFIG ----------------

  else if (cmd == "GETCONFIG") {

  Serial.print("TEXT=");
  Serial.println(config.text);

  Serial.print("SPEED=");
  Serial.println(config.scrollSpeed);

  Serial.print("SPACING=");
  Serial.println(config.scrollSpacing);

  Serial.print("FORCESCROLL=");
  Serial.println(config.forceScroll);

  Serial.print("ANIM=");
  Serial.println(config.animationMode);

  Serial.println("ENDCONFIG");
  }

  // ---------------- GET MAP ----------------

  else if (cmd == "GETMAP") {

    Serial.print("SEGMAP=");

    for (int i = 0; i < 8; i++) {

      Serial.print(config.segmentMap[i]);

      if (i < 7)
        Serial.print(",");
    }

    Serial.println();

    Serial.print("GRIDMAP=");

    for (int i = 0; i < 8; i++) {

      Serial.print(config.gridMap[i]);

      if (i < 7)
        Serial.print(",");
    }

    Serial.println();

    Serial.println("ENDMAP");
  }

}

void readSerial() {

  while (Serial.available()) {

    char c = Serial.read();

    if (c == '\n') {

      handleCommand(serialBuffer);

      serialBuffer = "";

    } else if (c != '\r') {

      serialBuffer += c;
    }
  }
}

// ======================================================
// CHARACTER TO SEGMENTS
// ======================================================

uint32_t charToSegments(char c) {
  switch (c) {
    case '0': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F);
    case '1': return segMask(SEG_B) | segMask(SEG_C);
    case '2': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_G) | segMask(SEG_E) | segMask(SEG_D);
    case '3': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_G);
    case '4': return segMask(SEG_F) | segMask(SEG_G) | segMask(SEG_B) | segMask(SEG_C);
    case '5': return segMask(SEG_A) | segMask(SEG_F) | segMask(SEG_G) | segMask(SEG_C) | segMask(SEG_D);
    case '6': return segMask(SEG_A) | segMask(SEG_F) | segMask(SEG_G) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E);
    case '7': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C);
    case '8': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case '9': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_F) | segMask(SEG_G);

    case 'A': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'B': return segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'C': return segMask(SEG_A) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F);
    case 'D': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_G);
    case 'E': return segMask(SEG_A) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'F': return segMask(SEG_A) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'G': return segMask(SEG_A) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F);
    case 'H': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'I': return segMask(SEG_B) | segMask(SEG_C);
    case 'J': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E);
    case 'K': return segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'L': return segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F);
    case 'M': return segMask(SEG_A) | segMask(SEG_C) | segMask(SEG_E) | segMask(SEG_F);
    case 'N': return segMask(SEG_C) | segMask(SEG_E) | segMask(SEG_G);
    case 'O': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F);
    case 'P': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'Q': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_F) | segMask(SEG_G);
    case 'R': return segMask(SEG_E) | segMask(SEG_G);
    case 'S': return segMask(SEG_A) | segMask(SEG_F) | segMask(SEG_G) | segMask(SEG_C) | segMask(SEG_D);
    case 'T': return segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'U': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F);
    case 'V': return segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E);
    case 'W': return segMask(SEG_B) | segMask(SEG_D) | segMask(SEG_F);
    case 'X': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'Y': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_F) | segMask(SEG_G);
    case 'Z': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_G);

    case 'a': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_G);
    case 'b': return segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'c': return segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_G);
    case 'd': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_G);
    case 'e': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'f': return segMask(SEG_A) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'g': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_F) | segMask(SEG_G);
    case 'h': return segMask(SEG_C) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'i': return segMask(SEG_C);
    case 'j': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D);
    case 'l': return segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F);
    case 'n': return segMask(SEG_C) | segMask(SEG_E) | segMask(SEG_G);
    case 'o': return segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_G);
    case 'p': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'q': return segMask(SEG_A) | segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_F) | segMask(SEG_G);
    case 'r': return segMask(SEG_E) | segMask(SEG_G);
    case 't': return segMask(SEG_D) | segMask(SEG_E) | segMask(SEG_F) | segMask(SEG_G);
    case 'u': return segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_E);
    case 'y': return segMask(SEG_B) | segMask(SEG_C) | segMask(SEG_D) | segMask(SEG_F) | segMask(SEG_G);

    case '-': return segMask(SEG_G);
    case '_': return segMask(SEG_D);
    case '=': return segMask(SEG_G) | segMask(SEG_D);
    case ' ': return 0;
    case '.': return segMask(SEG_DP);
    case ',': return segMask(SEG_DP);
    case '\'': return segMask(SEG_B);
    case '"': return segMask(SEG_B) | segMask(SEG_F);

    default:  return 0;
  }
}

// ======================================================
// MESSAGE PREP
// ======================================================

String makeSpaces(int n) {

  String s = "";

  for (int i = 0; i < n; i++) {
    s += " ";
  }

  return s;
}

void prepareMessage() {

  scrollMessage = "";

  // uppercase conversion

  for (unsigned int i = 0; i < strlen(config.text); i++) {

    char c = config.text[i];

    if (c >= 'a' && c <= 'z') {
      c = c - 32;
    }

    scrollMessage += c;
  }

  // spacing between repetitions

  for (int i = 0; i < config.scrollSpacing; i++) {
    scrollMessage += " ";
  }

  scrollIndex = 0;

  lastScrollMs = millis();
}

void buildDefaultAnimation() {

  animationStepCount = 0;

  // =================================================
  // SHORT TEXT
  // =================================================

  if (strlen(config.text) <= 8 && !config.forceScroll) {

    AnimationStep step;

    step.type = STEP_STATIC;

    strcpy(step.text, config.text);

    step.duration = 0;

    step.speed = 0;

    animationSteps[0] = step;

    animationStepCount = 1;
  }

  // =================================================
  // LONG TEXT
  // =================================================

  else {

    AnimationStep step;

    step.type = STEP_SCROLL;

    strcpy(step.text, config.text);

    step.duration = 0;

    step.speed = config.scrollSpeed;

    animationSteps[0] = step;

    animationStepCount = 1;
  }

  anim.currentStep = 0;

  anim.stepStartTime = millis();

  anim.lastFrameTime = millis();

  anim.frameIndex = 0;
}

// ======================================================
// WINDOW BUILD
// ======================================================

void setWindowFromText(const String &txt, int startIndex) {

  for (int i = 0; i < 8; i++) {

    int idx = startIndex + i;

    uint32_t segs = 0;

    if (idx >= 0 && idx < (int)txt.length()) {

      char c = txt.charAt(idx);

      if (c == '.' || c == ',') {

        segs = segMask(SEG_DP);

      } else {

        segs = charToSegments(c);

        if (idx + 1 < (int)txt.length()) {

          char next = txt.charAt(idx + 1);

          if (next == '.' || next == ',') {
            segs |= segMask(SEG_DP);
          }
        }
      }
    }

    displayBuf[i] = segs;
  }

  for (int i = 0; i < 7; i++) {

    int idx = startIndex + i + 1;

    if (idx >= 0 && idx < (int)txt.length()) {

      char c = txt.charAt(idx);

      if (c == '.' || c == ',') {
        displayBuf[i + 1] = 0;
      }
    }
  }
}

// ======================================================
// UPDATE DISPLAY BUFFER
// ======================================================

void updateDisplayBuffer() {

  String frame = getFrame();

  setWindowFromText(frame, 0);
}

void updateAnimationState() {

  if (animationStepCount == 0) {
    return;
  }

  unsigned long now = millis();

  AnimationStep &step =
    animationSteps[anim.currentStep];

  // =================================================
  // SCROLL
  // =================================================

  if (step.type == STEP_SCROLL) {

    if (now - anim.lastFrameTime >= step.speed) {

      anim.lastFrameTime = now;

      anim.frameIndex++;
    }
  }

  // =================================================
  // BLINK
  // =================================================

  if (step.type == STEP_BLINK) {

    if (now - anim.lastFrameTime >= step.speed) {

      anim.lastFrameTime = now;

      anim.blinkState = !anim.blinkState;
    }
  }

  // =================================================
  // STEP DURATION
  // =================================================

  if (step.duration > 0) {

    if (now - anim.stepStartTime >= step.duration) {

      anim.currentStep++;

      if (anim.currentStep >= animationStepCount) {
        anim.currentStep = 0;
      }

      anim.stepStartTime = now;

      anim.lastFrameTime = now;

      anim.frameIndex = 0;

      anim.blinkState = false;
    }
  }
}

// ======================================================
// REFRESH DISPLAY
// ======================================================

void refreshDisplayOnce() {

  for (int i = 0; i < 8; i++) {

    uint32_t data =
      displayBuf[i] |
      (1UL << config.gridMap[i]);

    send20(data);

    delayMicroseconds(refreshPerDigitUs);
  }
}

// ======================================================
// SETUP
// ======================================================

void setup() {

  pinMode(DIN, OUTPUT);
  pinMode(CLK, OUTPUT);
  pinMode(LOAD, OUTPUT);
  pinMode(BLANK, OUTPUT);

  digitalWrite(BLANK, LOW);

  send20(0);

  Serial.begin(115200);

  // Load saved config

  loadConfig();

  prepareMessage();
  buildDefaultAnimation();

  updateDisplayBuffer();
}

// ======================================================
// LOOP
// ======================================================

void loop() {

  readSerial();

  updateAnimationState();
  updateDisplayBuffer();
  refreshDisplayOnce();
}