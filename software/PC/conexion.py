import socket
import time

def enviar_mensajes(colavoz, colacam, IP_RASPI="192.168.137.134", PORT=65432):
    while True:
        try:
            with socket.create_connection((IP_RASPI, PORT), timeout=5) as sock:
                print("[TCP] Conectado a Raspberry Pi")
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                while True:
                    mensaje = None
                    if not colacam.empty():
                        mensaje = colacam.get()
                    elif not colavoz.empty():
                        mensaje = colavoz.get()
                    
                    if mensaje:
                        try:
                            sock.sendall(mensaje.encode())
                            print(f"📤 Enviado a RPi: {mensaje}")
                        except Exception as e:
                            print(f"[TCP] Error al enviar: {e}")
                            break
                    time.sleep(0.1)
        except Exception as e:
            print(f"[TCP] Error de conexión: {e}")
            time.sleep(2)  # Espera antes de reintentar