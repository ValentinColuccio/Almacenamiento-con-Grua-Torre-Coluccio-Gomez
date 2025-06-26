import cv2
import time
import numpy as np
from keras.models import load_model
from multiprocessing import Process, Queue
from threading import Thread

# Configuraciones
cam_url = "http://192.168.137.225:4747/video"
model_path = "C:/Users/valen/OneDrive/Mis cosas/Facu/Cuat/GitHub/Almacenamiento-con-Grua-Torre-Coluccio-Gomez/software/PC/keras_model.h5"
IMG_SIZE = (224, 224)
TIEMPO_REQUERIDO = 5  # segundos
THRESHOLD = 0.90
clases = ["bidon uno", "bidon dos", "caja", "carrete", "libre"]

def esperar_desaparicion(frame_queue, modelo, esperando_flag, timeout=120):
    print("⏳ Esperando desaparición del objeto.")
    inicio = time.time()
    while time.time() - inicio < timeout:
        if not frame_queue.empty():
            frame = frame_queue.get()
            input_img = cv2.resize(frame, IMG_SIZE) / 255.0
            input_img = np.expand_dims(input_img, axis=0)

            pred = modelo.predict(input_img, verbose=0)
            clase = clases[np.argmax(pred)]
            if clase == 'libre':
                print("✅ Objeto retirado.")
                esperando_flag[0] = False
                return
        time.sleep(0.3)
    print("⚠️ Timeout esperando desaparición. Continuando de todos modos.")
    esperando_flag[0] = False

def captura_video(frame_queue):
    cap = cv2.VideoCapture(cam_url)
    while True:
        ret, frame = cap.read()
        if ret:
            frame_queue.put(frame)
        time.sleep(0.2)

def inferencia_modelo(frame_queue, salida_queue):
    modelo = load_model(model_path)
    ultima_clase = None
    tiempo_inicio = 0
    esperando_flag = [False]  # Lista para mutabilidad compartida

    while True:
        if not frame_queue.empty():
            frame = frame_queue.get()
            input_img = cv2.resize(frame, IMG_SIZE) / 255.0
            input_img = np.expand_dims(input_img, axis=0)

            pred = modelo.predict(input_img, verbose=0)
            clase_actual = clases[np.argmax(pred)]
            prob = np.max(pred)

            # Mostrar info en pantalla
            texto = f"{clase_actual} ({prob*100:.1f}%)"
            color = (0, 255, 0) if prob > THRESHOLD else (0, 255, 255)
            cv2.putText(frame, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.imshow("Detección desde DroidCam", frame)

            if prob > THRESHOLD and not esperando_flag[0]:
                if clase_actual != "libre":
                    if clase_actual == ultima_clase:
                        if time.time() - tiempo_inicio >= TIEMPO_REQUERIDO:
                            salida_queue.put(f"cam {clase_actual}")
                            print(f"📷 Detectado cam: {clase_actual}")
                            esperando_flag[0] = True
                            t = Thread(
                                target=esperar_desaparicion,
                                args=(frame_queue, modelo, esperando_flag),
                                daemon=True
                            )
                            t.start()
                            ultima_clase = None
                    else:
                        ultima_clase = clase_actual
                        tiempo_inicio = time.time()
                else:
                    ultima_clase = None

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()
    
def iniciar_camara(salida_queue):
    frame_queue = Queue()
    t1 = Thread(target=captura_video, args=(frame_queue,), daemon=True)
    t2 = Thread(target=inferencia_modelo, args=(frame_queue, salida_queue), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()