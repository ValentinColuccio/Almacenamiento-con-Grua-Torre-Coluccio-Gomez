import socket
import serial  # type:ignore
import threading
import queue
import re
import RPi.GPIO as GPIO #type:ignore
import cinematica as cin  # type:ignore
import subprocess
import time

Ardu = serial.Serial('/dev/ttyS0', 9600, timeout=1)

HOST = ''
PORT = 65432
GATEWAY = "192.168.137.1"  
CHEQUEO_CADA = 15          
cola_comandos = queue.Queue()
cola_prioritaria = queue.Queue()
Flag = False
arduino_listo = threading.Event()

# Registro de ocupación: dos espacios por punto
ocupacion = {
    "caja uno": [True, False],
    "caja dos": [False, False],
    "caja tres": [False, False],
    "caja cuatro": [False, False],
    "cubito": [False, False],
    "perrito": [False, False]
    # descarga y carga no se controlan
}
                        
def escuchar_socket():
    global Flag, cola_comandos, cola_prioritaria, arduino_listo 
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((HOST, PORT))
                s.listen(1)
                print(f"Esperando conexión en el puerto {PORT}...")

                conn, addr = s.accept()
                print(f"Conectado por {addr}")
                with conn:
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            print("[SOCKET] Cliente desconectado.")
                            break
                        mensaje = data.decode().strip()
                        print(f"Mensaje recibido desde PC: {mensaje}")
                        if mensaje.lower().startswith("cam"):
                            cola_prioritaria.put(mensaje[3:].strip())
                        elif mensaje.lower().startswith("voz"):
                            cola_comandos.put(mensaje[3:].strip())
        except Exception as e:
            print(f"[SOCKET] Error de conexión: {e}")
            time.sleep(2)

def wifi_watchdog():
    fallo = 0
    while True:
        ok = subprocess.call(["ping", "-c", "1", "-W", "2", GATEWAY],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL) == 0
        if ok:
            fallo = 0
        else:
            fallo += 1

        if fallo >= 3:
            print("[WIFI] Reiniciando interfaz wlan0...")
            subprocess.call(["sudo", "ifconfig", "wlan0", "down"])
            time.sleep(2)
            subprocess.call(["sudo", "ifconfig", "wlan0", "up"])
            fallo = 0
        time.sleep(CHEQUEO_CADA)

def escuchar_arduino():
    while True:
        try:
            if Ardu.in_waiting > 0:
                raw = Ardu.readline()
                linea = raw.decode(errors='ignore').strip()
                print(f"Mensaje recibido desde Arduino: {linea}")
                if "listo" in linea.lower():
                    arduino_listo.set()
        except Exception as e:
            print(f"[Error serie] {e}")            

def seleccionar_posicion_libre(nombre):
    if nombre in ocupacion:
        for i in range(2):
            if not ocupacion[nombre][i]:
                return i
    return None

def procesar_comandos():
    global Flag, cola_comandos, cola_prioritaria, arduino_listo 
    while True:
        # Revisar primero si hay comandos prioritarios
        try:
            mensaje = cola_prioritaria.get_nowait()
            modo = "cam"
        except queue.Empty:
            try:
                mensaje = cola_comandos.get(timeout=1)
                modo = "voz"
            except queue.Empty:
                continue  # ninguna cola tiene datos, reintenta

        print(f"[{modo.upper()}] Procesando: {mensaje}")    

        try:
            if modo == "voz":
                # Buscar qué posición está ocupada
                idx = None
                for i in range(2):
                    if mensaje in ocupacion and ocupacion[mensaje][i]:
                        idx = i
                        break

                if idx is None:
                    print(f"No hay objeto en {mensaje} para recoger. Omitido.")
                    continue

                pasos = cin.obtener_sec_voz(mensaje, idx)
                ocupacion[mensaje][idx] = False  # se libera el espacio

            elif modo == "cam":
                idx = seleccionar_posicion_libre(mensaje)
                if idx is None:
                    print(f"No hay espacio libre en {mensaje}, omitiendo.")
                    continue
                pasos = cin.obtener_entrada_cam(mensaje, idx)
                ocupacion[mensaje][idx] = True

            for angulo, distancia, subir, garra in pasos:
                comando = f"A:{angulo:.1f};B:{distancia:.1f};C:{subir:.1f};D:{int(garra)}\n"
                Ardu.write(comando.encode())
                print(f"Mensaje enviado: {comando.strip()}")
                arduino_listo.clear()
                arduino_listo.wait()  # espera confirmación
        except ValueError as e:
            print(f"Error: {e}")

        Flag = False

# Iniciar los hilos
hilo_socket = threading.Thread(target=escuchar_socket, daemon=True)
hilo_watchdog = threading.Thread(target=wifi_watchdog, daemon=True)
hilo_arduino = threading.Thread(target=escuchar_arduino, daemon=True)
hilo_procesador = threading.Thread(target=procesar_comandos, daemon=True)

hilo_socket.start()
hilo_watchdog.start()
hilo_arduino.start()
hilo_procesador.start()

# Mantener el programa vivo
hilo_socket.join()
