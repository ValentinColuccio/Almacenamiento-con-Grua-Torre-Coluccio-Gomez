import socket
import serial  # type:ignore
import threading
import queue
import re
import RPi.GPIO as GPIO #type:ignore
import cinematica as cin  # type:ignore
import subprocess
import time
from RPLCD.i2c import CharLCD #type:ignore

PC_IP = "10.186.157.39"                                                             #FIJATE IP PC

Espi = serial.Serial('/dev/ttyS0',115200, timeout=1)

HOST = ''
PORT = 65432
CHEQUEO_CADA = 15          
cola_comandos = queue.Queue()
cola_prioritaria = queue.Queue()
Flag = False
esp_listo = threading.Event()
PIN_IR = 4
DEBOUNCE = 0.2
COOLDOWN = 2
ultimo_trigger = 0
estado_pausa = threading.Event()
estado_pausa.set()
ultimo_comando = None
secuencia_actual = []
indice_actual = 0
lock_estado = threading.Lock()
conn_global = None
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_IR, GPIO.IN)
lock_conn = threading.Lock()

try:
    lcd = CharLCD(
    i2c_expander='PCF8574',
    address=0x27,
    port=1,
    cols=16,
    rows=2,
    charmap='A02',
    auto_linebreaks=True
    )
except:
    pass

# Registro de ocupación: dos espacios por punto
ocupacion = {
    "caja": [False, True],
    "bidon Uno": [False, True],
    "bidon Dos": [False, True],
    "carrete": [False, True],
    # descarga y carga no se controlan
}

def pantalla(caso, objeto=None):
    
    match caso:
        case 0:
            lcd.clear()
            lcd.write_string("Hola, bienvenido")
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Esperando orden")
        case 1:
            lcd.clear()
            lcd.write_string(f"Objeto:{objeto}")
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Almacenando.....")
        case 2:
            lcd.clear()
            lcd.write_string(f"Objeto:{objeto}")
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Entregando......")
        case 3:
            lcd.clear()
            lcd.write_string("Ningun objeto detectado")
            lcd.cursor_pos = (1, 0)
            lcd.write_string("     !!!!!!!")
        case 4:
            lcd.clear()
            lcd.write_string("Almcanamiento")
            lcd.cursor_pos = (1, 0)
            lcd.write_string("pedido lleno")
        case 5:
            lcd.clear()
            lcd.write_string("Comando de voz")
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Invalido")
        case 6:
            lcd.clear()
            lcd.write_string("Secuencia")
            lcd.cursor_pos = (1, 0)
            lcd.write_string("finalizada")
            pantalla(0)
                 
def escuchar_socket():  
    global Flag, cola_comandos, cola_prioritaria, esp_listo 
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((HOST, PORT))
                s.listen(1)
                print(f"[SOCKET]Esperando conexión en el puerto {PORT}...")

                global conn_global
                conn, addr = s.accept()
                conn_global = conn
                print(f"[SOCKET]Conectado por {addr}")
                try:pantalla(0) 
                except:pass
                with conn:
                    buffer = ""

                    while True:
                        data = conn.recv(1024).decode()
                        if not data:
                            print("[SOCKET] Cliente desconectado.")
                            break

                        buffer += data

                        while "\n" in buffer:
                            linea, buffer = buffer.split("\n", 1)
                            mensaje = linea.strip()

                            if not mensaje:
                                continue

                            if mensaje == "TRIGGER":
                                continue

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
    pc_presente = False

    while True:
        try:
            ok = subprocess.run(
                ["ping", "-c", "1", "-W", "2", PC_IP],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4
            ).returncode == 0

            if ok:
                if not pc_presente:
                    print("[WATCHDOG] PC detectada. Watchdog activo.")
                pc_presente = True
                fallo = 0
            else:
                if not pc_presente:
                    # Todavía no hubo conexión: NO hacer nada
                    time.sleep(CHEQUEO_CADA)
                    continue

                fallo += 1
                print(f"[WATCHDOG] PC no responde ({fallo}/3)")

            if pc_presente and fallo >= 3:
                print("[WATCHDOG] PC perdida. Reiniciando wlan0...")
                subprocess.run(["ip", "link", "set", "wlan0", "down"], timeout=3)
                time.sleep(2)
                subprocess.run(["ip", "link", "set", "wlan0", "up"], timeout=3)
                fallo = 0
                pc_presente = False   # vuelve al estado inicial

        except Exception as e:
            print(f"[WATCHDOG] Error watchdog: {e}")

        time.sleep(CHEQUEO_CADA)

def escuchar_esp():
    while True:
        try:
            if Espi.in_waiting > 0:
                raw = Espi.readline()
                linea = raw.decode(errors='ignore').strip()
                print(f"[ESP32] Mensaje recibido desde ESP32: {linea}")
                if "listo" in linea.lower():
                    esp_listo.set()
        except Exception as e:
            print(f"[ESP32][Error serie] {e}")            

def sensor_ir_loop():
    global ultimo_trigger

    estado_anterior = GPIO.input(PIN_IR)

    while True:
        estado_actual = GPIO.input(PIN_IR)

        # Detectar cambio de estado
        if estado_actual != estado_anterior:

            # 👉 cuando deja de detectar el objeto
            if estado_anterior == 0 and estado_actual == 1:

                ahora = time.time()

                if ahora - ultimo_trigger > COOLDOWN:
                    ultimo_trigger = ahora

                    print("[IR] TRIGGER")
                    
                    
                    with lock_conn:
                        if conn_global:
                            try:
                                conn_global.sendall(b"TRIGGER\n")
                            except:
                                pass

            estado_anterior = estado_actual

        time.sleep(0.01)

def seleccionar_posicion_libre(nombre):
    if nombre in ocupacion:
        for i in range(2):
            if not ocupacion[nombre][i]:
                return i
    return None

def procesar_comandos():
    global secuencia_actual, indice_actual
    global Flag, cola_comandos, cola_prioritaria, esp_listo 
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
                    try:pantalla(5) 
                    except:pass
                    continue

                pasos = cin.obtener_sec_voz(mensaje, idx)
                ocupacion[mensaje][idx] = False  # se libera el espacio
                try:pantalla(2, mensaje) 
                except:pass

            elif modo == "cam":
                idx = seleccionar_posicion_libre(mensaje)
                if idx is None:
                    print(f"No hay espacio libre en {mensaje}, omitiendo.")
                    try:pantalla(4)
                    except:pass
                    continue
                pasos = cin.obtener_entrada_cam(mensaje, idx)
                ocupacion[mensaje][idx] = True
                try:pantalla(1, mensaje)
                except:pass

            with lock_estado:
                secuencia_actual = pasos
                indice_actual = 0

            while indice_actual < len(secuencia_actual):

                estado_pausa.wait()  # ⛔ pausa

                # cinematica ya entrega la trama lista (con velocidades por motor)
                comando = secuencia_actual[indice_actual] + "\n"

                with lock_estado:
                    ultimo_comando = comando

                Espi.write(comando.encode())
                print(f"Mensaje enviado: {comando.strip()}")

                if not esp_listo.wait(timeout=50):
                    print("[ESP] Timeout - abortando secuencia")
                    break

                esp_listo.clear()

                with lock_estado:
                    indice_actual += 1

            print("[SEQ] Secuencia finalizada")
            try:pantalla(6) 
            except:pass

            # avisar a PC
            try:
                if conn_global:
                    try:
                        conn_global.sendall(b"SEQ_DONE\n")
                    except:
                        pass
            except:
                pass
        except ValueError as e:
            print(f"Error: {e}")

        Flag = False

# Iniciar los hilos
hilo_socket = threading.Thread(target=escuchar_socket, daemon=True)
hilo_watchdog = threading.Thread(target=wifi_watchdog, daemon=True)
hilo_esp = threading.Thread(target=escuchar_esp, daemon=True)
hilo_procesador = threading.Thread(target=procesar_comandos, daemon=True)
hilo_ir = threading.Thread(target=sensor_ir_loop, daemon=True)

hilo_socket.start()
hilo_watchdog.start()
hilo_esp.start()
hilo_procesador.start()
hilo_ir.start()

# Mantener el programa vivo
hilo_socket.join()





