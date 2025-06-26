import math

ORIGEN_X = 0
ORIGEN_Y = 0
MAX_ANGULO = 720
MIN_ANGULO = -720
angulo_actual = 0
angulo_garra_actual = 0

puntos = {
    "bidon uno_0": (-5, -5),
    "bidon uno_1": (-5.5, -5),
    "bidon dos_0": (-6, -5),
    "bidon dos_1": (-6.5, -5),
    "caja_0": (0, 150),
    "caja_1": (-5.5, -5),
    "carrete_0": (0, 150),
    "carrete_1": (-5.5, -6),
    "descarga": (-150, 0),
    "carga": (150, 0)
}

def cartesianas_a_polares(x, y):
    dx = x - ORIGEN_X
    dy = y - ORIGEN_Y
    angulo = math.degrees(math.atan2(dy, dx)) 
    distancia = math.hypot(dx, dy)            
    return angulo, distancia

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
    
    return 2*nuevo_angulo

def calcular_radio_grados(radio):
    R = 12 
    grados = -1*((radio * 180) / (math.pi * R))
    return grados

def calcular_angulo_garra(angulo_brazo):
    global angulo_garra_actual

    angulo_objetivo = -(angulo_brazo/2)
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

def obtener_sec_voz(nombre,idx):
    punto_nombre = f"{nombre}_{idx}"
    if punto_nombre not in puntos:
        raise ValueError(f"El punto '{punto_nombre}' no está definido.")
    
    x, y = puntos[punto_nombre]

    secuencia = []

    # 1. Ir al punto original
    angulo_destino, radio = cartesianas_a_polares(x, y)
    angulo_final = calcular_angulo_seguro(angulo_destino)
    angulo_garra = calcular_angulo_garra(angulo_final)
    radio_final = calcular_radio_grados(radio)
    secuencia.append((angulo_final, radio_final, -1440, angulo_garra))  # Bajar

    # 2. Moverse 60 mm hacia adelante (norte / +x)
    x2 = x + 60
    y2 = y
    angulo_adelante, radio_adelante = cartesianas_a_polares(x2, y2)
    angulo_final2 = calcular_angulo_seguro(angulo_adelante)
    angulo_garra2 = calcular_angulo_garra(angulo_final2)
    radio_final2 = calcular_radio_grados(radio_adelante)
    secuencia.append((angulo_final2, radio_final2, 2, angulo_garra2))  # Subir

    # 3. Ir al punto de descarga (x=10, y=10)
    x3, y3 = puntos["descarga"]
    angulo3, radio3 = cartesianas_a_polares(x3, y3)
    angulo_final3 = calcular_angulo_seguro(angulo3)
    radio_final3 = calcular_radio_grados(radio3)
    secuencia.append((angulo_final3, radio_final3, -1440, 180))  # Bajar

    # 4. Moverse 60 mm hacia atrás (sur / -x)
    x4 = x3 - 60
    y4 = y3
    angulo4, radio4 = cartesianas_a_polares(x4, y4)
    angulo_final4 = calcular_angulo_seguro(angulo4)
    radio_final4 = calcular_radio_grados(radio4)
    secuencia.append((angulo_final4, radio_final4, 2, 180))  # Subir

    return secuencia

def obtener_entrada_cam(nombre,idx):
    punto_nombre = f"{nombre}_{idx}"
    if punto_nombre not in puntos:
        raise ValueError(f"El punto '{punto_nombre}' no está definido.")

    secuencia = []

    # 1. Ir al punto carga
    x0, y0 = puntos["carga"]
    ang0, rad0 = cartesianas_a_polares(x0, y0)
    ang0f = calcular_angulo_seguro(ang0)
    garra0 = calcular_angulo_garra(ang0f)
    rad0f = calcular_radio_grados(rad0)
    secuencia.append((ang0f, rad0f, -1440, garra0))  # Bajar

    # 2. Moverse 60 mm hacia adelante desde carga
    x1 = x0 + 60
    ang1, rad1 = cartesianas_a_polares(x1, y0)
    ang1f = calcular_angulo_seguro(ang1)
    garra1 = calcular_angulo_garra(ang1f)
    rad1f = calcular_radio_grados(rad1)
    secuencia.append((ang1f, rad1f, 5, garra1))  # Subir

    # 3. Ir al punto destino + 60 mm
    x2, y2 = puntos[punto_nombre]
    x2 += 60
    ang2, rad2 = cartesianas_a_polares(x2, y2)
    ang2f = calcular_angulo_seguro(ang2)
    garra2 = calcular_angulo_garra(ang2f)
    rad2f = calcular_radio_grados(rad2)
    secuencia.append((ang2f, rad2f, -1440, garra2))  # Bajar

    # 4. Volver 60 mm atrás
    x3 = x2 - 60
    ang3, rad3 = cartesianas_a_polares(x3, y2)
    ang3f = calcular_angulo_seguro(ang3)
    garra3 = calcular_angulo_garra(ang3f)
    rad3f = calcular_radio_grados(rad3)
    secuencia.append((ang3f, rad3f, 5, garra3))  # Subir

    return secuencia

