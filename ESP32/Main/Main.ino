/*
 * PROYECTO GRÚA - CONTROL Y COMUNICACIÓN
 * Objetivo: Ejecutar secuencias de movimiento y comunicarse con Raspberry Pi.
 */

#include "Config.h"
#include "Motor.h"

// --- INSTANCIAS CON FÍSICA CORRECTA ---
StepperMotor motorA(PINS_A, SPEED_A, STEPS_PER_DEG_GEARED);
StepperMotor motorB(PINS_B, SPEED_B, STEPS_PER_DEG_DIRECT);
StepperMotor motorC(PINS_C, SPEED_C, STEPS_PER_DEG_DIRECT);
StepperMotor motorD(PINS_D, SPEED_D, STEPS_PER_DEG_DIRECT);

// --- VARIABLES DE COMUNICACIÓN ---
String inputString = "";
bool stringComplete = false;

// --- MÁQUINA DE ESTADOS ---
enum EstadoGrua { ESPERANDO, MOVIENDO_ABD, MOVIENDO_C };
EstadoGrua estadoActual = ESPERANDO;

// Declaración de funciones
void parseCommand(String cmd);
void processSingleCommand(String singleCmd);

void setup() {
  Serial.begin(115200);
  delay(1000); // Pausa de seguridad para estabilizar conexión
  
  // Energizamos todos (Hold)
  motorA.energize();
  motorB.energize();
  motorC.energize();
  motorD.energize();

  // Requisito: Mensaje inicial automático
  Serial.println("\n**************************************************");
  Serial.println("ESP32 CONECTADA, ESPERANDO COMUNICACION");
  Serial.println("**************************************************\n");
}

void loop() {
  // 1. Escuchar a la Raspberry Pi
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;
    } else {
      inputString += inChar;
    }
  }

  // 2. Interpretar la orden completa
  if (stringComplete) {
    inputString.trim();
    if (inputString.length() > 0) {
      parseCommand(inputString);
    }
    inputString = "";
    stringComplete = false;
  }

  // 3. Mover (Lógica de la Máquina de Estados)
  switch (estadoActual) {
    case ESPERANDO:
      // No hacemos nada, esperamos nuevos comandos.
      break;

    case MOVIENDO_ABD:
      // Actualizamos solo A, B y D
      motorA.update();
      motorB.update();
      motorD.update();

      // ¿Ya terminaron los tres de moverse?
      if (!motorA.isBusy() && !motorB.isBusy() && !motorD.isBusy()) {
        
        // Si terminaron, revisamos si el motor C tiene trabajo pendiente
        if (motorC.isBusy()) {
          estadoActual = MOVIENDO_C; // Pasamos a la siguiente fase
        } else {
          // El motor C no se tenía que mover, así que terminamos todo
          Serial.println("Listo");
          Serial.println("==================================================\n"); // Cierre visual
          estadoActual = ESPERANDO;
        }
      }
      break;

    case MOVIENDO_C:
      // Actualizamos solo C
      motorC.update();

      // ¿Ya terminó el motor C?
      if (!motorC.isBusy()) {
        Serial.println("Listo"); // Avisamos a la Raspberry que terminamos
        Serial.println("==================================================\n"); // Cierre visual
        estadoActual = ESPERANDO;
      }
      break;
  }
}

// --- FUNCIONES DE INTERPRETACIÓN ---

// Separa la cadena "A:90;B:180;C:45" en comandos individuales
void parseCommand(String cmd) {
  // Mejoras visuales de inicio de comando
  Serial.println("==================================================");
  Serial.println("Mensaje recibido");
  Serial.print("Orden a ejecutar: ");
  Serial.println(cmd);
  Serial.println("--------------------------------------------------");

  int startIdx = 0;
  int endIdx = cmd.indexOf(';');

  // Mientras encuentre un punto y coma, extrae ese pedazo
  while (endIdx != -1) {
    processSingleCommand(cmd.substring(startIdx, endIdx));
    startIdx = endIdx + 1;
    endIdx = cmd.indexOf(';', startIdx);
  }
  // Procesa el último comando (o el único si no había punto y coma)
  processSingleCommand(cmd.substring(startIdx));

  // Decidimos a qué estado pasar según los motores que deban moverse
  if (motorA.isBusy() || motorB.isBusy() || motorD.isBusy()) {
    estadoActual = MOVIENDO_ABD;
  } else if (motorC.isBusy()) {
    estadoActual = MOVIENDO_C;
  } else {
    // Si la Raspberry mandó posiciones en las que los motores ya están
    Serial.println("Listo");
    Serial.println("==================================================\n"); // Cierre visual
  }
}

// Extrae la letra y el número (ej. "A:90") y se lo asigna al motor
void processSingleCommand(String singleCmd) {
  int separator = singleCmd.indexOf(':');
  if (separator != -1) {
    char id = singleCmd.charAt(0);
    int val = singleCmd.substring(separator + 1).toInt();
    
    switch(id) {
      case 'A': motorA.setTargetDegrees(val); break;
      case 'B': motorB.setTargetDegrees(val); break;
      case 'C': motorC.setTargetDegrees(val); break;
      case 'D': motorD.setTargetDegrees(val); break;
    }
  }
}