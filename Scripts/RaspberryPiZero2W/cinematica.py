import json
import math
from collections import namedtuple
from pathlib import Path

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

# Tope inferior del eje C. Es una guarda de seguridad, no una altura de trabajo:
# ni la tabla ALTURAS ni el jog del panel de calibración pueden bajar de acá.
# VALOR PROVISORIO: hay que medir cuál es la altura más baja a la que la pala
# puede ir sin tocar nada en el peor punto del estante.
ALTURA_MINIMA = -1300

# Alturas del eje C (0 = arriba, negativo = abajo), en unidades del ESP.
ALTURA_ARRIBA = 0        # pala recogida: altura de tránsito

# Las alturas de TRABAJO no son globales: cada punto tiene las suyas, porque la
# superficie no está pareja. Están en la tabla ALTURAS, más abajo, pegada a la
# definición de los puntos para que se lean juntas.

FRAC_TRAMO1 = 0.5   # parte del recorrido que se hace en el primer tramo


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

# Los movimientos del panel de Calibración NO son parte del ciclo, así que esta
# fase queda FUERA de FASES: no es un sexto paso de la lista. El HMI la trata
# como un estado aparte.
FASE_CALIBRAR = "Calibrando"

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
ANGULO_PRIMER_SLOT = 40    # grados del primer slot de la caja (referencia)
PASO_ANGULAR       = 15    # grados entre los DOS slots de un mismo objeto
PASO_CUADRANTE     = 90    # grados entre objetos: uno por cuadrante

# Un objeto por cuadrante, cada uno con sus dos slots contiguos. El par de la
# caja es la referencia y los otros tres son ese mismo par rotado 90°, 180° y
# 270°, así la planta queda simétrica alrededor del eje de giro.
#
# Nombres SIN tilde: son las mismas claves que usa el dict 'ocupacion' de
# SEpower, que normaliza todo lo que le entra por voz o por cámara.
ORDEN_OBJETOS = ["caja", "bidon uno", "bidon dos", "carrete"]

ORDEN_SLOTS = [f"{obj}_{s}" for obj in ORDEN_OBJETOS for s in (0, 1)]

# (ángulo, radio) de la posición FINAL de la carga. Para mover un slot suelto,
# pisalo después de esta línea: puntos["caja_0"] = (37, 380)
puntos = {
    f"{obj}_{s}": (ANGULO_PRIMER_SLOT + c * PASO_CUADRANTE + s * PASO_ANGULAR,
                   RADIO_ESTANTE)
    for c, obj in enumerate(ORDEN_OBJETOS)
    for s in (0, 1)
}

# Puntos fijos de la planta (reales, no tocar). Ya eran radiales.
puntos["descarga"] = (180, 500)
puntos["carga"]    = (0, 515)


# ---------------------------------------------------------------------------
# ALTURAS DE TRABAJO, PUNTO POR PUNTO
# ---------------------------------------------------------------------------
# La superficie no está pareja, así que cada punto lleva sus propias alturas en
# lugar de compartir una global. Son valores ABSOLUTOS del eje C (0 = arriba,
# negativo = abajo): lo que se pone acá es literalmente lo que se le manda al
# ESP32, no un offset de nada.
#
# Cuatro números independientes por punto:
#
#   toma_aprox    la pala entra al pallet a esta altura
#   toma_final    completa el enganche y levanta desde acá
#   dejar_aprox   baja y apoya la carga a esta altura
#   dejar_final   termina de retirar la pala a esta altura
#
# El par de TOMA manda cuando el punto es origen (ir a buscar) y el de DEJAR
# cuando es destino. Cada slot del estante usa los dos: es origen por voz y
# destino por cámara, y no tienen por qué coincidir.
#
# Si las dos alturas de una maniobra son IGUALES, ese tramo se hace de una sola
# tirada: no se emite el escalón intermedio ni las tramas de más. Así está
# configurada la descarga.
#
# ALTURA_GIRO tiene que quedar por encima de todas estas.

AlturasPunto = namedtuple("AlturasPunto",
                          "toma_aprox toma_final dejar_aprox dejar_final")

CUALES = AlturasPunto._fields   # ("toma_aprox", "toma_final", ...)

# Estos son los valores de ARRANQUE. Los reales viven en 'alturas.json', que
# escribe el panel de Calibración del HMI. Si el archivo no está (por ejemplo en
# la copia que tiene la PC para dibujar el mímico), se usan estos.
ALTURAS_POR_DEFECTO = {
    #                          toma_aprox  toma_final  dejar_aprox  dejar_final
    "caja_0":     AlturasPunto(    -980,      -1020,      -1000,       -970    ),
    "caja_1":     AlturasPunto(    -980,      -1020,      -1000,       -970    ),
    "bidon uno_0":AlturasPunto(    -980,      -1020,      -1000,       -970    ),
    "bidon uno_1":AlturasPunto(    -980,      -1020,      -1000,       -970    ),
    "bidon dos_0":AlturasPunto(    -980,      -1020,      -1000,       -970    ),
    "bidon dos_1":AlturasPunto(    -980,      -1020,      -1000,       -970    ),
    "carrete_0":  AlturasPunto(    -980,      -1020,      -1000,       -970    ),
    "carrete_1":  AlturasPunto(    -980,      -1020,      -1000,       -970    ),

    # Puntos fijos de la planta. 'carga' solo se usa como origen y 'descarga'
    # solo como destino; las columnas que no aplican quedan igualadas.
    "carga":      AlturasPunto(    -980,      -1020,       -980,       -980    ),
    "descarga":   AlturasPunto(    -915,       -915,       -915,       -915    ),
}

ARCHIVO_ALTURAS = Path(__file__).resolve().parent / "alturas.json"

ALTURAS = dict(ALTURAS_POR_DEFECTO)


def cargar_alturas():
    """Relee 'alturas.json' sobre los valores por defecto.

    Se llama al empezar cada secuencia, así una recalibración desde el HMI toma
    efecto sin reiniciar SEpower ni mandar ningún comando de recarga."""
    global ALTURAS
    tabla = dict(ALTURAS_POR_DEFECTO)

    try:
        crudo = json.loads(ARCHIVO_ALTURAS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        crudo = {}
    except Exception as e:
        print(f"[ALTURAS] No se pudo leer {ARCHIVO_ALTURAS.name}: {e}. "
              "Se usan los valores por defecto.", flush=True)
        crudo = {}

    for nombre, valores in crudo.items():
        try:
            tabla[nombre] = AlturasPunto(**{c: int(valores[c]) for c in CUALES})
        except (TypeError, KeyError, ValueError):
            print(f"[ALTURAS] Fila inválida para '{nombre}', se ignora.", flush=True)

    faltan = [n for n in puntos if n not in tabla]
    if faltan:
        raise ValueError("Puntos sin alturas definidas: " + ", ".join(sorted(faltan)))

    bajas = {n: min(a) for n, a in tabla.items() if min(a) < ALTURA_MINIMA}
    if bajas:
        raise ValueError(
            f"Alturas por debajo de ALTURA_MINIMA ({ALTURA_MINIMA}): "
            + ", ".join(f"{n}={v}" for n, v in sorted(bajas.items()))
        )

    ALTURAS = tabla
    return tabla


def guardar_alturas(tabla=None):
    """Escribe la tabla completa en 'alturas.json'."""
    tabla = tabla or ALTURAS
    datos = {n: dict(zip(CUALES, a)) for n, a in tabla.items()}
    ARCHIVO_ALTURAS.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    return ARCHIVO_ALTURAS


def fijar_altura(nombre, cual, valor):
    """Cambia una sola celda y persiste. Valida contra el tope inferior."""
    if cual not in CUALES:
        raise ValueError(f"'{cual}' no es una altura válida. Opciones: {', '.join(CUALES)}")
    if nombre not in ALTURAS:
        raise ValueError(f"El punto '{nombre}' no existe.")
    valor = int(valor)
    if valor < ALTURA_MINIMA:
        raise ValueError(f"{valor} está por debajo de ALTURA_MINIMA ({ALTURA_MINIMA}).")

    ALTURAS[nombre] = ALTURAS[nombre]._replace(**{cual: valor})
    guardar_alturas()
    return ALTURAS[nombre]


try:
    cargar_alturas()
except Exception as _e:      # que un JSON roto no impida arrancar SEpower
    print(f"[ALTURAS] {_e} Se usan los valores por defecto.", flush=True)
    ALTURAS = dict(ALTURAS_POR_DEFECTO)


def alturas_de(nombre):
    """Alturas de trabajo de un punto, con un error claro si falta la fila."""
    if nombre not in ALTURAS:
        raise ValueError(
            f"El punto '{nombre}' no tiene alturas definidas. "
            "Agregale una fila a la tabla ALTURAS de cinematica.py."
        )
    return ALTURAS[nombre]


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


def _ciclo_pick_and_place(origen, destino, alt_origen, alt_destino):
    """Construye el ciclo completo con almacenamiento radial.

    'origen' y 'destino' son (ángulo, radio) de la posición FINAL de la carga.
    'alt_origen' y 'alt_destino' son las AlturasPunto de cada uno: del origen se
    usan las de TOMA y del destino las de DEJAR, así cada punto lleva su propia
    calibración de altura sin arrastrar a los demás.

    TOMAR en origen: posicionarse a DIST_ENGANCHE mm por dentro del pallet sobre
    el mismo radio y a 'toma_aprox', entrar (SOLO B), despegar hasta ALTURA_GIRO
    (SOLO C), girar la pala a la pose de traslado (SOLO D) y terminar de subir.
    DEJAR en destino: trasladarse bajando hasta ALTURA_GIRO con la pala girada,
    devolverla al eje radial (SOLO D), bajar a 'dejar_aprox' apoyando la carga
    (SOLO C), retirar la pala (SOLO B) y subir vacía (SOLO C).

    El avance y el retiro se parten en dos tramos con un escalón de altura en el
    medio. Si las dos alturas de esa maniobra son iguales, el escalón no aporta
    nada y el tramo sale de una sola tirada.

    Los tramos de enganche/retiro no mueven A ni D por construcción: se pide dos
    veces el mismo ángulo, así que A y D salen con el valor idéntico anterior.

    Devuelve (secuencia, fases): dos listas paralelas, una con los pasos y otra
    con la etiqueta gruesa de cada uno para la pantalla de Operación."""
    ang_o, rad_o = origen
    ang_d, rad_d = destino

    rad_o_aprox = _radio_aproximacion(rad_o, "origen")
    rad_d_aprox = _radio_aproximacion(rad_d, "destino")

    de_trabajo = [alt_origen.toma_aprox, alt_origen.toma_final,
                  alt_destino.dejar_aprox, alt_destino.dejar_final]
    if ALTURA_GIRO <= max(de_trabajo):
        raise ValueError(
            f"ALTURA_GIRO ({ALTURA_GIRO}) tiene que quedar por encima de todas "
            f"las alturas de trabajo del ciclo "
            f"({', '.join(str(h) for h in de_trabajo)}): si no, el giro de la "
            "pala pasa a ser una bajada."
        )

    # Puntos donde se corta el avance y el retiro para cambiar de altura
    rad_o_medio = rad_o_aprox + (rad_o - rad_o_aprox) * FRAC_TRAMO1
    rad_d_medio = rad_d - (rad_d - rad_d_aprox) * FRAC_TRAMO1

    secuencia = []
    fases = []

    def agregar(paso, fase):
        """Encola la trama junto con su fase, así las dos listas no se separan."""
        secuencia.append(paso)
        fases.append(fase)

    # --- TOMAR en el origen ---
    # Traslado: gira, extiende hasta la aproximación y baja a la altura de toma
    agregar(_paso(ang_o, rad_o_aprox, alt_origen.toma_aprox), FASE_APROXIMAR)

    if alt_origen.toma_final != alt_origen.toma_aprox:
        # Primer tramo del avance -> SOLO B
        agregar(_paso(ang_o, rad_o_medio, alt_origen.toma_aprox, vel=V_ENGANCHE),
                FASE_ENGANCHAR)
        # Escalón de altura antes de completar la entrada -> SOLO C
        agregar(_paso(ang_o, rad_o_medio, alt_origen.toma_final), FASE_ENGANCHAR)

    # Completa el avance hasta el pallet -> SOLO B
    agregar(_paso(ang_o, rad_o, alt_origen.toma_final, vel=V_ENGANCHE),
            FASE_ENGANCHAR)

    # Despegar la carga hasta la altura de giro -> SOLO C
    agregar(_paso(ang_o, rad_o, ALTURA_GIRO), FASE_TRASLADAR)
    # Girar la pala a la pose de traslado -> SOLO D
    agregar(_paso(ang_o, rad_o, ALTURA_GIRO, giro_pala=ANGULO_TRANSPORTE),
            FASE_TRASLADAR)
    # Terminar de subir -> SOLO C
    agregar(_paso(ang_o, rad_o, ALTURA_ARRIBA, giro_pala=ANGULO_TRANSPORTE),
            FASE_TRASLADAR)

    # --- DEJAR en el destino ---
    # Traslado con la carga hasta el destino, bajando a la altura de giro
    agregar(_paso(ang_d, rad_d, ALTURA_GIRO, giro_pala=ANGULO_TRANSPORTE),
            FASE_TRASLADAR)
    # Devolver la pala al eje radial -> SOLO D
    agregar(_paso(ang_d, rad_d, ALTURA_GIRO), FASE_DEJAR)
    # Bajar hasta apoyar la carga -> SOLO C
    agregar(_paso(ang_d, rad_d, alt_destino.dejar_aprox), FASE_DEJAR)

    if alt_destino.dejar_final != alt_destino.dejar_aprox:
        # Primer tramo del retiro -> SOLO B
        agregar(_paso(ang_d, rad_d_medio, alt_destino.dejar_aprox, vel=V_ENGANCHE),
                FASE_DEJAR)
        # Escalón de altura antes de completar el retiro -> SOLO C
        agregar(_paso(ang_d, rad_d_medio, alt_destino.dejar_final), FASE_DEJAR)

    # Completa el retiro -> SOLO B
    agregar(_paso(ang_d, rad_d_aprox, alt_destino.dejar_final, vel=V_ENGANCHE),
            FASE_DEJAR)

    # Subir la pala vacía -> SOLO C
    agregar(_paso(ang_d, rad_d_aprox, ALTURA_ARRIBA), FASE_HOME)

    # Recoger el eje B (traslación) a cero para no quedar haciendo palanca.
    #    Se conservan A y D en su último valor.
    agregar(((angulo_actual, 0, ALTURA_ARRIBA, angulo_garra_actual),
             (V_DEFECTO["A"], V_DEFECTO["B"], V_DEFECTO["C"], V_DEFECTO["D"])),
            FASE_HOME)

    return secuencia, fases



# ---------------------------------------------------------------------------
# CALIBRACIÓN
# ---------------------------------------------------------------------------
# Poses para el panel de Calibración del HMI. Las genera la Raspberry y NO la
# PC, aunque la PC también tenga este módulo: 'angulo_actual' y 'radio_actual'
# son estado de la máquina, y el que vale es el de SEpower. Si la PC armara las
# tramas con su propio estado, el desenrollado de A podría salir 360° corrido.

def _vel_tupla(vel=None):
    vel = vel or V_DEFECTO
    return (vel["A"], vel["B"], vel["C"], vel["D"])


def radio_de_calibracion(nombre, cual):
    """Radio en el que se calibra cada altura: el que le da su significado.

    Importa que sea exactamente el mismo que usa el ciclo real, porque el
    cabeceo de la pala depende de la POSICIÓN de B: calibrar a otro radio daría
    un número que después no sirve.
    """
    ang, rad = puntos[nombre]
    if cual in ("toma_aprox", "dejar_final"):
        return _radio_aproximacion(rad, cual)   # afuera del pallet
    return rad                                  # dentro del pallet


def pose_calibracion(nombre, cual, altura=None):
    """Tramas para llevar la pala a la pose de una altura concreta.

    Sube primero, después gira y extiende, y recién ahí baja: mandar A, B y C
    juntos desde donde esté podría barrer el estante a media altura.
    La pala va alineada con la pluma (D=0), igual que en el ciclo real."""
    if nombre not in puntos:
        raise ValueError(f"El punto '{nombre}' no existe.")
    if cual not in CUALES:
        raise ValueError(f"'{cual}' no es una altura válida.")

    ang, _ = puntos[nombre]
    rad = radio_de_calibracion(nombre, cual)
    altura = getattr(alturas_de(nombre), cual) if altura is None else int(altura)

    if altura < ALTURA_MINIMA:
        raise ValueError(f"{altura} está por debajo de ALTURA_MINIMA ({ALTURA_MINIMA}).")

    secuencia = [
        # 1. Subir donde esté, sin mover nada más
        ((angulo_actual, calcular_radio_grados(radio_actual), ALTURA_ARRIBA,
          angulo_garra_actual), _vel_tupla()),
        # 2. Girar y extender, arriba
        _paso(ang, rad, ALTURA_ARRIBA),
        # 3. Bajar a la altura a calibrar
        _paso(ang, rad, altura),
    ]
    return construir_tramas(secuencia), altura


def paso_jog(altura):
    """Una sola trama que mueve SOLO C, desde donde esté la pala."""
    altura = int(altura)
    if altura < ALTURA_MINIMA:
        raise ValueError(
            f"{altura} está por debajo del tope ALTURA_MINIMA ({ALTURA_MINIMA})."
        )
    if altura > ALTURA_ARRIBA:
        raise ValueError(f"{altura} está por encima del tope superior ({ALTURA_ARRIBA}).")

    paso = ((angulo_actual, calcular_radio_grados(radio_actual), altura,
             angulo_garra_actual), _vel_tupla())
    return construir_tramas([paso]), altura


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
    """Modo voz: TOMA del estante y DEJA en el punto de descarga.

    El slot del estante aporta sus alturas de TOMA y la descarga las de DEJAR."""
    punto_nombre = f"{nombre}_{idx}"
    if punto_nombre not in puntos:
        raise ValueError(f"El punto '{punto_nombre}' no está definido.")

    cargar_alturas()   # toma la última calibración sin reiniciar SEpower

    secuencia, fases = _ciclo_pick_and_place(
        puntos[punto_nombre], puntos["descarga"],
        alt_origen=alturas_de(punto_nombre),
        alt_destino=alturas_de("descarga"),
    )
    return construir_tramas(secuencia), fases


def obtener_entrada_cam(nombre, idx):
    """Modo cam: TOMA de carga y DEJA en el estante.

    La carga aporta sus alturas de TOMA y el slot del estante las de DEJAR."""
    punto_nombre = f"{nombre}_{idx}"
    if punto_nombre not in puntos:
        raise ValueError(f"El punto '{punto_nombre}' no está definido.")

    cargar_alturas()   # toma la última calibración sin reiniciar SEpower

    secuencia, fases = _ciclo_pick_and_place(
        puntos["carga"], puntos[punto_nombre],
        alt_origen=alturas_de("carga"),
        alt_destino=alturas_de(punto_nombre),
    )
    return construir_tramas(secuencia), fases
