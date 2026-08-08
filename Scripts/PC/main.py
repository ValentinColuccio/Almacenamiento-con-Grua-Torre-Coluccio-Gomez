import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QTabWidget, QLabel, QTextEdit,
    QVBoxLayout, QHBoxLayout, QStatusBar, 
    QPushButton, QLineEdit, QSizePolicy
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QUrl
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from matplotlib import text
import paramiko
import time
import re
import subprocess
import os
import sys
import cv2
import socket
import struct
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TTPOWER_PATH = BASE_DIR / "TTpower.py"

ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

IP_RPI = "10.109.34.9"

# ---------------------------
# TAB GLOBAL
# ---------------------------
class GlobalTab(QWidget):
    def __init__(self):
        super().__init__()

        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }

            QTextEdit {
                border: 2px solid #3a3a3a;
                border-radius: 6px;
            }
        """)

        main_layout = QHBoxLayout(self)
        
        # Cámara
        self.camera_widget = CameraWidget()
        
        self.camera_widget.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 3px solid #444;
                border-radius: 8px;
                color: #888;
                font-size: 14px;
            }
        """)

        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(
            "background-color: black;"
            "color: #00FF00;"
            "font-family: Consolas;"  
            "font-size: 15pt;"   
        )

        main_layout.addWidget(self.camera_widget, 2)
        main_layout.addWidget(self.console, 3)
        

    def add_log(self, text):
        # Limpiar códigos ANSI por si llegan
        clean = ANSI_ESCAPE.sub('', text)

        # Detectar origen
        if clean.startswith("[RPi]"):
            color = "#4aa3ff"   # azul
            prefix = "[RPi]"
        elif clean.startswith("[PC]"):
            color = "#55ff55"   # verde
            prefix = "[PC]"
        elif clean.startswith("[GUI]"):
            color = "#FFFFFF"   # blanco
            prefix = "[GUI]"
        else:
            color = "#dddddd"
            prefix = ""

        # Quitar prefijo del mensaje para no duplicarlo
        msg = clean[len(prefix):].lstrip()

        html = (
            f'<span style="color:{color};">'
            f'{prefix} {msg}'
            f'</span>'
        )

        self.console.moveCursor(self.console.textCursor().End)
        self.console.insertHtml(html + "<br>")
        self.console.moveCursor(self.console.textCursor().End)
        self.console.verticalScrollBar().setValue(     
            self.console.verticalScrollBar().maximum()  
        ) 

class CameraWidget(QWebEngineView):
    def __init__(self):
        super().__init__()
        
        self.setMinimumSize(504, 896)
        self.setMaximumSize(504, 896)
        
        # URL de la cámara
        self.setUrl(QUrl("http://192.168.3.11/monitor/image/live-any/overlay-single-custom/-1/errorhighlight"))

# ---------------------------
# TABS secundarias
# ---------------------------
class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent: QMainWindow = parent
        self.setFixedHeight(38)

        self.setStyleSheet("""
            QWidget {
                background-color: #1f1f1f;
            }
            QLabel {
                color: #dddddd;
                font-size: 12pt;
            }
            QPushButton {
                border: none;
                color: white;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton#closeBtn:hover {
                background-color: #c42b1c;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(0)

        self.title = QLabel("Sistema Grúa Torre – Panel de Control")

        btn_min = QPushButton("—")
        btn_max = QPushButton("▢")
        btn_close = QPushButton("✕")
        btn_close.setObjectName("closeBtn")

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

class RaspberryTab(QWidget):
    sepower_status_signal = pyqtSignal(str)
    def __init__(self, ssh_worker):
        super().__init__()
        self.ssh = ssh_worker

        layout = QVBoxLayout(self)

        # Botones
        self.btn_connect = QPushButton("Conectar SSH")
        self.btn_start_sepower = QPushButton("Iniciar SEpower")
        self.btn_stop_sepower = QPushButton("Detener SEpower")

        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(
            "background-color: black;"
            "color: #00FF00;"
            "font-family: Consolas;"
            "font-size: 15pt;"  
        )

        # Input
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ingrese comando y presione Enter")
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: #121212;
                color: #e0e0e0;
                font-size: 11pt;
                padding: 8px;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
            QLineEdit:focus {
                border: 1px solid #1976d2;
            }
            QLineEdit::placeholder {
                color: #8a8a8a;
                font-style: italic;
            }
        """)

        # Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(10, 10, 10, 10)
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_start_sepower)
        btn_layout.addWidget(self.btn_stop_sepower)
        layout.addLayout(btn_layout)
        
        layout.addWidget(self.console)
        layout.addWidget(self.input)
        
        for btn in (
            self.btn_connect,
            self.btn_start_sepower,
            self.btn_stop_sepower
        ):
            btn.setFixedHeight(100)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                font-size: 12pt;
                font-weight: bold;
                border-radius: 8px;
            }

            QPushButton:hover {
                background-color: #42a5f5;
                border: 2px solid #90caf9;
            }

            QPushButton:pressed {
                background-color: #0d47a1;
            }

            QPushButton:disabled {
                background-color: #37474f;
                color: #78909c;
                border: 2px dashed #546e7a;
            }
        """)  
        
        self.btn_start_sepower.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-size: 12pt;
                font-weight: bold;
                border-radius: 8px;
            }

            QPushButton:hover {
                background-color: #66bb6a;
                border: 2px solid #a5d6a7;
            }

            QPushButton:pressed {
                background-color: #1b5e20;
            }

            QPushButton:disabled {
                background-color: #2e4f32;
                color: #81c784;
                border: 2px dashed #4caf50;
            }
        """) 

        self.btn_stop_sepower.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                font-size: 12pt;
                font-weight: bold;
                border-radius: 8px;
            }

            QPushButton:hover {
                background-color: #ef5350;
                border: 2px solid #ef9a9a;
            }

            QPushButton:pressed {
                background-color: #8e0000;
            }

            QPushButton:disabled {
                background-color: #5f2a2a;
                color: #ef9a9a;
                border: 2px dashed #e57373;
            }
        """)
        
        # Conexiones
        self.btn_connect.clicked.connect(self.ssh.connect_ssh)
        self.btn_start_sepower.clicked.connect(self.start_sepower)  
        self.btn_stop_sepower.clicked.connect(self.stop_sepower)
        self.input.returnPressed.connect(self.send_command)

        self.ssh.output_signal.connect(self.append_output)

        self.btn_start_sepower.setEnabled(False) 
        self.btn_stop_sepower.setEnabled(False)  
        self.btn_start_sepower.setEnabled(False)
        self.btn_stop_sepower.setEnabled(False)                                  

    def append_output(self, text):
        self.console.moveCursor(self.console.textCursor().End)
        self.console.insertPlainText(text)
        self.console.moveCursor(self.console.textCursor().End)

    def send_command(self):
        cmd = self.input.text()
        if not cmd:
            return
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
        self.btn_start = QPushButton("Iniciar TTpower")
        self.btn_stop = QPushButton("Detener TTpower")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_start.setFixedHeight(100)
        self.btn_stop.setFixedHeight(100)
        
        self.btn_start.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_stop.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(10, 10, 10, 10)
        
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-size: 13pt;
                font-weight: bold;
                border-radius: 8px;
            }

            QPushButton:hover {
                background-color: #66bb6a;
                border: 2px solid #a5d6a7;
            }

            QPushButton:pressed {
                background-color: #1b5e20;
            }

            QPushButton:disabled {
                background-color: #2e4f32;
                color: #81c784;
                border: 2px dashed #4caf50;
            }
        """)

        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                font-size: 13pt;
                font-weight: bold;
                border-radius: 8px;
            }

            QPushButton:hover {
                background-color: #ef5350;
                border: 2px solid #ef9a9a;
            }

            QPushButton:pressed {
                background-color: #8e0000;
            }

            QPushButton:disabled {
                background-color: #5f2a2a;
                color: #ef9a9a;
                border: 2px dashed #e57373;
            }
        """)

        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(
            "background-color: black;"
            "color: #00FF00;"
            "font-family: Consolas;"
            "font-size: 15pt;"
        )

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
        self.worker.stop()

# ---------------------------
# VENTANA PRINCIPAL
# ---------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setStyleSheet("""
            QMainWindow {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a3a3a,
                    stop:1 #1f1f1f
                );
            }
        """)

        self.setWindowTitle("Sistema Grúa Torre - Panel de Control")
        self.resize(1200, 700)
        self.setWindowFlags(Qt.FramelessWindowHint)#type: ignore
        self.setAttribute(Qt.WA_TranslucentBackground, False)#type: ignore

        # ----- Tabs -----
        self.tabs = QTabWidget()
        
        self.tabs.setStyleSheet("""
        QTabWidget::pane {
            border: 1px solid #333;
            top: -1px;
        }

        /* Barra de tabs */
        QTabBar::tab {
            background: #222;
            color: #00FF00;
            font-family: Consolas;
            font-size: 15pt;
            min-height: 500px;
            min-width: 200px;
            padding: 10px;
            border: 1px solid #333;
        }

        /* Tab seleccionada */
        QTabBar::tab:selected {
            background: #000;
            color: #00FF00;
            border-bottom: 3px solid #00FF00;
        }

        /* Hover */
        QTabBar::tab:hover {
            background: #111;
        }

        /* Quitar margen raro */
        QTabBar::tab:!selected {
            margin-top: 2px;
        }
        """)

        self.global_tab = GlobalTab()
        self.tabs.addTab(self.global_tab, "GLOBAL")
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444;
                background: #1e1e1e;
            }

            QTabBar::tab {
                background: #2b2b2b;
                color: #ccc;
                padding: 8px;
                min-width: 400px;
            }

            QTabBar::tab:selected {
                background: #1e1e1e;
                color: #00c8ff;
                font-weight: bold;
            }

            QTabBar::tab:hover {
                background: #3a3a3a;
            }
            
            QWidget#centralwidget {
                border: 1px solid #444;
            }
        """)
        
        self.ssh_worker = SSHWorker()
        self.ssh_worker.status_signal.connect(self.update_status)
        self.ssh_worker.output_signal.connect(lambda txt: self.global_tab.add_log("[RPi] " + txt))
        self.raspberry_tab = RaspberryTab(self.ssh_worker)
        self.raspberry_tab.sepower_status_signal.connect(self.update_status)
        self.tabs.addTab(self.raspberry_tab, "Raspberry / SSH")

        self.ttpower_worker = TTpowerWorker()
        self.ttpower_worker.log_signal.connect(self.global_tab.add_log)
        self.ttpower_worker.status_signal.connect(self.update_status)
        self.tabs.insertTab(1,ControlPCTab(self.ttpower_worker),"Control PC")


        #--------------------------------------------------------------------

        central = QWidget()
        central.setStyleSheet("background-color: #1e1e1e;")

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = TitleBar(self)

        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(self.tabs)

        self.setCentralWidget(central)

        # ----- Barra de estado -----
        self.status = QStatusBar()
        self.status.setFixedHeight(28)
        self.setStatusBar(self.status)

        self.status.setStyleSheet("""
            QStatusBar {
                background-color: #1f1f1f;
                color: #ddd;
                border-top: 1px solid #444;
            }
        """)
        
        def make_status_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("""
                QLabel {
                    padding: 4px 10px;
                    border-right: 1px solid #444;
                    color: #aaa;
                    font-size: 10pt;
                }
            """)
            return lbl

        self.lbl_pc       = make_status_label("PC:")
        self.lbl_camera   = make_status_label("Cámara:")
        self.lbl_socket   = make_status_label("Socket:")
        self.lbl_rpi      = make_status_label("RPi:")
        self.lbl_esp  = make_status_label("ESP32:")
        
        self.status.addWidget(self.lbl_pc)
        self.status.addWidget(self.lbl_camera)
        self.status.addWidget(self.lbl_socket)
        self.status.addWidget(self.lbl_rpi)
        self.status.addWidget(self.lbl_esp)
        
        self.set_status(self.lbl_pc, "PC: OFF", "#f44336")
        self.set_status(self.lbl_camera, "Cámara: OFF", "#f44336")
        self.set_status(self.lbl_socket, "Socket: OFF", "#f44336")
        self.set_status(self.lbl_rpi, "RPi: OFF", "#f44336")
        self.set_status(self.lbl_esp, "ESP32: OFF", "#f44336")
        
        # Logs de prueba
        self.global_tab.add_log("[GUI] Interfaz iniciada correctamente.")     
    
    def update_status(self, code):
        # ---- SSH ----
        if code == "RPi_OK":
            self.set_status(self.lbl_rpi, "SSH: ON", "#2196f3")
            self.tabs.widget(2).btn_connect.setEnabled(False)
            self.tabs.widget(2).btn_start_sepower.setEnabled(True)

        elif code == "RPi_ERR":
            self.rpi_ssh_connected = False
            self.rpi_sepower_running = False
            self.set_status(self.lbl_rpi, "RPi: ERROR", "#f44336")
            self.tabs.widget(2).btn_connect.setEnabled(True)
            self.tabs.widget(2).btn_start_sepower.setEnabled(False)
            self.tabs.widget(2).btn_stop_sepower.setEnabled(False)
            self.ssh_worker.esp_ok = False
            self.set_status(self.lbl_esp, "ESP32: OFF", "#f44336")

        # ---- SEpower ----
        elif code == "RPI_SEP_ON":
            self.set_status(self.lbl_rpi, "RPi: ON", "#4caf50")
            self.tabs.widget(2).btn_start_sepower.setEnabled(False)
            self.tabs.widget(2).btn_stop_sepower.setEnabled(True)

        elif code == "RPI_SEP_OFF":
            self.rpi_sepower_running = False
            self.set_status(self.lbl_rpi, "SSH: ON", "#2196f3")
            self.tabs.widget(2).btn_connect.setEnabled(False)
            self.tabs.widget(2).btn_start_sepower.setEnabled(True)
            self.tabs.widget(2).btn_stop_sepower.setEnabled(False)
            self.ssh_worker.esp_ok = False
            self.set_status(self.lbl_esp, "ESP32: OFF", "#f44336")
            
        # ---- PC ----   
        
        elif code == "PC_ON":
            self.set_status(self.lbl_pc, "PC: TTpower ON", "#4caf50")

            pc_tab = self.tabs.widget(1)  # Control PC
            pc_tab.btn_start.setEnabled(False)
            pc_tab.btn_stop.setEnabled(True)

        elif code == "PC_OFF":
            self.set_status(self.lbl_pc, "PC: TTpower OFF", "#f44336")

            pc_tab = self.tabs.widget(1)
            pc_tab.btn_start.setEnabled(True)
            pc_tab.btn_stop.setEnabled(False)
            
        
        # ---- Socket ---- 
        elif code == "SOCKET_ON":
            self.set_status(self.lbl_socket, "Socket: ON", "#4caf50")

            pc_tab = self.tabs.widget(1)  # Control PC
            pc_tab.btn_start.setEnabled(False)
            pc_tab.btn_stop.setEnabled(True)

        elif code == "SOCKET_OFF":
            self.set_status(self.lbl_socket, "Socket: OFF", "#f44336")

            pc_tab = self.tabs.widget(1)
            pc_tab.btn_start.setEnabled(True)
            pc_tab.btn_stop.setEnabled(False)
            
        # ---- Camara ---- 
        elif code == "CAMARA_ON":
            self.set_status(self.lbl_camera, "Cámara: ON", "#4caf50")

            pc_tab = self.tabs.widget(1)  # Control PC
            pc_tab.btn_start.setEnabled(False)
            pc_tab.btn_stop.setEnabled(True)

        elif code == "CAMARA_OFF":
            self.set_status(self.lbl_camera, "Cámara: OFF", "#f44336")

            pc_tab = self.tabs.widget(1)
            pc_tab.btn_start.setEnabled(True)
            pc_tab.btn_stop.setEnabled(False)
        
        # ---- ESP32 ----    
        elif code == "ESP32_ON":
            self.set_status(self.lbl_esp, "ESP32: ON", "#4caf50")

        elif code == "ESP32_OFF":
            self.set_status(self.lbl_esp, "ESP32: OFF", "#f44336")
        
    def set_status(self, label, text, color):
            label.setText(text)
            label.setStyleSheet(f"""
                QLabel {{
                    padding: 4px 10px;
                    border-right: 1px solid #444;
                    font-size: 10pt;
                    font-weight: bold;
                    color: {color};
                }}
            """)

    def closeEvent(self, event):
        if hasattr(self, "video_worker"):
            self.video_worker.stop()
            self.video_worker.wait()

    
# ---------------------------
# Logicas de fondo
# ---------------------------
class SSHWorker(QThread):
    output_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)

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
                hostname=IP_RPI,
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

        if "esp32" in bajo and "conectada" in bajo:
            if not self.esp_ok:
                self.esp_ok = True
                self.status_signal.emit("ESP32_ON")
                
        if "esp32" in bajo and "listo" in bajo:
            if not self.esp_ok:
                self.esp_ok = True
                self.status_signal.emit("ESP32_ON")

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

    def __init__(self):
        super().__init__()
        self.process = None
        self.running = False

    def run(self):
        env = os.environ.copy()
        env["TT_GUI"] = "1"   # activa modo GUI en TTpower

        self.process = subprocess.Popen(
            [sys.executable, str(TTPOWER_PATH)],
            cwd=str(BASE_DIR),            
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )

        self.running = True
        self.status_signal.emit("PC_ON")

        stdout = self.process.stdout

        # Leer stdout
        if stdout is not None:
            for line in stdout: 
                if not self.running:
                    break

                msg = line.strip()

                if msg == "[SOCKET] Conectado a la Raspberry Pi.":
                    self.status_signal.emit("SOCKET_ON")

                elif "[SOCKET] Error al conectar" in msg:
                    self.status_signal.emit("SOCKET_OFF")

                elif "[CAM] Conectado a la cámara" in msg:
                    self.status_signal.emit("CAMARA_ON")

                elif "[CAM] Error conectando cámara" in msg:
                    self.status_signal.emit("CAMARA_OFF")

                self.log_signal.emit(f"[PC] {msg}")



        self.running = False
        self.status_signal.emit("PC_OFF")

    def stop(self):
        if self.process and self.running:
            self.log_signal.emit("[GUI] Deteniendo TTpower...")
            self.running = False
            self.process.terminate()

            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.log_signal.emit("[GUI] TTpower forzado a cerrar")


# ---------------------------
# MAIN
# ---------------------------
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
    
    




