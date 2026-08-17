# Cálculos de diseño

Verificación eléctrica y mecánica del prototipo.

---

## 1. Datos de partida

### Actuadores

Motor paso a paso bipolar **JK42HS48-1684-08AF** (NEMA 17), cuatro unidades:

| Parámetro | Símbolo | Valor |
|---|---|---|
| Tensión nominal | V_n | 2,8 V |
| Corriente por fase | I_f | 1,68 A |
| Resistencia por fase | R_f | 1,65 Ω |
| Inductancia por fase | L_f | 2,8 mH |
| Par de retención | T_h | 5,0 kg·cm = 0,49 N·m |
| Par de detención | T_d | 260 g·cm = 0,0255 N·m |
| Inercia del rotor | J_r | 68 g·cm² = 6,8×10⁻⁶ kg·m² |
| Configuración | — | Bipolar, 4 hilos |

> **Nota:** los ejes C y D montan motores NEMA 17 *pancake*, de menor par y menor
> corriente nominal (típicamente 1,0 A y 0,15 N·m). El cálculo eléctrico se
> realiza con los datos del motor de mayor consumo para los cuatro ejes, de modo
> que los resultados constituyen una **cota superior conservadora**.

### Etapa de potencia

- Drivers **A4988**, uno por eje, en micropaso **1/16** con ambas fases excitadas.
- Fuente conmutada **24 V / 15 A** (360 W), dedicada exclusivamente a motores.
- ESP32 y Raspberry Pi Zero con fuentes independientes.

### Cinemática de los ejes

| Eje | Función | Transmisión | Radio efectivo |
|---|---|---|---|
| A | Giro del brazo | Engranajes, relación 1:2 | — |
| B | Traslación del carro | Polea Ø20 mm | 10 mm |
| C | Izaje del gancho | Polea Ø20 mm | 10 mm |
| D | Rotación del gancho | Directa | — |

### Geometría

| Magnitud | Valor |
|---|---|
| Altura hasta la pluma | 320 mm |
| Altura máxima de la estructura | 450 mm |
| Longitud de la pluma, del eje a la punta | 450 mm |
| Longitud de la contrapluma | 200 mm |
| Radio mínimo del carro | 75 mm |
| Radio máximo del carro | 200 mm |
| Carrera vertical útil | 100 mm |

---

## 2. Cálculos eléctricos

### 2.1 Consumo por motor

En micropaso, el driver regula las corrientes de fase según

$$i_A = I_f \cos\theta \qquad i_B = I_f \sin\theta$$

de modo que el **módulo del vector de corriente permanece constante** e igual a
I_f, independientemente de la posición dentro del ciclo eléctrico. La pérdida en
el cobre resulta entonces constante:

$$P_{Cu} = R_f \left( i_A^2 + i_B^2 \right) = R_f \, I_f^2$$

$$P_{Cu} = 1{,}65 \times 1{,}68^2 = 4{,}66 \ \mathrm{W} \ \text{por motor}$$

Este valor **no depende de si el motor gira o está detenido manteniendo
posición**: es la característica distintiva del motor paso a paso y la razón por
la que el consumo en reposo coincide con el consumo en régimen.

La potencia mecánica entregada es despreciable frente a este valor. Para el eje
de izaje, con 0,13 kg elevados a 20 mm/s:

$$P_{mec} = m \, g \, v = 0{,}13 \times 9{,}81 \times 0{,}02 = 0{,}026 \ \mathrm{W}$$

es decir, el **0,6 %** de la pérdida en el cobre.

### 2.2 Disipación en los drivers

El A4988 presenta una resistencia de conducción total, sumando rama alta y rama
baja, de aproximadamente 0,64 Ω. Aplicando el mismo razonamiento vectorial:

$$P_{drv} = R_{DS(on)} \, I_f^2 = 0{,}64 \times 1{,}68^2 = 1{,}81 \ \mathrm{W} \ \text{por driver}$$

### 2.3 Balance de potencia y dimensionamiento de la fuente

Los cuatro motores permanecen excitados de forma permanente, por lo que el
consumo es constante y no depende de cuántos ejes se muevan simultáneamente:

| Concepto | Cantidad | Potencia |
|---|---|---|
| Pérdida en cobre de motores | 4 | 18,64 W |
| Disipación en drivers | 4 | 7,24 W |
| Consumo lógico de los drivers (VDD) | 4 | 0,07 W |
| Potencia mecánica útil | — | ≈ 0,03 W |
| **Total** | | **≈ 26 W** |

Corriente demandada a la fuente de 24 V:

$$I_{24V} = \frac{26}{24} \approx 1{,}08 \ \mathrm{A}$$

Agregando un 20 % por pérdidas en el hierro, conmutación y transitorios de
arranque:

$$I_{dise\tilde{n}o} \approx 1{,}3 \ \mathrm{A} \qquad P_{dise\tilde{n}o} \approx 31 \ \mathrm{W}$$

**Verificación:** la fuente instalada entrega 15 A. El factor de utilización es
del **8,7 %**, con un margen superior a once veces la demanda. La fuente está
sobredimensionada respecto del requerimiento estricto; una unidad de 24 V / 3 A
cubriría el consumo con más del doble de margen. La selección se justifica por
disponibilidad y por reserva de capacidad ante ampliaciones, no por necesidad de
corriente.

### 2.4 Ajuste de corriente de los drivers

La corriente de recorte del A4988 se fija mediante el potenciómetro de
referencia:

$$I_{max} = \frac{V_{ref}}{8 \, R_S}$$

Para las placas con resistencia de sensado de 0,1 Ω:

| Corriente deseada | V_ref |
|---|---|
| 1,68 A (nominal del motor) | 1,344 V |
| 1,20 A (recomendada) | 0,960 V |

**Se recomienda limitar la corriente a 1,2 A.** Los cálculos mecánicos de la
sección 4 muestran márgenes de par superiores a treinta veces en todos los ejes,
de modo que la reducción no compromete el funcionamiento. El beneficio térmico es
sustancial:

| | A 1,68 A | A 1,20 A | Reducción |
|---|---|---|---|
| Pérdida en cobre (4 motores) | 18,64 W | 9,50 W | −49 % |
| Disipación en drivers (4) | 7,24 W | 3,69 W | −49 % |
| Corriente de fuente | 1,08 A | 0,55 A | −49 % |

A 1,68 A cada A4988 disipa 1,81 W, valor que exige disipador y ventilación
forzada. A 1,20 A la disipación baja a 0,92 W, dentro de lo que la placa maneja
con disipador adhesivo y convección natural.

### 2.5 Desacoplamiento

El A4988 requiere un condensador electrolítico de 47 a 100 µF conectado entre
VMOT y GND, físicamente próximo a cada driver, para absorber los picos de
corriente de conmutación. Sin él, los transitorios sobre la línea de 24 V pueden
superar la tensión máxima del integrado. Se complementa con un cerámico de
100 nF en paralelo.

---

## 3. Verificación de pines

### 3.1 ESP32

| Pin | Destino | Corriente |
|---|---|---|
| GPIO 13, 14 | Driver A (STEP, DIR) | ≤ 10 µA c/u |
| GPIO 27, 26 | Driver B (STEP, DIR) | ≤ 10 µA c/u |
| GPIO 25, 33 | Driver C (STEP, DIR) | ≤ 10 µA c/u |
| GPIO 32, 4 | Driver D (STEP, DIR) | ≤ 10 µA c/u |
| TX, RX | Enlace UART con Raspberry | despreciable |

Las entradas del A4988 son de tipo CMOS con corriente de fuga máxima de 10 µA.
El consumo total de los ocho pines de control es de **80 µA**, frente a los
12 mA nominales por pin del ESP32: un **0,07 %** del límite.

Componente dinámica por carga capacitiva de entrada, a la frecuencia máxima de
pulsos:

$$I_{din} = C_{in} \, V \, f = 10 \times 10^{-12} \times 3{,}3 \times 3200 = 0{,}1 \ \mu\mathrm{A}$$

También despreciable. **Los pines de control no representan una condición
crítica.**

**Alimentación lógica de los drivers:** el pin de 3,3 V del ESP32 alimenta los
cuatro VDD, con 5 mA típicos cada uno:

$$I_{VDD} = 4 \times 5 = 20 \ \mathrm{mA}$$

El regulador de la placa de desarrollo entrega 800 mA, de los cuales el propio
módulo ESP32 consume hasta 250 mA con la radio desactivada. El margen es amplio.

**Frecuencia de pulsos:** en micropaso 1/16, una vuelta completa requiere
3200 pulsos. Para 1 rev/s el tren es de 3,2 kHz, con período de 312 µs. El tiempo
de establecimiento de corriente en la fase es

$$t_r = \frac{L_f \, I_f}{V_{alim}} = \frac{2{,}8 \times 10^{-3} \times 1{,}68}{24} = 196 \ \mu\mathrm{s}$$

menor que el período disponible, por lo que la corriente alcanza su valor de
consigna en cada micropaso. La relación entre la tensión de alimentación y la
tensión nominal del motor, 24 / 2,8 = 8,6, es la que hace posible ese tiempo de
subida.

### 3.2 Raspberry Pi Zero

Límites del dispositivo: 16 mA por pin, 50 mA en la suma de todos los GPIO,
50 mA en el riel de 3,3 V.

El display y el sensor **se alimentan desde los pines de salida de 5 V de la
Raspberry, no desde los GPIO.** Sobre los GPIO solo circulan las corrientes de
señal.

| Pin | Función | Corriente |
|---|---|---|
| TX, RX | Enlace UART con ESP32 | despreciable |
| GPIO 2 (SDA), GPIO 3 (SCL) | Señal I2C hacia el display | 1,06 mA c/u |
| GPIO 4 | Entrada de la salida del sensor IR | ≈ 0 |
| Salida 5 V | Alimentación del display y del sensor | 45 mA |

Las líneas I2C están cargadas por las resistencias de pull-up del módulo
PCF8574, típicamente de 4,7 kΩ. Cuando la Raspberry impone nivel bajo:

$$I_{sink} = \frac{5}{4700} = 1{,}06 \ \mathrm{mA} \ \text{por línea}$$

El total sobre GPIO es de **2,1 mA**, un 4 % del límite agregado de 50 mA. Sin
observaciones por corriente.

El riel de 3,3 V no alimenta ninguna carga externa, de modo que su límite de
50 mA no está comprometido.

Sobre la salida de 5 V: display 16×2 con retroiluminación, 25 mA; sensor
infrarrojo con LED emisor, 20 mA. El total de 45 mA se suma a los
aproximadamente 150 mA de la propia Raspberry Pi Zero. Una fuente de 5 V / 1 A
resulta suficiente; se adopta 5 V / 2 A por margen de arranque.

### 3.3 Observación crítica: compatibilidad de niveles lógicos

Los GPIO de la Raspberry Pi operan a 3,3 V y **no toleran 5 V**: no incorporan
diodos de protección hacia el riel de alimentación, por lo que la tensión máxima
admisible en una entrada es de aproximadamente 3,3 V. Dos señales del diseño
actual la superan, como consecuencia de que ambos periféricos se alimentan a
5 V.

**a) Salida del sensor infrarrojo.** El módulo entrega su salida digital a nivel
de su alimentación, es decir, 5 V sobre GPIO 4.

*Corrección:* divisor resistivo de 10 kΩ y 15 kΩ.

$$V_{out} = 5 \times \frac{15}{10 + 15} = 3{,}0 \ \mathrm{V}$$

La corriente por el divisor es de 5 / 25 kΩ = 0,2 mA. El nivel de 3,0 V supera
holgadamente el umbral de entrada alta de la Raspberry, de 1,8 V.

**b) Líneas I2C del display.** El módulo PCF8574 alimentado a 5 V mantiene SDA y
SCL en reposo a 5 V a través de sus resistencias de pull-up.

*Correcciones posibles, en orden de preferencia:*

1. Alimentar el módulo I2C a 3,3 V. Es la solución más simple, ya que el PCF8574
   opera desde 2,5 V. Contrapartida: la retroiluminación pierde brillo y el
   contraste requiere reajuste.
2. Intercalar un adaptador de niveles bidireccional, tipo BSS138, que preserva el
   brillo pleno del display.
3. Retirar las resistencias de pull-up del módulo y alimentar únicamente su
   circuito lógico a 3,3 V, dejando la retroiluminación a 5 V.

El circuito puede estar operando correctamente pese a la sobretensión, ya que es
una condición frecuente que no siempre produce falla inmediata, pero constituye
una operación fuera de especificación que degrada el dispositivo y debe
corregirse o, como mínimo, quedar documentada como desviación conocida.

---

## 4. Cálculos mecánicos

### 4.1 Distribución de masas

La disposición constructiva concentra tres de los cuatro motores sobre la
contrapluma, junto con un contrapeso. El cuarto motor, correspondiente al eje D,
va montado sobre el conjunto que desciende con el gancho.

| Elemento | Masa [kg] | Posición x respecto del eje de giro [m] |
|---|---|---|
| Torre, base y corona de giro | 1,60 | 0 |
| Pluma, tramo delantero (0,45 m) | 0,242 | +0,225 |
| Contrapluma, tramo trasero (0,20 m) | 0,108 | −0,100 |
| Motores A, B y C | 0,96 | −0,120 |
| Contrapeso | 0,40 | −0,180 |
| Carro | 0,15 | +R |
| Gancho más motor D | 0,23 | +R |
| **Masa total en vacío** | **3,69** | |

El signo positivo corresponde al lado de trabajo y el negativo al lado de la
contrapluma. La masa de la pluma se obtiene suponiendo densidad lineal uniforme
de 0,538 kg/m sobre los 0,65 m totales, con el centro de gravedad de cada tramo
en su punto medio.

Restantes hipótesis de cálculo:

| Magnitud | Símbolo | Valor |
|---|---|---|
| Masa de la pieza más pesada | m_q | 0,10 kg |
| Semiancho de la base | a | 0,10 m |
| Coeficiente de rozamiento en guías | μ | 0,30 |
| Coeficiente de seguridad al vuelco | n_v | 1,5 |

El coeficiente de rozamiento es el habitual para PLA sobre PLA sin lubricación, y
el coeficiente de seguridad al vuelco es el que se adopta usualmente en el
análisis estático de grúas.

### 4.2 Equilibrio del conjunto giratorio

Antes de analizar la estabilidad de la máquina completa corresponde verificar el
equilibrio de la parte que gira, tomando momentos respecto del eje de giro. Este
balance determina la solicitación sobre la corona y sobre el engranaje del eje A.

Momento del lado de la contrapluma:

$$M_{cp} = \left( 0{,}108 \times 0{,}100 + 0{,}96 \times 0{,}120 + 0{,}40 \times 0{,}180 \right) g = 1{,}942 \ \mathrm{N \cdot m}$$

Momento del lado de trabajo, con el carro en su radio máximo de 0,20 m y sin
carga:

$$M_{tr} = \left( 0{,}242 \times 0{,}225 + 0{,}38 \times 0{,}200 \right) g = 1{,}280 \ \mathrm{N \cdot m}$$

En vacío el conjunto queda desequilibrado hacia la contrapluma en 0,662 N·m. La
carga que produciría el equilibrio exacto en ese radio es

$$Q_{eq} = \frac{0{,}662}{g \times 0{,}200} = 0{,}337 \ \mathrm{kg}$$

es decir, algo más de tres veces la carga nominal de trabajo. **La grúa opera
siempre con predominio del lado de la contrapluma**, condición favorable para la
estabilidad y coherente con el criterio de diseño de las grúas torre reales,
donde el contrapeso se dimensiona para equilibrar aproximadamente un tercio de la
carga nominal.

### 4.3 Carga admisible en función del radio

El comportamiento característico de una grúa torre es que **su capacidad no es un
valor único, sino una función decreciente de la distancia al eje de giro.** El
límite lo impone el momento de vuelco, que es constante, mientras que el brazo de
palanca de la carga crece linealmente con el radio.

Se toman momentos respecto de la arista de vuelco, ubicada a la distancia a del
eje sobre el lado de trabajo. El brazo de palanca de cada masa es la distancia
horizontal que la separa de esa arista.

Momento estabilizador, aportado por las masas situadas del lado de la
contrapluma más el peso propio de la torre:

$$M_{est} = \left( 1{,}60 \times 0{,}100 + 0{,}108 \times 0{,}200 + 0{,}96 \times 0{,}220 + 0{,}40 \times 0{,}280 \right) g = 4{,}952 \ \mathrm{N \cdot m}$$

Momento volcador del tramo delantero de la pluma, cuyo centro de gravedad queda
0,125 m por delante de la arista:

$$M_{pl} = 0{,}242 \times 9{,}81 \times 0{,}125 = 0{,}297 \ \mathrm{N \cdot m}$$

La condición de estabilidad exige que el momento estabilizador, afectado por el
coeficiente de seguridad, supere a la suma de los momentos volcadores:

$$\frac{M_{est}}{n_v} \geq M_{pl} + \left( m_{mov} + Q \right) g \left( R - a \right)$$

donde m_mov es la masa del conjunto móvil, igual a 0,38 kg entre carro, gancho y
motor D. Despejando se obtiene la **ecuación de carga admisible**:

$$Q(R) = \frac{M_{est} / n_v - M_{pl}}{g \left( R - a \right)} - m_{mov}$$

$$Q(R) = \frac{0{,}3062}{R - 0{,}100} - 0{,}38$$

Es una hipérbola desplazada: la carga admisible decae de forma inversamente
proporcional a la distancia entre la carga y la arista de vuelco.

| Radio R [m] | Carga admisible Q [kg] | Coef. de seguridad con 0,10 kg |
|---|---|---|
| 0,150 | 5,74 | 57 |
| 0,200 (radio máximo del carro) | 2,68 | 27 |
| 0,250 | 1,66 | 17 |
| 0,300 | 1,15 | 12 |
| 0,350 | 0,85 | 8,5 |
| 0,400 | 0,64 | 6,4 |
| 0,450 (punta de la pluma) | 0,50 | 5,0 |

Para radios inferiores al semiancho de la base la carga queda del lado interior
de la arista de vuelco y no puede producir volcamiento, por lo que la expresión
deja de tener sentido físico y la capacidad pasa a estar limitada por otros
factores.

El carro opera entre 0,075 y 0,200 m, de modo que **la condición más desfavorable
del ciclo de trabajo real es el radio de 0,200 m**, con capacidad de 2,68 kg y un
margen de veintisiete veces sobre la carga efectiva. Aun extrapolando hasta la
punta de la pluma el margen se mantiene en cinco veces.

El aporte de los tres motores y del contrapeso sobre la contrapluma resulta
decisivo: por sí solos suman 3,17 N·m de los 4,95 N·m del momento estabilizador,
es decir, casi dos tercios del total. **Sin ese lastre la capacidad en el radio
máximo del carro caería aproximadamente a una cuarta parte.**

### 4.4 Verificación por flexión de la pluma

Corresponde comprobar que la estabilidad sea efectivamente el factor limitante y
no la resistencia del material. Suponiendo para la pluma una sección rectangular
hueca de 20 mm de ancho por 25 mm de alto con 3 mm de pared:

$$I = \frac{20 \times 25^3 - 14 \times 19^3}{12} = 18039 \ \mathrm{mm^4} \qquad W = \frac{I}{c} = 1443 \ \mathrm{mm^3}$$

Adoptando para el PLA impreso una tensión admisible de 10 MPa, resultante de
afectar la tensión de rotura por un coeficiente de seguridad de 5 que contempla
la anisotropía propia de la impresión por capas:

$$M_{adm} = \sigma_{adm} \, W = 10 \times 1443 = 14{,}4 \ \mathrm{N \cdot m}$$

El momento flector en el empotramiento, con la carga en la punta de la pluma,
es

$$M_f = \left( Q + 0{,}38 \right) g \times 0{,}45 + 0{,}534$$

Igualando al momento admisible se obtiene una carga límite por flexión de
2,76 kg en la punta, frente a los 0,50 kg que admite el criterio de vuelco.
**La estabilidad gobierna el diseño con un factor de 5,5 sobre la resistencia
del material.**

### 4.5 Par requerido en cada eje

**Eje C — Izaje.** Eleva el conjunto del gancho, que incluye el motor D, más la
carga. Transmisión directa sobre polea de radio 0,010 m:

$$T_C = \left( m_q + m_{gancho+D} \right) g \, r = 0{,}33 \times 9{,}81 \times 0{,}010 = 0{,}0324 \ \mathrm{N \cdot m}$$

**Eje B — Traslación del carro.** Movimiento horizontal: solo debe vencerse el
rozamiento.

$$T_B = \mu \left( m_{mov} + m_q \right) g \, r = 0{,}30 \times 0{,}48 \times 9{,}81 \times 0{,}010 = 0{,}0141 \ \mathrm{N \cdot m}$$

**Eje A — Giro del brazo.** Eje vertical: la gravedad no genera par resistente y
el requerimiento proviene de la inercia. El momento de inercia respecto del eje
de giro incorpora todas las masas del conjunto giratorio, con los tramos de pluma
modelados como barras empotradas en el eje:

$$J = \tfrac{1}{3} m_{pl} L_{pl}^2 + \tfrac{1}{3} m_{cp} L_{cp}^2 + \left( m_{mov} + m_q \right) R^2 + m_{mot} x_{mot}^2 + m_{cpeso} x_{cpeso}^2$$

$$J = 0{,}0163 + 0{,}0014 + 0{,}0192 + 0{,}0138 + 0{,}0130 = 0{,}0637 \ \mathrm{kg \cdot m^2}$$

Con una aceleración angular de 1 rad/s² y relación de transmisión 1:2:

$$T_A = \frac{J \, \alpha}{i} = \frac{0{,}0637 \times 1}{2} = 0{,}0319 \ \mathrm{N \cdot m}$$

**Resumen frente al par disponible:**

| Eje | Par requerido [N·m] | Par de retención [N·m] | Coef. de seguridad |
|---|---|---|---|
| A (giro) | 0,0319 | 0,49 | 15 |
| B (carro) | 0,0141 | 0,49 | 35 |
| C (izaje) | 0,0324 | 0,15 (pancake) | 4,6 |
| D (rotación del gancho) | < 0,005 | 0,15 (pancake) | > 30 |

### 4.6 Conclusiones del análisis mecánico

1. **El factor limitante del sistema es la estabilidad al vuelco**, no la
   resistencia del material ni el par de los motores. La verificación por flexión
   arroja una capacidad 5,5 veces superior a la que admite el criterio de
   estabilidad.

2. **El eje de izaje es el más solicitado en términos relativos**, con un
   coeficiente de seguridad de 4,6. La razón es que debe elevar el motor D junto
   con la carga: el actuador del último grado de libertad se convierte en carga
   del actuador que lo sostiene. Montar el motor D sobre el gancho simplifica la
   transmisión del giro final, pero traslada su masa al eje de izaje, que es
   además el que emplea un motor de menor par. El margen sigue siendo suficiente,
   pero conviene tenerlo presente ante cualquier aumento futuro de la carga
   nominal.

3. **El contrapeso presenta una contrapartida dinámica.** Junto con los tres
   motores aporta casi dos tercios del momento estabilizador, pero también
   duplica el momento de inercia del conjunto giratorio, lo que reduce el
   coeficiente de seguridad del eje A de treinta y cuatro a quince. Es el
   compromiso clásico entre estabilidad estática y respuesta dinámica.

4. Ese margen remanente **es lo que hace viable una decisión de diseño adoptada
   en el firmware**: la ausencia de rampas de aceleración y desaceleración. Un
   accionamiento sin rampas somete al motor al par inercial completo en el
   instante del arranque, lo que habitualmente provoca pérdida de pasos. Con un
   margen de quince veces en el eje más comprometido dinámicamente, el motor
   absorbe ese transitorio sin desincronizarse. La simplificación del control no
   es arbitraria: está respaldada por la reserva de par disponible.

5. La curva de carga admisible obtenida reproduce el comportamiento de una grúa
   torre real, donde la capacidad nominal se especifica siempre asociada a un
   radio determinado. El rango de trabajo del carro se ubica en la zona de la
   curva donde el margen es mayor.
