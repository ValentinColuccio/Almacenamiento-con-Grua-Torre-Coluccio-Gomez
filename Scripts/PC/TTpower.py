import multiprocessing as mp
import socket
import time
import queue
import sounddevice as sd
import json
import numpy as np
import vosk
import os

# --------------- CONFIGURACIÓN ---------------

GUI_MODE = os.environ.get("TT_GUI", "0") == "1"

IP_RPI = '172.28.49.9'

HOST = IP_RPI
PORT = 65432
samplerate = 16000
IP_CAMARA = '192.168.3.11'   
PORT_CAMARA = 2006   

# --------------- FUNCIONES ---------------

def crear_socket_con_keepalive():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    return s

def conectar_raspiz():
    while True:
        try:
            s = crear_socket_con_keepalive()
            s.connect((HOST, PORT))
            print("[SOCKET] Conectado a la Raspberry Pi.", flush=True)
            return s
        except Exception as e:
            print(f"[SOCKET] Error al conectar la Raspberry Pi. Reintentando...", flush=True)
            time.sleep(2)

def conectar_camara_socket():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((IP_CAMARA, PORT_CAMARA))
            print("[CAM] Conectado a la cámara inteligente.", flush=True)
            return s
        except Exception:
            print("[CAM] Error conectando cámara. Reintentando...", flush=True)
            time.sleep(2)

def reconocimiento_por_voz(colavoz):
    model_vosk = vosk.Model("C:/Users/valen/OneDrive/Mis cosas/Facu/GitHub/Almacenamiento-con-Grua-Torre-Coluccio-Gomez/software/PC/vosk-model-small-es-0.42")
    rec = vosk.KaldiRecognizer(model_vosk, samplerate)
    mic = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, flush=True)
        mic.put(bytes(indata))

    Flag = False
    with sd.RawInputStream(samplerate=samplerate, blocksize=500, dtype='int16', channels=1, callback=callback):
        print("[VOZ] Diga algo...", flush=True)
        while True:
            data = mic.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                mensaje = result.get("text", "")
                if mensaje.lower() == 'salir':
                    print("[VOZ] Saliendo por voz.", flush=True)
                    break
                if not Flag and "torre" in mensaje.lower():
                    Flag = True
                    print("[VOZ] Activado", flush=True)
                elif Flag:
                    print(f"[VOZ] Interpretado: {mensaje}", flush=True)
                    colavoz.put(f"voz {mensaje}")
                    Flag = False

def deteccion_por_camara(colacam, cola_trigger):
    sock_cam = conectar_camara_socket()

    while True:
        trigger = cola_trigger.get()  

        if trigger == "TRIGGER":
            try:
                sock_cam.sendall(b"TRX000")
                print("[CAM] Trigger enviado", flush=True)

                data = sock_cam.recv(1024).decode().strip()

                if data:
                    OBJETOS_VALIDOS = [
                        "cajauno", "cajados", "cajatres",
                        "cajacuatro", "cubito", "perrito"
                    ]

                    objeto_detectado = None

                    for obj in OBJETOS_VALIDOS:
                        if obj in data:
                            objeto_detectado = obj
                            break

                    if objeto_detectado:
                        # Convertir a formato con espacio (como usa tu sistema)
                        objeto_formateado = objeto_detectado.replace("caja", "caja ")

                        print(f"[CAM] Detectado: {objeto_formateado}")

                        colacam.put(f"cam {objeto_formateado}")
                    else:
                        print("[CAM] Sin detección")

            except (ConnectionResetError, BrokenPipeError):
                print("[CAM] Reconectando cámara...", flush=True)
                sock_cam = conectar_camara_socket()

def despachador(colacam, colavoz, cola_trigger):
    sock = conectar_raspiz()
    buffer = ""
    while True:
        try:
            data = sock.recv(1024).decode()
            buffer += data
            
            while "\n" in buffer:
                linea, buffer = buffer.split("\n", 1)
                if linea == "TRIGGER":
                    cola_trigger.put("TRIGGER")
                    continue
                

            mensaje = None
            if not colacam.empty():
                mensaje = colacam.get()
            elif not colavoz.empty():
                mensaje = colavoz.get()

            if mensaje:
                #print(f"[SOCKET] Enviando: {mensaje}", flush=True)
                sock.sendall((mensaje + "\n").encode())

        except (ConnectionResetError, BrokenPipeError):
            print("[SOCKET] Reconectando...", flush=True)
            sock = conectar_raspiz()
        time.sleep(0.1)


# --------------- EJECUCIÓN PRINCIPAL ---------------

if __name__ == '__main__':
    mp.set_start_method('spawn')  # importante en Windows
    
    colacam = mp.Queue()
    colavoz = mp.Queue()
    cola_trigger = mp.Queue()

    p1 = mp.Process(target=deteccion_por_camara, args=(colacam, cola_trigger))
    p2 = mp.Process(target=reconocimiento_por_voz, args=(colavoz,))
    p3 = mp.Process(target=despachador, args=(colacam, colavoz, cola_trigger))

    p1.start()
    p2.start()
    p3.start()

    p1.join()
    p2.join()
    p3.join()
    
    


