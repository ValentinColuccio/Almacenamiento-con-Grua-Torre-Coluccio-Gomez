# Justificación del subsistema de visión artificial

**Proyecto Final de Carrera — Ingeniería en Mecatrónica — FI UNLZ**
Grúa Torre Robótica Inteligente

---

## 1. Función del subsistema

El subsistema de visión cumple una única función dentro del ciclo operativo:
determinar **qué pieza** ha sido depositada en la estación de entrada. Las
clases reconocidas son caja, bidón uno, bidón dos y carrete, además del estado
de estación vacía.

La pieza se coloca siempre en la misma posición y orientación dentro de la
estación de entrada. El subsistema, por lo tanto, no realiza medición de
posición ni cálculo de coordenadas: su salida es la clase de la pieza. La
posición de almacenamiento se resuelve luego por asignación lógica en la
estación de campo, que mantiene un registro de ocupación con dos posiciones
disponibles por tipo de pieza y devuelve la primera libre.

Se trata, en consecuencia, de un problema de **clasificación sobre un conjunto
cerrado de piezas conocidas, en una estación fija y con condiciones de escena
controlables**.

---

## 2. Implementación inicial

La primera versión resolvía la clasificación con un modelo de red neuronal
reentrenado sobre un conjunto de imágenes propio, ejecutado mediante TensorFlow
Lite y OpenCV en la estación de operación. La imagen se adquiría con la cámara
de un teléfono celular.

Esta implementación cumplía la función requerida, pero presentaba tres
limitaciones de fondo:

**Cadena de adquisición no controlada.** El teléfono aplica de forma automática
y no desactivable el ajuste de exposición, el enfoque y el balance de blancos.
La imagen entregada al clasificador variaba según la hora del día y la
iluminación del ambiente. El modelo debía absorber una variabilidad introducida
por el propio instrumento de medición, ajena al problema a resolver.

**Montaje no repetible.** Sin una fijación mecánica normalizada, la distancia y
el ángulo de trabajo no eran reproducibles entre ensayos, lo que agregaba una
fuente de variación independiente de la iluminación.

**Costo de mantenimiento del modelo.** Incorporar una pieza nueva al catálogo
requería ampliar el conjunto de imágenes, reentrenar el modelo y volver a
desplegarlo. Es una tarea que exige conocimiento específico de aprendizaje
automático y que, en un entorno productivo real, no puede resolver el personal
de mantenimiento.

---

## 3. Solución adoptada

Se reemplaza la cámara de teléfono y el modelo propio por un sensor de visión
industrial **SensoPart VISOR Object AI**, que incorpora un detector de
clasificación por aprendizaje ejecutado en el propio dispositivo.

El sensor se entrena presentándole imágenes de muestra de cada clase desde el
software de configuración del fabricante. El algoritmo se ejecuta de forma
embebida, sin requerir conexión a red externa ni servicios en la nube. El
resultado se entrega como telegrama por interfaz Ethernet TCP/IP.

---

## 4. Fundamento de la decisión

Corresponde aclarar en primer término qué **no** cambió. Ambas implementaciones
resuelven la clasificación mediante aprendizaje automático: no se reemplazó
inteligencia artificial por procesamiento clásico de imagen. Lo que se modificó
es la **plataforma de ejecución y la cadena de adquisición**, migrando desde un
montaje de prototipo hacia un componente industrial calificado.

**Control de la escena en el origen.** El sensor integra iluminación propia,
óptica y tiempo de exposición fijos, y montaje mecánico normalizado. Este es el
argumento central de la decisión: dado que la pose de la pieza es fija y la
escena es controlable, el margen de mejora del subsistema no estaba en el
modelo sino en la calidad y la repetibilidad de la imagen de entrada. Al fijar
las condiciones de adquisición, la variabilidad de iluminación deja de existir
como perturbación en lugar de tener que ser compensada por el clasificador.

**Reducción del costo de alta de piezas.** El detector se entrena con unas pocas
imágenes de muestra por clase desde la herramienta de configuración, sin
escribir código. La incorporación de una pieza nueva pasa de ser una tarea de
ingeniería de software a una tarea de configuración, ejecutable por personal
técnico sin formación en aprendizaje automático.

**Descarga de cómputo en la estación de operación.** La estación de operación
deja de ejecutar la inferencia del modelo de visión. Esto libera el proceso que
competía por recursos con el reconocimiento de voz y con la interfaz gráfica,
ejecutados de forma concurrente en el mismo equipo.

**Componente instalable en planta.** El sensor cuenta con grado de protección
industrial, montaje normalizado y soporte para protocolos de comunicación de
campo además de Ethernet TCP/IP. Esto hace que el subsistema sea trasladable a
una arquitectura de automatización real con controlador lógico programable,
condición que un teléfono celular no puede satisfacer.

**Disponibilidad del equipamiento.** El sensor fue facilitado sin cargo para el
desarrollo del proyecto, lo que permitió incorporar un componente de catálogo
industrial sin impacto sobre el presupuesto.

---

## 5. Integración en la arquitectura del sistema

El sensor se comunica con la **estación de operación**, y no directamente con la
estación de campo. La razón es de interfaz física: el sensor entrega su
resultado por Ethernet, y la Raspberry Pi Zero no dispone de interfaz Ethernet.
La estación de operación, que ya se encuentra en la misma red, actúa como nodo
de integración.

Esto es consistente con el rol que dicha estación cumple en el sistema, que no
es el de un nodo de cómputo dedicado a la visión sino el de puesto de
supervisión y operación: aloja la interfaz hombre-máquina, ejecuta el
reconocimiento de voz, concentra las comunicaciones con la estación de campo y
registra el intercambio de mensajes entre todos los nodos.

El sensor opera **por disparo bajo demanda**, no en adquisición continua. La
secuencia es la siguiente:

1. Un sensor infrarrojo en la estación de entrada detecta la presencia de una
   pieza. La estación de campo lo gestiona por detección de flanco con
   antirrebote y tiempo de inhibición, y notifica el evento a la estación de
   operación.
2. La estación de operación envía el comando de disparo al sensor de visión.
3. El sensor clasifica y devuelve la clase identificada por telegrama TCP/IP.
4. La estación de operación traduce la clase en una orden de misión y la remite
   a la estación de campo, que asigna la posición libre y ejecuta el ciclo de
   almacenamiento.

La imagen en vivo del sensor se visualiza en la pestaña de supervisión de la
interfaz hombre-máquina, junto con el registro de eventos de todos los nodos.

La arquitectura resultante responde a una estructura jerárquica de automatización
de tres niveles: actuación en tiempo real, control de campo, y supervisión y
operación. El sensor de visión se incorpora como dispositivo inteligente de
campo cuyo resultado ingresa al sistema por el nivel de supervisión.

---

## 6. Alcance del trabajo propio en el subsistema

- Definición del requerimiento funcional y de las condiciones de operación de la
  estación de entrada.
- Desarrollo de la implementación inicial con modelo propio, que aportó el
  criterio técnico necesario para especificar, configurar y poner a punto
  correctamente el sensor finalmente adoptado.
- Construcción del conjunto de imágenes de entrenamiento y puesta a punto del
  detector de clasificación.
- Diseño del montaje y de las condiciones de iluminación de la estación de
  entrada.
- Implementación del enlace por sockets con el sensor: comando de disparo,
  recepción y validación del telegrama de resultado, y reconexión automática
  ante caída del enlace.
- Integración del resultado con la lógica de misión y con el registro de
  ocupación del almacén.
- Visualización del estado y de la imagen del sensor en la interfaz
  hombre-máquina.
