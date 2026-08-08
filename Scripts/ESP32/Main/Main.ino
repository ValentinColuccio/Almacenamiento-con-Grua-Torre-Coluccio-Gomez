/*
 * PROYECTO GRÚA ROBOTICA AUTOMATIZADA
 */
#include "Config.h"
#include "Motor.h"

StepperMotor motorA(PINS_A, SPEED_A, DEG_A);
StepperMotor motorB(PINS_B, SPEED_B, DEG_GENERIC);
StepperMotor motorC(PINS_C, SPEED_C, DEG_GENERIC);
StepperMotor motorD(PINS_D, SPEED_D, DEG_GENERIC);

String inputString = "";
bool stringComplete = false;

enum EstadoGrua { ESPERANDO, MOVIENDO_ABD, MOVIENDO_C };
EstadoGrua estadoActual = ESPERANDO;

void parseCommand(String cmd);
void processSingleCommand(String singleCmd);

void setup() {
  Serial.begin(115200);
  delay(1000); 
  
  motorA.energize();
  motorB.energize();
  motorC.energize();
  motorD.energize();

  Serial.println("\n**************************************************");
  Serial.println("ESP32 CONECTADA");
  Serial.println("**************************************************\n");
}

void loop() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') stringComplete = true;
    else inputString += inChar;
  }

  if (stringComplete) {
    inputString.trim();
    if (inputString.length() > 0) {
      
      // PARADA DE SEGURIDAD 
      if (inputString.equalsIgnoreCase("STOP")) {
        motorA.stop(); motorB.stop(); motorC.stop(); motorD.stop();
        Serial.println("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
        Serial.println("ALERTA: Comando 'STOP' recibido.");
        Serial.println("Sistema en espera.");
        Serial.println("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n");
        estadoActual = ESPERANDO; 
      } else {
        parseCommand(inputString);
      }
    }
    inputString = "";
    stringComplete = false;
  }

  // MÁQUINA DE ESTADOS HÍBRIDA (Se respeta la secuencia A,B,D -> C)
  switch (estadoActual) {
    case ESPERANDO: break;
    case MOVIENDO_ABD:
      motorA.update(); motorB.update(); motorD.update();
      if (!motorA.isBusy() && !motorB.isBusy() && !motorD.isBusy()) {
        if (motorC.isBusy()) estadoActual = MOVIENDO_C;
        else {
          Serial.println("Listo");
          estadoActual = ESPERANDO;
        }
      }
      break;
    case MOVIENDO_C:
      motorC.update();
      if (!motorC.isBusy()) {
        Serial.println("Listo");
        estadoActual = ESPERANDO;
      }
      break;
  }
}

void parseCommand(String cmd) {
  Serial.println("==================================================");
  Serial.print("Orden recibida: "); Serial.println(cmd);
  Serial.println("--------------------------------------------------");

  int startIdx = 0;
  int endIdx = cmd.indexOf(';');
  while (endIdx != -1) {
    processSingleCommand(cmd.substring(startIdx, endIdx));
    startIdx = endIdx + 1;
    endIdx = cmd.indexOf(';', startIdx);
  }
  processSingleCommand(cmd.substring(startIdx));

  if (motorA.isBusy() || motorB.isBusy() || motorD.isBusy()) estadoActual = MOVIENDO_ABD;
  else if (motorC.isBusy()) estadoActual = MOVIENDO_C;
  else Serial.println("Listo");
}

void processSingleCommand(String singleCmd) {
  int separator = singleCmd.indexOf(':');
  
  if (separator != -1) {
    char id = singleCmd.charAt(0);
    // Buscamos si existe el marcador de velocidad "-V"
    int velocityMarker = singleCmd.indexOf("-V");
    
    float val = 0.0;
    int newSpeed = -1;

    // Si encontramos "-V", separamos los grados de la velocidad
    if (velocityMarker != -1) {
      val = singleCmd.substring(separator + 1, velocityMarker).toFloat();
      newSpeed = singleCmd.substring(velocityMarker + 2).toInt();
    } else {
      // Si no hay "-V", solo leemos los grados
      val = singleCmd.substring(separator + 1).toFloat();
    }

    // Aplicamos los cambios al motor correspondiente
    switch(id) {
      case 'A': 
        if (newSpeed > 0) motorA.setSpeed(newSpeed);
        motorA.setTargetDegrees(val); 
        break;
      case 'B': 
        if (newSpeed > 0) motorB.setSpeed(newSpeed);
        motorB.setTargetDegrees(val); 
        break;
      case 'C': 
        if (newSpeed > 0) motorC.setSpeed(newSpeed);
        motorC.setTargetDegrees(val); 
        break;
      case 'D': 
        if (newSpeed > 0) motorD.setSpeed(newSpeed);
        motorD.setTargetDegrees(val); 
        break;
    }
  }
}