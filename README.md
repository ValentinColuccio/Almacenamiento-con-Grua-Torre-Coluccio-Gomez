<div align="center">

<img src="https://github.com/JonatanBogadoUNLZ/PPS-Jonatan-Bogado/blob/9952aac097aca83a1aadfc26679fc7ec57369d82/LOGO%20AZUL%20HORIZONTAL%20-%20fondo%20transparente.png" alt="Logo UNLZ" width="400"/>

<h2 align="center">Facultad de Ingeniería – Universidad Nacional de Lomas de Zamora</h2>

# 🏗️ Grúa Torre Robótica Inteligente

### Proyecto Final de Carrera | Ingeniería en Mecatrónica

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![C++](https://img.shields.io/badge/C++-ESP32_IDF-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![TensorFlow](https://img.shields.io/badge/TensorFlow-Lite-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Hardware](https://img.shields.io/badge/Hardware-Raspberry_Pi_%7C_ESP32-A22846?style=for-the-badge)

</div>

---

## 📑 Índice

- [🧠 Descripción General](#descripción-general)
- [🚀 Arquitectura del Sistema](#arquitectura-del-sistema)
- [⚙️ Funcionalidades Clave](#funcionalidades-clave)
- [🛠️ Tecnologías Utilizadas](#tecnologías-utilizadas)
- [📂 Estructura del Repositorio](#estructura-del-repositorio)
- [📈 Aplicaciones Potenciales](#aplicaciones-potenciales)
- [👤 Autores](#autores)

---

<a id="descripción-general"></a>

## 🧠 Descripción General

Este repositorio contiene el código fuente, diagramas y documentación del desarrollo de una **grúa torre robótica a escala**, presentada como Proyecto Final para la carrera de **Ingeniería en Mecatrónica** en la Universidad Nacional de Lomas de Zamora (UNLZ).

El sistema simula un entorno logístico inteligente de alta complejidad. Integra hardware embebido, control de movimiento de precisión e Inteligencia Artificial para lograr un ciclo automatizado de:

1.  **Percepción:** Detección y clasificación de objetos mediante visión artificial.
2.  **Decisión:** Procesamiento de comandos de voz y gestión de inventario.
3.  **Actuación:** Movimiento cinemático preciso para la manipulación, almacenamiento y entrega de cargas.

> **Actualización Tecnológica:** En esta versión del proyecto, se ha migrado el módulo de actuación de baja latencia de una placa Arduino Uno a un microcontrolador **ESP32**, mejorando las capacidades de procesamiento y comunicación.

---

<a id="arquitectura-del-sistema"></a>

## 🚀 Arquitectura del Sistema

El proyecto implementa un modelo de computación distribuida e *Edge Computing*, dividiendo las tareas según la capacidad de cómputo requerida:

```mermaid
graph TD
    User([👤 Usuario]) -->|Voz / Cámara Celular| PC[💻 PC Central - High Power Computing]
    
    subgraph "Nivel de Inteligencia y Percepción (PC)"
        PC -->|Hilos Paralelos| ML_Img[🧠 ML: Detección Objetos TensorFlow]
        PC -->|Hilos Paralelos| ML_Voice[🎙️ ML: Reconocimiento Voz Vosk]
    end

    PC -->|Comunicación Wi-Fi Sockets TCP/IP| RPi[🍓 Raspberry Pi Zero 2W - Máster de Campo]

    subgraph "Nivel de Coordinación y Lógica (Raspberry Pi)"
        RPi --> Logic[⚙️ Lógica de Misión e Inventario]
        RPi --> Kinematics[📐 Cálculo Cinemática Directa/Inversa]
        RPi --> Sensors[🚨 Sensores de Proximidad]
        RPi --> Display[📟 Display LCD]
    end

    RPi -->|UART Serial Protocolo Propio| ESP32[🔧 ESP32 - Control de Tiempo Real]

    subgraph "Nivel de Actuación y Sensores (ESP32)"
        ESP32 --> Drivers[🔌 Control Drivers L298N]
        ESP32 --> Motors[🚙 Motores Paso a Paso NEMA]
    end

    Motors --> Crane[🏗️ Estructura Mecánica Grúa]
    Crane -.->|Retroalimentación Visual| User

    style PC fill:#f9f,stroke:#333,stroke-width:2px
    style RPi fill:#ff9,stroke:#333,stroke-width:2px
    style ESP32 fill:#9cf,stroke:#333,stroke-width:2px
    style User fill:#fff,stroke:#333,stroke-width:2px
```

### Flujo de Trabajo Simplificado

1.  La **PC** procesa video y audio pesados (IA). Envía comandos de alto nivel ("Buscar Cubo Rojo") a la Pi.
2.  La **Raspberry Pi** gestiona la lógica del almacén, traduce el comando en coordenadas angulares/lineales necesarias y monitorea los sensores de seguridad en tiempo real.
3.  El **ESP32** recibe las coordenadas y genera los pulsos precisos para los motores.

---

<a id="funcionalidades-clave"></a>

## ⚙️ Funcionalidades Clave

- ✅ **Arquitectura Modular Híbrida:** Separación clara de responsabilidades entre PC (IA), RPi (Lógica) y ESP32 (Actuación).
- ✅ **Procesamiento en Paralelo:** Uso intensivo de *threading* en Python para gestionar simultáneamente cámara y micrófono sin bloqueos.
- ✅ **NLP (Natural Language Processing):** Análisis de comandos de voz para la búsqueda y entrega autónoma de objetos inventariados.
- ✅ **Visión Artificial:** Detección automática y clasificación de objetos en la zona de carga para su ingreso al sistema.
- ✅ **Control de Movimiento de Precisión:** Implementación de aceleración/desaceleración y manejo de cinemática para mover motores paso a paso NEMA con exactitud.
- ✅ **Protocolo de Comunicación Robusto:** Diseño de un protocolo serie personalizado sobre UART para garantizar la integridad de los comandos enviados al ESP32.

---

<a id="tecnologías-utilizadas"></a>

## 🛠️ Tecnologías Utilizadas

| Módulo / Componente | Tecnologías / Herramientas Clave |
| :--- | :--- |
| **Visión Inteligente (PC)** | Python, OpenCV, **TensorFlow Lite** (Modelo `.h5`), Multi-threading. |
| **Procesamiento de Voz (PC)** | Python, Vosk (Modelo Español), Speech Recognition. |
| **Control de Campo (Raspi)** | Python, Cinemática (Matemática vectorial), Sockets TCP/IP. |
| **Firmware Actuación (ESP32)** | **C/C++**, Arduino IDE/VS Code (Framework), Control preciso de timings. |
| **Hardware de Potencia** | Motores NEMA, Drivers L298N, Sensores Optoacopladores. |
| **Redes** | Comunicación Sockets TCP/IP (Wi-Fi PC-RPi), UART Serial (RPi-ESP32). |

---

<a id="estructura-del-repositorio"></a>

## 📂 Estructura del Repositorio

A continuación se detalla la organización de los archivos principales de software:

```bash
.
├── 📂 doc/                     # Documentación del proyecto, planos y tesis.
├── 📂 hardware/                # Esquemas de conexión y diseños 3D.
├── 📂 software/
│   ├── 📂 PC/                  # Ejecución en Computadora Central
│   │   ├── 📄 TTpower.py       # Script principal (Orquestador de IA y Comunicaciones)
│   │   ├── 📄 keras_model.h5   # Modelo entrenado para detección de objetos
│   │   └── 📂 vosk-model-.../  # Modelo ligero para reconocimiento de voz
│   ├── 📂 Raspi/               # Ejecución en Raspberry Pi Zero 2W
│   │   ├── 📄 SEpower.py       # Script principal (Lógica de Misión y Enlace)
│   │   └── 📄 cinematica.py    # Módulo matemático de movimientos
│   └── 📂 ESP32/               # Firmware del Microcontrolador
│       └── 📂 Main/            # Proyecto principal separado en bloques modulares
│           ├── 📄 Main.ino     # Lógica central y bucle principal
│           ├── 📄 Config.cpp   # Definición de parámetros y pines
│           ├── 📄 Motor.cpp    # Implementación del control de motores paso a paso
│           └── 📄 Motor.h      # Headers y declaración de clases
└── 📄 README.md
```

---

<a id="aplicaciones-potenciales"></a>

## 📈 Aplicaciones Potenciales

Este proyecto no es solo un desarrollo académico, sino un prototipo funcional con bases sólidas para:

1.  **Educación y R&D:** Plataforma de demostración avanzada para robótica, IA aplicada y sistemas embebidos.
2.  **Logística Inteligente:** Base para el desarrollo de sistemas de clasificación y *picking* automatizado en almacenes a escala.
3.  **Robótica de Servicio:** Automatización de tareas de manipulación y traslado en entornos controlados.

---

<a id="autores"></a>

## 👤 Autores

Trabajo final realizado por los estudiantes de Ingeniería en Mecatrónica de la UNLZ:

<div align="center">

| **Valentín Coluccio** | **Franco Gómez** |
| :---: | :---: |
| <a href="https://github.com/ValentinColuccio"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" /></a> | <a href="https://github.com/FrancoGomez-98"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" /></a> |
| <a href="https://www.linkedin.com/in/valentin-coluccio-804301359/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" /></a> | <a href="https://www.linkedin.com/in/franco-gomez-0a71822a7/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" /></a> |

---

_Desarrollado con pasión, curiosidad y muchas pruebas y errores 🚀_

</div>
