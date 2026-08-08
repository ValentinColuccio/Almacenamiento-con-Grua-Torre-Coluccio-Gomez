import math

ORIGEN_X = 0
ORIGEN_Y = 0
MAX_ANGULO = 360
MIN_ANGULO = -360
angulo_actual = 0
angulo_garra_actual = 0

# --- Parámetros de la maniobra lineal ---
DIST_ENGANCHE = 150        # mm que avanza para enganchar / retrocede para soltar

# Alturas del eje C (0 = arriba, negativo = abajo). Calibradas por posición.
ALTURA_ARRIBA        = 0
ALTURA_DESCARGA      = -1250   # bajar en el punto de descarga

# --- Velocidades por motor (unidades del ESP). Ajustables a mano. ---
# Protocolo de trama: en la PRIMERA trama de la secuencia se envían las 4
# velocidades; después solo se re-emite la de un motor cuando CAMBIA (el ESP
# mantiene la última que recibió para cada uno).
V_DEFECTO = {"A": 6500, "B": 2000, "C": 1000, "D": 3250}

# Tramo lineal de "acercarse"/"retirar" (avance/retiro en la dirección de la
# pala): A tiende a ir más rápido que B y el trayecto no sale recto, así que acá
# se baja la velocidad de A para que acompañe a B. Ajustá estos valores probando.
V_ACERCARSE = {"A": 12000, "B": 2000, "C": 1000, "D": 4000}

# Orientación de la pala (grados, mundo) al servir cada punto. Por defecto +X (0°):
# la carga mira a +X, la pala entra en +X y se retira en -X. 'descarga' es INVERSO:
# la pala mira a -X (180°) y se retira hacia +X (hacia el centro), para no pasarse
# de alcance. Cualquier punto no listado usa ORIENTACION_DEFECTO.
ORIENTACION_DEFECTO = 0
ORIENTACIONES = {
    "descarga": 180,
}

def _orientacion(nombre):
    return ORIENTACIONES.get(nombre, ORIENTACION_DEFECTO)

# Todas las coordenadas en mm. Son la posición FINAL de la carga (donde queda /
# donde está). El sistema aproxima DIST_ENGANCHE mm por detrás de la pala (opuesto
# a su orientación) para tomar/dejar.
#
# Estante: cada objeto tiene 2 posiciones. Columna _0 en X=200, _1 en X=300
# (pasillos de enganche en X disjuntos, no chocan). Una fila (Y) por objeto.
puntos = {
    "caja_0": (200, 200),        # real (no tocar)
    "caja_1": (300, 200),
    "bidon uno_0": (200, 140),
    "bidon uno_1": (300, 140),
    "bidon dos_0": (200, 260),
    "bidon dos_1": (300, 260),
    "carrete_0": (200, 320),
    "carrete_1": (300, 320),
    "descarga": (-475, 0),       # real (no tocar)
    "carga": (460, 0)            # real (no tocar)
}

def cartesianas_a_polares(x, y):
    dx = x - ORIGEN_X
    dy = y - ORIGEN_Y
    angulo = math.degrees(math.atan2(dy, dx))
    distancia = math.hypot(dx, dy)
    return angulo, distancia

def mover_en_direccion(x, y, angulo_deg, distancia):
    theta = math.radians(angulo_deg)
    x_new = x + distancia * math.cos(theta)
    y_new = y + distancia * math.sin(theta)
    return x_new, y_new

def calcular_angulo_seguro(angulo_destino):
    global angulo_actual

    objetivo_normalizado = (angulo_destino + 360) % 360
    actual_normalizado = (angulo_actual + 360) % 360

    diferencia = objetivo_normalizado - actual_normalizado

    if diferencia > 180:
        diferencia -= 360
    elif diferencia < -180:
        diferencia += 360
    nuevo_angulo = angulo_actual + diferencia

    if nuevo_angulo > MAX_ANGULO:
        nuevo_angulo -= 360
    elif nuevo_angulo < MIN_ANGULO:
        nuevo_angulo += 360
    angulo_actual = nuevo_angulo

    return nuevo_angulo

def calcular_radio_grados(radio):
    R = 20
    grados = (radio * 180) / (math.pi * R)
    return grados

def calcular_angulo_garra(angulo_brazo, orientacion=0):
    global angulo_garra_actual

    # 'orientacion' = ángulo (mundo) al que debe apuntar la pala. Queda en absoluto:
    # angulo_brazo + D = orientacion  ->  D objetivo = orientacion - angulo_brazo.
    angulo_objetivo = orientacion - angulo_brazo
    objetivo_normalizado = (angulo_objetivo + 360) % 360
    actual_normalizado = (angulo_garra_actual + 360) % 360

    diferencia = objetivo_normalizado - actual_normalizado

    if diferencia > 180:
        diferencia -= 360
    elif diferencia < -180:
        diferencia += 360

    nuevo_angulo = angulo_garra_actual + diferencia

    if nuevo_angulo > MAX_ANGULO:
        nuevo_angulo -= 360
    elif nuevo_angulo < MIN_ANGULO:
        nuevo_angulo += 360

    angulo_garra_actual = nuevo_angulo
    return nuevo_angulo


def _paso(x, y, altura, orientacion=0, vel=None):
    """Genera un paso ((A, B, C, D), (vA, vB, vC, vD)) para una posición
    cartesiana (x, y) a la altura dada. La pala (D) se compensa para apuntar a
    'orientacion' (grados, mundo; 0 = +X). 'vel' es el dict de velocidades por
    motor (por defecto V_DEFECTO).

    OJO: usa/actualiza el estado global de ángulos (angulo_actual,
    angulo_garra_actual), por lo que debe llamarse en el orden real de la
    secuencia."""
    if vel is None:
        vel = V_DEFECTO
    angulo, radio = cartesianas_a_polares(x, y)
    A = calcular_angulo_seguro(angulo)              # rotación
    D = calcular_angulo_garra(A, orientacion)       # pala: mantiene 'orientacion'
    B = calcular_radio_grados(radio)                # traslación (radio -> grados)
    return ((A, B, altura, D), (vel["A"], vel["B"], vel["C"], vel["D"]))


def _campo(motor, texto_valor, vel, vel_prev):
    """Arma 'MOTOR:valor' y le agrega '-Vxxxx' solo si la velocidad cambió
    respecto de la trama anterior (vel_prev se actualiza in-place)."""
    if vel_prev.get(motor) != vel:
        vel_prev[motor] = vel
        return f"{motor}:{texto_valor}-V{int(vel)}"
    return f"{motor}:{texto_valor}"


def construir_tramas(secuencia):
    """Convierte la secuencia [((A,B,C,D),(vA,vB,vC,vD)), ...] en la lista de
    tramas de texto a enviar al ESP (ej: 'A:90.5-V6500;B:180.0-V2000;...').
    La velocidad de cada motor se incluye solo cuando cambia; en la PRIMERA
    trama van siempre las cuatro."""
    tramas = []
    vel_prev = {}
    for (A, B, C, D), (vA, vB, vC, vD) in secuencia:
        campos = [
            _campo("A", f"{A:.1f}", vA, vel_prev),
            _campo("B", f"{B:.1f}", vB, vel_prev),
            _campo("C", f"{C:.1f}", vC, vel_prev),
            _campo("D", f"{int(D)}", vD, vel_prev),
        ]
        tramas.append(";".join(campos))
    return tramas


def _ciclo_pick_and_place(origen, destino, altura_origen, altura_destino,
                          orient_origen=0, orient_destino=0):
    """Construye el ciclo lineal completo. Los puntos 'origen' y 'destino' son
    la posición FINAL de la carga (donde está / donde debe quedar). 'orient_*'
    es el ángulo (mundo) al que apunta la pala en cada punto (0 = +X).

    TOMAR en origen: la carga ya está en el punto -> aproximar DIST_ENGANCHE mm
    por detrás de la pala (opuesto a su orientación), bajar, avanzar en la
    dirección de la pala hasta el punto (engancha) y subir.
    DEJAR en destino: ir al punto (la carga debe quedar ahí), bajar, retirar la
    pala DIST_ENGANCHE mm hacia atrás (opuesto a su orientación) dejando la
    carga, y subir.
    Termina volviendo el eje B (traslación) a cero para no hacer palanca.

    Los tramos lineales de enganche/retiro usan V_ACERCARSE (A más lento para que
    el trayecto salga recto); el resto usa V_DEFECTO."""
    xo, yo = origen
    xd, yd = destino
    secuencia = []

    # --- TOMAR en el origen ---
    # Aproximación: DIST_ENGANCHE mm por detrás de la pala (opuesto a su orientación).
    xoa, yoa = mover_en_direccion(xo, yo, orient_origen + 180, DIST_ENGANCHE)

    # 1. Ir a la aproximación
    secuencia.append(_paso(xoa, yoa, altura_origen, orient_origen))
    # 2. Avanzar hasta el punto (tramo lineal) -> engancha
    secuencia.append(_paso(xo, yo, ALTURA_ARRIBA, orient_origen, vel=V_ACERCARSE))

    # --- DEJAR en el destino ---
    # 3. Ir al destino; la pala pasa a 'orient_destino' con el eje D
    secuencia.append(_paso(xd, yd, altura_destino, orient_destino))
    # 4. Retirar la pala DIST_ENGANCHE mm hacia atrás (tramo lineal) -> deja la carga
    xda, yda = mover_en_direccion(xd, yd, orient_destino + 180, DIST_ENGANCHE)
    secuencia.append(_paso(xda, yda, ALTURA_ARRIBA, orient_destino, vel=V_ACERCARSE))
    # 5. Subir
    secuencia.append(_paso(xda, yda, ALTURA_ARRIBA, orient_destino))

    # 6. Volver el eje B (traslación) a cero para no quedar haciendo palanca.
    #    Se conservan A y D en su último valor.
    secuencia.append(((angulo_actual, 0, ALTURA_ARRIBA, angulo_garra_actual),
                      (V_DEFECTO["A"], V_DEFECTO["B"], V_DEFECTO["C"], V_DEFECTO["D"])))

    return secuencia


def obtener_sec_voz(nombre, idx):
    """Modo voz: TOMA del estante y DEJA en descarga."""
    punto_nombre = f"{nombre}_{idx}"
    if punto_nombre not in puntos:
        raise ValueError(f"El punto '{punto_nombre}' no está definido.")

    origen = puntos[punto_nombre]
    destino = puntos["descarga"]

    secuencia = _ciclo_pick_and_place(
        origen, destino,
        altura_origen=ALTURA_DESCARGA,
        altura_destino=ALTURA_DESCARGA,
        orient_origen=_orientacion(punto_nombre),
        orient_destino=_orientacion("descarga"),
    )
    return construir_tramas(secuencia)


def obtener_entrada_cam(nombre, idx):
    """Modo cam: TOMA de carga y DEJA en el estante."""
    punto_nombre = f"{nombre}_{idx}"
    if punto_nombre not in puntos:
        raise ValueError(f"El punto '{punto_nombre}' no está definido.")

    origen = puntos["carga"]
    destino = puntos[punto_nombre]

    secuencia = _ciclo_pick_and_place(
        origen, destino,
        altura_origen=ALTURA_DESCARGA,
        altura_destino=ALTURA_DESCARGA,
        orient_origen=_orientacion("carga"),
        orient_destino=_orientacion(punto_nombre),
    )
    return construir_tramas(secuencia)
