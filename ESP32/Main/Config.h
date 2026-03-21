#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// --- PINES ---
const int PINS_A[4] = {13, 12, 14, 27}; // Brazo (Engranajes)
const int PINS_B[4] = {26, 25, 33, 32}; // Carro (Cable)
const int PINS_C[4] = {16, 17, 5,  18}; // Gancho (Cable)
const int PINS_D[4] = {19, 21, 22, 23}; // Giro (Directo)

// --- VELOCIDADES FIJAS (Microsegundos de espera por paso) ---
// Mayor número = Más Lento.
// Ajustados según la física de la grúa:

const int SPEED_A = 20000;  // RÁPIDO: Tiene engranajes 1:2, el motor debe volar para mover el brazo.
const int SPEED_B = 10000;  // MUY RÁPIDO: El carro es liviano y el cable tiene poca fricción.
const int SPEED_C = 8000;  // LENTO: El gancho levanta peso (gravedad). Necesita fuerza, no velocidad.
const int SPEED_D = 12000; // MUY LENTO: Mueve toda la estructura. Si va rápido, la inercia sacudirá todo.

// --- MATEMÁTICA DE TRANSMISIÓN ---
const float STEPS_BASE = 400.0; // Pasos por vuelta del motor (Half-Step)

// 1. Para Motor A (Engranajes 1:2)
// El motor da 2 vueltas para que el brazo de 1.
const float STEPS_PER_DEG_GEARED = (STEPS_BASE * 2.0) / 360.0; 

// 2. Para Motores B, C y D (Directos al eje)
// 1 vuelta de motor = 1 vuelta de eje (o polea).
const float STEPS_PER_DEG_DIRECT = STEPS_BASE / 360.0; 

#endif