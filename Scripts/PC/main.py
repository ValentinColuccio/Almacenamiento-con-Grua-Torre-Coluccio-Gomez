import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QTabWidget, QLabel, QTextEdit,
    QVBoxLayout, QHBoxLayout, QStatusBar,
    QPushButton, QLineEdit, QSizePolicy, QComboBox, QFrame, QProgressBar,
    QDialog, QStackedWidget, QButtonGroup
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QUrl, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from matplotlib import text
import paramiko
import time
import math
import re
import signal
from datetime import datetime
import subprocess
import os
import sys
import cv2
import socket
import struct
import numpy as np
import html as _html
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TTPOWER_PATH = BASE_DIR / "TTpower.py"

# cinematica.py vive en la raíz del proyecto y no importa nada de la Raspberry,
# así que se puede leer desde acá. La GUI la usa como única fuente de las fases
# y de la geometría del estante, en vez de duplicar las dos cosas a mano.
sys.path.insert(0, str(BASE_DIR.parent))
try:
    import cinematica as cin
except Exception:
    cin = None

ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

# Sin IP hardcodeada: la resuelve config_red y se puede cambiar desde el
# botón "Configurar red" de la pestaña Estación de Campo.
import config_red
from calibracion import CalibracionTab
import estilo

# ---------------------------
# CONTROL DE EMERGENCIA (compartido entre pestañas)
# ---------------------------
class ControlEmergencia(QWidget):
    """Par de botones PARADA / CONTINUAR con la máquina de tres estados.

    Lo usan Supervisión y Operación. El estado no lo asume la GUI: lo reporta la
    Raspberry, porque la parada puede venir del sensor IR y el continuar por voz.
    MainWindow mantiene sincronizadas todas las instancias."""

    log_signal = pyqtSignal(str)

    def __init__(self, ssh_worker, alto=None):
        super().__init__()
        self.ssh = ssh_worker
        self.sepower_activo = False
        # "normal" -> "enclavada" -> "desenclavada" -> "normal"
        self.estado = "normal"

        # La parada vive en su propia banda: nada más en la app mide 168 px de
        # alto, así que su silueta se reconoce con visión periférica.
        self.btn_parada = QPushButton("PARADA DE\nEMERGENCIA")
        self.btn_parada.setObjectName("estopBtn")
        self.btn_parada.setMinimumWidth(estilo.ANCHO_ESTOP)
        self.btn_parada.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_parada.clicked.connect(self.toggle)

        # Segundo acto: solo se habilita con la parada ya desenclavada
        self.btn_continuar = QPushButton("CONTINUAR")
        self.btn_continuar.setObjectName("primario")
        self.btn_continuar.setFixedHeight(estilo.ALTO_PRIMARIO)
        self.btn_continuar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_continuar.setEnabled(False)
        self.btn_continuar.clicked.connect(self.continuar)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(estilo.SEPARACION)
        layout.addWidget(self.btn_continuar, 1)
        layout.addWidget(self.btn_parada, 2)   # a la derecha, lejos del riel

    def _hay_camino(self):
        if not self.ssh.channel:
            self.log_signal.emit("[GUI] No hay conexión SSH: no se puede accionar la parada.") #type:ignore
            return False
        if not self.sepower_activo:
            self.log_signal.emit("[GUI] El Control de Campo no está en marcha: no hay nada que frenar.") #type:ignore
            return False
        return True

    def toggle(self):
        if not self._hay_camino():
            return

        if self.estado == "enclavada":
            # Soltar el hongo NO arranca la máquina: solo libera el enclavamiento
            self.ssh.send_command("desenclavar")
            self.log_signal.emit("[GUI] Parada desenclavada. Falta dar CONTINUAR.") #type:ignore
        else:
            self.ssh.send_command("emergencia")
            self.log_signal.emit("[GUI] PARADA DE EMERGENCIA accionada.") #type:ignore

    def continuar(self):
        if not self._hay_camino():
            return
        if self.estado != "desenclavada":
            self.log_signal.emit("[GUI] Primero hay que desenclavar la parada.") #type:ignore
            return
        self.ssh.send_command("continuar")
        self.log_signal.emit("[GUI] Continuando la secuencia...") #type:ignore

    def set_estado(self, estado):
        """Refleja el estado real que reporta la Raspberry, sin reenviar nada."""
        if estado == self.estado:
            return
        self.estado = estado

        if estado == "enclavada":
            self.btn_parada.setText("DESENCLAVAR")
            self.btn_parada.setStyleSheet(estilo.QSS_DESENCLAVAR)
            self.btn_continuar.setEnabled(False)
        else:
            self.btn_parada.setText("PARADA DE\nEMERGENCIA")
            self.btn_parada.setStyleSheet("")     # vuelve a la hoja global
            self.btn_continuar.setEnabled(estado == "desenclavada")

    def set_sepower_activo(self, activo):
        """La parada viaja por el stdin de SEpower: sin SEpower no hay camino."""
        self.sepower_activo = activo
        if not activo:
            self.set_estado("normal")


# ---------------------------
# TAB GLOBAL
# ---------------------------
class GlobalTab(QWidget):
    def __init__(self, ssh_worker):
        super().__init__()
        self.ssh = ssh_worker

        main_layout = QHBoxLayout(self)
        
        # Cámara
        self.camera_widget = CameraWidget()

        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)

        # Parada de emergencia
        self.emergencia = ControlEmergencia(self.ssh, alto=90)
        self.emergencia.log_signal.connect(self.add_log)

        columna_der = QVBoxLayout()
        columna_der.setSpacing(10)
        columna_der.addWidget(self.emergencia)
        columna_der.addWidget(self.console, 1)

        main_layout.addWidget(self.camera_widget, 2)
        main_layout.addLayout(columna_der, 3)

    def set_estado_emergencia(self, estado):
        self.emergencia.set_estado(estado)

    def set_sepower_activo(self, activo):
        self.emergencia.set_sepower_activo(activo)

    def add_log(self, text):
        clean = ANSI_ESCAPE.sub('', text)

        # El origen se detecta una sola vez, para todo el bloque recibido
        if clean.startswith("[RPi]"):
            color, prefix = estilo.ACENTO, "[RPi]"
        elif clean.startswith("[PC]"):
            color, prefix = estilo.OK_TEXTO, "[PC]"
        elif clean.startswith("[GUI]"):
            color, prefix = "#FFFFFF", "[GUI]"
        else:
            color, prefix = estilo.TEXTO, ""

        # Se quita el prefijo de la primera línea; después se re-agrega a cada una
        cuerpo = clean[len(prefix):] if prefix else clean

        for linea in cuerpo.splitlines():
            linea = linea.strip()
            if not linea:
                continue

            seguro = _html.escape(linea)
            etiqueta = f"{prefix} " if prefix else ""

            self.console.moveCursor(self.console.textCursor().End)
            self.console.insertHtml(
                f'<span style="color:{color};">{etiqueta}{seguro}</span><br>'
            )

        self.console.moveCursor(self.console.textCursor().End)
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum()
        )

class CameraWidget(QWebEngineView):
    def __init__(self, ancho=504, alto=896):
        super().__init__()

        self.setMinimumSize(ancho, alto)
        self.setMaximumSize(ancho, alto)

        # URL de la cámara
        # La IP sale de config_red, igual que la del socket de la cámara
        self.setUrl(QUrl(f"http://{config_red.ip_camara()}/monitor/image/live-any/overlay-single-custom/-1/errorhighlight"))


# ---------------------------
# TAB OPERACIÓN
# ---------------------------
class PasoWidget(QFrame):
    """Una fila de la lista de pasos.

    No trae colores propios: se marca con la propiedad dinámica "estado" y los
    valores salen de la hoja global. Los estados del diseño son pendiente
    (gris), activo (azul) y ok (verde)."""

    def __init__(self, numero, texto):
        super().__init__()
        self.setFixedHeight(estilo.ALTO_PASO)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        self.punto = QLabel()
        self.punto.setFixedSize(26, 26)
        self.punto.setAlignment(Qt.AlignCenter)  # type: ignore

        self.texto = QLabel("%d.  %s" % (numero, texto))
        self.texto.setStyleSheet("font-size: %dpx; font-weight: 600; border: none;"
                                 % estilo.F_CUERPO)

        layout.addWidget(self.punto)
        layout.addWidget(self.texto, 1)

        self.set_estado("pendiente")

    def set_estado(self, estado):
        estilo.marcar(self, estado)
        estilo.marcar(self.texto, estado)
        colores = {"pendiente": estilo.BORDE, "activo": estilo.ACENTO,
                   "ok": estilo.OK, "alarma": estilo.PELIGRO_TEXTO}
        self.punto.setStyleSheet(
            "background-color: %s; border-radius: 13px; border: none;"
            " color: %s; font-size: 15px; font-weight: 700;"
            % (colores.get(estado, estilo.BORDE), estilo.BG_PANEL))
        self.punto.setText("✓" if estado == "ok" else "")


class Lampara(QWidget):
    """Indicador con etiqueta, para el estado de los subsistemas.

    El diseño pide cuadros con borde de color y no círculos sueltos: el borde
    hace de halo sin necesidad de sombra y el texto queda siempre legible."""

    def __init__(self, texto):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.punto = QFrame()
        self.punto.setFixedSize(20, 20)
        self.lbl = QLabel(texto)
        self.lbl.setObjectName("etiqueta")

        lay.addWidget(self.punto)
        lay.addWidget(self.lbl, 1)
        self.set_estado("off")

    def set_estado(self, estado):
        # "ok" / "mal" / "aviso" / "off" -> vocabulario de la hoja global
        equivale = {"ok": "ok", "mal": "alarma", "aviso": "warn", "off": "off"}
        estilo.marcar(self.punto, equivale.get(estado, "off"))


class MimicoEstante(QWidget):
    """Vista radial de la planta: pivote, los slots en abanico, carga y descarga.

    Toma la geometría de cinematica.puntos, así que si movés un slot allá, acá
    se dibuja solo en el lugar nuevo."""

    # Claves sin tilde, igual que ORDEN_SLOTS y el dict 'ocupacion'
    ABREV = {"caja": "CJ", "bidon uno": "B1", "bidon dos": "B2", "carrete": "CR"}

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.ocupacion = {}    # "caja_0" -> bool
        self.destino = None    # slot resaltado

    def set_ocupacion(self, mapa):
        self.ocupacion = dict(mapa)
        self.update()

    def set_destino(self, slot):
        self.destino = slot
        self.update()

    def _puntos(self):
        if cin is None:
            return [], []
        slots = [(n, cin.puntos[n]) for n in cin.ORDEN_SLOTS if n in cin.puntos]
        fijos = [(n, cin.puntos[n]) for n in ("carga", "descarga") if n in cin.puntos]
        return slots, fijos

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
        from PyQt5.QtCore import QRectF, QPointF

        slots, fijos = self._puntos()
        if not slots and not fijos:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        margen = 30
        w, h = self.width(), self.height()

        # El encuadre se calcula solo a partir de los puntos: sirve tanto si la
        # planta ocupa medio plano como los cuatro cuadrantes.
        xs, ys = [0.0], [0.0]                        # el pivote siempre entra
        for _, (ang, rad) in slots + fijos:
            a = math.radians(ang)
            xs.append(rad * math.cos(a))
            ys.append(rad * math.sin(a))

        ancho_mm = max(max(xs) - min(xs), 1.0)
        alto_mm = max(max(ys) - min(ys), 1.0)
        escala = min((w - 2 * margen) / ancho_mm, (h - 2 * margen) / alto_mm)

        # Centro del dibujo = centro del bounding box de los puntos
        mx = (max(xs) + min(xs)) / 2
        my = (max(ys) + min(ys)) / 2
        cx = w / 2 - mx * escala
        cy = h / 2 + my * escala

        def en_pantalla(ang, rad):
            a = math.radians(ang)
            return QPointF(cx + rad * escala * math.cos(a),
                           cy - rad * escala * math.sin(a))

        # Círculo de alcance
        radios = [r for _, (_, r) in slots + fijos]
        rr = (max(radios) if radios else 1) * escala
        p.setPen(QPen(QColor(estilo.BORDE), 2, Qt.DashLine))       # type: ignore
        p.setBrush(Qt.NoBrush)                                   # type: ignore
        p.drawEllipse(QPointF(cx, cy), rr, rr)

        # Pivote
        p.setPen(Qt.NoPen)                                       # type: ignore
        p.setBrush(QBrush(QColor(estilo.TEXTO_2)))
        p.drawEllipse(QPointF(cx, cy), 7, 7)

        fuente = p.font()
        fuente.setBold(True)
        fuente.setPointSize(9)
        p.setFont(fuente)

        # Carga y descarga
        for nombre, (ang, rad) in fijos:
            c = en_pantalla(ang, rad)
            p.setPen(QPen(QColor(estilo.BORDE_FUERTE), 2))
            p.setBrush(QBrush(QColor(estilo.BG_CONTROL)))
            p.drawRoundedRect(QRectF(c.x() - 34, c.y() - 13, 68, 26), 5, 5)
            p.setPen(QPen(QColor(estilo.TEXTO_2)))
            p.drawText(QRectF(c.x() - 34, c.y() - 13, 68, 26),
                       Qt.AlignCenter, nombre.upper())          # type: ignore

        # Slots del estante
        for nombre, (ang, rad) in slots:
            c = en_pantalla(ang, rad)
            ocupado = self.ocupacion.get(nombre, False)
            es_destino = (nombre == self.destino)

            if es_destino:
                relleno, borde, grosor = QColor(estilo.WARN_BG), QColor(estilo.WARN), 4
            elif ocupado:
                relleno, borde, grosor = QColor(estilo.ACENTO_BG), QColor(estilo.ACENTO), 2
            else:
                relleno, borde, grosor = QColor(estilo.BG_CONTROL), QColor(estilo.BORDE), 2

            p.setPen(QPen(borde, grosor))
            p.setBrush(QBrush(relleno))
            p.drawEllipse(c, 19, 19)

            base = nombre.rsplit("_", 1)[0]
            p.setPen(QPen(QColor("#FFFFFF" if (ocupado or es_destino) else estilo.OFF)))
            p.drawText(QRectF(c.x() - 19, c.y() - 19, 38, 38),
                       Qt.AlignCenter, self.ABREV.get(base, base[:2].upper()))  # type: ignore

        p.end()


# Fase que manda la Raspberry durante un movimiento del panel de Calibración.
# No es uno de los cinco pasos del ciclo: se muestra como estado, no como paso.
FASE_CALIBRAR = cin.FASE_CALIBRAR if cin is not None else "Calibrando"


class OperacionTab(QWidget):
    """Pantalla de operación: cámara, avance del ciclo, mímico del estante y
    controles. Sin consola: acá no se lee texto crudo."""

    # Fuente única: las mismas fases que arma la cinemática.
    FASES = list(cin.FASES) if cin is not None else [
        "Aproximando a la carga", "Enganchando la carga",
        "Trasladando la carga", "Dejando la carga", "Volviendo a home",
    ]

    # (texto, color de trazo, tinte de fondo) — todos del sistema de diseño
    ESTADOS = {
        "espera":       ("EN ESPERA",            estilo.ACENTO,        estilo.ACENTO_BG),
        "operando":     ("EN OPERACIÓN",         estilo.OK_TEXTO,      estilo.OK_BG),
        "enclavada":    ("PARADA DE EMERGENCIA", estilo.PELIGRO_TEXTO, estilo.PELIGRO_BG),
        "desenclavada": ("LISTA PARA CONTINUAR", estilo.WARN,          estilo.WARN_BG),
        "calibrando":   ("CALIBRANDO",           estilo.WARN,          estilo.WARN_BG),
        "sin_campo":    ("SIN CONTROL DE CAMPO", estilo.OFF,           estilo.BG_CONTROL),
    }

    def __init__(self, ssh_worker):
        super().__init__()
        self.ssh = ssh_worker
        self.estado_emergencia = "normal"
        self.hay_ciclo = False
        self.calibrando = False
        self.sepower_activo = False
        self.t_inicio_ciclo = None
        self.duracion_ultimo = None


        raiz = QVBoxLayout(self)
        raiz.setSpacing(12)
        raiz.setContentsMargins(14, 14, 14, 14)

        # ===== Fila superior: reloj + banner =====
        self.lbl_reloj = QLabel("--:--:--")
        # Sin ancho fijo a propósito: lo define la métrica de la fuente, así
        # no se recorta si mañana cambia el tamaño en el sistema de diseño.
        self.lbl_reloj.setFixedHeight(78)
        self.lbl_reloj.setAlignment(Qt.AlignCenter)  # type: ignore
        self.lbl_reloj.setObjectName("reloj")

        self.lbl_estado = QLabel()
        self.lbl_estado.setFixedHeight(78)
        self.lbl_estado.setAlignment(Qt.AlignCenter)  # type: ignore

        fila_sup = QHBoxLayout()
        fila_sup.setSpacing(12)
        fila_sup.addWidget(self.lbl_reloj)
        fila_sup.addWidget(self.lbl_estado, 1)

        # ===== Columna izquierda: cámara =====
        self.camera_widget = CameraWidget(300, 533)

        # ===== Columna central =====
        self.lbl_operacion = QLabel("—")
        self.lbl_operacion.setFixedHeight(52)
        self.lbl_operacion.setAlignment(Qt.AlignCenter)  # type: ignore
        self.lbl_operacion.setObjectName("tituloPantalla")

        self.lbl_tiempo = QLabel("Ciclo 00:00   ·   anterior --:--")
        self.lbl_tiempo.setFixedHeight(40)
        self.lbl_tiempo.setAlignment(Qt.AlignCenter)  # type: ignore
        self.lbl_tiempo.setObjectName("etiqueta")

        self.lbl_progreso = QLabel("paso —/—")
        self.lbl_progreso.setFixedHeight(34)
        self.lbl_progreso.setAlignment(Qt.AlignCenter)  # type: ignore
        self.lbl_progreso.setObjectName("etiqueta")

        self.barra = QProgressBar()
        self.barra.setFixedHeight(22)
        self.barra.setTextVisible(False)
        self.barra.setRange(0, 100)
        self.barra.setValue(0)

        self.mimico = MimicoEstante()
        self.mimico.setObjectName("panel")

        # Lámparas de subsistemas
        self.lamparas = {
            "socket":  Lampara("Enlace"),
            "camara":  Lampara("Visión"),
            "campo":   Lampara("Campo"),
            "esp":     Lampara("Actuación"),
            "ir":      Lampara("Sensor IR"),
            "voz":     Lampara("Escuchando"),
        }
        grilla = QHBoxLayout()
        grilla.setSpacing(14)
        col_a = QVBoxLayout(); col_a.setSpacing(8)
        col_b = QVBoxLayout(); col_b.setSpacing(8)
        for i, lamp in enumerate(self.lamparas.values()):
            (col_a if i % 2 == 0 else col_b).addWidget(lamp)
        grilla.addLayout(col_a); grilla.addLayout(col_b)

        caja_lamparas = QFrame()
        caja_lamparas.setObjectName("panel")
        caja_lamparas.setFixedHeight(96)
        lay_lamp = QVBoxLayout(caja_lamparas)
        lay_lamp.setContentsMargins(14, 8, 14, 8)
        lay_lamp.addLayout(grilla)

        col_centro = QVBoxLayout()
        col_centro.setSpacing(10)
        col_centro.addWidget(self.lbl_operacion)
        col_centro.addWidget(self.lbl_tiempo)
        col_centro.addWidget(self.barra)
        col_centro.addWidget(self.lbl_progreso)
        col_centro.addWidget(self.mimico, 1)
        col_centro.addWidget(caja_lamparas)

        # ===== Columna derecha: pasos =====
        self.pasos = [PasoWidget(i + 1, f) for i, f in enumerate(self.FASES)]
        col_pasos = QVBoxLayout()
        col_pasos.setSpacing(10)
        for p in self.pasos:
            col_pasos.addWidget(p)
        col_pasos.addStretch()

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(14)
        cuerpo.addWidget(self.camera_widget)
        cuerpo.addLayout(col_centro, 1)
        cuerpo.addLayout(col_pasos, 1)

        # ===== Último evento =====
        self.lbl_evento = QLabel("Sin eventos")
        self.lbl_evento.setFixedHeight(44)
        self.lbl_evento.setObjectName("panel")

        # ===== Botonera =====
        self.emergencia = ControlEmergencia(self.ssh, alto=82)

        self.btn_home = QPushButton("HOME")
        self.btn_home.setFixedHeight(82)
        self.btn_home.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_home.setEnabled(False)
        self.btn_home.clicked.connect(self.ir_a_home)

        fila_botones = QHBoxLayout()
        fila_botones.setSpacing(10)
        fila_botones.addWidget(self.emergencia, 3)
        fila_botones.addWidget(self.btn_home, 1)

        raiz.addLayout(fila_sup)
        raiz.addLayout(cuerpo, 1)
        raiz.addWidget(self.lbl_evento)
        raiz.addLayout(fila_botones)

        # Reloj y cronómetro de ciclo
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self._tick()

        self._refrescar_estado()

    # ---- acciones ----

    def ir_a_home(self):
        if not self.ssh.channel or not self.sepower_activo:
            return
        self.ssh.send_command("home")

    # ---- entradas desde la Raspberry ----

    def set_fase(self, fase):
        """'---' cierra el ciclo; cualquier otra cosa marca esa fase como activa
        y da por hechas las anteriores.

        'Calibrando' no es un paso del ciclo: no toca la lista ni arranca el
        cronómetro, solo cambia el banner a ámbar."""
        if fase == FASE_CALIBRAR:
            self.calibrando = True
            self._refrescar_estado()
            return

        if fase == "---":
            self.calibrando = False
            if self.hay_ciclo and self.t_inicio_ciclo is not None:
                self.duracion_ultimo = time.time() - self.t_inicio_ciclo
            self.hay_ciclo = False
            self.t_inicio_ciclo = None
            for p in self.pasos:
                p.set_estado("pendiente")
            self.lbl_operacion.setText("—")
            self.mimico.set_destino(None)
            self.barra.setValue(0)
            self.lbl_progreso.setText("paso —/—")
            self._tick()
            self._refrescar_estado()
            return

        if fase not in self.FASES:
            return

        if not self.hay_ciclo:
            self.t_inicio_ciclo = time.time()
        self.hay_ciclo = True

        actual = self.FASES.index(fase)
        for i, p in enumerate(self.pasos):
            if i < actual:
                p.set_estado("ok")
            elif i == actual:
                p.set_estado("activo")
            else:
                p.set_estado("pendiente")
        self._refrescar_estado()

    def set_paso(self, n, total):
        self.lbl_progreso.setText(f"paso {n}/{total}")
        self.barra.setValue(int(100 * n / total) if total else 0)

    def set_operacion(self, texto):
        self.lbl_operacion.setText(texto.upper())

        # Qué slot resaltar en el mímico. Dos formatos posibles:
        #   "caja -> estante 2"                 (ciclo normal)
        #   "calibrando caja_0 · toma_aprox"    (panel de calibración)
        limpio = texto.strip()
        m = re.match(r"^(.*?)\s*->\s*estante\s*(\d+)", limpio, re.IGNORECASE)
        if m:
            self.mimico.set_destino("%s_%d" % (m.group(1).strip(),
                                               int(m.group(2)) - 1))
            return

        m = re.match(r"^calibrando\s+(.+?)\s*·", limpio, re.IGNORECASE)
        self.mimico.set_destino(m.group(1).strip() if m else None)

    def set_ocupacion(self, mapa):
        self.mimico.set_ocupacion(mapa)

    def set_ir(self, cortado):
        self.lamparas["ir"].set_estado("aviso" if cortado else "ok")

    def set_voz(self, escuchando):
        """Se dijo la palabra de activación y el sistema espera el comando."""
        self.lamparas["voz"].set_estado("ok" if escuchando else "off")

    def set_lampara(self, clave, estado):
        if clave in self.lamparas:
            self.lamparas[clave].set_estado(estado)

    def set_evento(self, texto):
        self.lbl_evento.setText(
            f"{datetime.now().strftime('%H:%M:%S')}   ·   {texto}")

    def set_estado_emergencia(self, estado):
        self.estado_emergencia = estado
        self.emergencia.set_estado(estado)
        self._refrescar_estado()

    def set_sepower_activo(self, activo):
        self.sepower_activo = activo
        self.emergencia.set_sepower_activo(activo)
        self.btn_home.setEnabled(activo)
        self.set_lampara("campo", "ok" if activo else "off")
        if not activo:
            self.set_fase("---")
            self.set_lampara("ir", "off")
        self._refrescar_estado()

    # ---- refrescos ----

    def _tick(self):
        self.lbl_reloj.setText(datetime.now().strftime("%H:%M:%S"))

        def mmss(seg):
            return f"{int(seg) // 60:02d}:{int(seg) % 60:02d}"

        actual = mmss(time.time() - self.t_inicio_ciclo) if self.t_inicio_ciclo else "00:00"
        previo = mmss(self.duracion_ultimo) if self.duracion_ultimo else "--:--"
        self.lbl_tiempo.setText(f"Ciclo {actual}   ·   anterior {previo}")

    def _refrescar_estado(self):
        if self.estado_emergencia in ("enclavada", "desenclavada"):
            clave = self.estado_emergencia
        elif not self.sepower_activo:
            clave = "sin_campo"
        elif self.calibrando:
            clave = "calibrando"
        elif self.hay_ciclo:
            clave = "operando"
        else:
            clave = "espera"

        texto, color, fondo = self.ESTADOS[clave]
        self.lbl_estado.setText(texto)
        self.lbl_estado.setStyleSheet(
            "font-size: %dpx; font-weight: 600; color: %s;"
            "background-color: %s; border: 3px solid %s; border-radius: 4px;"
            % (estilo.F_TITULO, color, fondo, color))

# ---------------------------
# TABS secundarias
# ---------------------------
class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent: QMainWindow = parent
        self.setObjectName("tituloBarra")
        self.setFixedHeight(estilo.ALTO_TITULO)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        self.title = QLabel("Sistema Grúa Torre – Panel de Control")
        self.title.setObjectName("tituloVentana")

        # Sin objectName heredarían la regla global de QPushButton: 84 px de
        # alto dentro de una barra de 48, y quedaban cortados y sin texto.
        btn_min = QPushButton("–")
        btn_max = QPushButton("□")
        btn_close = QPushButton("✕")
        btn_min.setObjectName("tituloBtn")
        btn_max.setObjectName("tituloBtn")
        btn_close.setObjectName("cerrarBtn")

        btn_min.setToolTip("Minimizar")
        btn_max.setToolTip("Maximizar / restaurar")
        btn_close.setToolTip("Cerrar el HMI")

        btn_min.clicked.connect(parent.showMinimized)
        btn_max.clicked.connect(self.toggle_max_restore)
        btn_close.clicked.connect(parent.close)

        layout.addWidget(self.title)
        layout.addStretch()
        layout.addWidget(btn_min)
        layout.addWidget(btn_max)
        layout.addWidget(btn_close)

    def toggle_max_restore(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    # Permitir arrastrar la ventana
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:         #type: ignore
            self.drag_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:    #type: ignore
            self.parent.move(
                self.parent.pos() + event.globalPos() - self.drag_pos
            )
            self.drag_pos = event.globalPos()

# ---------------------------
# CONFIGURACIÓN DE RED
# ---------------------------
class BuscadorRPi(QThread):
    """Barre la red buscando la Raspberry. En un hilo para no congelar el HMI."""
    resultado = pyqtSignal(list)

    def run(self):
        try:
            self.resultado.emit(config_red.descubrir())
        except Exception:
            self.resultado.emit([])


class DialogoRed(QDialog):
    """Dónde está la Raspberry. Se carga una vez y queda guardado en disco.

    El AP es un celular, así que no hay IP fija ni subred estable: por eso el
    botón Buscar deriva la subred de la IP que tenga la PC en ese momento."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de red")
        self.setMinimumWidth(520)

        cfg = config_red.cargar()

        self.campo_rpi = QLineEdit(cfg["ip_rpi"])
        self.campo_cam = QLineEdit(cfg["ip_camara"])

        self.estado = QLabel("Tu PC está en " + (config_red.ip_local() or "—"))
        self.estado.setWordWrap(True)
        self.estado.setObjectName("etiqueta")

        btn_buscar = QPushButton("Buscar")
        btn_probar = QPushButton("Probar")
        btn_guardar = QPushButton("Guardar")
        btn_cerrar = QPushButton("Cerrar")
        for b in (btn_buscar, btn_probar, btn_guardar, btn_cerrar):
            b.setFixedHeight(estilo.ALTO_SECUNDARIO)
        self.btn_buscar = btn_buscar

        btn_buscar.clicked.connect(self.buscar)
        btn_probar.clicked.connect(self.probar)
        btn_guardar.clicked.connect(self.guardar)
        btn_cerrar.clicked.connect(self.accept)

        fila_rpi = QHBoxLayout()
        fila_rpi.addWidget(self.campo_rpi, 1)
        fila_rpi.addWidget(btn_buscar)
        fila_rpi.addWidget(btn_probar)

        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(btn_guardar)
        botones.addWidget(btn_cerrar)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.addWidget(QLabel("Raspberry Pi  (nombre o IP)"))
        lay.addLayout(fila_rpi)
        lay.addWidget(QLabel("Cámara inteligente"))
        lay.addWidget(self.campo_cam)
        lay.addWidget(self.estado)
        lay.addLayout(botones)

        self.buscador = None

    def _avisar(self, texto, color=estilo.TEXTO_2):
        self.estado.setText(texto)
        self.estado.setStyleSheet("color: %s; font-size: %dpx;"
                                  % (color, estilo.F_ETIQUETA))

    def buscar(self):
        self.btn_buscar.setEnabled(False)
        self._avisar("Buscando en la red... (unos segundos)", estilo.WARN)
        self.buscador = BuscadorRPi()
        self.buscador.resultado.connect(self._encontrado)
        self.buscador.start()

    def _encontrado(self, hosts):
        self.btn_buscar.setEnabled(True)
        if not hosts:
            self._avisar("No se encontró ninguna Raspberry. ¿Está encendida y "
                         "conectada al mismo WiFi?", estilo.PELIGRO_TEXTO)
            return
        self.campo_rpi.setText(hosts[0])
        if len(hosts) == 1:
            self._avisar("Encontrada en " + hosts[0], estilo.OK_TEXTO)
        else:
            self._avisar("Varios equipos con SSH: " + ", ".join(hosts)
                         + ". Se cargó el primero.", estilo.WARN)

    def probar(self):
        host = self.campo_rpi.text().strip()
        if config_red.probar(host):
            self._avisar(host + " responde en el puerto SSH.", estilo.OK_TEXTO)
        else:
            self._avisar(host + " no responde. Probá con Buscar.",
                         estilo.PELIGRO_TEXTO)

    def guardar(self):
        config_red.guardar({
            "ip_rpi": self.campo_rpi.text().strip(),
            "ip_camara": self.campo_cam.text().strip(),
        })
        self._avisar("Guardado. Se usa en la próxima conexión.", estilo.OK_TEXTO)


class RaspberryTab(QWidget):
    sepower_status_signal = pyqtSignal(str)
    def __init__(self, ssh_worker):
        super().__init__()
        self.ssh = ssh_worker

        layout = QVBoxLayout(self)

        # Botones
        # Etiquetas cortas: cuatro botones a 26 px con los nombres largos
        # exigían 2538 px de ancho, más de lo que da el panel. El nombre
        # completo queda en el tooltip.
        self.btn_red           = QPushButton("RED")
        self.btn_connect       = QPushButton("CONECTAR")
        self.btn_start_sepower = QPushButton("INICIAR")
        self.btn_stop_sepower  = QPushButton("DETENER")

        self.btn_red.setToolTip("Configurar red: dónde está la Raspberry")
        self.btn_connect.setToolTip("Conectar por SSH a la Estación de Campo")
        self.btn_start_sepower.setToolTip("Iniciar el Control de Campo (SEpower)")
        self.btn_stop_sepower.setToolTip("Detener el Control de Campo")
        '''self.btn_connect = QPushButton("Conectar SSH")
        self.btn_start_sepower = QPushButton("Iniciar SEpower")
        self.btn_stop_sepower = QPushButton("Detener SEpower")'''

        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)

        # Selector de destino del comando
        self.sepower_activo = False
        self.destino = QComboBox()
        self.destino.addItems(["Raspberry (shell)", "ESP32 (serie)"])
        self.destino.setFixedWidth(200)

        # Input
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ingrese comando y presione Enter")

        # Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(10, 10, 10, 10)
        btn_layout.addWidget(self.btn_red)
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_start_sepower)
        btn_layout.addWidget(self.btn_stop_sepower)
        layout.addLayout(btn_layout)

        entrada_layout = QHBoxLayout()
        entrada_layout.setSpacing(8)
        entrada_layout.addWidget(self.destino)
        entrada_layout.addWidget(self.input, 1)

        layout.addWidget(self.console)
        layout.addLayout(entrada_layout)

        for btn in (
            self.btn_red,
            self.btn_connect,
            self.btn_start_sepower,
            self.btn_stop_sepower
        ):
            btn.setFixedHeight(estilo.ALTO_PRIMARIO)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)   
        
        # Conexiones
        self.btn_red.clicked.connect(self.configurar_red)
        self.btn_connect.clicked.connect(self.ssh.connect_ssh)
        self.btn_start_sepower.clicked.connect(self.start_sepower)  
        self.btn_stop_sepower.clicked.connect(self.stop_sepower)
        self.input.returnPressed.connect(self.send_command)
        self.destino.currentIndexChanged.connect(self.cambiar_destino)

        self.ssh.output_signal.connect(self.append_output)

        self.btn_start_sepower.setEnabled(False) 
        self.btn_stop_sepower.setEnabled(False)  
        self.btn_start_sepower.setEnabled(False)
        self.btn_stop_sepower.setEnabled(False)                                  

    def configurar_red(self):
        dlg = DialogoRed(self)
        dlg.exec_()
        self.append_output("[GUI] Raspberry configurada en: " + config_red.ip_rpi() + "\n")

    def append_output(self, text):
        self.console.moveCursor(self.console.textCursor().End)
        self.console.insertPlainText(text)
        self.console.moveCursor(self.console.textCursor().End)

    def cambiar_destino(self, idx):
        if idx == 1:
            self.input.setPlaceholderText(
                "Trama para la ESP32 (ej: A:90.0-V6500;B:180.0-V2000;C:0.0;D:1) y Enter"
            )
        else:
            self.input.setPlaceholderText("Ingrese comando y presione Enter")

    def set_sepower_activo(self, activo):
        """La ESP32 solo es alcanzable a través de SEpower: es quien tiene el puerto serie."""
        self.sepower_activo = activo
        if not activo and self.destino.currentIndex() == 1:
            self.destino.setCurrentIndex(0)

    def send_command(self):
        cmd = self.input.text().strip()
        if not cmd:
            return

        if not self.ssh.channel:
            self.append_output("[GUI] No hay conexión SSH\n")
            return

        if self.destino.currentIndex() == 1:      # ESP32 por serie
            if not self.sepower_activo:
                self.append_output(
                    "[GUI] La ESP32 solo responde con el Control de Campo en marcha.\n"
                )
                return
            self.console.append(f"→ ESP32: {cmd}")
            self.ssh.send_command(f"esp {cmd}")   # SEpower lo reenvía por serie
        else:
            self.console.append(f"$ {cmd}")
            self.ssh.send_command(cmd)

        self.input.clear()

    def start_sepower(self):
        if not self.ssh.channel:
            self.append_output("[GUI] No hay conexión SSH\n")
            return

        self.append_output("[GUI] Iniciando SEpower...\n")

        # 1) activar entorno virtual
        self.ssh.send_command("source ~/gruavenv/bin/activate")

        # pequeña pausa para que bash procese
        self.ssh.msleep(200)

        # 2) ejecutar script con sudo
        self.ssh.send_command("sudo ~/gruavenv/bin/python SEpower.py")
        self.sepower_status_signal.emit("RPI_SEP_ON")   #type: ignore
    
    def stop_sepower(self):
        if not self.ssh.channel:
            self.append_output("[GUI] No hay conexión SSH\n")
            return

        self.append_output("[GUI] Deteniendo SEpower (Ctrl+C)...\n")
        # Enviar Ctrl+C
        self.ssh.channel.send("\x03")
        self.sepower_status_signal.emit("RPI_SEP_OFF")  #type: ignore

class ControlPCTab(QWidget):
    def __init__(self, ttpower_worker):
        super().__init__()
        self.worker = ttpower_worker

        layout = QVBoxLayout(self)

        # Botones
        self.btn_start = QPushButton("INICIAR PERCEPCIÓN")
        self.btn_stop  = QPushButton("DETENER PERCEPCIÓN")
        '''self.btn_start = QPushButton("Iniciar TTpower")
        self.btn_stop = QPushButton("Detener TTpower")'''

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_start.setObjectName("primario")
        self.btn_start.setFixedHeight(estilo.ALTO_PRIMARIO)
        self.btn_stop.setFixedHeight(estilo.ALTO_PRIMARIO)
        
        self.btn_start.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_stop.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(10, 10, 10, 10)

        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)

        # Layout final
        layout.addLayout(btn_layout)
        layout.addWidget(self.console)

        # Conexiones
        self.btn_start.clicked.connect(self.start_ttpower)
        self.btn_stop.clicked.connect(self.stop_ttpower)

        self.worker.log_signal.connect(self.append_log)
        
        self.btn_stop.setEnabled(False)

    def append_log(self, text):
        if text.startswith("[PC]"):
            self.console.moveCursor(self.console.textCursor().End)
            self.console.append(text)
            self.console.moveCursor(self.console.textCursor().End)

    def start_ttpower(self):
        if not self.worker.isRunning():
            self.console.append("[GUI] Iniciando TTpower...")
            self.worker.start()        
        
    def stop_ttpower(self):
        self.btn_stop.setEnabled(False)   # evita doble click durante el cierre
        self.console.append("[GUI] Deteniendo TTpower...")
        self.worker.stop()

# ---------------------------
# VENTANA PRINCIPAL
# ---------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sistema Grúa Torre - Panel de Control")
        self.resize(1920, 1080)   # panel de 15,6 pulgadas a 1080p
        self.setWindowFlags(Qt.FramelessWindowHint)#type: ignore
        self.setAttribute(Qt.WA_TranslucentBackground, False)#type: ignore

        # ----- Tabs -----
        # Riel de navegación en vez de QTabWidget (ver más abajo)
        self.paginas = QStackedWidget()

        # El SSH se crea primero: la pestaña de supervisión lo necesita
        # para mandar la parada de emergencia.
        self.ssh_worker = SSHWorker()

        self.global_tab = GlobalTab(self.ssh_worker)

        self.ssh_worker.status_signal.connect(self.update_status)
        self.ssh_worker.output_signal.connect(lambda txt: self.global_tab.add_log("[RPi] " + txt))
        self.raspberry_tab = RaspberryTab(self.ssh_worker)
        self.raspberry_tab.sepower_status_signal.connect(self.update_status)

        self.ttpower_worker = TTpowerWorker()
        self.ttpower_worker.log_signal.connect(self.global_tab.add_log)
        self.ttpower_worker.status_signal.connect(self.update_status)
        self.ttpower_worker.voz_signal.connect(self.update_voz)
        self.pc_tab = ControlPCTab(self.ttpower_worker)

        # Pantalla de operación: es la primera de la barra (ver más abajo)
        self.operacion_tab = OperacionTab(self.ssh_worker)
        self.ssh_worker.fase_signal.connect(self.operacion_tab.set_fase)
        self.ssh_worker.operacion_signal.connect(self.operacion_tab.set_operacion)
        self.ssh_worker.paso_signal.connect(self.operacion_tab.set_paso)
        self.ssh_worker.ocupacion_signal.connect(self.operacion_tab.set_ocupacion)
        self.ssh_worker.ir_signal.connect(self.operacion_tab.set_ir)
        self.ssh_worker.evento_signal.connect(self.operacion_tab.set_evento)
        self.operacion_tab.emergencia.log_signal.connect(self.global_tab.add_log)

        # Calibración: en su propio archivo, mismo proceso y mismo canal SSH
        self.calibracion_tab = CalibracionTab(self.ssh_worker)
        self.ssh_worker.calib_c_signal.connect(self.calibracion_tab.set_c)
        self.ssh_worker.calib_pose_signal.connect(self.calibracion_tab.set_pose)
        self.ssh_worker.calib_tabla_signal.connect(self.calibracion_tab.set_tabla)
        self.ssh_worker.calib_error_signal.connect(self.calibracion_tab.set_error)

        # ----- Riel de navegación -----
        # Un solo lugar donde se decide el orden. Ninguna otra parte del código
        # depende del índice: todo accede por nombre (self.raspberry_tab, etc.).
        pantallas = (
            (self.operacion_tab,   "OPERACIÓN"),            # la de uso diario, primera
            (self.global_tab,      "SUPERVISIÓN"),
            (self.pc_tab,          "ESTACIÓN DE\nOPERACIÓN"),
            (self.raspberry_tab,   "ESTACIÓN DE\nCAMPO"),
            (self.calibracion_tab, "CALIBRACIÓN"),          # mantenimiento, última
        )

        self.riel = QWidget()
        self.riel.setObjectName("riel")
        self.riel.setFixedWidth(estilo.ANCHO_NAV)
        lay_riel = QVBoxLayout(self.riel)
        lay_riel.setContentsMargins(0, 0, 0, 0)
        lay_riel.setSpacing(0)

        titulo = QLabel("GRÚA T-01")
        titulo.setObjectName("navTitulo")
        subtitulo = QLabel("modo automático")
        subtitulo.setObjectName("navSubtitulo")
        lay_riel.addWidget(titulo)
        lay_riel.addWidget(subtitulo)

        # Exclusivo: exactamente una pantalla activa, siempre
        self.grupo_nav = QButtonGroup(self)
        self.grupo_nav.setExclusive(True)

        for i, (widget, etiqueta) in enumerate(pantallas):
            self.paginas.addWidget(widget)
            b = QPushButton(etiqueta)
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)   # type: ignore
            self.grupo_nav.addButton(b, i)
            lay_riel.addWidget(b)

        lay_riel.addStretch()
        self.grupo_nav.buttonClicked[int].connect(self.paginas.setCurrentIndex)
        self.grupo_nav.button(0).setChecked(True)

        # Todos los paneles de parada se mantienen sincronizados entre sí
        self.paneles_emergencia = [self.global_tab, self.operacion_tab]

        #--------------------------------------------------------------------

        central = QWidget()

        columna = QVBoxLayout()
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(0)
        self.title_bar = TitleBar(self)
        columna.addWidget(self.title_bar)
        columna.addWidget(self.paginas, 1)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.riel)
        main_layout.addLayout(columna, 1)

        self.setCentralWidget(central)

        # ----- Barra de estado -----
        self.status = QStatusBar()
        self.status.setFixedHeight(estilo.ALTO_ESTADO)
        self.setStatusBar(self.status)
        
        def make_status_label(text):
            lbl = QLabel(text)
            return lbl

        self.lbl_pc       = make_status_label("Operación:")
        self.lbl_camera   = make_status_label("Visión:")
        self.lbl_socket   = make_status_label("Enlace:")
        self.lbl_rpi      = make_status_label("Campo:")
        self.lbl_esp  = make_status_label("Actuación:")
        self.lbl_voz  = make_status_label("Voz:")

        self.status.addWidget(self.lbl_pc)
        self.status.addWidget(self.lbl_camera)
        self.status.addWidget(self.lbl_socket)
        self.status.addWidget(self.lbl_rpi)
        self.status.addWidget(self.lbl_esp)
        self.status.addWidget(self.lbl_voz)

        self.set_status(self.lbl_pc, "Operación: OFF", estilo.PELIGRO_TEXTO)
        self.set_status(self.lbl_camera, "Visión: OFF", estilo.PELIGRO_TEXTO)
        self.set_status(self.lbl_socket, "Enlace: OFF", estilo.PELIGRO_TEXTO)
        self.set_status(self.lbl_rpi, "Campo: OFF", estilo.PELIGRO_TEXTO)
        self.set_status(self.lbl_esp, "Actuación: OFF", estilo.PELIGRO_TEXTO)
        self.set_status(self.lbl_voz, "Voz: en espera", estilo.OFF)

        # Logs de prueba
        self.global_tab.add_log("[GUI] Interfaz iniciada correctamente.")     
    
    def update_voz(self, escuchando):
        """Se dijo 'torre': el sistema espera el comando. Va a la barra de estado
        para que se vea desde cualquier pestaña."""
        if escuchando:
            self.set_status(self.lbl_voz, "Voz: ESCUCHANDO", estilo.OK_TEXTO)
        else:
            self.set_status(self.lbl_voz, "Voz: en espera", estilo.OFF)
        self.operacion_tab.set_voz(escuchando)

    def update_status(self, code):
        # ---- SSH ----
        if code == "RPi_OK":
            self.set_status(self.lbl_rpi, "SSH: ON", estilo.ACENTO)
            self.raspberry_tab.btn_connect.setEnabled(False)
            self.raspberry_tab.btn_start_sepower.setEnabled(True)

        elif code == "RPi_ERR":
            self.rpi_ssh_connected = False
            self.rpi_sepower_running = False
            self.set_status(self.lbl_rpi, "Campo: ERROR", estilo.PELIGRO_TEXTO)
            self.raspberry_tab.btn_connect.setEnabled(True)
            self.raspberry_tab.btn_start_sepower.setEnabled(False)
            self.raspberry_tab.btn_stop_sepower.setEnabled(False)
            self.raspberry_tab.set_sepower_activo(False)
            self.calibracion_tab.set_sepower_activo(False)
            for panel in self.paneles_emergencia:
                panel.set_sepower_activo(False)
            self.ssh_worker.esp_ok = False
            self.set_status(self.lbl_esp, "Actuación: OFF", estilo.PELIGRO_TEXTO)

        # ---- SEpower ----
        elif code == "RPI_SEP_ON":
            self.set_status(self.lbl_rpi, "Campo: ON", estilo.OK_TEXTO)
            self.raspberry_tab.btn_start_sepower.setEnabled(False)
            self.raspberry_tab.btn_stop_sepower.setEnabled(True)
            self.raspberry_tab.set_sepower_activo(True)
            self.calibracion_tab.set_sepower_activo(True)
            for panel in self.paneles_emergencia:
                panel.set_sepower_activo(True)

        elif code == "RPI_SEP_OFF":
            self.rpi_sepower_running = False
            self.set_status(self.lbl_rpi, "SSH: ON", estilo.ACENTO)
            self.raspberry_tab.btn_connect.setEnabled(False)
            self.raspberry_tab.btn_start_sepower.setEnabled(True)
            self.raspberry_tab.btn_stop_sepower.setEnabled(False)
            self.raspberry_tab.set_sepower_activo(False)
            self.calibracion_tab.set_sepower_activo(False)
            for panel in self.paneles_emergencia:
                panel.set_sepower_activo(False)
            self.ssh_worker.esp_ok = False
            self.set_status(self.lbl_esp, "Actuación: OFF", estilo.PELIGRO_TEXTO)

        # ---- PC ----
        
        elif code == "PC_ON":
            self.set_status(self.lbl_pc, "Operación: Percepción ON", estilo.OK_TEXTO)

            pc_tab = self.pc_tab
            pc_tab.btn_start.setEnabled(False)
            pc_tab.btn_stop.setEnabled(True)

        elif code == "PC_OFF":
            self.set_status(self.lbl_pc, "Operación: Percepción OFF", estilo.PELIGRO_TEXTO)

            pc_tab = self.pc_tab
            pc_tab.btn_start.setEnabled(True)
            pc_tab.btn_stop.setEnabled(False)
            
        
        # ---- Socket ----
        # OJO: estos estados NO tocan los botones. Los reintentos de conexión
        # emiten SOCKET_OFF/CAMARA_OFF constantemente y dejaban "Detener" gris.
        elif code == "SOCKET_ON":
            self.set_status(self.lbl_socket, "Enlace: ON", estilo.OK_TEXTO)
            self.operacion_tab.set_lampara("socket", "ok")

        elif code == "SOCKET_OFF":
            self.set_status(self.lbl_socket, "Enlace: OFF", estilo.PELIGRO_TEXTO)
            self.operacion_tab.set_lampara("socket", "mal")

        # ---- Camara ----
        elif code == "CAMARA_ON":
            self.set_status(self.lbl_camera, "Visión: ON", estilo.OK_TEXTO)
            self.operacion_tab.set_lampara("camara", "ok")

        elif code == "CAMARA_OFF":
            self.set_status(self.lbl_camera, "Visión: OFF", estilo.PELIGRO_TEXTO)
            self.operacion_tab.set_lampara("camara", "mal")
        
        # ---- Parada de emergencia ----
        elif code == "EMERGENCIA_ENCLAVADA":
            for panel in self.paneles_emergencia:
                panel.set_estado_emergencia("enclavada")

        elif code == "EMERGENCIA_DESENCLAVADA":
            for panel in self.paneles_emergencia:
                panel.set_estado_emergencia("desenclavada")

        elif code == "EMERGENCIA_NORMAL":
            for panel in self.paneles_emergencia:
                panel.set_estado_emergencia("normal")

        # ---- ESP32 ----
        elif code == "ESP32_ON":
            self.set_status(self.lbl_esp, "Actuación: ON", estilo.OK_TEXTO)
            self.operacion_tab.set_lampara("esp", "ok")

        elif code == "ESP32_OFF":
            self.set_status(self.lbl_esp, "Actuación: OFF", estilo.PELIGRO_TEXTO)
            self.operacion_tab.set_lampara("esp", "mal")
        
    def set_status(self, label, text, color):
        label.setText(text)
        label.setStyleSheet(
            "padding: 6px 14px; border-right: 1px solid %s;"
            "font-size: %dpx; font-weight: 700; color: %s;"
            % (estilo.BORDE, estilo.F_ETIQUETA, color))

    def closeEvent(self, event):
        # Cerrar la GUI tiene que llevarse todo: si no, TTpower y sus
        # subprocesos quedaban vivos con el micrófono y el socket tomados.
        try:
            self.ttpower_worker.stop()
        except Exception:
            pass
        try:
            self.ssh_worker.stop()
        except Exception:
            pass
        if hasattr(self, "video_worker"):
            self.video_worker.stop()
            self.video_worker.wait()
        event.accept()

    
# ---------------------------
# Logicas de fondo
# ---------------------------
class SSHWorker(QThread):
    output_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    fase_signal = pyqtSignal(str)       # fase gruesa del ciclo, o "---" al terminar
    operacion_signal = pyqtSignal(str)  # "caja -> estante 1"
    paso_signal = pyqtSignal(int, int)  # paso n de N
    ocupacion_signal = pyqtSignal(dict) # {"caja_0": True, ...}
    ir_signal = pyqtSignal(bool)        # True = haz cortado (hay objeto)
    evento_signal = pyqtSignal(str)     # texto corto del último evento relevante
    calib_c_signal = pyqtSignal(int)                 # altura actual del jog
    calib_pose_signal = pyqtSignal(str, str, int)    # punto, cual, altura
    calib_tabla_signal = pyqtSignal(dict)            # tabla completa de alturas
    calib_error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.client = None
        self.channel = None
        self.running = True
        self.buffer = ""
        self.esp_ok = False

    def connect_ssh(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=config_red.ip_rpi(),
                username="grua",
                password="grua",
                timeout=5
            )

            self.channel = self.client.invoke_shell()
            self.buffer = ""
            self.esp_ok = False
            self.output_signal.emit("[GUI] Sesión SSH interactiva iniciada")
            self.status_signal.emit("RPi_OK")

            self.start()  # arranca el hilo de lectura

        except Exception as e:
            self.output_signal.emit(f"[RPi][ERR] {e}")
            self.status_signal.emit("RPi_ERR")

    def run(self):
        while self.running and self.channel:
            if self.channel.recv_ready():
                raw = self.channel.recv(4096).decode(errors="ignore")
                clean = ANSI_ESCAPE.sub('', raw)
                self.output_signal.emit(clean)
                
                # Acumular y analizar solo líneas completas
                self.buffer += clean
                while "\n" in self.buffer:
                    linea, self.buffer = self.buffer.split("\n", 1)
                    self._analizar_linea(linea.strip())
            self.msleep(50)
            
    def _analizar_linea(self, linea):
        bajo = linea.lower()

        # Progreso del ciclo para la pantalla de Operación
        if linea.startswith("[FASE]"):
            self.fase_signal.emit(linea[6:].strip())

        if linea.startswith("[OPER]"):
            self.operacion_signal.emit(linea[6:].strip())

        if linea.startswith("[PASO]"):
            try:
                n, total = linea[6:].strip().split("/")
                self.paso_signal.emit(int(n), int(total))
            except ValueError:
                pass

        if linea.startswith("[OCUP]"):
            mapa = {}
            for parte in linea[6:].strip().split(";"):
                if "=" not in parte:
                    continue
                nombre, bits = parte.rsplit("=", 1)
                for i, bit in enumerate(bits.strip()):
                    mapa[f"{nombre.strip()}_{i}"] = (bit == "1")
            if mapa:
                self.ocupacion_signal.emit(mapa)

        if linea.startswith("[CALIB][ERR]"):
            self.calib_error_signal.emit(linea[12:].strip())
        elif linea.startswith("[CALIB]"):
            self._analizar_calib(linea[7:].strip())

        if linea.startswith("[IR] HAZ="):
            self.ir_signal.emit(linea.strip().endswith("0"))   # 0 = haz cortado

        # ---- Estados del sistema ----
        if "esp32" in bajo and "conectada" in bajo:
            if not self.esp_ok:
                self.esp_ok = True
                self.status_signal.emit("ESP32_ON")

        if "esp32" in bajo and "listo" in bajo:
            if not self.esp_ok:
                self.esp_ok = True
                self.status_signal.emit("ESP32_ON")

        # Estados de la parada de emergencia. Se leen de la salida de SEpower
        # porque puede dispararla el sensor IR y continuarla la voz, no solo
        # los botones del HMI.
        if "[emergencia] stop enviado" in bajo:
            self.status_signal.emit("EMERGENCIA_ENCLAVADA")

        if "[emergencia] desenclavada" in bajo:
            self.status_signal.emit("EMERGENCIA_DESENCLAVADA")

        if "[emergencia] continuando" in bajo:
            self.status_signal.emit("EMERGENCIA_NORMAL")

        # SEpower se apagó solo (orden de voz "torre salir", Ctrl+C o error)
        if "sepower detenido" in bajo:
            self.esp_ok = False
            self.status_signal.emit("ESP32_OFF")
            self.status_signal.emit("RPI_SEP_OFF")

        # Último, y sin cortar nada de lo anterior: es solo texto para mostrar.
        self._detectar_evento(linea, bajo)

    # Líneas que valen como "último evento" en la pantalla de Operación.
    # (fragmento en minúsculas a buscar, texto a mostrar)
    EVENTOS = [
        ("trigger con la grúa en movimiento", "Intrusión detectada por sensor IR"),
        ("[emergencia] stop enviado",         "Parada de emergencia"),
        ("[emergencia] desenclavada",         "Parada desenclavada"),
        ("[emergencia] continuando",          "Ciclo reanudado"),
        ("secuencia finalizada",              "Ciclo completado"),
        ("timeout - abortando",               "Timeout de la ESP32: ciclo abortado"),
        ("no hay espacio libre",              "Estante lleno: objeto omitido"),
        ("no hay objeto en",                  "Posición vacía: pedido omitido"),
        ("[home] regreso a reposo",           "Regreso a reposo"),
        ("sepower detenido",                  "Control de Campo detenido"),
    ]

    def _analizar_calib(self, resto):
        """Marcadores del panel de Calibración: TABLA, POSE y C=.

        Los nombres de punto llevan espacios ("bidon uno_0"), por eso el POSE se
        parte desde la derecha."""
        try:
            if resto.startswith("TABLA "):
                self.calib_tabla_signal.emit(json.loads(resto[6:]))
            elif resto.startswith("POSE "):
                punto, cual, c = resto[5:].rsplit(" ", 2)
                self.calib_pose_signal.emit(punto, cual, int(float(c.split("=")[1])))
            elif resto.startswith("C="):
                self.calib_c_signal.emit(int(float(resto[2:])))
        except (ValueError, IndexError, KeyError):
            pass

    def _detectar_evento(self, linea, bajo):
        for fragmento, texto in self.EVENTOS:
            if fragmento in bajo:
                # La parada lleva el motivo entre paréntesis en la misma línea
                if fragmento == "[emergencia] stop enviado" and "(" in linea:
                    texto += " " + linea[linea.rindex("("):].rstrip(".")
                self.evento_signal.emit(texto)
                return

    def send_command(self, cmd):
        if self.channel:
            self.channel.send(cmd + "\n")

    def stop(self):
        self.running = False
        if self.channel:
            self.channel.close()
        if self.client:
            self.client.close()

class TTpowerWorker(QThread):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    voz_signal = pyqtSignal(bool)   # True = escuchó "torre" y espera el comando

    def __init__(self):
        super().__init__()
        self.process = None
        self.running = False

    def run(self):
        env = os.environ.copy()
        env["TT_GUI"] = "1"          # activa modo GUI en TTpower
        env["PYTHONUNBUFFERED"] = "1"
        # Que TTpower use exactamente la misma IP que el HMI, sin releer nada
        env["TT_IP_RPI"] = config_red.ip_rpi()
        env["TT_IP_CAMARA"] = config_red.ip_camara()

        # Grupo de procesos propio: permite pedir un cierre ordenado con
        # CTRL_BREAK y, si no alcanza, matar el árbol entero con taskkill.
        creation = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

        self.process = subprocess.Popen(
            [sys.executable, "-u", str(TTPOWER_PATH)],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            creationflags=creation
        )

        self.running = True
        self.status_signal.emit("PC_ON")

        stdout = self.process.stdout

        # Leer stdout hasta EOF (o sea: hasta que muera TTpower y TODOS sus hijos)
        if stdout is not None:
            try:
                for line in stdout:
                    msg = line.strip()
                    if not msg:
                        continue

                    if msg == "[SOCKET] Conectado a la Raspberry Pi.":
                        self.status_signal.emit("SOCKET_ON")

                    elif "[SOCKET] Error al conectar" in msg:
                        self.status_signal.emit("SOCKET_OFF")

                    elif "[CAM] Conectado a la cámara" in msg:
                        self.status_signal.emit("CAMARA_ON")

                    elif "[CAM] Error conectando cámara" in msg:
                        self.status_signal.emit("CAMARA_OFF")

                    # Palabra de activación: prende el indicador de escucha
                    if msg == "[VOZ] Activado":
                        self.voz_signal.emit(True)
                    elif (msg.startswith("[VOZ] Interpretado:")
                          or msg.startswith("[VOZ] Orden de")
                          or msg == "[VOZ] Reconocimiento detenido."):
                        self.voz_signal.emit(False)

                    self.log_signal.emit(f"[PC] {msg}")
            except (ValueError, OSError):
                pass   # el pipe se cerró mientras leíamos

        try:
            self.process.wait(timeout=5)
        except Exception:
            pass

        self.running = False
        self.voz_signal.emit(False)
        self.status_signal.emit("SOCKET_OFF")
        self.status_signal.emit("CAMARA_OFF")
        self.status_signal.emit("PC_OFF")

    def stop(self):
        proc = self.process
        if proc is None or proc.poll() is not None:
            self.running = False
            return

        self.log_signal.emit("[GUI] Deteniendo TTpower...")
        self.running = False

        # 1) Cierre ordenado: TTpower atrapa la señal y baja sus 3 subprocesos
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.send_signal(signal.SIGINT)
        except Exception:
            pass

        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

        # 2) Garantía: matar el árbol completo (padre + cámara + voz + despachador).
        #    Tiene que hacerse con el padre TODAVÍA vivo para que /T lo recorra.
        if proc.poll() is None:
            self.log_signal.emit("[GUI] Cierre forzado del árbol de procesos...")
            self._matar_arbol(proc.pid)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

        self.wait(2000)   # esperar a que el hilo lector vea el EOF
        self.log_signal.emit("[GUI] TTpower detenido.")

    @staticmethod
    def _matar_arbol(pid):
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            pass


# ---------------------------
# MAIN
# ---------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(estilo.hoja_global())   # una sola hoja para toda la app
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
    
    




