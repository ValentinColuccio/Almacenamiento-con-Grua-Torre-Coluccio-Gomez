import math

ORIGEN_X = 0
ORIGEN_Y = 0
MAX_ANGULO = 360
MIN_ANGULO = -360
angulo_actual = 0
angulo_garra_actual = 0
radio_actual = 0          # último radio pedido, para poder armar el regreso a home

# --- Parámetros de la maniobra ---
DIST_ENGANCHE = 200        # mm que avanza para enganchar / retrocede para soltar
RADIO_MINIMO = 100         # mm: radio más chico al que puede ir la pala

# Alturas del eje C (0 = arriba, negativo = abajo), en unidades del ESP.
ALTURA_ARRIBA = 0        # pala recogida: altura de tránsito
ALTURA_APOYO  = -1000    # altura de la superficie donde descansa la carga

# Compensación del cabeceo de la pala, con un valor propio para cada maniobra.
# B y C comparten el accionamiento por hilos: al AVANZAR el hilo se afloja y la
# pala cabecea nariz abajo, así que hay que pedirle a C que vaya más arriba para
# que la punta termine a la altura correcta. Al RETROCEDER el hilo toma tensión y
# la pala queda casi recta, o sea que el cabeceo no es simétrico y estos dos
# valores no tienen por qué parecerse. Se ajustan por separado.
#
# Son offsets sobre ALTURA_APOYO: positivo = más arriba, negativo = más abajo.
# El ángulo y el radio NO se tocan, la corrección es solo sobre C.
# El avance de enganche se hace en dos tramos, con una bajada en el medio:
# se entra la primera mitad a COMP_TOMA, se baja a COMP_TOMA2 y se completa el
# recorrido. El retroceso de la dejada sigue siendo una sola tirada.
COMP_TOMA   = -80       # C respecto del apoyo para el primer tramo del avance
COMP_TOMA2  = -120       # C respecto del apoyo para el segundo tramo del avance
COMP_DEJADA = -15        # C respecto del apoyo al soltar (B retrocede)

FRAC_TRAMO1 = 0.5   # parte del recorrido que se hace en el primer tramo

ALTURA_TOMA   = ALTURA_APOYO + COMP_TOMA      # entrar al pallet
ALTURA_TOMA2  = ALTURA_APOYO + COMP_TOMA2     # completar el enganche
ALTURA_DEJADA = ALTURA_APOYO + COMP_DEJADA    # dejar el pallet en la descarga

# --- Dejada en el ESTANTE (modo cam) ---
# Guardar un pallet en el estante tiene alturas propias, independientes de las
# del punto de descarga: se apoya a COMP_GUARDADO y el retiro se hace en dos
# tramos, igual que el avance de la toma, con una altura por tramo.
# VALORES DE ARRANQUE: ajustar contra la máquina.
COMP_GUARDADO = -150     # C respecto del apoyo al apoyar el pallet en el estante
COMP_RETIRO1  = -150    # C para el primer tramo del retiro
COMP_RETIRO2  = -130    # C para el segundo tramo del retiro

ALTURA_GUARDADO = ALTURA_APOYO + COMP_GUARDADO
ALTURA_RETIRO1  = ALTURA_APOYO + COMP_RETIRO1
ALTURA_RETIRO2  = ALTURA_APOYO + COMP_RETIRO2

# La carga se traslada con la pala girada. El giro se hace a media subida (y a
# media bajada), con la carga ya despegada del apoyo pero todavía abajo.
# ALTURA_GIRO tiene que quedar por encima de las alturas de toma y de dejada.
ALTURA_GIRO       = -400   # altura del eje C a la que se gira la pala
ANGULO_TRANSPORTE = 80      # grados del eje D mientras se lleva la carga

# --- Fases para el HMI ---
# Etiqueta gruesa de cada trama, para la pantalla de Operación. Cada ciclo
# devuelve una lista paralela a las tramas con la fase de cada una.
# OJO: si tocás esta lista, actualizá también OperacionTab.FASES en PC/main.py:
# corren en máquinas distintas y se comparan por texto.
FASE_APROXIMAR = "Aproximando a la carga"
FASE_ENGANCHAR = "Enganchando la carga"
FASE_TRASLADAR = "Trasladando la carga"
FASE_DEJAR     = "Dejando la carga"
FASE_HOME      = "Volviendo a home"

FASES = [FASE_APROXIMAR, FASE_ENGANCHAR, FASE_TRASLADAR, FASE_DEJAR, FASE_HOME]

# --- Velocidades por motor (unidades del ESP). Ajustables a mano. ---
# Protocolo de trama: en la PRIMERA trama de la secuencia se envían las 4
# velocidades; después solo se re-emite la de un motor cuando CAMBIA (el ESP
# mantiene la última que recibió para cada uno).
V_DEFECTO = {"A": 6500, "B": 500, "C": 1000, "D": 3250}

# Enganche / retiro del pallet. Ahora es un tramo radial puro (solo se mueve B),
# así que ya no hace falta frenar A para enderezar el trayecto: lo único que
# importa acá es que B entre y salga suave.
V_ENGANCHE = {"A": 6500, "B": 500, "C": 1000, "D": 3250}

# ---------------------------------------------------------------------------
# ALMACENAMIENTO RADIAL
# ---------------------------------------------------------------------------
# Cada posición se define por (ángulo, radio) respecto del eje de giro, y la
# pala apunta SIEMPRE hacia afuera sobre ese mismo radio. Consecuencia directa:
# buscar el pallet y retirarse es un cambio de radio con el ángulo fijo, o sea
# que esas tramas mueven ÚNICAMENTE el motor B.
#
# Cada objeto ocupa dos slots contiguos sobre el arco (no uno detrás del otro),
# así ninguna posición tapa el acceso a la otra.
RADIO_ESTANTE      = 400   # mm del eje a la carga, igual para todos los slots
ANGULO_PRIMER_SLOT = 40    # grados del primer slot del estante
PASO_ANGULAR       = 15    # grados entre slots contiguos

# Nombres SIN tilde: son las mismas claves que usa el dict 'ocupacion' de
# SEpower, que normaliza todo lo que le entra por voz o por cámara.
ORDEN_SLOTS = [
    "caja_0",      "caja_1",
    "bidon uno_0", "bidon uno_1",
    "bidon dos_0", "bidon dos_1",
    "carrete_0",   "carrete_1",
]

# (ángulo, radio) de la posición FINAL de la carga. Para mover un slot suelto,
# pisalo después de esta línea: puntos["caja_0"] = (37, 380)
puntos = {
    nombre: (ANGULO_PRIMER_SLOT + i * PASO_ANGULAR, RADIO_ESTANTE)
    for i, nombre in enumerate(ORDEN_SLOTS)
}

# Puntos fijos de la planta (reales, no tocar). Ya eran radiales.
puntos["descarga"] = (180, 500)
puntos["carga"]    = (0, 520)


def polar_desde_xy(x, y):
    """(ángulo, radio) a partir de cartesianas, por si un punto se conoce medido
    en x/y sobre el piso."""
    dx = x - ORIGEN_X
    dy = y - ORIGEN_Y
    return math.degrees(math.atan2(dy, dx)), math.hypot(dx, dy)


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


def _paso(angulo, radio, altura, orientacion=None, vel=None, giro_pala=0):
    """Genera un paso ((A, B, C, D), (vA, vB, vC, vD)) para una posición polar.

    'orientacion' es el ángulo (mundo) al que apunta la pala; con None apunta
    hacia afuera sobre el propio radio, que es lo que hace radial al
    almacenamiento. 'vel' es el dict de velocidades por motor.

    'giro_pala' desplaza esa orientación respecto del brazo, o sea que es
    directamente el valor que toma el eje D. Con 0 la pala queda alineada con la
    pluma; con ANGULO_TRANSPORTE queda en la pose de traslado. Al seguir al
    brazo, D no se mueve durante los giros de A.

    OJO: usa/actualiza el estado global de ángulos (angulo_actual,
    angulo_garra_actual), por lo que debe llamarse en el orden real de la
    secuencia."""
    global radio_actual

    if vel is None:
        vel = V_DEFECTO
    if orientacion is None:
        orientacion = angulo + giro_pala

    A = calcular_angulo_seguro(angulo)              # rotación
    D = calcular_angulo_garra(A, orientacion)       # pala: mantiene 'orientacion'
    B = calcular_radio_grados(radio)                # traslación (radio -> grados)
    radio_actual = radio
    return ((A, B, altura, D), (vel["A"], vel["B"], vel["C"], vel["D"]))


def _radio_aproximacion(radio, cual):
    """Radio desde el que se ataca el pallet: DIST_ENGANCHE mm más cerca del eje."""
    r = radio - DIST_ENGANCHE
    if r < RADIO_MINIMO:
        raise ValueError(
            f"El punto de {cual} está a {radio:.0f} mm del eje: con "
            f"DIST_ENGANCHE={DIST_ENGANCHE} mm la aproximación cae en {r:.0f} mm, "
            f"por debajo del radio mínimo ({RADIO_MINIMO} mm)."
        )
    return r


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


def _ciclo_pick_and_place(origen, destino, altura_toma, altura_toma2,
                          altura_dejada, alturas_retiro=None):
    """Construye el ciclo completo con almacenamiento radial. 'origen' y
    'destino' son (ángulo, radio) de la posición FINAL de la carga.

    TOMAR en origen: posicionarse a DIST_ENGANCHE mm por dentro del pallet sobre
    el mismo radio y a 'altura_toma', entrar la primera parte del recorrido
    (SOLO B), bajar a 'altura_toma2' (SOLO C), completar el avance hasta el
    pallet (SOLO B), despegar hasta ALTURA_GIRO (SOLO C), girar la pala a la
    pose de traslado (SOLO D) y terminar de subir (SOLO C).
    DEJAR en destino: trasladarse bajando hasta ALTURA_GIRO con la pala girada,
    devolverla al eje radial (SOLO D), terminar de bajar hasta 'altura_dejada'
    apoyando la carga (SOLO C), retirar la pala y subir vacía (SOLO C).

    El retiro tiene dos formas según 'alturas_retiro':
      None            -> una sola tirada a 'altura_dejada' (punto de descarga).
      (h1, h2)        -> baja a h1, retrocede el primer tramo, pasa a h2 y
                         completa el retiro; espejo del avance de la toma.
                         Es lo que se usa para guardar en el estante.

    Termina recogiendo el eje B a cero para no hacer palanca.

    Devuelve (secuencia, fases): dos listas paralelas, una con los pasos y otra
    con la etiqueta gruesa de cada uno para la pantalla de Operación.

    Los tramos de enganche/retiro no mueven A ni D por construcción: se pide dos
    veces el mismo ángulo, así que A y D salen con el valor idéntico anterior."""
    ang_o, rad_o = origen
    ang_d, rad_d = destino

    rad_o_aprox = _radio_aproximacion(rad_o, "origen")
    rad_d_aprox = _radio_aproximacion(rad_d, "destino")

    alturas_bajas = [altura_toma, altura_toma2, altura_dejada]
    if alturas_retiro is not None:
        alturas_bajas.extend(alturas_retiro)

    if ALTURA_GIRO <= max(alturas_bajas):
        raise ValueError(
            f"ALTURA_GIRO ({ALTURA_GIRO}) tiene que quedar por encima de todas "
            f"las alturas de trabajo ({', '.join(str(h) for h in alturas_bajas)}): "
            "si no, el giro de la pala pasa a ser una bajada."
        )

    # Punto donde se corta el avance para bajar a la segunda altura
    rad_o_medio = rad_o_aprox + (rad_o - rad_o_aprox) * FRAC_TRAMO1

    secuencia = []
    fases = []

    def agregar(paso, fase):
        """Encola la trama junto con su fase, así las dos listas no se separan."""
        secuencia.append(paso)
        fases.append(fase)

    # --- TOMAR en el origen ---
    # Traslado: gira, extiende hasta la aproximación y baja a la altura de toma
    agregar(_paso(ang_o, rad_o_aprox, altura_toma), FASE_APROXIMAR)
    # Primer tramo del avance -> SOLO B
    agregar(_paso(ang_o, rad_o_medio, altura_toma, vel=V_ENGANCHE), FASE_ENGANCHAR)
    # Bajar a la segunda altura de toma -> SOLO C
    agregar(_paso(ang_o, rad_o_medio, altura_toma2), FASE_ENGANCHAR)
    # Segundo tramo: completa el avance hasta el pallet -> SOLO B
    agregar(_paso(ang_o, rad_o, altura_toma2, vel=V_ENGANCHE), FASE_ENGANCHAR)
    # Despegar la carga hasta la altura de giro -> SOLO C
    agregar(_paso(ang_o, rad_o, ALTURA_GIRO), FASE_TRASLADAR)
    # Girar la pala a la pose de traslado -> SOLO D
    agregar(_paso(ang_o, rad_o, ALTURA_GIRO, giro_pala=ANGULO_TRANSPORTE), FASE_TRASLADAR)
    # Terminar de subir -> SOLO C
    agregar(_paso(ang_o, rad_o, ALTURA_ARRIBA, giro_pala=ANGULO_TRANSPORTE), FASE_TRASLADAR)

    # --- DEJAR en el destino ---
    # Traslado con la carga hasta el destino, bajando a la altura de giro
    agregar(_paso(ang_d, rad_d, ALTURA_GIRO, giro_pala=ANGULO_TRANSPORTE), FASE_TRASLADAR)
    # Devolver la pala al eje radial -> SOLO D
    agregar(_paso(ang_d, rad_d, ALTURA_GIRO), FASE_DEJAR)
    # Terminar de bajar hasta apoyar la carga -> SOLO C
    agregar(_paso(ang_d, rad_d, altura_dejada), FASE_DEJAR)

    if alturas_retiro is None:
        # Retiro de una sola tirada (punto de descarga)
        agregar(_paso(ang_d, rad_d_aprox, altura_dejada, vel=V_ENGANCHE), FASE_DEJAR)
    else:
        # Retiro en dos tramos (estante), espejo del avance de la toma
        h_retiro1, h_retiro2 = alturas_retiro
        rad_d_medio = rad_d - (rad_d - rad_d_aprox) * FRAC_TRAMO1

        # Liberar la pala de debajo del pallet -> SOLO C
        agregar(_paso(ang_d, rad_d, h_retiro1), FASE_DEJAR)
        # Primer tramo del retiro -> SOLO B
        agregar(_paso(ang_d, rad_d_medio, h_retiro1, vel=V_ENGANCHE), FASE_DEJAR)
        # Segunda altura de retiro -> SOLO C
        agregar(_paso(ang_d, rad_d_medio, h_retiro2), FASE_DEJAR)
        # Segundo tramo: completa el retiro -> SOLO B
        agregar(_paso(ang_d, rad_d_aprox, h_retiro2, vel=V_ENGANCHE), FASE_DEJAR)

    # Subir la pala vacía -> SOLO C
    agregar(_paso(ang_d, rad_d_aprox, ALTURA_ARRIBA), FASE_HOME)

    # Recoger el eje B (traslación) a cero para no quedar haciendo palanca.
    #    Se conservan A y D en su último valor.
    agregar(((angulo_actual, 0, ALTURA_ARRIBA, angulo_garra_actual),
             (V_DEFECTO["A"], V_DEFECTO["B"], V_DEFECTO["C"], V_DEFECTO["D"])),
            FASE_HOME)

    return secuencia, fases


def secuencia_home():
    """Lleva la grúa a reposo desde donde esté: sube la pala, la alinea con la
    pluma y recoge el eje B. No toca el giro A, para no barrer la planta.

    El orden importa: primero arriba, después alinear, y recién ahí recoger.
    Al revés arrastraría la pala a media altura."""
    vel = (V_DEFECTO["A"], V_DEFECTO["B"], V_DEFECTO["C"], V_DEFECTO["D"])
    b_actual = calcular_radio_grados(radio_actual)

    secuencia = [
        # 1. Subir manteniendo posición y pala como estén
        ((angulo_actual, b_actual, ALTURA_ARRIBA, angulo_garra_actual), vel),
        # 2. Alinear la pala con la pluma (D -> 0)
        _paso(angulo_actual, radio_actual, ALTURA_ARRIBA),
        # 3. Recoger el eje B
        _paso(angulo_actual, 0, ALTURA_ARRIBA),
    ]
    return construir_tramas(secuencia), [FASE_HOME] * len(secuencia)


def obtener_sec_voz(nombre, idx):
    """Modo voz: TOMA del estante y DEJA en descarga."""
    punto_nombre = f"{nombre}_{idx}"
    if punto_nombre not in puntos:
        raise ValueError(f"El punto '{punto_nombre}' no está definido.")

    origen = puntos[punto_nombre]
    destino = puntos["descarga"]

    secuencia, fases = _ciclo_pick_and_place(
        origen, destino,
        altura_toma=ALTURA_TOMA,
        altura_toma2=ALTURA_TOMA2,
        altura_dejada=ALTURA_DEJADA,
    )
    return construir_tramas(secuencia), fases


def obtener_entrada_cam(nombre, idx):
    """Modo cam: TOMA de carga y DEJA en el estante."""
    punto_nombre = f"{nombre}_{idx}"
    if punto_nombre not in puntos:
        raise ValueError(f"El punto '{punto_nombre}' no está definido.")

    origen = puntos["carga"]
    destino = puntos[punto_nombre]

    # Guardar en el estante usa sus propias alturas y retiro en dos tramos.
    secuencia, fases = _ciclo_pick_and_place(
        origen, destino,
        altura_toma=ALTURA_TOMA,
        altura_toma2=ALTURA_TOMA2,
        altura_dejada=ALTURA_GUARDADO,
        alturas_retiro=(ALTURA_RETIRO1, ALTURA_RETIRO2),
    )
    return construir_tramas(secuencia), fases
