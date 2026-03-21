#include "Motor.h"
#include "Config.h"

const int SEQUENCE[8][4] = {
  {1, 0, 0, 0}, {1, 0, 1, 0}, {0, 0, 1, 0}, {0, 1, 1, 0},
  {0, 1, 0, 0}, {0, 1, 0, 1}, {0, 0, 0, 1}, {1, 0, 0, 1}
};

// Constructor recibe la precisión específica
StepperMotor::StepperMotor(const int motorPins[4], int speed, float stepsPerDeg) {
  for (int i = 0; i < 4; i++) {
    pins[i] = motorPins[i];
    pinMode(pins[i], OUTPUT);
  }
  stepDelay = speed;
  stepsPerDegree = stepsPerDeg; // Guardamos el dato
  
  stepIndex = 0;
  currentPos = 0;
  targetPos = 0;
  lastStepTime = 0;
}

void StepperMotor::energize() {
  step(0); 
}

void StepperMotor::setTargetDegrees(int deg) {
  // Usamos la variable interna stepsPerDegree en lugar de la global
  targetPos = (long)(deg * stepsPerDegree);
  lastStepTime = micros(); 
}

bool StepperMotor::isBusy() {
  return currentPos != targetPos;
}

long StepperMotor::getPosition() {
  return currentPos;
}

void StepperMotor::update() {
  if (currentPos == targetPos) return;

  if ((micros() - lastStepTime) >= stepDelay) {
    lastStepTime = micros();

    if (targetPos > currentPos) {
      currentPos++;
      step(1);
    } else {
      currentPos--;
      step(-1);
    }
  }
}

void StepperMotor::step(int dir) {
  stepIndex += dir;
  if (stepIndex > 7) stepIndex = 0;
  if (stepIndex < 0) stepIndex = 7;

  for (int i = 0; i < 4; i++) {
    digitalWrite(pins[i], SEQUENCE[stepIndex][i]);
  }
}