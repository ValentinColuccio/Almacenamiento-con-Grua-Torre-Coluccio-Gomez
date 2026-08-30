"""Sistema de diseño del HMI: tokens y hoja de estilo global.

Viene del documento de diseño (PC/Design/). Antes había 57 `setStyleSheet`
inline con los colores copiados a mano — `#3a3a3a` aparecía 19 veces. Acá está
todo una sola vez, y los widgets se estilan por objectName o por propiedad
dinámica en vez de traer su propio CSS.

Reglas del sistema, en orden de importancia:

- **El rojo es monopolio de la parada de emergencia.** Ningún otro control es
  rojo, ni al fallar. Los errores usan ámbar, o el tinte de alarma sin relleno.
- **El azul es información, no acción**: dice "dónde estoy" y "qué está pasando".
  Nunca en un botón que se aprieta.
- **Deshabilitado pierde color y contraste, nunca tamaño ni posición.** Nada se
  oculta: el layout no se mueve bajo el dedo.
- **Cada cambio de estado mueve al menos dos propiedades** (fondo + borde, o
  fondo + texto). QSS no tiene transiciones: un cambio sutil se pierde con
  vibración y luz de galpón.

Todo se construye con lo que QSS soporta de verdad: color, borde, radio,
padding, `qlineargradient` y pseudo-estados. Cero sombras, cero animación.
"""

# ---------------------------------------------------------------------------
# TOKENS DE COLOR — doce, cada uno con un rol
# ---------------------------------------------------------------------------

BG_APP      = "#0F1419"   # fondo de la ventana y del riel. Nunca lleva texto encima
BG_PANEL    = "#1A2129"   # todo QFrame que agrupa contenido. Un solo nivel
BG_CONTROL  = "#151C23"   # botón secundario, combo, línea de entrada, cabeceras
BG_INSET    = "#06090C"   # solo lo que "entra": cámara y consolas de log

BORDE       = "#2A343E"   # 1 px, separación neutra. Sustituye a toda sombra
BORDE_FUERTE= "#3E4C58"   # 2 px en lo que se toca y no tiene color semántico

TEXTO       = "#E6EDF3"   # dato, valor, título, etiqueta de botón
TEXTO_2     = "#8D9BA8"   # rótulos, unidades, horas. Nunca para el dato en sí

ACENTO      = "#2A9FD8"   # información y "estoy acá". Nunca en un botón de acción
ACENTO_BG   = "#0D2130"

OK          = "#21B364"   # hecho o sano
OK_BG       = "#0E2318"
OK_TEXTO    = "#37D97D"

WARN        = "#E9A21A"   # fuera de rango pero operable. Así el rojo no se gasta
WARN_BG     = "#2A2008"

PELIGRO     = "#C1121C"   # exclusivo de la parada de emergencia
PELIGRO_ALTO= "#D42027"
PELIGRO_BAJO= "#A00C14"
PELIGRO_BORDE = "#FF7A72"
PELIGRO_BG  = "#2B1214"
PELIGRO_TEXTO = "#FF5147"

OFF         = "#4E5862"   # texto de lo inactivo
OFF_BORDE   = "#232C35"

# ---------------------------------------------------------------------------
# ESCALA DE TAMAÑOS — en px, para un panel de 15,6" a 1920×1080 (5,56 px/mm)
# ---------------------------------------------------------------------------

ALTO_ESTOP      = 168   # 30 mm: alcanzable con la palma, sin apuntar
ANCHO_ESTOP     = 600
ALTO_NAV        = 120   # 5 × 120 = 600 de 1080: el desborde es imposible
ANCHO_NAV       = 220
ALTO_PRIMARIO   = 96    # 17 mm
ALTO_SECUNDARIO = 84    # 15 mm: mínimo táctil absoluto con guante
ALTO_JOG        = 84    # cuadrado, en pares +/-
ALTO_FILA       = 64
ALTO_PASO       = 56
ALTO_LAMPARA    = 44
ALTO_CABECERA   = 44    # cabecera de panel, constante en toda la app
ALTO_TITULO     = 48    # barra de título de la ventana
BOTON_TITULO    = 44    # 8 mm: alcanzable, pero no invita a cerrar sin querer
ALTO_BARRA      = 26
ALTO_ESTADO     = 38    # barra de estado inferior: 16 px de texto + padding

SEPARACION      = 16    # entre controles táctiles. 12 solo entre pares +/-
PADDING_PANEL   = 16

# Tipografía
F_DATO      = 56   # cronómetro y número de calibración. Mono, tabular
F_TITULO    = 30   # uno por pantalla
F_BOTON     = 26
F_NAV       = 22
F_ESTOP     = 44
F_CUERPO    = 19
F_PANEL     = 18   # título de panel: lo distingue el peso, no el tamaño
F_ETIQUETA  = 16   # piso absoluto
F_RELOJ     = 34   # reloj de pared: se lee de lejos pero no compite con el dato

SANS = '"IBM Plex Sans", "DejaVu Sans", "Segoe UI", sans-serif'
MONO = '"IBM Plex Mono", "DejaVu Sans Mono", Consolas, monospace'


def hoja_global():
    """QSS de toda la aplicación. Se aplica una vez sobre QApplication."""
    return f"""
/* ---------- base ---------- */
QWidget {{
    background-color: {BG_APP};
    color: {TEXTO};
    font-family: {SANS};
    font-size: {F_CUERPO}px;
}}

QFrame#panel {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDE};
    border-radius: 4px;
}}

QLabel#tituloPantalla {{ font-size: {F_TITULO}px; font-weight: 600; }}
QLabel#tituloPanel    {{ font-size: {F_PANEL}px;  font-weight: 700; color: {TEXTO}; }}
QLabel#etiqueta       {{ font-size: {F_ETIQUETA}px; font-family: {MONO};
                         color: {TEXTO_2}; }}
QLabel#dato           {{ font-size: {F_DATO}px; font-family: {MONO};
                         font-weight: 600; color: {TEXTO}; }}
/* El reloj NO usa el tamaño de dato: "23:02:35" a 56 px pide 448 px de ancho.
   Además es información de contexto, no el número que se está operando. */
QLabel#reloj          {{ font-size: {F_RELOJ}px; font-family: {MONO};
                         font-weight: 600; color: {TEXTO};
                         background-color: {BG_PANEL};
                         border: 1px solid {BORDE}; border-radius: 4px; }}

/* ---------- riel de navegación ---------- */
/* Vertical y a la izquierda: arriba, cinco botones robarían 120 px del alto,
   que es el recurso escaso (cámara 16:9 + mímico + botonera compiten por él).
   El riel cuesta ancho, que sobra, y devuelve el alto completo. */
QWidget#riel {{ background-color: {BG_APP}; }}

QPushButton#navBtn {{
    min-height: {ALTO_NAV}px; max-height: {ALTO_NAV}px;
    min-width: {ANCHO_NAV}px;
    background-color: {BG_APP};
    color: {TEXTO_2};
    border: none;
    /* En reposo el acento va del color del fondo, no transparent: QSS pinta
       transparent como negro en algunos temas. */
    border-left: 6px solid {BG_APP};
    border-bottom: 1px solid {BORDE};
    border-radius: 0;
    /* 12 + 6 del acento = 18: el texto no salta al seleccionar */
    padding-left: 12px; padding-right: 18px;
    font-size: {F_NAV}px; font-weight: 500;
    text-align: left;
}}
QPushButton#navBtn:hover   {{ background-color: {BG_CONTROL}; color: {TEXTO};
                              border-left-color: {BORDE_FUERTE}; }}
QPushButton#navBtn:pressed {{ background-color: {ACENTO_BG}; color: #FFFFFF;
                              border-left-color: {ACENTO}; }}
QPushButton#navBtn:checked {{ background-color: {BG_PANEL}; color: #FFFFFF;
                              border-left-color: {ACENTO}; font-weight: 600; }}
QPushButton#navBtn:disabled{{ color: {OFF}; }}

QLabel#navTitulo {{ font-size: 22px; font-weight: 700; color: {TEXTO};
                    padding: 18px 18px 0 18px; }}
QLabel#navSubtitulo {{ font-size: {F_ETIQUETA}px; font-family: {MONO};
                       color: {TEXTO_2}; padding: 0 18px 18px 18px; }}

/* ---------- botones ---------- */
QPushButton {{
    min-height: {ALTO_SECUNDARIO}px;
    background-color: {BG_CONTROL};
    color: {TEXTO};
    border: 2px solid {BORDE_FUERTE};
    border-radius: 6px;
    padding: 0 20px;
    font-size: {F_BOTON}px; font-weight: 600;
}}
QPushButton:hover   {{ background-color: {BG_PANEL}; border-color: {TEXTO_2}; }}
QPushButton:pressed {{ background-color: {ACENTO_BG}; border-color: {ACENTO}; }}
QPushButton:disabled{{ background-color: {BG_CONTROL}; color: {OFF};
                       border-color: {OFF_BORDE}; }}

QPushButton#primario {{
    min-height: {ALTO_PRIMARIO}px; min-width: 280px;
    background-color: {OK_BG}; color: {OK_TEXTO}; border: 2px solid {OK};
}}
QPushButton#primario:hover   {{ background-color: #14301F; }}
QPushButton#primario:pressed {{ background-color: #0A1A11; border-color: {OK_TEXTO}; }}
QPushButton#primario:disabled{{ background-color: {BG_CONTROL}; color: {OFF};
                                border-color: {OFF_BORDE}; }}

/* La parada: relleno con gradiente = volumen, borde claro de 4 px = halo.
   Sin :hover — su aspecto en reposo ya es el máximo posible.
   Nunca se deshabilita: una parada gris es una contradicción de seguridad. */
QPushButton#estopBtn {{
    min-height: {ALTO_ESTOP}px; max-height: {ALTO_ESTOP}px;
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 {PELIGRO_ALTO}, stop:1 {PELIGRO_BAJO});
    color: #FFFFFF;
    border: 4px solid {PELIGRO_BORDE};
    border-radius: 6px;
    font-size: {F_ESTOP}px; font-weight: 700;
}}
QPushButton#estopBtn:pressed {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #8E0A12, stop:1 #6E060C);
    border-color: #FFFFFF;
}}

QPushButton#jog {{
    min-height: {ALTO_JOG}px; max-height: {ALTO_JOG}px;
    min-width: {ALTO_JOG}px;
    font-family: {MONO}; font-size: 24px; padding: 0;
}}

/* ---------- barra de título ----------
   Es chrome, no un control de operación: no lleva los 84 px táctiles ni el
   borde de 2 px, o los tres botones no entrarían en la barra. 44 px alcanza
   para tocarlos sin que inviten a cerrar la app por accidente. */
QWidget#tituloBarra {{ background-color: {BG_CONTROL};
                       border-bottom: 1px solid {BORDE}; }}
QLabel#tituloVentana {{ font-size: {F_ETIQUETA}px; color: {TEXTO_2};
                        padding-left: 6px; }}

QPushButton#tituloBtn {{
    min-width: {BOTON_TITULO}px; max-width: {BOTON_TITULO}px;
    min-height: {BOTON_TITULO}px; max-height: {BOTON_TITULO}px;
    background-color: transparent;
    color: {TEXTO_2};
    border: none; border-radius: 0;
    padding: 0;
    font-size: 18px; font-weight: 500;
}}
QPushButton#tituloBtn:hover   {{ background-color: {BG_PANEL}; color: {TEXTO}; }}
QPushButton#tituloBtn:pressed {{ background-color: {BG_APP}; }}

/* Cerrar: es el único rojo permitido fuera de la parada, y solo al hover.
   En reposo es igual que los otros dos, así que no compite con la parada. */
QPushButton#cerrarBtn {{
    min-width: {BOTON_TITULO}px; max-width: {BOTON_TITULO}px;
    min-height: {BOTON_TITULO}px; max-height: {BOTON_TITULO}px;
    background-color: transparent;
    color: {TEXTO_2};
    border: none; border-radius: 0;
    padding: 0;
    font-size: 18px; font-weight: 500;
}}
QPushButton#cerrarBtn:hover   {{ background-color: {PELIGRO}; color: #FFFFFF; }}
QPushButton#cerrarBtn:pressed {{ background-color: {PELIGRO_BAJO}; }}

/* ---------- entradas ---------- */
QComboBox, QLineEdit, QSpinBox {{
    min-height: {ALTO_SECUNDARIO}px;
    background-color: {BG_CONTROL};
    color: {TEXTO};
    border: 2px solid {BORDE_FUERTE};
    border-radius: 6px;
    padding: 0 14px;
    font-size: {F_CUERPO}px;
}}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{ border-color: {ACENTO}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_CONTROL}; color: {TEXTO};
    selection-background-color: {ACENTO_BG};
    border: 1px solid {BORDE};
}}

/* ---------- consolas ---------- */
QTextEdit {{
    background-color: {BG_INSET};
    color: {OK_TEXTO};
    font-family: {MONO}; font-size: {F_CUERPO}px;
    border: 1px solid {BORDE};
    border-radius: 4px;
}}

/* ---------- tabla ---------- */
QTableWidget {{
    background-color: {BG_INSET};
    color: {TEXTO};
    gridline-color: {BORDE};
    border: 1px solid {BORDE};
    border-radius: 4px;
    font-size: {F_CUERPO}px;
}}
QHeaderView::section {{
    background-color: {BG_CONTROL}; color: {TEXTO_2};
    padding: 8px; border: none; font-weight: 700;
    font-size: {F_ETIQUETA}px;
}}
QTableWidget::item:selected {{ background-color: {ACENTO_BG}; color: {TEXTO}; }}

/* ---------- barra de progreso ---------- */
QProgressBar {{
    min-height: {ALTO_BARRA}px; max-height: {ALTO_BARRA}px;
    background-color: {BG_CONTROL};
    border: 1px solid {BORDE}; border-radius: 4px;
    padding: 3px;
}}
QProgressBar::chunk {{ background-color: {ACENTO}; border-radius: 2px; }}

/* ---------- estados por propiedad dinámica ----------
   Un solo bloque de QSS sirve para pasos, lámparas y celdas del mímico.
   En Python: w.setProperty("estado", "ok"); repintar(w)                */
QFrame[estado="pendiente"] {{ background-color: {BG_CONTROL}; border: 2px solid {BORDE}; }}
QFrame[estado="ok"]        {{ background-color: {OK_BG};      border: 2px solid {OK}; }}
QFrame[estado="activo"]    {{ background-color: {ACENTO_BG};  border: 2px solid {ACENTO}; }}
QFrame[estado="warn"]      {{ background-color: {WARN_BG};    border: 2px solid {WARN}; }}
QFrame[estado="alarma"]    {{ background-color: {PELIGRO_BG}; border: 2px solid {PELIGRO_TEXTO}; }}
QFrame[estado="off"]       {{ background-color: {BG_CONTROL}; border: 2px solid {OFF_BORDE}; }}

QLabel[estado="pendiente"] {{ color: {TEXTO_2}; }}
QLabel[estado="ok"]        {{ color: {OK_TEXTO}; }}
QLabel[estado="activo"]    {{ color: #FFFFFF; }}
QLabel[estado="warn"]      {{ color: {WARN}; }}
QLabel[estado="alarma"]    {{ color: {PELIGRO_TEXTO}; }}
QLabel[estado="off"]       {{ color: {OFF}; }}

/* ---------- barra de estado ---------- */
QStatusBar {{ background-color: {BG_APP}; color: {TEXTO_2};
              border-top: 1px solid {BORDE}; }}
"""


# El botón de parada, mientras está enclavado, muestra DESENCLAVAR.
# Es la única excepción a la regla "la parada no cambia de aspecto": acá el
# botón deja de ser una parada y pasa a ser otra acción, así que tiene que
# dejar de parecer una parada. Ámbar y no rojo, porque el rojo es monopolio.
QSS_DESENCLAVAR = f"""
QPushButton#estopBtn {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 {WARN}, stop:1 #B8790A);
    color: #1A1200;
    border: 4px solid #FFD166;
}}
QPushButton#estopBtn:pressed {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #B8790A, stop:1 #8A5A06);
    border-color: #FFFFFF;
}}
"""


def repintar(widget):
    """Aplica un cambio de propiedad dinámica.

    Qt no reevalúa el QSS solo cuando cambia una propiedad: hay que forzar el
    unpolish/polish o el widget se queda con el estilo viejo."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def marcar(widget, estado):
    """Cambia el estado semántico de un widget y lo repinta."""
    widget.setProperty("estado", estado)
    repintar(widget)
