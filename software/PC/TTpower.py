import sounddevice as sd
import queue
import vosk
import json
import socket
import threading
import time
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model   #type: ignore

# ---------------- CONFIGURACIÓN ----------------

HOST = '192.168.137.134'
PORT = 65432
cam_url = "http://192.168.137.104:4747/video"
model_path = "C:/Users/valen/OneDrive/Mis cosas/Facu/Cuat/1-5B-Proyecto Final/Codigos/PC/keras_model.h5"
clases = ['cubito', 'perrito']
IMG_SIZE = (224, 224)
THRESHOLD = 0.95
TIEMPO_REQUERIDO = 7  # en segundos

# ---------------- VOSK (Reconocimiento de voz) ----------------

mic = queue.Queue()
Flag = False
samplerate = 16000
model_vosk = vosk.Model("C:/Users/valen/OneDrive/Mis cosas/Facu/Cuat/1-5B-Proyecto Final/Codigos/PC/vosk-model-small-es-0.42")
rec = vosk.KaldiRecognizer(model_vosk, samplerate)

def callback(indata, frames, time, status):
    if status:
        print(status)
    mic.put(bytes(indata))

# ---------------- DETECCIÓN POR CÁMARA ----------------

def deteccion_por_camara(sock):
    modelo = load_model(model_path)
    cap = cv2.VideoCapture(cam_url)

    ultima_clase = None
    tiempo_inicio = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        input_img = cv2.resize(frame, IMG_SIZE)
        input_img = input_img / 255.0
        input_img = np.expand_dims(input_img, axis=0)

        pred = modelo.predict(input_img, verbose=0)
        idx = np.argmax(pred)
        prob = np.max(pred)
        clase_actual = clases[idx]

        if prob > THRESHOLD:
            if clase_actual == ultima_clase:
                if time.time() - tiempo_inicio >= TIEMPO_REQUERIDO:
                    mensaje = f"cam {clase_actual}"
                    print(f"📷 Enviando por cámara: {mensaje}")
                    sock.sendall(mensaje.encode())
                    ultima_clase = None  # reiniciar después de enviar
            else:
                ultima_clase = clase_actual
                tiempo_inicio = time.time()
        else:
            ultima_clase = None  # reiniciar si probabilidad baja

        # Mostrar en ventana opcional
        texto = f"{clase_actual} ({prob*100:.1f}%)"
        color = (0, 255, 0) if prob > 0.8 else (0, 255, 255)
        cv2.putText(frame, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.imshow("Detección desde DroidCam (IP)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
        time.sleep(0.1)

    cap.release()
    cv2.destroyAllWindows()

# ---------------- CONEXIÓN Y CICLO PRINCIPAL ----------------

def crear_socket_con_keepalive():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    return s

def conectar_raspiz():
    while True:
        try:
            s = crear_socket_con_keepalive()
            s.connect((HOST, PORT))
            print("✅ Conectado a la Raspberry Pi.")
            return s
        except Exception as e:
            print(f"[CONEXIÓN] Error al conectar: {e}. Reintentando en 3s...")
            time.sleep(3)

Raspiz = conectar_raspiz()

# Iniciar hilo para cámara
hilo_camara = threading.Thread(target=deteccion_por_camara, args=(Raspiz,))
hilo_camara.daemon = True
hilo_camara.start()

# Iniciar stream de audio
with sd.RawInputStream(samplerate=samplerate, blocksize=500, dtype='int16', channels=1, callback=callback):
    print('🎤 Decí algo: ')
    while True:
        data = mic.get()
        if rec.AcceptWaveform(data):
            resultado = json.loads(rec.Result())
            mensaje = resultado.get("text", "")
            
            if mensaje.lower() == 'salir':
                print("⛔ Cerrando conexión por comando de voz.")
                break
            if not Flag and "torre" in mensaje.lower():
                print("📢 Habilitado")
                Flag = True
            elif Flag:
                print("📢 Enviando:", mensaje)
                Raspiz.sendall(('voz ' + mensaje).encode())
                Flag = False
            elif mensaje:
                print("📢 No valido:", mensaje)