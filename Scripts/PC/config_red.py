"""Configuración de red del sistema, editable desde el HMI.

Las IPs cambian en cada arranque porque el AP es un celular: no se puede
reservar una IP fija ni asumir la subred (cambia el /24 entero). Por eso acá no
hay ninguna IP hardcodeada en los scripts; se leen de 'config_red.json', que el
HMI escribe desde su diálogo de configuración.

Orden de resolución: variable de entorno -> archivo -> valor por defecto.
La variable de entorno la pone el HMI cuando lanza TTpower, así que los dos
procesos siempre coinciden sin releer nada.
"""

import ipaddress
import json
import os
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO = BASE_DIR / "config_red.json"

PUERTO_SSH = 22          # el que se barre para descubrir la Raspberry
PUERTO_SEPOWER = 65432   # socket de SEpower: NO barrerlo (ver descubrir())

NOMBRE_MDNS = "grua.local"

POR_DEFECTO = {
    "ip_rpi": NOMBRE_MDNS,
    "ip_camara": "192.168.3.11",   # otra subred, fija: no depende del celular
}


# --------------------------------------------------------------------------
# Lectura / escritura
# --------------------------------------------------------------------------

def cargar():
    """Config completa, con los valores por defecto para lo que falte."""
    datos = dict(POR_DEFECTO)
    try:
        datos.update(json.loads(ARCHIVO.read_text(encoding="utf-8")))
    except Exception:
        pass
    return datos


def guardar(datos):
    completa = cargar()
    completa.update(datos)
    ARCHIVO.write_text(json.dumps(completa, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    return completa


def ip_rpi():
    return os.environ.get("TT_IP_RPI") or cargar()["ip_rpi"]


def ip_camara():
    return os.environ.get("TT_IP_CAMARA") or cargar()["ip_camara"]


# --------------------------------------------------------------------------
# Prueba y descubrimiento
# --------------------------------------------------------------------------

def probar(host, puerto=PUERTO_SSH, timeout=2.0):
    """True si el host acepta conexión en ese puerto."""
    if not host:
        return False
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except OSError:
        return False


def _es_ssh(host, timeout=1.0):
    """Lee el banner: sirve para no confundir la Pi con otro equipo."""
    try:
        with socket.create_connection((host, PUERTO_SSH), timeout=timeout) as s:
            s.settimeout(timeout)
            return "SSH" in s.recv(64).decode(errors="ignore")
    except OSError:
        return False


def resolver(nombre, timeout=1.5):
    """IP de un nombre, o None si no resuelve a tiempo.

    Va en un hilo aparte porque el timeout de create_connection() NO cubre la
    resolución de nombres: si 'grua.local' no existe, el DNS del sistema puede
    tardar 7 segundos antes de fallar.
    """
    resultado = {}

    def _tarea():
        try:
            resultado["ip"] = socket.gethostbyname(nombre)
        except OSError:
            pass

    h = threading.Thread(target=_tarea, daemon=True)
    h.start()
    h.join(timeout)
    return resultado.get("ip")


def ip_local():
    """IP de esta PC en la red del celular. Define qué subred barrer."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No manda nada: solo fuerza al SO a elegir la interfaz de salida.
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return ""
    finally:
        s.close()


def descubrir(timeout_host=0.5):
    """Busca la Raspberry en la red y devuelve la lista de candidatos.

    Primero prueba el nombre mDNS (instantáneo si el AP deja pasar multicast).
    Si no, barre la subred de esta PC.

    Se barre el 22 y NO el 65432 a propósito: el servidor de SEpower acepta un
    cliente por vez, así que conectarse ahí le robaría el 'conn_global' a
    TTpower y le cortaría los TRIGGER del sensor IR.
    """
    # mDNS primero, pero con la resolución acotada: si el AP no deja pasar
    # multicast, no tiene sentido esperar al DNS del sistema.
    if resolver(NOMBRE_MDNS) and probar(NOMBRE_MDNS, timeout=1.5):
        return [NOMBRE_MDNS]

    propia = ip_local()
    if not propia:
        return []

    red = ipaddress.ip_network(f"{propia}/24", strict=False)
    hosts = [str(h) for h in red.hosts() if str(h) != propia]

    with ThreadPoolExecutor(max_workers=256) as pool:
        abiertos = list(pool.map(
            lambda h: probar(h, timeout=timeout_host), hosts))

    candidatos = [h for h, ok in zip(hosts, abiertos) if ok]
    return [h for h in candidatos if _es_ssh(h)]
