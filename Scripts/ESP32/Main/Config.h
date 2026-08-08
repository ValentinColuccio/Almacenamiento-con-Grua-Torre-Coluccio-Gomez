#ifndef CONFIG_H
#define CONFIG_H
#include <Arduino.h>

// --- PINES: (STEP, DIR) ---
const int PINS_A[2] = {13, 14}; // Brazo  
const int PINS_B[2] = {27, 26}; // Carro  
const int PINS_C[2] = {25, 33}; // Gancho 
const int PINS_D[2] = {32, 4};  // Giro   

// --- VELOCIDADES DE INICIO (Por defecto al encender) ---
const int SPEED_A = 6500;  
const int SPEED_B = 2000;   
const int SPEED_C = 1000; 
const int SPEED_D = 3250; 

// --- MATEMÁTICA DE TRANSMISIÓN ---
const float BASE_STEPS = 3200.0; // Paso 1/16

// Motor A: Tiene reducción por engranajes 1:2
const float DEG_A = (BASE_STEPS * 2.0) / 360.0; 

// Motores B, C y D: Directos (o transmisión 1:1)
const float DEG_GENERIC = BASE_STEPS / 360.0; 

#endif