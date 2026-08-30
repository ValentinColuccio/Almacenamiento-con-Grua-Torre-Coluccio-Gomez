"""Pestaña de Calibración del HMI.

Vive en su propio archivo para no seguir engordando main.py, pero corre en el
mismo proceso y sobre el MISMO canal SSH: los comandos a la ESP32 viajan por el
stdin de SEpower, que pertenece a la sesión que lo arrancó. Una app aparte
abriría otra sesión y le hablaría a bash.

Las tramas las arma la Raspberry, no la PC: "angulo_actual" y "radio_actual" son
estado de la máquina y el que vale es el de SEpower. Si la PC compusiera las
tramas con su propia copia de cinematica, el desenrollado de A podría salir 360°
corrido.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox,
)

import estilo

try:
    import cinematica as cin
except Exception:
    cin = None


CUALES = ("toma_aprox", "toma_final", "dejar_aprox", "dejar_final")

ETIQUETAS = {
    "toma_aprox":  "Toma · aproximación",
    "toma_final":  "Toma · final (en el pallet)",
    "dejar_aprox": "Dejar · apoyo (en el pallet)",
    "dejar_final": "Dejar · retiro",
}

SALTOS = (-20, -5, -1, 1, 5, 20)

class CalibracionTab(QWidget):
    """Panel de jog para calibrar las cuatro alturas de cada punto."""

    def __init__(self, ssh_worker):
        super().__init__()
        self.ssh = ssh_worker
        self.sepower_activo = False
        self.tabla_alturas = {}

        raiz = QHBoxLayout(self)
        raiz.setSpacing(16)
        raiz.setContentsMargins(16, 16, 16, 16)
        raiz.addLayout(self._panel_jog(), 1)
        raiz.addWidget(self._construir_tabla(), 1)

        self._set_habilitado(False)

    # ---------------- construcción ----------------

    def _boton(self, texto, nombre=None, alto=None):
        """Botón del panel. El aspecto lo pone la hoja global; acá solo el alto
        táctil y, si corresponde, el rol (objectName)."""
        b = QPushButton(texto)
        b.setFixedHeight(alto or estilo.ALTO_SECUNDARIO)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if nombre:
            b.setObjectName(nombre)
        return b

    def _panel_jog(self):
        col = QVBoxLayout()
        col.setSpacing(12)

        self.combo_punto = QComboBox()
        self.combo_cual = QComboBox()
        self.combo_origen = QComboBox()

        if cin is not None:
            nombres = list(cin.ALTURAS.keys())
            self.combo_punto.addItems(nombres)
            self.combo_origen.addItems(nombres)
        for c in CUALES:
            self.combo_cual.addItem(ETIQUETAS[c], c)

        self.combo_punto.currentTextChanged.connect(self._refrescar_objetivo)
        self.combo_cual.currentIndexChanged.connect(self._refrescar_objetivo)

        self.btn_ir = self._boton("IR AL PUNTO", alto=estilo.ALTO_PRIMARIO)
        self.btn_ir.clicked.connect(self.ir_al_punto)

        # Altura actual, grande y legible desde lejos
        self.lbl_c = QLabel("—")
        self.lbl_c.setAlignment(Qt.AlignCenter)   # type: ignore
        self.lbl_c.setObjectName("dato")
        self.lbl_c.setFixedHeight(110)

        grilla = QGridLayout()
        grilla.setSpacing(12)
        self.botones_jog = []
        for i, salto in enumerate(SALTOS):
            b = self._boton("%+d" % salto, "jog", alto=estilo.ALTO_JOG)
            b.clicked.connect(lambda _, s=salto: self.jog(s))
            grilla.addWidget(b, 0, i)
            self.botones_jog.append(b)

        self.btn_guardar = self._boton("GUARDAR ESTA ALTURA", "primario",
                                   alto=estilo.ALTO_PRIMARIO)
        self.btn_guardar.clicked.connect(self.guardar)

        self.spin_desfase = QSpinBox()
        self.spin_desfase.setRange(-500, 500)
        self.spin_desfase.setSingleStep(5)
        self.spin_desfase.setFixedWidth(110)

        self.btn_copiar = self._boton("COPIAR LAS 4")
        self.btn_copiar.clicked.connect(self.copiar_de)

        fila_copia = QHBoxLayout()
        fila_copia.setSpacing(8)
        fila_copia.addWidget(self.combo_origen, 1)
        fila_copia.addWidget(self.spin_desfase)
        fila_copia.addWidget(self.btn_copiar, 1)

        self.estado = QLabel("Arrancá el Control de Campo para calibrar.")
        self.estado.setWordWrap(True)
        self.estado.setObjectName("etiqueta")

        col.addWidget(QLabel("Punto"))
        col.addWidget(self.combo_punto)
        col.addWidget(QLabel("Altura a calibrar"))
        col.addWidget(self.combo_cual)
        col.addWidget(self.btn_ir)
        col.addWidget(self.lbl_c)
        col.addLayout(grilla)
        col.addWidget(self.btn_guardar)
        col.addSpacing(8)
        col.addWidget(QLabel("Copiar de otro punto, con desfase"))
        col.addLayout(fila_copia)
        col.addWidget(self.estado)
        col.addStretch()
        return col

    def _construir_tabla(self):
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Punto", "Toma aprox", "Toma final", "Dejar aprox", "Dejar final"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        if cin is not None:
            self.set_tabla({n: dict(zip(CUALES, a))
                            for n, a in cin.ALTURAS.items()})
        return self.tabla

    # ---------------- acciones ----------------

    def _enviar(self, cmd):
        if not self.ssh.channel or not self.sepower_activo:
            self._avisar("No hay Control de Campo en marcha.", estilo.PELIGRO_TEXTO)
            return False
        self.ssh.send_command(cmd)
        return True

    def _avisar(self, texto, color=estilo.TEXTO_2):
        self.estado.setText(texto)
        self.estado.setStyleSheet("color: %s; font-size: %dpx;"
                                  % (color, estilo.F_ETIQUETA))

    def punto(self):
        return self.combo_punto.currentText()

    def cual(self):
        return self.combo_cual.currentData()

    def ir_al_punto(self):
        if self._enviar("calib ir %s %s" % (self.punto(), self.cual())):
            self._avisar("Yendo a %s · %s..."
                         % (self.punto(), ETIQUETAS[self.cual()]), estilo.WARN)

    def jog(self, salto):
        self._enviar("calib jog %+d" % salto)

    def guardar(self):
        if self._enviar("calib set"):
            self._avisar("Guardando en alturas.json de la Raspberry...", estilo.WARN)

    def copiar_de(self):
        """Copia las cuatro alturas de otro punto, desplazadas.

        Es el atajo que evita calibrar 40 números de a uno: la superficie
        despareja es propiedad del LUGAR, pero la diferencia entre aproximación
        y final es propiedad del MECANISMO y es la misma en todos los slots."""
        origen = self.combo_origen.currentText()
        destino = self.punto()
        if origen == destino:
            self._avisar("El origen y el destino son el mismo punto.", estilo.WARN)
            return
        fila = self.tabla_alturas.get(origen)
        if not fila:
            self._avisar("No tengo los valores de " + origen, estilo.PELIGRO_TEXTO)
            return
        desfase = self.spin_desfase.value()
        for c in CUALES:
            self._enviar("calib ir %s %s" % (destino, c))
            self._enviar("calib set %d" % (int(fila[c]) + desfase))
        self._avisar("Copiadas las 4 de %s con %+d." % (origen, desfase), estilo.OK_TEXTO)

    def _refrescar_objetivo(self):
        fila = self.tabla_alturas.get(self.punto())
        if fila and self.cual() in fila:
            self.lbl_c.setText(str(fila[self.cual()]))

    # ---------------- entradas desde la Raspberry ----------------

    def set_c(self, valor):
        self.lbl_c.setText(str(valor))

    def set_pose(self, punto, cual, valor):
        self.lbl_c.setText(str(valor))
        self._avisar("En %s · %s. Ajustá con los botones y guardá."
                     % (punto, ETIQUETAS.get(cual, cual)), estilo.OK_TEXTO)

    def set_tabla(self, datos):
        self.tabla_alturas = datos
        self.tabla.setRowCount(len(datos))
        for f, nombre in enumerate(datos):
            fila = datos[nombre]
            self.tabla.setItem(f, 0, QTableWidgetItem(nombre))
            for c, cual in enumerate(CUALES, start=1):
                item = QTableWidgetItem(str(fila.get(cual, "—")))
                item.setTextAlignment(Qt.AlignCenter)   # type: ignore
                self.tabla.setItem(f, c, item)
        self._refrescar_objetivo()

    def set_error(self, texto):
        self._avisar(texto, estilo.PELIGRO_TEXTO)

    def set_sepower_activo(self, activo):
        self.sepower_activo = activo
        self._set_habilitado(activo)
        if activo:
            self._avisar("Listo. Elegí punto y altura, y dale IR AL PUNTO.")
            self.ssh.send_command("calib tabla")
        else:
            self._avisar("Arrancá el Control de Campo para calibrar.")

    def _set_habilitado(self, activo):
        for w in [self.btn_ir, self.btn_guardar, self.btn_copiar] + self.botones_jog:
            w.setEnabled(activo)
