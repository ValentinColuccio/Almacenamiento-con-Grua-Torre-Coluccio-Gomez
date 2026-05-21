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

- [🧠 Descripción General](#-descripción-general)
- [📸 Galería y Demostraciones](#-galería-y-demostraciones)
- [🚀 Arquitectura del Sistema](#-arquitectura-del-sistema)
- [🔌 Protocolos de Comunicación](#-protocolos-de-comunicación)
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
3. **Actuación:** Movimiento coordinado de precisión para la manipulación, almacenamiento y entrega de cargas.

> **Evolución Tecnológica:** La arquitectura de control de bajo nivel fue migrada y optimizada utilizando un microcontrolador **ESP32** bajo un paradigma de programación estructurada y modular. Esto garantiza una ejecución determinista de tiempo real y baja latencia para el manejo simultáneo de actuadores con velocidades independientes.

---

## 📸 Galería y Demostraciones

El proyecto cuenta con un diseño de ingeniería respaldado por modelos CAD y esquemas electrónicos detallados, los cuales se encuentran completamente disponibles en este repositorio.

<div align="center">
  <img src="Media/Ensamblaje Completo.PNG" alt="Ensamblaje Completo 3D" width="750"/>
  <br>
  <em>Render del ensamblaje mecánico completo de la grúa torre.</em>
</div>

<br>

<div align="center">
  <img src="Media/Esquematico.png" alt="Esquema Electrónico" width="750"/>
  <br>
  <em>Esquemático del circuito de potencia y control (Integración de ESP32, Drivers y Raspberry Pi).</em>
</div>

> **🎬 Demostración en Video:** Para visualizar una simulación animada de la cinemática, los rangos de movimiento y la interacción del modelo de la estructura, revise el archivo `Media/Animacion.mp4`.

---

## 🚀 Arquitectura del Sistema

El proyecto implementa un modelo de computación distribuida y *Edge Computing*, segmentando las tareas críticas según la capacidad de cómputo y determinismo requeridos:

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

### Flujo de Trabajo Operativo

1. **Visión e Inteligencia Artificial (PC):** Procesa flujos masivos de video y audio en hilos paralelos (*multi-threading*). Traduce las intenciones del usuario ("Buscar Cubo Rojo") y envía comandos lógicos a la estación de campo.
2. **Coordinación de Campo (Raspberry Pi):** Gestiona el mapa de inventario del almacén, interactúa con sensores de seguridad periféricos y traduce las coordenadas espaciales cartesianas a coordenadas angulares y lineales.
3. **Actuación Dedicada (ESP32):** Recibe de forma secuencial las coordenadas parametrizadas y genera los trenes de pulsos precisos para los drivers de potencia, aislando los lazos de control de los motores.

---

## 🔌 Protocolos de Comunicación

La robustez del sistema se fundamenta en un esquema de comunicación híbrido de dos niveles:

* **Sockets TCP/IP (PC $\leftrightarrow$ Raspberry Pi):** Comunicación inalámbrica asíncrona mediante sockets TCP sobre una red Wi-Fi local. Permite la transferencia bidireccional segura de strings serializados de comandos y confirmaciones de estado del inventario.
* **Protocolo Serial UART Custom (Raspberry Pi $\leftrightarrow$ ESP32):** Conexión física directa mediante los pines RX/TX. Se diseñó un protocolo de tramas con delimitadores específicos para empaquetar variables de movimiento (como coordenadas de grados y perfiles de velocidad para los motores A, B, C y D). Esto evita bloqueos en el microcontrolador y asegura una recepción libre de ruidos.

---

## 📐 Cinemática y Control Embebido

### Modelado Matemático
La traslación de la carga en el espacio tridimensional no responde a trayectorias arbitrarias. En el módulo de la Raspberry Pi se implementó la resolución analítica de la cinemática de la grúa:
* **Parámetros Denavit-Hartenberg (DH):** Definición de los sistemas de coordenadas locales por eslabón (base rotativa, carro de traslación y gancho de elevación).
* **Matrices de Transformación Homogénea:** Operaciones algebraicas matriciales para calcular de forma unívoca la cinemática inversa, obteniendo los pasos exactos que requiere cada motor a partir de un punto (X, Y, Z) objetivo.

### Firmware Embebido Modular
El código fuente desarrollado para el **ESP32** rompe con el paradigma convencional de archivos monolíticos extensos, adoptando una arquitectura de software limpia y desacoplada:
* **Módulo Principal (`Main.ino`):** Orquesta el ciclo de vida del microcontrolador, la escucha del puerto serial y la máquina de estados principal.
* **Módulo de Configuración (`Config.cpp` / `Config.h`):** Centraliza la definición de pines del hardware, mapeo de GPIOs, temporizaciones y constantes cinemáticas de calibración.
* **Módulo de Motores (`Motor.cpp` / `Motor.h`):** Implementa la lógica orientada a objetos para el control individualizado de los motores paso a paso NEMA. Gestiona el cálculo dinámico de rampas de aceleración y desaceleración trapezoidales, permitiendo controlar hasta 4 motores con velocidades independientes de manera suave y precisa.

---

## ⚙️ Funcionalidades Clave

* **Procesamiento Concurrente:** Uso estricto de hilos en Python en la PC central, evitando que los algoritmos de detección de TensorFlow Lite bloqueen la captura de audio o la interfaz.
* **NLP (Natural Language Processing):** Reconocimiento e interpretación local de comandos verbales en español (utilizando Vosk), facilitando una interfaz hombre-máquina intuitiva.
* **Manipulación de Precisión:** Control milimétrico del posicionamiento espacial de la carga gracias al acople matemático de la cinemática y la resolución de pasos de los motores NEMA.
* **Seguridad Industrial:** Integración en tiempo real de sensores de proximidad y optoacopladores para frenado de emergencia y calibración de punto cero (Homing).

---

## 🛠️ Tecnologías Utilizadas

| Capa del Proyecto | Tecnologías y Herramientas |
| :--- | :--- |
| **Visión Artificial** | Python 3.9+, OpenCV, TensorFlow Lite (Modelos `.h5` / `.tflite`), Multithreading. |
| **Procesamiento de Voz** | API Vosk (Modelo en Español), Speech Recognition. |
| **Procesamiento de Campo** | Raspberry Pi OS, Sockets TCP/IP, Álgebra Matricial Vectorial. |
| **Control en Tiempo Real** | C++, Framework Arduino / ESP-IDF, Estructura Modular de Clases. |
| **Hardware y Potencia** | Microcontrolador ESP32, Drivers L298N, Motores Paso a Paso NEMA, Optoacopladores. |
| **Diseño e Ingeniería** | Esquemas Eléctricos, CAD / Modelado 3D, Parámetros DH. |

---

## 📂 Estructura del Repositorio

La disposición de los directorios refleja fielmente la organización multidisciplinaria del proyecto (Mecánica, Electrónica y Software):

```bash
.
├── 📂 Datasheets/     # Hojas de datos técnicas de componentes.
├── 📂 Diseños/        # Archivos CAD originales, piezas 3D.
├── 📂 Doc/            # Documentación.
├── 📂 Media/          # Recursos multimedia.
├── 📂 Planos/         # Planos constructivos.
├── 📂 Scripts/        # Scripts de software.
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

_Desarrollado con rigor ingenieril, enfoque modular y pasión por la robótica aplicada 🚀_

</div>
