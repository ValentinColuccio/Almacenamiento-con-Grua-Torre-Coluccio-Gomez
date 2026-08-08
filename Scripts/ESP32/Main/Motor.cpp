#include "Motor.h"
#include "Config.h"

StepperMotor::StepperMotor(const int motorPins[2], int speed, float stepsPerDeg) {
  stepPin = motorPins[0];
  dirPin = motorPins[1];
  
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  
  stepDelay = speed;
  stepsPerDegree = stepsPerDeg;
  currentPos = 0;
  targetPos = 0;
  lastStepTime = 0;
}

void StepperMotor::update() {
  if (currentPos == targetPos) return;

  if ((micros() - lastStepTime) >= stepDelay) {
    lastStepTime = micros();
    
    if (targetPos > currentPos) {
      digitalWrite(dirPin, HIGH);
      currentPos++;
    } else {
      digitalWrite(dirPin, LOW);
      currentPos--;
    }
    
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(2); 
    digitalWrite(stepPin, LOW);
  }
}

void StepperMotor::energize() { 
}

void StepperMotor::setTargetDegrees(float deg) {
  targetPos = (long)(deg * stepsPerDegree);
  lastStepTime = micros(); 
}

bool StepperMotor::isBusy() { return currentPos != targetPos; }

long StepperMotor::getPosition() { return currentPos; }

float StepperMotor::getCurrentDegrees() {
  return (float)currentPos / stepsPerDegree;
}

void StepperMotor::stop() {
  targetPos = currentPos;
}

// --- ACTUALIZADOR DE VELOCIDAD DINÁMICA ---
void StepperMotor::setSpeed(int speed) {
  stepDelay = speed;
}