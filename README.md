with open("README.md", "w", encoding="utf-8") as f:
    f.write("""<div align="center">

<img src="assets/FI-UNLZ.png" alt="Logo FI UNLZ" width="400"/>

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

- [🧠 Descripción General](#-descripción-general)
- [📸 Galería y Demostraciones](#-galería-y-demostraciones)
- [🚀 Arquitectura del Sistema](#-arquitectura-del-sistema)
- [🔌 Hardware y Esquema de Conexiones](#-hardware-y-esquema-de-conexiones)
- [📡 Protocolos de Comunicación](#-protocolos-de-comunicación)
- [📐 Cinemática y Control Embebido](#-cinemática-y-control-embebido)
- [⚙️ Funcionalidades Clave](#️-funcionalidades-clave)
- [🛠️ Tecnologías Utilizadas](#️-tecnologías-utilizadas)
- [📂 Estructura del Repositorio](#-estructura-del-repositorio)
- [👤 Autores](#-autores)

---

## 🧠 Descripción General

Este repositorio contiene el desarrollo integral (software, hardware, planos y documentación) de una **grúa torre robótica a escala**, presentada como Proyecto Final de Carrera para la carrera de **Ingeniería en Mecatrónica** en la Universidad Nacional de Lomas de Zamora (UNLZ).

El sistema simula un entorno logístico automatizado de alta complejidad. Integra hardware embebido, modelado cinemático tridimensional e Inteligencia Artificial distribuida para lograr un ciclo autónomo de:

1. **Percepción:** Detección y clasificación de objetos en tiempo real mediante visión artificial.
2. **Decisión:** Procesamiento de lenguaje natural (comandos de voz) y gestión lógica de inventario.
3. **Actuación:** Movimiento coordinado de precisión para la manipulación, almacenamiento y entrega de cargas. El diseño mecánico contempla diferentes mecanismos de transmisión, empleando reducción por engranajes para el eje principal (Motor A) y transmisión por cable para el resto de los ejes de la estructura.

> **Evolución Tecnológica:** La arquitectura de control de bajo nivel fue optimizada utilizando un microcontrolador **ESP32** bajo un paradigma de programación estructurada y modular. Esto garantiza una ejecución determinista de tiempo real para el manejo simultáneo de 4 actuadores paso a paso con velocidades independientes.

---

## 📸 Galería y Demostraciones

El proyecto cuenta con un diseño de ingeniería respaldado por modelos CAD y esquemas electrónicos, disponibles en este repositorio.

<div align="center">
  <img src="Media/Ensamblaje_Completo.PNG" alt="Ensamblaje Completo 3D" width="750"/>
  <br>
  <em>Render del ensamblaje mecánico completo de la grúa torre.</em>
</div>

<br>

<div align="center">
  <img src="Media/Diagrama_de_Conexion.png" alt="Esquema Electrónico" width="750"/>
  <br>
  <em>Esquemático del circuito de potencia y control (Integración de ESP32, Drivers L298N, Raspberry Pi, Sensor, Pantalla LCD).</em>
</div>

<br>

### ⚙️ Modos de Operación Activos

**1. Almacenamiento Automatizado (Visión Artificial)** El sistema detecta e identifica los objetos en el espacio de trabajo para calcular sus coordenadas y almacenarlos de forma autónoma.

<div align="center">
  <img src="Media/Almacenamiento.gif" alt="Almacenamiento por Visión Artificial" width="750"/>
</div>

<br>

**2. Despacho (Reconocimiento de Voz)** Mediante comandos de voz en lenguaje natural, la grúa busca el material solicitado en el inventario y lo despacha dinámicamente hacia la zona de descarga.

<div align="center">
  <img src="Media/Despacho.gif" alt="Despacho por Comando de Voz" width="750"/>
</div>

<br>

> **🎬 Video Completo:** La simulación íntegra y en alta resolución de todo el proceso logístico está disponible en el repositorio. [Haz clic aquí para ver o descargar Animacion_Completa.mp4](Media/Animacion_Completa.mp4).

---

## 🚀 Arquitectura del Sistema

El proyecto implementa un modelo de computación distribuida y *Edge Computing*, segmentando las tareas críticas según la capacidad de cómputo:

```mermaid
graph TD
    User([👤 Usuario]) -->|Voz / Cámara Celular| PC[💻 PC Central - High Power Computing]
    
    subgraph "Nivel de Inteligencia y Percepción (PC)"
        PC -->|Hilos Paralelos| ML_Img[🧠 ML: Detección Objetos TensorFlow]
        PC -->|Hilos Paralelos| ML_Voice[🎙️ ML: Reconocimiento Voz Vosk]
    end

    PC -->|Comunicación Wi-Fi Sockets TCP/IP| RPi[🍓 Raspberry Pi Zero - Máster de Campo]

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

### Flujo de Trabajo Operativo

1. **Visión e Inteligencia Artificial (PC):** Procesa flujos de video y audio en hilos paralelos (*multi-threading*). Traduce las intenciones del usuario y envía comandos lógicos a la estación de campo.
2. **Coordinación de Campo (Raspberry Pi):** Gestiona el inventario, interactúa con sensores y traduce las coordenadas espaciales cartesianas a coordenadas angulares y lineales.
3. **Actuación Dedicada (ESP32):** Recibe de forma secuencial las coordenadas parametrizadas y genera los trenes de pulsos precisos para los drivers de potencia de los motores A, B, C y D.

---

## 🔌 Hardware y Esquema de Conexiones

Para asegurar la estabilidad del sistema y mitigar ruidos lógicos o caídas de tensión bruscas, todas las referencias de tierra (`GND` de la fuente de alimentación externa, placa de desarrollo ESP32, Raspberry Pi Zero, sensor óptico de proximidad y pantalla LCD) están interconectadas eléctricamente a una única masa común.

### Asignación de Pines - ESP32 (Etapa de Potencia y Drivers)

| Componente | Motor Asociado | IN1 | IN2 | IN3 | IN4 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Driver L298N (A)** | Brazo (Eje Principal) | GPIO 13 | GPIO 12 | GPIO 14 | GPIO 27 |
| **Driver L298N (B)** | Carro (Traslación) | GPIO 26 | GPIO 25 | GPIO 33 | GPIO 32 |
| **Driver L298N (C)** | Gancho (Subida/Bajada) | GPIO 16 | GPIO 17 | GPIO 5  | GPIO 18 |
| **Driver L298N (D)** | Gancho (Rotación) | GPIO 19 | GPIO 21 | GPIO 22 | GPIO 23 |

### Asignación de Pines - Raspberry Pi Zero (Periféricos e Interfaces)

| Componente | VCC (Alimentación) | GND (Tierra) | Señales de Datos / Pines |
| :--- | :---: | :---: | :--- |
| **Sensor de Proximidad** | 5V | Masa Común | OUT ➔ Pin 7 (GPIO 4) |
| **Pantalla LCD (Módulo I2C)** | 5V | Masa Común | SDA ➔ Pin 3 (GPIO 2) <br> SCL ➔ Pin 5 (GPIO 3) |

---

## 📡 Protocolos de Comunicación

La transferencia de datos e instrucciones dentro de la arquitectura distribuida se organiza en dos niveles jerárquicos independientes:

1. **Sockets TCP/IP (PC ↔ Raspberry Pi):** Comunicación inalámbrica bidireccional y asíncrona establecida a través de una red Wi-Fi local. Permite el envío seguro de comandos lógicos de misión y la actualización del estado de inventario en tiempo real.
2. **Protocolo Serial UART Custom (Raspberry Pi ↔ ESP32):** Conexión física directa cableada por hardware a través de los pines dedicados RX/TX. Para una correcta transferencia de tramas de datos sin pérdidas ni corrupción de bytes, las líneas de comunicación se conectan de manera estrictamente cruzada:
   * `PIN TX (Raspberry Pi Zero)` ➔ `PIN RX (ESP32)`
   * `PIN RX (Raspberry Pi Zero)` ➔ `PIN TX (ESP32)`
   
   *Soporte de datos:* El intérprete de comandos del firmware del ESP32 está desarrollado con soporte nativo para procesar valores decimales de alta precisión (por ejemplo, comandos de coordenadas como `A:90.45`), permitiendo un control de posición angular y lineal submilimétrico.

---

## 📐 Cinemática y Control Embebido

### Lógica Secuencial de Fases Independientes
El algoritmo de control embebido ejecuta los movimientos de los 4 actuadores paso a paso siguiendo una estricta máquina de estados con secuencias de fase independientes. Esto previene esfuerzos mecánicos innecesarios y colisiones en el entorno de almacenamiento:
* **Fase 1 (Posicionamiento de Coordenadas Espaciales):** Se calcula la cinemática y se ejecuta el movimiento en paralelo y simultáneo de los motores A (rotación de brazo), B (traslación de carro) y D (giro de gancho). El sistema bloquea cualquier otra acción hasta que estos tres actuadores hayan alcanzado su posición de destino de forma precisa.
* **Fase 2 (Manipulación y Elevación):** Una vez concluida y confirmada la Fase 1, el sistema habilita de forma aislada e independiente el movimiento del Motor C para controlar el descenso o ascenso del gancho de carga.

*Optimización Dinámica:* Con el objetivo de mejorar el rendimiento visual, la velocidad de respuesta en las demostraciones y garantizar una traslación directa, la lógica de control del firmware prescinde por completo del uso de rampas de aceleración y desaceleración en los trenes de pulsos de los motores paso a paso.

### Firmware Embebido Modular
El código fuente en C++ estructurado para el entorno del **ESP32** rompe con el esquema de script único y se organiza de forma modular y desacoplada:
* **Módulo Principal (`Main.ino`):** Administra el lazo de ejecución principal, la inicialización de periféricos y el parseo continuo del buffer del puerto serial.
* **Módulo de Configuración (`Config.cpp / .h`):** Centraliza de manera ordenada la asignación de GPIOs, constantes de paso, mapeos de hardware y variables globales.
* **Módulo de Control de Motores (`Motor.cpp / .h`):** Implementa la lógica orientada a objetos para la manipulación simultánea de los actuadores paso a paso con perfiles de velocidad independientes.

---

## ⚙️ Funcionalidades Clave

* **Procesamiento Concurrente:** Arquitectura de software basada en hilos paralelos (*multithreading*) en Python para evitar bloqueos durante la inferencia de modelos de IA.
* **Procesamiento de Lenguaje Natural (NLP Local):** Reconocimiento y traducción de comandos de voz en español ejecutado de forma local mediante la API de Vosk sin requerir conexión a internet.
* **Clasificación Inteligente:** Integración de modelos optimizados de TensorFlow Lite acoplados a OpenCV para la detección de objetos y cálculo automático de coordenadas cartesianas de almacenamiento.

---

## 🛠️ Tecnologías Utilizadas

| Capa del Proyecto | Tecnologías y Herramientas |
| :--- | :--- |
| **Visión Artificial** | Python 3.9+, OpenCV, TensorFlow Lite, Multithreading. |
| **Procesamiento de Voz** | API Vosk (Modelo en Español), Speech Recognition. |
| **Procesamiento de Campo** | Raspberry Pi OS, Sockets TCP/IP, Álgebra Matricial. |
| **Control en Tiempo Real** | C++, Framework Arduino / ESP-IDF, Arquitectura Modular. |
| **Hardware y Potencia** | Microcontrolador ESP32, Drivers L298N, Motores Paso a Paso NEMA. |
| **Diseño e Ingeniería** | SolidWorks (Modelado CAD 3D), Planos Técnicos, Parámetros DH. |

---

## 📂 Estructura del Repositorio

```bash
.
├── 📂 Datasheets/     # Hojas de datos técnicas de componentes (ESP32, NEMA, L298N, sensores).
├── 📂 Diseños/        # Archivos CAD originales, piezas 3D y elementos para manufactura.
├── 📂 Doc/            # Documentación de Ingeniería: cálculos, memoria técnica y tesis del PFC.
├── 📂 Media/          # Recursos multimedia utilizados en la documentación.
├── 📂 Planos/         # Planos constructivos mecánicos con vistas normalizadas y diagramas eléctricos.
├── 📂 Scripts/        # Scripts de software secundarios para pruebas de UART, red y calibración de motores.
├── 📂 assets/         # Archivos utilizados en el documento principal de presentación
└── 📄 README.md       # Documento principal de presentación del repositorio.
```

---

## 👤 Autores

Proyecto de fin de carrera desarrollado por los estudiantes de la Facultad de Ingeniería de la UNLZ:

<div align="center">

| **Valentín Coluccio** | **Franco Gómez** |
| :---: | :---: |
| <a href="https://github.com/ValentinColuccio"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" /></a> | <a href="https://github.com/FrancoGomez-98"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" /></a> |
| <a href="https://www.linkedin.com/in/valentin-coluccio-804301359/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" /></a> | <a href="https://www.linkedin.com/in/franco-gomez-0a71822a7/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" /></a> |

---

_Desarrollado con pasión, curiosidad y muchas pruebas y errores 🚀_

</div>
