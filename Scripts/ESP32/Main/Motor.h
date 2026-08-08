#ifndef MOTOR_H
#define MOTOR_H
#include <Arduino.h>

class StepperMotor {
  private:
    int stepPin;
    int dirPin;
    long currentPos;
    long targetPos;
    unsigned long lastStepTime;
    int stepDelay;
    float stepsPerDegree;

  public:
    StepperMotor(const int motorPins[2], int speed, float stepsPerDeg);

    void energize();
    void setTargetDegrees(float deg);
    void update();
    bool isBusy();
    long getPosition();
    void stop(); 
    float getCurrentDegrees(); 
    
    // Función para inyectar la velocidad desde el comando serial
    void setSpeed(int speed); 
};
#endif