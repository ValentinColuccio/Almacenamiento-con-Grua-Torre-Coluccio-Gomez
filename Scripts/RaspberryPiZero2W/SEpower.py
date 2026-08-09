import socket
import serial  # type:ignore
import threading
import queue
import re
import RPi.GPIO as GPIO #type:ignore
import cinematica as cin  # type:ignore
import subprocess
import signal
import sys
import os
import time
import unicodedata
from RPLCD.i2c import CharLCD #type:ignore

PC_IP = "10.13.16.39"

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
parando = threading.Event()   # apagado en curso: los hilos sueltan el hardware
emergencia = threading.Event()    # parada de emergencia activa
en_movimiento = threading.Event() # hay una secuencia ejecutándose en la grúa

# Si la ESP32 queda latcheada después de un STOP y necesita una trama para
# volver a aceptar comandos, ponerla acá (ej: b"RESUME\n"). Con None se le
# reenvía directamente el paso interrumpido.
CMD_DESBLOQUEO = None
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

def normalizar(texto):
    """Forma canónica de un nombre de objeto: minúsculas, sin tildes y con los
    espacios colapsados.

    Hace falta porque las dos fuentes escriben distinto: la cámara manda
    'bidonuno' -> 'bidon uno' sin tilde, y Vosk puede devolver 'bidón uno' con
    tilde. Adentro se usa siempre la forma sin tilde."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())

# Registro de ocupación: dos espacios por punto.
# Las claves van SIN tilde: todo lo que entra pasa por normalizar().
ocupacion = {
    "caja": [False, True],
    "bidon uno": [False, True],
    "bidon dos": [False, True],
    "carrete": [False, True],
    # descarga y carga no se controlan
}

def emitir_ocupacion():
    """Publica el estado del estante para el mímico del HMI.
    Formato: [OCUP] caja=01;bidón uno=10;..."""
    partes = [f"{k}=" + "".join("1" if v else "0" for v in vals)
              for k, vals in ocupacion.items()]
    print("[OCUP] " + ";".join(partes), flush=True)

LCD_COLS = 16
LCD_ROWS = 2
PAUSA_MENSAJE = 1.5   # s que queda visible un mensaje antes de volver al reposo

def _repartir(texto):
    """Parte una frase entre los dos renglones lo más parejo posible, sin
    cortar palabras y sin pasarse del ancho del display."""
    palabras = texto.split()
    if not palabras:
        return ["", ""]

    mejor = None
    for corte in range(1, len(palabras)):
        arriba = " ".join(palabras[:corte])
        abajo = " ".join(palabras[corte:])
        if len(arriba) > LCD_COLS or len(abajo) > LCD_COLS:
            continue
        desbalance = abs(len(arriba) - len(abajo))
        if mejor is None or desbalance < mejor[0]:
            mejor = (desbalance, arriba, abajo)

    if mejor:
        return [mejor[1], mejor[2]]

    # Una sola palabra, o ninguna partición entra: cortar a lo bruto
    entero = " ".join(palabras)
    if len(entero) <= LCD_COLS:
        return [entero, ""]
    return [entero[:LCD_COLS], entero[LCD_COLS:LCD_COLS * 2]]

def _mostrar(*partes):
    """Escribe en el LCD en MAYÚSCULAS y centrado en los dos renglones.

    Con una sola parte la reparte sola entre las dos alturas; con dos, una por
    renglón (para respetar el corte semántico de la frase)."""
    partes = [str(p).strip().upper() for p in partes if p is not None and str(p).strip()]

    if len(partes) == 1:
        renglones = _repartir(partes[0])
    else:
        renglones = (partes + ["", ""])[:LCD_ROWS]

    lcd.clear()
    for fila, texto in enumerate(renglones[:LCD_ROWS]):
        lcd.cursor_pos = (fila, 0)
        lcd.write_string(texto[:LCD_COLS].center(LCD_COLS))

def pantalla(caso, objeto=None):

    match caso:
        case 0:
            _mostrar("BIENVENIDO", "ESPERANDO ORDEN")
        case 1:
            _mostrar(objeto, "ALMACENANDO...")
        case 2:
            _mostrar(objeto, "ENTREGANDO...")
        case 3:
            _mostrar("NINGUN OBJETO", "DETECTADO")
        case 4:
            _mostrar("ALMACENAMIENTO", "LLENO")
        case 5:
            _mostrar("COMANDO DE VOZ", "INVALIDO")
        case 6:
            _mostrar("SECUENCIA", "FINALIZADA")
            time.sleep(PAUSA_MENSAJE)   # si no, pantalla(0) lo tapa al instante
            pantalla(0)
        case 7:
            _mostrar("PARADA DE", "EMERGENCIA")
        case 8:
            _mostrar("REANUDANDO", "SECUENCIA...")
        case 9:
            _mostrar("SISTEMA", "DETENIDO")
        case 10:
            _mostrar("OBSTACULO EN", "LA ENTRADA")
        case 11:
            _mostrar("DESENCLAVADA", "ESPERANDO ORDEN")
                 
def parada_emergencia(motivo="manual", lcd=7):
    """Clava los frenos de la ESP32 y congela la secuencia donde esté."""
    if emergencia.is_set():
        print("[EMERGENCIA] Ya estaba activa.", flush=True)
        return

    emergencia.set()
    estado_pausa.clear()      # procesar_comandos no manda ninguna trama más

    try:
        Espi.write(b"STOP\n")
        Espi.flush()
        print(f"[EMERGENCIA] STOP enviado a la ESP32 ({motivo}).", flush=True)
    except Exception as e:
        print(f"[EMERGENCIA][ERR] No se pudo enviar STOP: {e}", flush=True)

    with lock_estado:
        paso, total = indice_actual + 1, len(secuencia_actual)

    if total:
        print(f"[EMERGENCIA] Secuencia congelada en el paso {paso}/{total}. "
              "Al reanudar se reenvía ese mismo paso.", flush=True)
    else:
        print("[EMERGENCIA] No había secuencia en curso.", flush=True)

    try:pantalla(lcd)
    except:pass

def desenclavar():
    """Libera el enclavamiento, pero NO reanuda: la grúa sigue frenada.

    Es el primero de los dos actos. Recién después de esto se acepta la orden de
    continuar, igual que un pulsador de emergencia real: soltar el hongo no
    arranca la máquina."""
    if not emergencia.is_set():
        print("[EMERGENCIA] No hay ninguna parada activa.", flush=True)
        return

    if CMD_DESBLOQUEO:
        try:
            Espi.write(CMD_DESBLOQUEO)
            Espi.flush()
            time.sleep(0.2)
        except Exception as e:
            print(f"[EMERGENCIA][ERR] No se pudo desbloquear la ESP32: {e}", flush=True)

    emergencia.clear()        # estado_pausa sigue en clear(): nada se mueve

    print("[EMERGENCIA] Desenclavada. Falta la orden de continuar.", flush=True)
    try:pantalla(11)
    except:pass

def continuar_secuencia():
    """Segundo acto: reanuda de verdad, reenviando el paso interrumpido."""
    if emergencia.is_set():
        print("[EMERGENCIA] Primero hay que desenclavar la parada.", flush=True)
        return

    if estado_pausa.is_set():
        print("[EMERGENCIA] No hay nada pausado que continuar.", flush=True)
        return

    with lock_estado:
        paso, total = indice_actual + 1, len(secuencia_actual)

    esp_listo.clear()         # descartar cualquier 'listo' viejo o espurio
    estado_pausa.set()        # libera a procesar_comandos, que reenvía el paso

    if total and en_movimiento.is_set():
        print(f"[EMERGENCIA] Continuando desde el paso {paso}/{total}.", flush=True)
        try:pantalla(8)
        except:pass
    else:
        print("[EMERGENCIA] Continuando. Sistema operativo.", flush=True)
        try:pantalla(0)
        except:pass

def apagar_sepower(motivo="orden remota"):
    """Corta SEpower de cuajo: primero frena la ESP32, después libera todo."""
    print(f"[SEP] Apagando SEpower ({motivo})...", flush=True)

    # 1) Congelar la secuencia en curso para que nadie mande otra trama
    estado_pausa.clear()

    # 2) Frenar la ESP32. El lector serie sigue vivo a propósito: así queda
    #    en consola la confirmación que devuelve la ESP32.
    try:
        Espi.write(b"STOP\n")
        Espi.flush()
        time.sleep(0.3)          # que la trama llegue y conteste
        print("[ESP32] STOP enviado. Actuación detenida.", flush=True)
    except Exception as e:
        print(f"[ESP32][ERR] No se pudo enviar STOP: {e}", flush=True)

    # 3) Recién ahora sacar al lector del puerto, antes de cerrarlo
    parando.set()
    time.sleep(0.05)

    # 4) Avisar a la PC
    try:
        if conn_global:
            conn_global.sendall(b"BYE\n")
    except Exception:
        pass

    # 5) Liberar hardware
    try:
        pantalla(9)
    except Exception:
        pass
    try:
        Espi.close()
    except Exception:
        pass
    try:
        GPIO.cleanup()
    except Exception:
        pass

    print("[SEP] SEpower detenido.", flush=True)
    sys.stdout.flush()
    # Los hilos son daemon y están bloqueados en recv()/readline():
    # os._exit es la única salida que no queda colgada.
    os._exit(0)

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
                emitir_ocupacion()   # el HMI arranca con el estante al día
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

                            if mensaje.upper() == "SHUTDOWN":
                                print("[SOCKET] Orden de apagado recibida desde la PC.", flush=True)
                                apagar_sepower("comando de voz 'torre salir'")

                            # Llega por voz ("torre continuar"). Se atiende acá y
                            # no por cola_comandos, porque procesar_comandos está
                            # bloqueado justamente esperando esta orden.
                            if mensaje.upper() == "CONTINUAR":
                                print("[SOCKET] Orden de continuar recibida por voz.", flush=True)
                                continuar_secuencia()
                                continue

                            print(f"Mensaje recibido desde PC: {mensaje}")

                            # Se normaliza acá, en la frontera: cámara y voz
                            # escriben los nombres distinto.
                            if mensaje.lower().startswith("cam"):
                                cola_prioritaria.put(normalizar(mensaje[3:]))

                            elif mensaje.lower().startswith("voz"):
                                cola_comandos.put(normalizar(mensaje[3:]))
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
    while not parando.is_set():
        try:
            if Espi.in_waiting > 0:
                raw = Espi.readline()
                linea = raw.decode(errors='ignore').strip()
                print(f"[ESP32] Mensaje recibido desde ESP32: {linea}")
                if "listo" in linea.lower():
                    esp_listo.set()
        except Exception as e:
            if parando.is_set():
                break          # el puerto se cerró porque estamos apagando
            print(f"[ESP32][Error serie] {e}")
            time.sleep(0.5)    # no inundar la consola si el puerto falla
        time.sleep(0.005)      # antes era un busy-loop al 100% de CPU
    print("[ESP32] Lectura serie detenida.", flush=True)

def escuchar_consola():
    """Lee lo que se tipea en la consola SSH del HMI.

    'esp <trama>'  -> se reenvía tal cual a la ESP32 por serie
    'shutdown'     -> apaga SEpower igual que el comando de voz
    """
    while not parando.is_set():
        linea = sys.stdin.readline()
        if not linea:          # EOF: se cerró la sesión
            break

        linea = linea.strip()
        if not linea:
            continue

        if linea.lower().startswith("esp "):
            trama = linea[4:].strip()
            if not trama:
                continue

            if indice_actual < len(secuencia_actual):
                print("[CONSOLA][AVISO] Hay una secuencia en curso: "
                      "la trama manual puede interferir.", flush=True)
            try:
                Espi.write((trama + "\n").encode())
                Espi.flush()
                print(f"[CONSOLA] Enviado a la ESP32: {trama}", flush=True)
            except Exception as e:
                print(f"[CONSOLA][ERR] No se pudo enviar a la ESP32: {e}", flush=True)

        elif linea.lower() in ("emergencia", "parada"):
            parada_emergencia("botón del HMI")

        elif linea.lower() in ("desenclavar", "desbloquear"):
            desenclavar()

        elif linea.lower() in ("continuar", "reanudar"):
            continuar_secuencia()

        elif linea.lower() == "home":
            if en_movimiento.is_set():
                print("[HOME] La grúa está en movimiento: primero pará la secuencia.", flush=True)
            else:
                print("[HOME] Regreso a reposo pedido.", flush=True)
                cola_prioritaria.put("__HOME__")

        elif linea.upper() == "SHUTDOWN":
            apagar_sepower("comando manual desde la consola")

        else:
            print(f"[CONSOLA] '{linea}' no es un comando de SEpower. "
                  "Usá 'esp <trama>' para hablarle a la ESP32.", flush=True)

def sensor_ir_loop():
    global ultimo_trigger

    estado_anterior = GPIO.input(PIN_IR)

    while not parando.is_set():
        estado_actual = GPIO.input(PIN_IR)

        # Detectar cambio de estado
        if estado_actual != estado_anterior:

            # Lámpara del HMI: 0 = haz cortado (objeto), 1 = libre
            print(f"[IR] HAZ={estado_actual}", flush=True)

            # 👉 cuando deja de detectar el objeto
            if estado_anterior == 0 and estado_actual == 1:

                ahora = time.time()

                if ahora - ultimo_trigger > COOLDOWN:
                    ultimo_trigger = ahora

                    if en_movimiento.is_set():
                        # Enclavamiento: entró algo con la grúa en marcha.
                        # No se avisa a la PC: acá el trigger no es una orden
                        # de trabajo, es una intrusión.
                        print("[IR] TRIGGER con la grúa en movimiento.", flush=True)
                        parada_emergencia("sensor IR", lcd=10)

                    else:
                        print("[IR] TRIGGER", flush=True)

                        with lock_conn:
                            if conn_global:
                                try:
                                    conn_global.sendall(b"TRIGGER\n")
                                except:
                                    pass

            estado_anterior = estado_actual

        time.sleep(0.01)

def esperar_listo(timeout=50):
    """Espera el 'listo' de la ESP32 sin quedar sordo a la emergencia.

    Devuelve 'ok', 'timeout', o 'reenviar' si hubo una parada: en ese caso
    queda bloqueada hasta que se reanude, así el reloj del timeout no corre
    mientras el operario decide.

    Mira 'estado_pausa' y NO 'emergencia': desenclavar apaga la emergencia pero
    deja la pausa puesta, y la grúa tiene que seguir quieta hasta que llegue la
    orden de continuar.
    """
    limite = time.time() + timeout
    while True:
        if esp_listo.wait(timeout=0.2):
            return "ok"
        if not estado_pausa.is_set():
            estado_pausa.wait()      # bloquea hasta continuar_secuencia()
            return "reenviar"
        if time.time() > limite:
            return "timeout"

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
            if mensaje == "__HOME__":
                # Regreso manual a reposo pedido desde el HMI
                pasos, fases = cin.secuencia_home()
                print("[OPER] regreso a home", flush=True)

            elif modo == "voz":
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

                pasos, fases = cin.obtener_sec_voz(mensaje, idx)
                print(f"[OPER] {mensaje} -> descarga", flush=True)
                ocupacion[mensaje][idx] = False  # se libera el espacio
                emitir_ocupacion()
                try:pantalla(2, mensaje) 
                except:pass

            elif modo == "cam":
                idx = seleccionar_posicion_libre(mensaje)
                if idx is None:
                    print(f"No hay espacio libre en {mensaje}, omitiendo.")
                    try:pantalla(4)
                    except:pass
                    continue
                pasos, fases = cin.obtener_entrada_cam(mensaje, idx)
                print(f"[OPER] {mensaje} -> estante {idx + 1}", flush=True)
                ocupacion[mensaje][idx] = True
                emitir_ocupacion()
                try:pantalla(1, mensaje)
                except:pass

            with lock_estado:
                secuencia_actual = pasos
                indice_actual = 0

            # A partir de acá la grúa se mueve: el sensor IR usa esta bandera
            # para saber si un trigger es una entrada nueva o una intrusión.
            en_movimiento.set()
            fase_anterior = None
            try:
                while indice_actual < len(secuencia_actual):

                    estado_pausa.wait()  # ⛔ pausa

                    # Marcador de fase para la pantalla de Operación. Solo se
                    # emite cuando cambia, no una vez por trama.
                    fase = fases[indice_actual] if indice_actual < len(fases) else ""
                    if fase and fase != fase_anterior:
                        print(f"[FASE] {fase}", flush=True)
                        fase_anterior = fase

                    print(f"[PASO] {indice_actual + 1}/{len(secuencia_actual)}", flush=True)

                    # cinematica ya entrega la trama lista (con velocidades por motor)
                    comando = secuencia_actual[indice_actual] + "\n"

                    with lock_estado:
                        ultimo_comando = comando

                    esp_listo.clear()   # descartar restos antes de mandar
                    Espi.write(comando.encode())
                    print(f"Mensaje enviado: {comando.strip()}")

                    resultado = esperar_listo(50)

                    if resultado == "timeout":
                        print("[ESP] Timeout - abortando secuencia")
                        break

                    if resultado == "reenviar":
                        # Hubo parada de emergencia: el movimiento quedó a medias,
                        # así que se repite este mismo paso sin avanzar el índice.
                        print(f"[SEQ] Reenviando paso {indice_actual + 1}/{len(secuencia_actual)}")
                        continue

                    with lock_estado:
                        indice_actual += 1
            finally:
                en_movimiento.clear()
                print("[FASE] ---", flush=True)   # fin del ciclo para el HMI

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

# Ctrl+C (botón "Detener Control de Campo") y SIGTERM también frenan la ESP32
def _senal_apagado(signum, frame):
    apagar_sepower(f"señal {signum}")

signal.signal(signal.SIGINT, _senal_apagado)
signal.signal(signal.SIGTERM, _senal_apagado)

# Iniciar los hilos
hilo_socket = threading.Thread(target=escuchar_socket, daemon=True)
hilo_watchdog = threading.Thread(target=wifi_watchdog, daemon=True)
hilo_esp = threading.Thread(target=escuchar_esp, daemon=True)
hilo_procesador = threading.Thread(target=procesar_comandos, daemon=True)
hilo_ir = threading.Thread(target=sensor_ir_loop, daemon=True)
hilo_consola = threading.Thread(target=escuchar_consola, daemon=True)

hilo_socket.start()
hilo_watchdog.start()
hilo_esp.start()
hilo_procesador.start()
hilo_ir.start()
hilo_consola.start()

# Mantener el programa vivo
hilo_socket.join()





