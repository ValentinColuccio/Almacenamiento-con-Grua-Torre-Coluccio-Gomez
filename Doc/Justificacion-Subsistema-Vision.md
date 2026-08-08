# Justificación del subsistema de visión artificial

**Proyecto Final de Carrera — Ingeniería en Mecatrónica — FI UNLZ**
Grúa Torre Robótica Inteligente

---

## 1. Función del subsistema

El subsistema de visión cumple una única función dentro del ciclo operativo: determinar **qué pieza** ha sido depositada en la estación de entrada.

La pieza se coloca siempre en la misma posición y orientación dentro de dicha estación. El subsistema, por lo tanto, no realiza medición de posición ni cálculo de coordenadas: su salida es la clase de la pieza. La posición de almacenamiento se obtiene luego por asignación lógica en la Raspberry Pi Zero, a partir de esa clase y del estado del inventario.

Se trata de un problema de **clasificación sobre un conjunto cerrado de piezas conocidas, en una estación fija y con condiciones de escena controlables**.

---

## 2. Implementación inicial

La primera versión del subsistema resolvía la clasificación con un modelo de red neuronal reentrenado sobre un conjunto de imágenes propio, ejecutado mediante TensorFlow Lite y OpenCV en la PC del sistema. La imagen se adquiría con la cámara de un teléfono celular.

Esta implementación cumplía la función requerida, pero presentaba tres limitaciones de fondo:

**Cadena de adquisición no controlada.** El teléfono aplica de forma automática y no desactivable el ajuste de exposición, el enfoque y el balance de blancos. La imagen entregada al clasificador variaba según la hora del día y la iluminación del ambiente. El modelo debía absorber esa variabilidad, que es una exigencia adicional impuesta por el instrumento de medición y no por el problema a resolver.

**Montaje no repetible.** Sin una fijación mecánica normalizada, la distancia y el ángulo de trabajo no eran reproducibles entre ensayos, lo que introducía una fuente de variación independiente de la iluminación.

**Costo de mantenimiento del modelo.** Incorporar una pieza nueva al catálogo requería ampliar el conjunto de imágenes, reentrenar el modelo y volver a desplegarlo. Es una tarea que exige conocimiento específico de aprendizaje automático y que, en un entorno productivo real, no puede resolver el personal de mantenimiento.

---

## 3. Solución adoptada

Se reemplaza la cámara de teléfono y el modelo propio por un sensor de visión industrial **SensoPart VISOR Object AI**, que incorpora un detector de clasificación por aprendizaje ejecutado en el propio dispositivo.

El sensor se entrena presentándole imágenes de muestra de cada clase de pieza desde el software de configuración del fabricante. El algoritmo de clasificación se ejecuta de forma embebida en el sensor, sin requerir conexión a red externa ni servicios en la nube. El resultado se entrega como telegrama por interfaz Ethernet TCP/IP.

---

## 4. Fundamento de la decisión

Corresponde aclarar en primer término qué **no** cambió. Ambas implementaciones resuelven la clasificación mediante aprendizaje automático: no se reemplazó inteligencia artificial por procesamiento clásico de imagen. Lo que se modificó es la **plataforma de ejecución y la cadena de adquisición**, migrando desde un montaje de prototipo hacia un componente industrial calificado.

La decisión se fundamenta en los siguientes puntos:

**Control de la escena en el origen.** El sensor integra iluminación propia, óptica y tiempo de exposición fijos, y montaje mecánico normalizado. Al fijar las condiciones de adquisición, la variabilidad de iluminación deja de existir como perturbación en lugar de tener que ser compensada por el clasificador. Este es el argumento central: dado que la pose de la pieza es fija y la escena es controlable, el margen de mejora del subsistema no estaba en el modelo sino en la calidad y la repetibilidad de la imagen de entrada.

**Reducción del costo de alta de piezas.** El detector de clasificación se entrena con unas pocas imágenes de muestra por clase desde la herramienta de configuración del fabricante, sin escribir código. La incorporación de una pieza nueva pasa de ser una tarea de ingeniería de software a una tarea de configuración, ejecutable por personal técnico sin formación en aprendizaje automático.

**Descarga de cómputo de la estación de operación.** La PC deja de ejecutar la inferencia del modelo de visión. Esto libera el hilo de procesamiento que competía por recursos con el reconocimiento de voz, ejecutado también en la PC de forma concurrente.

**Componente instalable en planta.** El sensor cuenta con grado de protección industrial, montaje normalizado y soporte para protocolos de comunicación de campo además de Ethernet TCP/IP. Esto hace que el subsistema sea trasladable a una arquitectura de automatización real con controlador lógico programable, condición que un teléfono celular no puede satisfacer.

**Disponibilidad del equipamiento.** El sensor fue facilitado sin cargo para el desarrollo del proyecto, lo que permitió incorporar un componente de catálogo industrial sin impacto sobre el presupuesto.

---

## 5. Integración en la arquitectura del sistema

El sensor se comunica con la PC del sistema, y no directamente con la Raspberry Pi Zero. La razón es de interfaz física: el VISOR entrega su resultado por Ethernet, y la Raspberry Pi Zero no dispone de interfaz Ethernet. La PC, que ya se encuentra en la misma red que la Raspberry Pi, actúa como nodo de integración.

Esto es consistente con el rol que la PC cumple en el sistema, que no es el de un nodo de cómputo dedicado a la visión sino el de **estación de operación**:

- Aloja la interfaz hombre-máquina (HMI) desde la cual el operador supervisa y comanda el sistema.
- Aloja la base de datos de inventario.
- Ejecuta el reconocimiento de voz.
- Concentra las comunicaciones con la Raspberry Pi Zero y registra el intercambio de mensajes.

En consecuencia, la arquitectura resultante responde a una estructura jerárquica de automatización de tres niveles: actuación en tiempo real (ESP32), control de campo (Raspberry Pi Zero) y supervisión y operación (PC). El sensor de visión se incorpora como dispositivo inteligente de campo cuyo resultado ingresa al sistema por el nivel de supervisión.

---

## 6. Alcance del trabajo propio en el subsistema

El aporte de ingeniería del equipo en este subsistema comprende:

- La definición del requerimiento funcional y de las condiciones de operación de la estación de entrada.
- El desarrollo de la implementación inicial con modelo propio, que aportó el criterio técnico necesario para especificar, configurar y poner a punto correctamente el sensor finalmente adoptado.
- La construcción del conjunto de imágenes de entrenamiento y la puesta a punto del detector de clasificación.
- El diseño del montaje mecánico y de las condiciones de iluminación de la estación de entrada.
- La integración del telegrama de resultado con la lógica de misión y con la base de datos de inventario.
- La visualización del estado del subsistema en la interfaz hombre-máquina.
