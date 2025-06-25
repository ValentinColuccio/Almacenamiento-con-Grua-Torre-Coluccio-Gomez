// Pines para cada motor (puedes cambiar según tus conexiones)
const int motorPins[4][4] = {
  {2, 3, 4, 5},     // Motor A
  {6, 7, 8, 9},     // Motor B
  {10, 11, 12, 13}, // Motor C
  {A0, A1, A2, A3}  // Motor D
};

// Rango de movimiento por motor (modificables)
int minAngle[4] = {-2160, -2160, -2160, -2160};  // A, B, C, D
int maxAngle[4] = {2160, 2160, 2160, 2160};      // A, B, C, D

const int stepsPerRevolution = 200;
const float stepsPerDegree = stepsPerRevolution / 360.0;

const int stepSequence[4][4] = {
  {1, 0, 1, 0},
  {0, 1, 1, 0},
  {0, 1, 0, 1},
  {1, 0, 0, 1}
};

int currentStepIndex[4] = {0, 0, 0, 0};
int currentPosition[4] = {0, 0, 0, 0}; // posición en grados de cada motor

void setup() {
  Serial.begin(9600);

  // Configurar pines como salida
  for (int m = 0; m < 4; m++) {
    for (int p = 0; p < 4; p++) {
      pinMode(motorPins[m][p], OUTPUT);
    }
  }

  // Energizar motores con el paso inicial (evita que queden sueltos)
  for (int m = 0; m < 4; m++) {
    for (int p = 0; p < 4; p++) {
      digitalWrite(motorPins[m][p], stepSequence[currentStepIndex[m]][p]);
    }
  }

  Serial.println("Esperando comando:");
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    parseAndMove(input);
  }
}

void parseAndMove(String command) {
  command.trim();
  if (command.length() == 0) return;

  int motorTargets[4] = {0, 0, 0, 0};
  bool active[4] = {false, false, false, false};

  int start = 0;
  while (start < command.length()) {
    int sep = command.indexOf(';', start);
    if (sep == -1) sep = command.length();

    String part = command.substring(start, sep);
    part.trim();

    char motor = part.charAt(0);
    int idx = motor - 'A'; // A=0, B=1, etc.
    int colon = part.indexOf(':');
    if (colon > 0 && idx >= 0 && idx < 4) {
      int targetDeg = part.substring(colon + 1).toInt();

      // Validar rango
      if (targetDeg < minAngle[idx] || targetDeg > maxAngle[idx]) {
        Serial.print("⚠️ Motor ");
        Serial.print(motor);
        Serial.print(": Ángulo ");
        Serial.print(targetDeg);
        Serial.println(" fuera de rango, no se moverá.");
      } else {
        motorTargets[idx] = targetDeg;
        active[idx] = true;
      }
    }

    start = sep + 1;
  }

  // Mover A, B, D en simultáneo
  moveMotorsSimultaneously(motorTargets, active);

  // Mover motor C por separado si corresponde
  if (active[2]) {
    moveMotorTo(2, motorTargets[2]);
  }

  Serial.println("Listo");
}

void moveMotorsSimultaneously(int motorTargets[4], bool active[4]) {
  int stepsNeeded[4] = {0};
  int direction[4] = {0};
  int stepsDone[4] = {0};
  int maxSteps = 0;

  int indices[] = {0, 1, 3};  // motores A, B, D

  // Calcular pasos y dirección para A, B, D
  for (int i : indices) {
    if (active[i]) {
      int deltaDeg = motorTargets[i] - currentPosition[i];
      stepsNeeded[i] = abs(deltaDeg * stepsPerDegree);
      direction[i] = (deltaDeg >= 0) ? 1 : -1;
      if (stepsNeeded[i] > maxSteps) maxSteps = stepsNeeded[i];
    }
  }

  // Ejecutar pasos sincronizados con aceleración
  int baseDelay = 100; // Tiempo más lento al inicio/final
  int minDelay = 50;   // Tiempo más rápido en el centro

  for (int step = 0; step < maxSteps; step++) {
    for (int i : indices) {
      if (active[i] && stepsDone[i] < stepsNeeded[i]) {
        currentStepIndex[i] += direction[i];
        if (currentStepIndex[i] < 0) currentStepIndex[i] = 3;
        if (currentStepIndex[i] > 3) currentStepIndex[i] = 0;

        for (int p = 0; p < 4; p++) {
          digitalWrite(motorPins[i][p], stepSequence[currentStepIndex[i]][p]);
        }

        stepsDone[i]++;
      }
    }

    // Rampa de velocidad (forma de campana)
    float progress = (float)step / maxSteps;
    float rampFactor = 4 * progress * (1 - progress);
    int dynamicDelay = baseDelay - (baseDelay - minDelay) * rampFactor;

    delay(dynamicDelay);
  }

  // Actualizar posiciones finales
  for (int i : indices) {
    if (active[i]) {
      currentPosition[i] = motorTargets[i];
    }
  }
}

void moveMotorTo(int motorIndex, int targetDegrees) {
  int currentDeg = currentPosition[motorIndex];
  int deltaDeg = targetDegrees - currentDeg;
  int steps = deltaDeg * stepsPerDegree;
  int dir = (steps >= 0) ? 1 : -1;
  steps = abs(steps);

  int baseDelay = 100;
  int minDelay = 50;

  for (int i = 0; i < steps; i++) {
    currentStepIndex[motorIndex] += dir;
    if (currentStepIndex[motorIndex] < 0) currentStepIndex[motorIndex] = 3;
    if (currentStepIndex[motorIndex] > 3) currentStepIndex[motorIndex] = 0;

    for (int p = 0; p < 4; p++) {
      digitalWrite(motorPins[motorIndex][p], stepSequence[currentStepIndex[motorIndex]][p]);
    }

    float progress = (float)i / steps;
    float rampFactor = 4 * progress * (1 - progress);
    int dynamicDelay = baseDelay - (baseDelay - minDelay) * rampFactor;

    delay(dynamicDelay);
  }

  currentPosition[motorIndex] = targetDegrees;
}
