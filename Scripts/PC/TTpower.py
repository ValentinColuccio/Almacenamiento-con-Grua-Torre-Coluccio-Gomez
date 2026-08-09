import multiprocessing as mp
import socket
import time
import queue
import sounddevice as sd
import json
import numpy as np
import vosk
import os
import sys
import signal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELO_VOSK = BASE_DIR / "vosk-model-small-es-0.42"

# --------------- CONFIGURACIÓN ---------------

GUI_MODE = os.environ.get("TT_GUI", "0") == "1"

IP_RPI = "10.13.16.9"

HOST = IP_RPI
PORT = 65432
samplerate = 16000
IP_CAMARA = '192.168.3.11'
PORT_CAMARA = 2006

SHUTDOWN = "__SHUTDOWN__"   # sentinela interno: pedido de apagado total

# --------------- FUNCIONES ---------------

def ignorar_senales():
    """En los subprocesos: la salida la coordina el proceso principal."""
    for nombre in ("SIGINT", "SIGBREAK", "SIGTERM"):
        try:
            signal.signal(getattr(signal, nombre), signal.SIG_IGN)
        except (AttributeError, ValueError, OSError):
            pass

def crear_socket_con_keepalive():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    return s

def conectar_raspiz(parar):
    while not parar.is_set():
        try:
            s = crear_socket_con_keepalive()
            s.settimeout(3)
            s.connect((HOST, PORT))
            s.settimeout(None)
            print("[SOCKET] Conectado a la Raspberry Pi.", flush=True)
            return s
        except Exception as e:
            print(f"[SOCKET] Error al conectar la Raspberry Pi. Reintentando...", flush=True)
            parar.wait(2)   # duerme 2 s pero se despierta si piden apagar
    return None

def conectar_camara_socket(parar):
    while not parar.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((IP_CAMARA, PORT_CAMARA))
            print("[CAM] Conectado a la cámara inteligente.", flush=True)
            return s
        except Exception:
            print("[CAM] Error conectando cámara. Reintentando...", flush=True)
            parar.wait(2)
    return None

def reconocimiento_por_voz(colavoz, parar, salir_pedido):
    ignorar_senales()

    if not MODELO_VOSK.exists():
        raise FileNotFoundError(
            f"No se encontró el modelo de Vosk en {MODELO_VOSK}. "
            "Descargar desde https://alphacephei.com/vosk/models y descomprimir ahí."
        )
    model_vosk = vosk.Model(str(MODELO_VOSK))
    rec = vosk.KaldiRecognizer(model_vosk, samplerate)
    mic = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, flush=True)
        mic.put(bytes(indata))

    Flag = False
    try:
        with sd.RawInputStream(samplerate=samplerate, blocksize=500, dtype='int16', channels=1, callback=callback):
            print("[VOZ] Diga algo...", flush=True)
            while not parar.is_set():
                try:
                    data = mic.get(timeout=0.2)
                except queue.Empty:
                    continue

                if not rec.AcceptWaveform(data):
                    continue

                result = json.loads(rec.Result())
                mensaje = result.get("text", "").strip().lower()
                if not mensaje:
                    continue

                palabras = mensaje.split()

                # Apagado total: exige la palabra de activación, en la misma
                # frase ("torre salir") o habiendo activado antes.
                if "salir" in palabras and ("torre" in mensaje or Flag):
                    print("[VOZ] Orden de salida confirmada. Apagando el sistema...", flush=True)
                    colavoz.put(SHUTDOWN)
                    salir_pedido.set()
                    break

                # Continuar después de una parada de emergencia. Va como mensaje
                # de protocolo, no como comando de objeto: la Raspberry lo atiende
                # en el hilo del socket, que no está bloqueado por la secuencia.
                if "continuar" in palabras and ("torre" in mensaje or Flag):
                    print("[VOZ] Orden de continuar confirmada.", flush=True)
                    colavoz.put("CONTINUAR")
                    Flag = False
                    continue

                if not Flag and "torre" in mensaje:
                    Flag = True
                    print("[VOZ] Activado", flush=True)
                elif Flag:
                    print(f"[VOZ] Interpretado: {mensaje}", flush=True)
                    colavoz.put(f"voz {mensaje}")
                    Flag = False
    finally:
        print("[VOZ] Reconocimiento detenido.", flush=True)

def deteccion_por_camara(colacam, cola_trigger, parar):
    ignorar_senales()

    sock_cam = conectar_camara_socket(parar)

    try:
        while not parar.is_set():
            try:
                trigger = cola_trigger.get(timeout=0.2)
            except queue.Empty:
                continue

            if trigger != "TRIGGER" or sock_cam is None:
                continue

            try:
                sock_cam.settimeout(5)
                sock_cam.sendall(b"TRX000")
                print("[CAM] Trigger enviado", flush=True)

                data = sock_cam.recv(1024).decode().strip()
                if not data:
                    raise ConnectionResetError("La cámara cerró la conexión")

                OBJETOS_VALIDOS = [
                    "caja", "bidonuno", "bidondos",
                    "carrete", "vacio"
                ]

                objeto_detectado = None

                for obj in OBJETOS_VALIDOS:
                    if obj in data:
                        objeto_detectado = obj
                        break
                if objeto_detectado == "Vacio":
                    print("[CAM] Detectado: Vacio", flush=True)

                elif objeto_detectado:
                    # Convertir a formato con espacio (como usa tu sistema)
                    objeto_formateado = objeto_detectado.replace("bidon", "bidon ")

                    print(f"[CAM] Detectado: {objeto_formateado}", flush=True)

                    colacam.put(f"cam {objeto_formateado}")
                else:
                    print("[CAM] Sin detección", flush=True)

            except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError):
                if parar.is_set():
                    break
                print("[CAM] Reconectando cámara...", flush=True)
                try:
                    sock_cam.close()
                except Exception:
                    pass
                sock_cam = conectar_camara_socket(parar)
    finally:
        try:
            if sock_cam:
                sock_cam.close()
        except Exception:
            pass
        print("[CAM] Detección detenida.", flush=True)

def despachador(colacam, colavoz, cola_trigger, parar):
    ignorar_senales()

    sock = conectar_raspiz(parar)
    if sock is None:
        parar.set()
        return

    sock.settimeout(0.1)

    buffer = ""

    try:
        while not parar.is_set():
            try:
                try:
                    data = sock.recv(1024).decode()
                    if not data:
                        raise ConnectionResetError("La Raspberry cerró la conexión")
                    buffer += data
                except socket.timeout:
                    pass

                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    if linea.strip() == "TRIGGER":
                        cola_trigger.put("TRIGGER")

                mensaje = None
                if not colacam.empty():
                    mensaje = colacam.get()
                elif not colavoz.empty():
                    mensaje = colavoz.get()

                if mensaje == SHUTDOWN:
                    print("[SOCKET] Enviando SHUTDOWN a la Raspberry Pi...", flush=True)
                    try:
                        sock.sendall(b"SHUTDOWN\n")
                        time.sleep(0.5)   # que la trama salga antes de cerrar
                        print("[SOCKET] SHUTDOWN enviado.", flush=True)
                    except OSError:
                        print("[SOCKET] No se pudo avisar a la Raspberry Pi.", flush=True)
                    break

                if mensaje:
                    sock.sendall((mensaje + "\n").encode())

            except socket.timeout:
                pass
            except (ConnectionResetError, BrokenPipeError, OSError):
                if parar.is_set():
                    break
                print("[SOCKET] Reconectando...", flush=True)
                try:
                    sock.close()
                except Exception:
                    pass
                sock = conectar_raspiz(parar)
                if sock is None:
                    break
                sock.settimeout(0.1)

            time.sleep(0.05)
    finally:
        try:
            sock.close()
        except Exception:
            pass
        parar.set()   # si cae el despachador, se apaga todo el sistema
        print("[SOCKET] Despachador detenido.", flush=True)


# --------------- EJECUCIÓN PRINCIPAL ---------------

def apagar(procesos, timeout=3.0):
    """Baja los subprocesos: primero por las buenas, después a la fuerza."""
    limite = time.time() + timeout
    for p in procesos:
        p.join(max(0.1, limite - time.time()))

    for p in procesos:
        if p.is_alive():
            print(f"[MAIN] Forzando cierre de '{p.name}'...", flush=True)
            p.terminate()

    for p in procesos:
        p.join(1.0)
        if p.is_alive():
            p.kill()

    print("[MAIN] Sistema detenido.", flush=True)
    sys.stdout.flush()
    # Salida inmediata: evita que los hilos internos de mp.Queue
    # dejen el intérprete colgado al cerrar.
    os._exit(0)


if __name__ == '__main__':
    mp.set_start_method('spawn')  # importante en Windows

    colacam = mp.Queue()
    colavoz = mp.Queue()
    cola_trigger = mp.Queue()

    parar = mp.Event()          # orden de apagado para todos los subprocesos
    salir_pedido = mp.Event()   # se pidió "torre salir" por voz

    procesos = [
        mp.Process(target=deteccion_por_camara,
                   args=(colacam, cola_trigger, parar), name="camara"),
        mp.Process(target=reconocimiento_por_voz,
                   args=(colavoz, parar, salir_pedido), name="voz"),
        mp.Process(target=despachador,
                   args=(colacam, colavoz, cola_trigger, parar), name="despachador"),
    ]

    def pedir_apagado(signum, frame):
        print("[MAIN] Señal de apagado recibida.", flush=True)
        parar.set()

    signal.signal(signal.SIGINT, pedir_apagado)
    for extra in ("SIGBREAK", "SIGTERM"):
        try:
            signal.signal(getattr(signal, extra), pedir_apagado)
        except (AttributeError, ValueError, OSError):
            pass

    for p in procesos:
        p.start()

    limite_salida = None
    try:
        while not parar.is_set():
            # Tras un "torre salir", damos 3 s para avisar a la Raspberry
            if salir_pedido.is_set() and limite_salida is None:
                limite_salida = time.time() + 3

            if limite_salida is not None and time.time() > limite_salida:
                print("[MAIN] Salida forzada (sin confirmación de la Raspberry).", flush=True)
                break

            if not any(p.is_alive() for p in procesos):
                break

            time.sleep(0.1)
    except KeyboardInterrupt:
        print("[MAIN] Interrupción por teclado.", flush=True)
    finally:
        parar.set()
        apagar(procesos)
