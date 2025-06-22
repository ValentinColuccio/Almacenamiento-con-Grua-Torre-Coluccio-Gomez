# Grúa Torre Robótica Inteligente – Proyecto Final de Ingeniería en Mecatrónica 🎓🤖

Este repositorio contiene el código fuente y archivos asociados al desarrollo de una **grúa torre robótica a escala**, realizada como **proyecto final de la carrera de Ingeniería en Mecatrónica** en la *Universidad Nacional de Lomas de Zamora (UNLZ)*, Argentina.

## 🧠 Descripción General

El sistema está compuesto por una grúa robotizada a escala, controlada por una combinación de una **Raspberry Pi Zero 2W**, un **Arduino Uno** y una **Pc**, capaz de:

- **Detectar y clasificar objetos** mediante una cámara e inteligencia artificial (TensorFlow)
- **Almacenar y entregar objetos** según su categoría
- **Recibir comandos por voz** para ejecutar acciones en tiempo real
- **Moverse con precisión** utilizando motores paso a paso

Este proyecto simula un sistema logístico inteligente, con potencial aplicación en automatización de almacenes y robótica de servicio.

## 🚀 Arquitectura del Sistema

```plaintext
        [Usuario]
           |
     Voz / Cámara (celular)
           |
     [PC con Wi-Fi + IA]
   ┌─────────────────────────────┐
   │ • Detección de objetos (IA) │
   │ • Reconocimiento de voz     │
   │ • Envío de comandos a la Pi │
   └─────────────────────────────┘
           |
     Comunicación por Wi-Fi
           |
   Raspberry Pi Zero 2W
   ┌─────────────────────────────────────┐
   │ • Cinemática directa/inversa        │
   │ • Registro de inventario            │
   │ • Lógica de misión                  │
   │ • Envío de ángulos a Arduino (UART) │
   └─────────────────────────────────────┘
                   |
              UART Serial
                   |
             [Arduino Uno]
        ┌───────────────────────────┐
        │ • Control de motores      │
        │ • Sensores de pausa       │
        │ • Gestión de movimientos  │
        └───────────────────────────┘
                   |
     [Grúa Torre a Escala con sensores]
```

## ⚙️ Funcionalidades

- ✅ **Arquitectura modular**, con separación clara entre percepción, lógica y actuación
- ✅ **Procesamiento en paralelo** de cámara y micrófono (multihilo en Python)
- ✅ **Análisis de comandos de voz** para búsqueda y entrega de objetos
- ✅ **Detección automática de objetos**, con clasificación en zona de carga
- ✅ **Movimiento preciso de la grúa**, con motores paso a paso
- ✅ **Protocolo de comunicación serie personalizado**, robusto y extensible

## 🛠 Tecnologías Utilizadas

| Componente              | Tecnologías / Herramientas                           |
|-------------------------|------------------------------------------------------|
| Visión e IA             | Python, TensorFlow Lite, OpenCV, threading           |
| Control                 | Arduino C/C++, clases personalizadas para motores    |
| Comunicación            | UART, sockets TCP/IP, Python `queue` y `threading`   |
| Hardware de movimiento  | Motores NEMA, drivers L298N                          |
| Interfaz con el usuario | Micrófono, cámara, control por voz                   |

## 🧪 Estructura del Proyecto (resumen)

```
Data/
├── TransmisionTerminal.py     # Script principal ejecutado en la Raspberry Pi
├── Deteccion.py               # Módulo de detección con TensorFlow
├── motores.py                 # Clases para controlar motores paso a paso
├── cinematica.py              # Biblioteca de cinemática del brazo
├── comandos/                  # Lógica de interpretación de voz y acciones
├── arduino/                   # Código fuente para el Arduino (TorreGrua.ino)
├── etiquetas.txt              # Lista de etiquetas que puede reconocer el modelo
├── modelos/                   # Modelo de IA (TensorFlow Lite) y su configuración
└── README.md                  # Este archivo
```

## 📈 Aplicaciones Potenciales

- Demostración educativa de robótica aplicada
- Base para sistemas inteligentes de clasificación y logística
- Laboratorio portátil para control, visión y automatización

## 📚 Autor

**Valentín Coluccio y Franco Gabriel Gomez**  
Estudiantes de Ingeniería en Mecatrónica – UNLZ  
GitHub: [@ValentinColuccio](https://github.com/ValentinColuccio)  
LinkedIn: [valentin-coluccio-804301359](https://www.linkedin.com/in/valentin-coluccio-804301359/)

---

> Desarrollado con pasión, curiosidad y muchas pruebas y errores. 🚀