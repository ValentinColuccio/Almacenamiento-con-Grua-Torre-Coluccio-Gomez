#ifndef MOTOR_H
#define MOTOR_H

#include <Arduino.h>

class StepperMotor {
  private:
    int pins[4];
    int stepIndex;
    long currentPos;
    long targetPos;
    unsigned long lastStepTime;
    int stepDelay;
    float stepsPerDegree; // Cada motor sabe su reducción

    void step(int dir);

  public:
    // Constructor
    StepperMotor(const int motorPins[4], int speed, float stepsPerDeg);

    void energize();
    void setTargetDegrees(int deg);
    void update();
    bool isBusy();
    long getPosition();
};

#endif