"""
=====================================================================
 CALCULADORA DE PRODUCCIÓN DE ENERGÍA SOLAR
 Club de Ciencias - Proyecto de 5 Sábados
=====================================================================

 Estima la energía que produciría un sistema fotovoltaico según:
   - Ubicación (irradiación solar local)
   - Área e inclinación del panel
   - Eficiencia del panel y pérdidas del sistema

 Incluye gráficas mensuales, ahorro económico, CO2 evitado y
 exportación de resultados a CSV y PDF.

 Requisitos:
   pip install matplotlib

 Autor: Club de Ciencias
=====================================================================
"""

import csv
import json
import math
import threading
import tkinter as tk
import urllib.parse
import urllib.request
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# =====================================================================
#  NASA POWER API — irradiación solar de cualquier punto del mundo
#  Devuelve promedio mensual histórico (kWh/m²/día) por lat/lon.
# =====================================================================
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"


def obtener_hsp_nasa(latitud, longitud, timeout=20):
    """
    Consulta NASA POWER y devuelve (hsp_anual, lista_mensual).
    hsp_anual: float en kWh/m²/día
    lista_mensual: 12 valores (Ene..Dic)
    Lanza excepción si la red falla o la respuesta es inválida.
    """
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude": f"{longitud}",
        "latitude": f"{latitud}",
        "format": "JSON",
    }
    url = f"{NASA_POWER_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ClubCiencias/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    valores = data["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    claves_mes = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    mensual = [float(valores[m]) for m in claves_mes]
    anual = float(valores.get("ANN", sum(mensual) / 12))
    return anual, mensual


# =====================================================================
#  DATOS BASE: irradiación solar promedio (HSP - Horas Sol Pico)
#  Fuente: SENER / NASA POWER (kWh/m²/día, promedio anual)
# =====================================================================
CIUDADES_MEXICO = {
    "Mexicali, BC":      {"hsp": 6.20, "latitud": 32.6},
    "Hermosillo, SON":   {"hsp": 6.00, "latitud": 29.1},
    "Chihuahua, CHIH":   {"hsp": 5.80, "latitud": 28.6},
    "Tijuana, BC":       {"hsp": 5.50, "latitud": 32.5},
    "Monterrey, NL":     {"hsp": 5.50, "latitud": 25.7},
    "La Paz, BCS":       {"hsp": 6.10, "latitud": 24.1},
    "Durango, DGO":      {"hsp": 5.70, "latitud": 24.0},
    "Guadalajara, JAL":  {"hsp": 5.60, "latitud": 20.7},
    "León, GTO":         {"hsp": 5.70, "latitud": 21.1},
    "Querétaro, QRO":    {"hsp": 5.60, "latitud": 20.6},
    "Ciudad de México":  {"hsp": 5.30, "latitud": 19.4},
    "Puebla, PUE":       {"hsp": 5.40, "latitud": 19.0},
    "Veracruz, VER":     {"hsp": 4.90, "latitud": 19.2},
    "Acapulco, GRO":     {"hsp": 5.60, "latitud": 16.9},
    "Oaxaca, OAX":       {"hsp": 5.50, "latitud": 17.1},
    "Mérida, YUC":       {"hsp": 5.50, "latitud": 20.9},
    "Cancún, QROO":      {"hsp": 5.40, "latitud": 21.2},
    "Tuxtla Gutiérrez":  {"hsp": 5.20, "latitud": 16.8},
}

# Factor mensual relativo (1.00 = promedio anual). Hemisferio norte.
FACTOR_MENSUAL = [0.82, 0.90, 1.05, 1.12, 1.15, 1.12,
                  1.08, 1.08, 1.00, 0.95, 0.85, 0.80]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
DIAS_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Factor de emisión del sistema eléctrico nacional (CRE 2023)
FACTOR_CO2 = 0.494  # kg CO2 / kWh

# Consumo promedio mensual de un hogar mexicano (CFE)
CONSUMO_HOGAR_PROMEDIO = 250  # kWh/mes

# Tipos de sistema fotovoltaico
#   ganancia: factor aplicado a la producción del panel fijo óptimo
#   costo:    factor aplicado al costo del sistema (informativo)
TIPOS_SISTEMA = {
    "Fijo":             {"ganancia": 1.00, "costo": 1.00,
                          "desc": "Panel inmóvil, orientado al sur"},
    "Seguidor 1 eje":   {"ganancia": 1.27, "costo": 1.25,
                          "desc": "Rota este-oeste durante el día"},
    "Seguidor 2 ejes":  {"ganancia": 1.38, "costo": 1.50,
                          "desc": "Sigue al sol en azimut y altitud"},
}

# Costo del sistema fotovoltaico (precios México 2024–2025)
COSTO_FIJO_DEFAULT = 15000   # MXN: inversor + cableado + instalación base
COSTO_POR_M2_DEFAULT = 4500  # MXN/m² de panel: paneles + estructura


def calcular_costo_sistema(area, tipo_sistema,
                           costo_fijo=COSTO_FIJO_DEFAULT,
                           costo_por_m2=COSTO_POR_M2_DEFAULT):
    """Costo total estimado del sistema fotovoltaico instalado en México."""
    multiplicador = TIPOS_SISTEMA.get(tipo_sistema,
                                     TIPOS_SISTEMA["Fijo"])["costo"]
    return (costo_fijo + area * costo_por_m2) * multiplicador


# =====================================================================
#  TARIFAS CFE (México) — para modo ingeniería
#  Valores aproximados de referencia (mediados 2024-2025). CFE ajusta
#  los precios cada mes — ver https://app.cfe.mx/aplicaciones/ccfe/tarifas/
#
#  Estructura:
#    meses_verano: lista de meses (1=ene..12=dic) que aplican bloques de verano
#    bloques_verano / bloques_invierno: lista de (límite_kWh, precio_$_por_kWh)
#       el límite es acumulado por mes; precio se aplica en cascada
#    limite_dac_mensual: si el promedio anual supera este valor → DAC
#    cargo_fijo_mensual: solo para DAC y comercial
# =====================================================================
TARIFAS_CFE = {
    "1": {
        "nombre": "Tarifa 1 (templada)",
        "meses_verano": [],
        "bloques": [(75, 0.953), (140, 1.153), (float("inf"), 3.378)],
        "limite_dac_mensual": 250,
        "cargo_fijo_mensual": 0,
    },
    "1A": {
        "nombre": "Tarifa 1A (≥25 °C verano)",
        "meses_verano": [4, 5, 6, 7, 8, 9],
        "bloques_verano":  [(100, 0.812), (150, 0.991), (float("inf"), 2.971)],
        "bloques_invierno":[(75,  0.812), (140, 0.991), (float("inf"), 2.971)],
        "limite_dac_mensual": 300,
        "cargo_fijo_mensual": 0,
    },
    "1B": {
        "nombre": "Tarifa 1B (≥28 °C verano)",
        "meses_verano": [4, 5, 6, 7, 8, 9, 10],
        "bloques_verano":  [(125, 0.776), (225, 0.948), (float("inf"), 2.795)],
        "bloques_invierno":[(75,  0.776), (140, 0.948), (float("inf"), 2.795)],
        "limite_dac_mensual": 400,
        "cargo_fijo_mensual": 0,
    },
    "1C": {
        "nombre": "Tarifa 1C (≥30 °C verano)",
        "meses_verano": [4, 5, 6, 7, 8, 9, 10, 11],
        "bloques_verano":  [(150, 0.703), (300, 0.860), (450, 1.106), (float("inf"), 2.795)],
        "bloques_invierno":[(75,  0.703), (140, 0.860), (float("inf"), 2.795)],
        "limite_dac_mensual": 850,
        "cargo_fijo_mensual": 0,
    },
    "1D": {
        "nombre": "Tarifa 1D (≥31 °C verano)",
        "meses_verano": [4, 5, 6, 7, 8, 9, 10, 11],
        "bloques_verano":  [(175, 0.703), (400, 0.860), (600, 1.106), (float("inf"), 2.795)],
        "bloques_invierno":[(75,  0.703), (140, 0.860), (float("inf"), 2.795)],
        "limite_dac_mensual": 1000,
        "cargo_fijo_mensual": 0,
    },
    "1E": {
        "nombre": "Tarifa 1E (≥32 °C verano)",
        "meses_verano": [4, 5, 6, 7, 8, 9, 10, 11],
        "bloques_verano":  [(300, 0.578), (750, 0.752), (900, 1.106), (float("inf"), 2.795)],
        "bloques_invierno":[(75,  0.578), (140, 0.752), (float("inf"), 2.795)],
        "limite_dac_mensual": 2000,
        "cargo_fijo_mensual": 0,
    },
    "1F": {
        "nombre": "Tarifa 1F (≥33 °C verano)",
        "meses_verano": [4, 5, 6, 7, 8, 9, 10, 11],
        "bloques_verano":  [(300, 0.578), (1200, 0.752), (2500, 1.106), (float("inf"), 2.795)],
        "bloques_invierno":[(75,  0.578), (140,  0.752), (float("inf"), 2.795)],
        "limite_dac_mensual": 2500,
        "cargo_fijo_mensual": 0,
    },
    "DAC": {
        "nombre": "DAC (Doméstica Alto Consumo)",
        "meses_verano": [],
        "bloques": [(float("inf"), 6.069)],
        "limite_dac_mensual": float("inf"),
        "cargo_fijo_mensual": 109.95,
    },
    "PDBT": {
        # Pequeña Demanda en Baja Tensión (comercial < 25 kW).
        # Tarifa única por kWh + cargo fijo mensual. No tiene DAC.
        # Valor promedio región Noroeste 2024 (varía cada mes).
        "nombre": "PDBT (Comercial < 25 kW)",
        "meses_verano": [],
        "bloques": [(float("inf"), 5.00)],
        "limite_dac_mensual": float("inf"),
        "cargo_fijo_mensual": 70.00,
    },
}


def costo_factura_mes(consumo_kwh, tarifa, mes):
    """Calcula el costo de una factura mensual según la tarifa CFE.

    consumo_kwh: kWh consumidos en el mes (≥ 0)
    tarifa: clave de TARIFAS_CFE
    mes: 1-12
    Devuelve: pesos ($) sin IVA. El IVA se aplica fuera.
    """
    info = TARIFAS_CFE[tarifa]
    if mes in info.get("meses_verano", []) and "bloques_verano" in info:
        bloques = info["bloques_verano"]
    elif "bloques_invierno" in info:
        bloques = info["bloques_invierno"]
    else:
        bloques = info["bloques"]

    costo = 0.0
    consumo_restante = max(0.0, consumo_kwh)
    limite_previo = 0
    for limite, precio in bloques:
        kwh_bloque = min(consumo_restante, limite - limite_previo)
        if kwh_bloque <= 0:
            break
        costo += kwh_bloque * precio
        consumo_restante -= kwh_bloque
        limite_previo = limite

    costo += info.get("cargo_fijo_mensual", 0)
    return costo


def evaluar_dac(consumo_anual_kwh, tarifa):
    """¿El usuario está en DAC? True si el promedio mensual supera el límite."""
    if tarifa == "DAC":
        return True
    promedio = consumo_anual_kwh / 12.0
    limite = TARIFAS_CFE[tarifa]["limite_dac_mensual"]
    return promedio > limite


def simular_factura_anual(consumo_mensual, produccion_mensual, tarifa):
    """Calcula la facturación anual antes y después de instalar solar.

    consumo_mensual: lista de 12 valores (kWh/mes consumidos por el hogar)
    produccion_mensual: lista de 12 valores (kWh/mes producidos por el sistema)
    tarifa: clave de TARIFAS_CFE (la del usuario, por geografía)

    Devuelve un dict con:
      factura_sin_solar, factura_con_solar (pesos/año, sin IVA)
      ahorro_anual_real (factura_sin - factura_con)
      dac_antes, dac_despues (bool)
      tarifa_aplicada_antes, tarifa_aplicada_despues
      consumo_neto_mensual (lista 12)
      precio_efectivo_kwh (lo que realmente vale cada kWh evitado)
    """
    consumo_anual = sum(consumo_mensual)
    dac_antes = evaluar_dac(consumo_anual, tarifa)
    tarifa_antes = "DAC" if dac_antes else tarifa

    factura_antes = sum(
        costo_factura_mes(consumo_mensual[m], tarifa_antes, m + 1)
        for m in range(12)
    )

    # Después de solar: consumo neto = max(0, consumo - producción)
    # (modelo simple sin acumulación inter-mes; net metering instantáneo)
    consumo_neto = [max(0.0, consumo_mensual[m] - produccion_mensual[m])
                    for m in range(12)]
    consumo_neto_anual = sum(consumo_neto)
    dac_despues = evaluar_dac(consumo_neto_anual, tarifa)
    tarifa_despues = "DAC" if dac_despues else tarifa

    factura_despues = sum(
        costo_factura_mes(consumo_neto[m], tarifa_despues, m + 1)
        for m in range(12)
    )

    ahorro = factura_antes - factura_despues
    produccion_anual = sum(produccion_mensual)
    precio_efectivo = (ahorro / produccion_anual) if produccion_anual > 0 else 0

    return {
        "factura_sin_solar": factura_antes,
        "factura_con_solar": factura_despues,
        "ahorro_anual_real": ahorro,
        "dac_antes": dac_antes,
        "dac_despues": dac_despues,
        "tarifa_aplicada_antes": tarifa_antes,
        "tarifa_aplicada_despues": tarifa_despues,
        "consumo_neto_mensual": consumo_neto,
        "precio_efectivo_kwh": precio_efectivo,
        "consumo_anual": consumo_anual,
        "produccion_anual": produccion_anual,
    }

# Paleta de colores — Material Design (igual al índice de calor)
COLOR_FONDO     = "#1976d2"   # azul Material
COLOR_FONDO_2   = "#ff7043"   # naranja Material (acento)
COLOR_TARJETA   = "#FFFFFF"
COLOR_PRIMARIO  = "#1976d2"   # azul primario
COLOR_PRIM_OSC  = "#1565c0"   # azul oscuro
COLOR_NARANJA   = "#ff7043"   # naranja (acento sol)
COLOR_TEXTO     = "#212121"
COLOR_TEXTO_2   = "#424242"
COLOR_TEXTO_SUAVE = "#757575"
COLOR_BORDE     = "#e0e0e0"
COLOR_BORDE_2   = "#f0f0f0"
COLOR_EXITO     = "#2e7d32"
COLOR_ERROR     = "#c62828"
COLOR_GRIS_BG   = "#f5f5f5"


# =====================================================================
#  LÓGICA DE CÁLCULO
# =====================================================================
def factor_inclinacion(angulo_panel, latitud):
    """
    Factor de corrección por inclinación del panel.
    Óptimo cuando el ángulo ≈ latitud. Se modela como un coseno
    de la diferencia (aproximación didáctica útil para el club).
    """
    diferencia = abs(angulo_panel - latitud)
    factor = math.cos(math.radians(diferencia))
    return max(factor, 0.5)  # piso para evitar resultados absurdos


def calcular_produccion(parametros):
    """
    Aplica la fórmula:   E = A * r * HSP * PR * f_inclinacion
    Devuelve un diccionario con todos los resultados.
    """
    area = parametros["area"]
    eficiencia = parametros["eficiencia"] / 100.0
    perdidas = parametros["perdidas"] / 100.0
    pr = 1.0 - perdidas                  # Performance Ratio
    hsp = parametros["hsp"]
    latitud = parametros["latitud"]
    angulo = parametros["angulo"]
    precio_kwh = parametros["precio_kwh"]
    costo_sistema = parametros["costo_sistema"]

    # Tipo de sistema (Fijo, Seguidor 1 eje, Seguidor 2 ejes)
    tipo_sistema = parametros.get("tipo_sistema", "Fijo")
    info_sistema = TIPOS_SISTEMA.get(tipo_sistema, TIPOS_SISTEMA["Fijo"])
    ganancia_seguidor = info_sistema["ganancia"]

    # En seguidores el panel siempre está orientado óptimamente:
    # el factor por inclinación es ~1.0 y la ganancia adicional captura
    # el beneficio de perseguir al sol durante el día.
    if tipo_sistema == "Fijo":
        f_incl = factor_inclinacion(angulo, latitud)
    else:
        f_incl = 1.0

    mensual_personalizado = parametros.get("mensual_personalizado")

    # Energía diaria promedio (kWh/día)
    energia_diaria = area * eficiencia * hsp * pr * f_incl * ganancia_seguidor

    # Producción mensual y anual
    produccion_mensual = []
    if mensual_personalizado is not None:
        # Usamos la curva real (NASA POWER): cada mes con su propio HSP
        for i in range(12):
            kwh_dia_mes = (area * eficiencia * mensual_personalizado[i]
                           * pr * f_incl * ganancia_seguidor)
            produccion_mensual.append(kwh_dia_mes * DIAS_MES[i])
    else:
        for i in range(12):
            kwh_mes = energia_diaria * FACTOR_MENSUAL[i] * DIAS_MES[i]
            produccion_mensual.append(kwh_mes)

    produccion_anual = sum(produccion_mensual)
    ahorro_anual = produccion_anual * precio_kwh
    co2_evitado = produccion_anual * FACTOR_CO2  # kg/año

    # Periodo de retorno (años)
    if ahorro_anual > 0:
        payback = costo_sistema / ahorro_anual
    else:
        payback = float("inf")

    # Cobertura del consumo del hogar
    consumo_anual_hogar = CONSUMO_HOGAR_PROMEDIO * 12
    cobertura = (produccion_anual / consumo_anual_hogar) * 100 if consumo_anual_hogar else 0

    return {
        "energia_diaria": energia_diaria,
        "produccion_mensual": produccion_mensual,
        "produccion_anual": produccion_anual,
        "ahorro_anual": ahorro_anual,
        "co2_evitado": co2_evitado,
        "payback": payback,
        "cobertura": cobertura,
        "factor_inclinacion": f_incl,
        "tipo_sistema": tipo_sistema,
        "ganancia_seguidor": ganancia_seguidor,
    }


def comparar_sistemas(parametros):
    """Calcula los tres sistemas (Fijo, 1 eje, 2 ejes) para comparar."""
    resultados = {}
    for nombre in TIPOS_SISTEMA:
        p = dict(parametros)
        p["tipo_sistema"] = nombre
        resultados[nombre] = calcular_produccion(p)
    return resultados


# =====================================================================
#  INTERFAZ GRÁFICA
# =====================================================================
class CalculadoraSolarApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Calculadora de Energía Solar - Club de Ciencias")
        self.geometry("1180x780")
        self.configure(bg=COLOR_FONDO)
        self.minsize(1080, 720)

        self.resultado = None  # se llena tras cada cálculo

        self._configurar_estilos()
        self._construir_layout()

    # ----------------------------- estilos -----------------------------
    def _configurar_estilos(self):
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        # Fondo de la ventana = azul Material (como el gradient web)
        estilo.configure("TFrame", background=COLOR_FONDO)
        estilo.configure("Card.TFrame", background=COLOR_TARJETA, relief="flat")
        estilo.configure("Header.TFrame", background=COLOR_TARJETA, relief="flat")

        # Etiquetas sobre fondo azul (header) = texto blanco
        estilo.configure("TLabel",
                         background=COLOR_FONDO,
                         foreground="white",
                         font=("Helvetica", 10))
        # Etiquetas sobre tarjetas blancas = texto oscuro
        estilo.configure("Card.TLabel",
                         background=COLOR_TARJETA,
                         foreground=COLOR_TEXTO_2,
                         font=("Helvetica", 10))
        estilo.configure("Header.TLabel",
                         background=COLOR_TARJETA,
                         foreground=COLOR_TEXTO,
                         font=("Helvetica", 10))
        estilo.configure("Titulo.TLabel",
                         background=COLOR_TARJETA,
                         foreground=COLOR_TEXTO,
                         font=("Helvetica", 18, "bold"))
        estilo.configure("Subtitulo.TLabel",
                         background=COLOR_TARJETA,
                         foreground=COLOR_TEXTO_SUAVE,
                         font=("Helvetica", 10))
        estilo.configure("Seccion.TLabel",
                         background=COLOR_TARJETA,
                         foreground=COLOR_TEXTO_2,
                         font=("Helvetica", 13, "bold"))
        estilo.configure("SubSeccion.TLabel",
                         background=COLOR_TARJETA,
                         foreground=COLOR_PRIMARIO,
                         font=("Helvetica", 11, "bold"))
        estilo.configure("ResultadoTitulo.TLabel",
                         background=COLOR_GRIS_BG,
                         foreground=COLOR_TEXTO_SUAVE,
                         font=("Helvetica", 9))
        estilo.configure("ResultadoValor.TLabel",
                         background=COLOR_GRIS_BG,
                         foreground=COLOR_TEXTO,
                         font=("Helvetica", 18, "bold"))
        estilo.configure("Pie.TLabel",
                         background=COLOR_FONDO,
                         foreground="white",
                         font=("Helvetica", 9, "italic"))

        # Notebook (pestañas) con estilo blanco
        estilo.configure("TNotebook",
                         background=COLOR_TARJETA,
                         borderwidth=0,
                         tabmargins=[0, 0, 0, 0])
        estilo.configure("TNotebook.Tab",
                         padding=[14, 8],
                         font=("Helvetica", 10, "bold"),
                         background=COLOR_GRIS_BG,
                         foreground=COLOR_TEXTO_SUAVE)
        estilo.map("TNotebook.Tab",
                   background=[("selected", COLOR_PRIMARIO)],
                   foreground=[("selected", "white")])

        # Combobox y entries
        estilo.configure("TCombobox",
                         fieldbackground="white",
                         background="white")
        estilo.configure("TEntry",
                         fieldbackground="white")
        estilo.configure("TRadiobutton",
                         background=COLOR_TARJETA,
                         foreground=COLOR_TEXTO_2)

    # ----------------------------- layout ------------------------------
    def _construir_layout(self):
        # Encabezado: tarjeta blanca con logo a la izquierda + títulos a la derecha
        cabecera_marco = tk.Frame(self, bg=COLOR_FONDO)
        cabecera_marco.pack(fill="x", padx=20, pady=(20, 12))

        cabecera = tk.Frame(cabecera_marco, bg=COLOR_TARJETA,
                            highlightbackground="#cccccc",
                            highlightthickness=0,
                            padx=22, pady=14)
        cabecera.pack(fill="x")

        # Logo
        self.logo_img = self._cargar_logo()
        if self.logo_img is not None:
            tk.Label(cabecera, image=self.logo_img,
                     bg=COLOR_TARJETA).pack(side="left", padx=(0, 18))

        # Títulos a la derecha
        marco_textos = tk.Frame(cabecera, bg=COLOR_TARJETA)
        marco_textos.pack(side="right", fill="x", expand=True)

        tk.Label(marco_textos,
                 text="Calculadora de Energía Solar",
                 bg=COLOR_TARJETA,
                 fg=COLOR_TEXTO,
                 font=("Helvetica", 18, "bold"),
                 anchor="e").pack(anchor="e")
        tk.Label(marco_textos,
                 text="Desarrollos de Ideas Mexicanas — Para aprendizaje en clubes de ciencia",
                 bg=COLOR_TARJETA,
                 fg=COLOR_TEXTO_SUAVE,
                 font=("Helvetica", 10),
                 anchor="e").pack(anchor="e", pady=(2, 0))

        # Contenedor principal
        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill="both", expand=True, padx=20, pady=4)

        cuerpo.columnconfigure(0, weight=0)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)

        self._panel_entradas(cuerpo)
        self._panel_resultados(cuerpo)

        # Pie de página sobre el fondo azul
        ttk.Label(self,
                  text="Desarrollado por DIMEX — Modelo didáctico. "
                       "Para una instalación real, consulta a un instalador certificado.",
                  style="Pie.TLabel").pack(pady=(2, 14))

    def _cargar_logo(self):
        """Carga el logo Dimex desde un archivo .png en la misma carpeta del script."""
        import os
        try:
            ruta_script = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            ruta_script = os.getcwd()
        for nombre in ("logo_dimex.png", "logo_dimex.png.png"):
            ruta = os.path.join(ruta_script, nombre)
            if os.path.exists(ruta):
                try:
                    img = tk.PhotoImage(file=ruta)
                    # subsample para hacerlo más pequeño si es muy grande
                    if img.height() > 60:
                        factor = max(1, img.height() // 50)
                        img = img.subsample(factor, factor)
                    return img
                except Exception:
                    return None
        return None

    # --------------------------- entradas ------------------------------
    def _panel_entradas(self, parent):
        marco = ttk.Frame(parent, style="Card.TFrame", padding=20)
        marco.grid(row=0, column=0, sticky="nsw", padx=(0, 15))

        ttk.Label(marco, text="📍 Fuente de irradiación", style="Seccion.TLabel").pack(anchor="w", pady=(0, 6))

        # Selector de modo: ciudad / manual / NASA POWER
        self.var_modo = tk.StringVar(value="ciudad")
        marco_modos = ttk.Frame(marco, style="Card.TFrame")
        marco_modos.pack(anchor="w", pady=(0, 8))
        for txt, val in [("Ciudad", "ciudad"),
                         ("Manual", "manual"),
                         ("NASA POWER", "nasa")]:
            ttk.Radiobutton(marco_modos, text=txt, value=val,
                            variable=self.var_modo,
                            command=self._cambiar_modo).pack(side="left", padx=(0, 8))

        # Contenedor que cambia según el modo
        self.marco_fuente = ttk.Frame(marco, style="Card.TFrame")
        self.marco_fuente.pack(fill="x", pady=(0, 14))

        # --- modo ciudad ---
        self.var_ciudad = tk.StringVar(value="Ciudad de México")
        self.frame_ciudad = ttk.Frame(self.marco_fuente, style="Card.TFrame")
        ttk.Label(self.frame_ciudad, text="Ciudad:",
                  style="Card.TLabel").pack(anchor="w")
        ttk.Combobox(self.frame_ciudad,
                     textvariable=self.var_ciudad,
                     values=list(CIUDADES_MEXICO.keys()),
                     state="readonly",
                     width=28).pack(anchor="w", pady=(2, 0))

        # --- modo manual ---
        self.frame_manual = ttk.Frame(self.marco_fuente, style="Card.TFrame")
        self.var_hsp_manual = tk.StringVar(value="5.30")
        self.var_lat_manual = tk.StringVar(value="19.4")
        f1 = ttk.Frame(self.frame_manual, style="Card.TFrame")
        f1.pack(fill="x", pady=2)
        ttk.Label(f1, text="HSP (kWh/m²/día):", style="Card.TLabel",
                  width=22, anchor="w").pack(side="left")
        ttk.Entry(f1, textvariable=self.var_hsp_manual,
                  width=10, justify="right").pack(side="left")
        f2 = ttk.Frame(self.frame_manual, style="Card.TFrame")
        f2.pack(fill="x", pady=2)
        ttk.Label(f2, text="Latitud (°):", style="Card.TLabel",
                  width=22, anchor="w").pack(side="left")
        ttk.Entry(f2, textvariable=self.var_lat_manual,
                  width=10, justify="right").pack(side="left")

        # --- modo NASA ---
        self.frame_nasa = ttk.Frame(self.marco_fuente, style="Card.TFrame")
        self.var_lat_nasa = tk.StringVar(value="19.43")
        self.var_lon_nasa = tk.StringVar(value="-99.13")
        self.lbl_nasa_estado = ttk.Label(self.frame_nasa,
                                          text="Sin datos descargados",
                                          style="Card.TLabel",
                                          font=("Helvetica", 9, "italic"))
        f3 = ttk.Frame(self.frame_nasa, style="Card.TFrame")
        f3.pack(fill="x", pady=2)
        ttk.Label(f3, text="Latitud (°):", style="Card.TLabel",
                  width=22, anchor="w").pack(side="left")
        ttk.Entry(f3, textvariable=self.var_lat_nasa,
                  width=10, justify="right").pack(side="left")
        f4 = ttk.Frame(self.frame_nasa, style="Card.TFrame")
        f4.pack(fill="x", pady=2)
        ttk.Label(f4, text="Longitud (°):", style="Card.TLabel",
                  width=22, anchor="w").pack(side="left")
        ttk.Entry(f4, textvariable=self.var_lon_nasa,
                  width=10, justify="right").pack(side="left")

        self.btn_nasa = tk.Button(self.frame_nasa,
                                  text="Descargar de NASA POWER",
                                  bg=COLOR_NARANJA, fg="white",
                                  activebackground="#f4511e",
                                  activeforeground="white",
                                  font=("Helvetica", 10, "bold"),
                                  relief="flat", padx=12, pady=6,
                                  cursor="hand2",
                                  command=self._descargar_nasa)
        self.btn_nasa.pack(anchor="w", pady=(6, 2))
        self.lbl_nasa_estado.pack(anchor="w")

        # Datos NASA cacheados tras descarga
        self._nasa_hsp = None
        self._nasa_mensual = None

        # Mostrar el modo inicial
        self._cambiar_modo()

        ttk.Label(marco, text="🔆 Panel solar", style="Seccion.TLabel").pack(anchor="w", pady=(0, 6))

        # Tipo de sistema: fijo / 1 eje / 2 ejes
        fila_tipo = ttk.Frame(marco, style="Card.TFrame")
        fila_tipo.pack(fill="x", pady=2)
        ttk.Label(fila_tipo, text="Tipo de sistema:", style="Card.TLabel",
                  width=28, anchor="w").pack(side="left")
        self.var_tipo_sistema = tk.StringVar(value="Fijo")
        ttk.Combobox(fila_tipo,
                     textvariable=self.var_tipo_sistema,
                     values=list(TIPOS_SISTEMA.keys()),
                     state="readonly",
                     width=18).pack(side="left", padx=(8, 0))

        self.var_area = self._fila_entrada(marco, "Área total de paneles (m²):", "10")
        self.var_eficiencia = self._fila_entrada(marco, "Eficiencia del panel (%):", "20")
        self.var_angulo = self._fila_entrada(marco, "Ángulo de inclinación (°):", "20")

        ttk.Label(marco, text="⚙ Sistema", style="Seccion.TLabel").pack(anchor="w", pady=(14, 6))
        self.var_perdidas = self._fila_entrada(marco, "Pérdidas del sistema (%):", "20")

        ttk.Label(marco, text="💰 Economía", style="Seccion.TLabel").pack(anchor="w", pady=(14, 6))

        # Modo de facturación: precio único vs CFE
        fila_modo_fact = ttk.Frame(marco, style="Card.TFrame")
        fila_modo_fact.pack(fill="x", pady=(0, 4))
        ttk.Label(fila_modo_fact, text="Modo facturación:", style="Card.TLabel",
                  width=28, anchor="w").pack(side="left")
        self.var_modo_fact = tk.StringVar(value="simple")
        marco_radios = ttk.Frame(marco, style="Card.TFrame")
        marco_radios.pack(fill="x", pady=(0, 6))
        for txt, val in [("Precio único $/kWh", "simple"),
                         ("Tarifa CFE (México)", "cfe")]:
            ttk.Radiobutton(marco_radios, text=txt, value=val,
                            variable=self.var_modo_fact,
                            command=self._cambiar_modo_facturacion).pack(side="left", padx=(0, 8))

        # Contenedor que cambia según modo
        self.marco_fact = ttk.Frame(marco, style="Card.TFrame")
        self.marco_fact.pack(fill="x")

        # --- modo simple ---
        self.frame_fact_simple = ttk.Frame(self.marco_fact, style="Card.TFrame")
        self.var_precio = self._fila_entrada(self.frame_fact_simple,
                                              "Precio de la luz ($/kWh):", "3.50")

        # --- modo CFE ---
        self.frame_fact_cfe = ttk.Frame(self.marco_fact, style="Card.TFrame")
        fila_tarifa = ttk.Frame(self.frame_fact_cfe, style="Card.TFrame")
        fila_tarifa.pack(fill="x", pady=2)
        ttk.Label(fila_tarifa, text="Tarifa CFE:", style="Card.TLabel",
                  width=28, anchor="w").pack(side="left")
        self.var_tarifa = tk.StringVar(value="1")
        ttk.Combobox(fila_tarifa,
                     textvariable=self.var_tarifa,
                     values=list(TARIFAS_CFE.keys()),
                     state="readonly",
                     width=12).pack(side="left", padx=(8, 0))
        self.var_consumo_mes = self._fila_entrada(self.frame_fact_cfe,
                                                   "Consumo promedio (kWh/mes):", "250")

        # Campos editables sólo para PDBT (precio y cargo fijo personalizables)
        self.frame_pdbt = ttk.Frame(self.frame_fact_cfe, style="Card.TFrame")
        ttk.Label(self.frame_pdbt,
                  text="↓ Personaliza según tu recibo (PDBT):",
                  background=COLOR_TARJETA,
                  foreground=COLOR_PRIMARIO,
                  font=("Helvetica", 9, "italic")).pack(anchor="w", pady=(6, 2))
        self.var_pdbt_precio = self._fila_entrada(self.frame_pdbt,
                                                   "Precio por kWh ($):", "5.00")
        self.var_pdbt_cargo = self._fila_entrada(self.frame_pdbt,
                                                  "Cargo fijo mensual ($):", "70")

        # Mostrar/ocultar campos PDBT al cambiar tarifa
        self.var_tarifa.trace_add("write", lambda *a: self._actualizar_campos_pdbt())

        # Toggle: auto-calcular costo
        fila_toggle = ttk.Frame(marco, style="Card.TFrame")
        fila_toggle.pack(fill="x", pady=(8, 2))
        self.var_auto_costo = tk.BooleanVar(value=True)
        ttk.Checkbutton(fila_toggle,
                        text="Auto-calcular costo según área",
                        variable=self.var_auto_costo,
                        command=self._actualizar_costo_auto).pack(side="left")

        # Campos de costo unitario
        self.var_costo_fijo = self._fila_entrada(
            marco, "Costo fijo (inversor, etc.) $:", str(COSTO_FIJO_DEFAULT))
        self.var_costo_m2 = self._fila_entrada(
            marco, "Costo por m² (paneles+est.) $:", str(COSTO_POR_M2_DEFAULT))

        # Costo total (auto-calculado o manual)
        self.var_costo = self._fila_entrada(marco, "Costo del sistema ($):", "60000")

        # Recalcular cuando cambien parámetros relevantes
        self.var_area.trace_add("write", lambda *a: self._actualizar_costo_auto())
        self.var_tipo_sistema.trace_add("write", lambda *a: self._actualizar_costo_auto())
        self.var_costo_fijo.trace_add("write", lambda *a: self._actualizar_costo_auto())
        self.var_costo_m2.trace_add("write", lambda *a: self._actualizar_costo_auto())

        # Inicializar el costo y mostrar modo simple
        self._actualizar_costo_auto()
        self._cambiar_modo_facturacion()
        self._actualizar_campos_pdbt()

        # Botón principal grande (estilo Material azul)
        btn_calcular = tk.Button(marco, text="Calcular",
                                 bg=COLOR_PRIMARIO, fg="white",
                                 activebackground=COLOR_PRIM_OSC,
                                 activeforeground="white",
                                 font=("Helvetica", 12, "bold"),
                                 relief="flat", padx=20, pady=10,
                                 cursor="hand2",
                                 command=self.calcular)
        btn_calcular.pack(fill="x", pady=(18, 8))

        # Botones secundarios en fila
        marco_btn = tk.Frame(marco, bg=COLOR_TARJETA)
        marco_btn.pack(fill="x", pady=(0, 0))

        btn_limpiar = tk.Button(marco_btn, text="Limpiar",
                                bg=COLOR_GRIS_BG, fg=COLOR_TEXTO_2,
                                activebackground=COLOR_BORDE,
                                font=("Helvetica", 9, "bold"),
                                relief="flat", padx=10, pady=6,
                                cursor="hand2",
                                command=self.limpiar)
        btn_limpiar.pack(side="left", padx=(0, 4), expand=True, fill="x")

        btn_csv = tk.Button(marco_btn, text="Exportar CSV",
                            bg=COLOR_GRIS_BG, fg=COLOR_TEXTO_2,
                            activebackground=COLOR_BORDE,
                            font=("Helvetica", 9, "bold"), relief="flat",
                            padx=10, pady=6, cursor="hand2",
                            command=self.exportar_csv)
        btn_csv.pack(side="left", padx=4, expand=True, fill="x")

        btn_pdf = tk.Button(marco_btn, text="Exportar PDF",
                            bg=COLOR_GRIS_BG, fg=COLOR_TEXTO_2,
                            activebackground=COLOR_BORDE,
                            font=("Helvetica", 9, "bold"), relief="flat",
                            padx=10, pady=6, cursor="hand2",
                            command=self.exportar_pdf)
        btn_pdf.pack(side="left", padx=(4, 0), expand=True, fill="x")

    def _fila_entrada(self, parent, etiqueta, valor_inicial):
        contenedor = ttk.Frame(parent, style="Card.TFrame")
        contenedor.pack(fill="x", pady=2)
        ttk.Label(contenedor, text=etiqueta, style="Card.TLabel",
                  width=28, anchor="w").pack(side="left")
        var = tk.StringVar(value=valor_inicial)
        entrada = ttk.Entry(contenedor, textvariable=var, width=12, justify="right")
        entrada.pack(side="left", padx=(8, 0))
        return var

    # --------------------------- resultados ----------------------------
    def _panel_resultados(self, parent):
        marco = ttk.Frame(parent, style="Card.TFrame", padding=15)
        marco.grid(row=0, column=1, sticky="nsew")
        marco.columnconfigure(0, weight=1)
        marco.rowconfigure(1, weight=1)

        # Tarjetas de resultados destacados
        self.marco_tarjetas = ttk.Frame(marco, style="Card.TFrame")
        self.marco_tarjetas.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for i in range(4):
            self.marco_tarjetas.columnconfigure(i, weight=1)

        self.tarjetas = {}
        self._crear_tarjeta("anual", "Producción anual", "— kWh", 0)
        self._crear_tarjeta("ahorro", "Ahorro anual", "— $", 1)
        self._crear_tarjeta("co2", "CO₂ evitado", "— kg", 2)
        self._crear_tarjeta("payback", "Recuperación", "— años", 3)

        # Panel con gráficas en pestañas
        self.notebook = ttk.Notebook(marco)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        self.tab_mensual = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_ahorro = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_consumo = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_seguidor = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_cfe = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_detalle = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_aprende = ttk.Frame(self.notebook, style="Card.TFrame")
        self.tab_biblio = ttk.Frame(self.notebook, style="Card.TFrame")

        self.notebook.add(self.tab_mensual, text="Producción mensual")
        self.notebook.add(self.tab_ahorro, text="Ahorro acumulado")
        self.notebook.add(self.tab_consumo, text="vs Consumo hogar")
        self.notebook.add(self.tab_seguidor, text="🔁 Fijo vs Seguidor")
        self.notebook.add(self.tab_cfe, text="🇲🇽 Factura CFE")
        self.notebook.add(self.tab_detalle, text="Detalle numérico")
        self.notebook.add(self.tab_aprende, text="📚 Aprende")
        self.notebook.add(self.tab_biblio, text="📖 Bibliografía")

        self._mensaje_inicial(self.tab_mensual)
        self._mensaje_inicial(self.tab_ahorro)
        self._mensaje_inicial(self.tab_consumo)
        self._mensaje_inicial(self.tab_seguidor)
        self._mensaje_inicial(self.tab_cfe)
        self._mensaje_inicial(self.tab_detalle)
        self._llenar_aprende()
        self._llenar_biblio()

    def _crear_tarjeta(self, key, titulo, valor, col):
        colores_borde = [COLOR_PRIMARIO, COLOR_NARANJA, COLOR_EXITO, "#7b1fa2"]
        color_borde = colores_borde[col % 4]

        marco = tk.Frame(self.marco_tarjetas, bg=COLOR_GRIS_BG,
                         highlightbackground=COLOR_BORDE_2,
                         highlightthickness=0)
        marco.grid(row=0, column=col, padx=4, pady=4, sticky="nsew", ipady=8)

        # Barra lateral de color
        tk.Frame(marco, bg=color_borde, width=4).pack(side="left", fill="y")

        contenido = tk.Frame(marco, bg=COLOR_GRIS_BG)
        contenido.pack(side="left", fill="both", expand=True, padx=8, pady=4)

        tk.Label(contenido, text=titulo.upper(),
                 bg=COLOR_GRIS_BG, fg=COLOR_TEXTO_SUAVE,
                 font=("Helvetica", 8, "bold")).pack(anchor="w")
        lbl = tk.Label(contenido, text=valor,
                       bg=COLOR_GRIS_BG, fg=COLOR_TEXTO,
                       font=("Helvetica", 17, "bold"))
        lbl.pack(anchor="w")
        self.tarjetas[key] = lbl

    def _mensaje_inicial(self, tab):
        for w in tab.winfo_children():
            w.destroy()
        ttk.Label(tab,
                  text="Ingresa los datos y presiona “Calcular” para ver resultados.",
                  style="Card.TLabel",
                  font=("Helvetica", 11, "italic")).pack(pady=40)

    # ----------------------------- acciones ----------------------------
    def calcular(self):
        try:
            # Si PDBT está activo, actualizar TARIFAS_CFE con valores del recibo
            self._aplicar_valores_pdbt()
            parametros = self._leer_parametros()
        except ValueError as e:
            messagebox.showerror("Datos inválidos", str(e))
            return

        self.resultado = calcular_produccion(parametros)
        self.parametros_actuales = parametros

        # Si el usuario eligió tarifa CFE, sustituir el ahorro y payback
        # por los valores reales según bloques.
        self.factura_cfe = None
        if parametros.get("modo_facturacion") == "cfe":
            consumo_mes = parametros["consumo_mensual_kwh"]
            consumo_mensual = [consumo_mes] * 12
            self.factura_cfe = simular_factura_anual(
                consumo_mensual,
                self.resultado["produccion_mensual"],
                parametros["tarifa_cfe"]
            )
            # Reemplazar ahorro y payback con los datos reales de CFE
            ahorro_real = self.factura_cfe["ahorro_anual_real"]
            self.resultado["ahorro_anual"] = ahorro_real
            self.resultado["payback"] = (
                parametros["costo_sistema"] / ahorro_real
                if ahorro_real > 0 else float("inf")
            )

        # Actualizar tarjetas
        r = self.resultado
        self.tarjetas["anual"].config(text=f"{r['produccion_anual']:.0f} kWh")
        self.tarjetas["ahorro"].config(text=f"${r['ahorro_anual']:,.0f}")
        self.tarjetas["co2"].config(text=f"{r['co2_evitado']:.0f} kg")
        payback_txt = (f"{r['payback']:.1f} años"
                       if r["payback"] != float("inf") else "—")
        self.tarjetas["payback"].config(text=payback_txt)

        # Gráficas
        self._graficar_mensual()
        self._graficar_ahorro()
        self._graficar_consumo()
        self._graficar_seguidor()
        self._mostrar_factura_cfe()
        self._tabla_detalle()

    def limpiar(self):
        self.var_ciudad.set("Ciudad de México")
        self.var_area.set("10")
        self.var_eficiencia.set("20")
        self.var_angulo.set("20")
        self.var_perdidas.set("20")
        self.var_precio.set("3.50")
        self.var_costo.set("60000")
        self.resultado = None
        for lbl in self.tarjetas.values():
            lbl.config(text="—")
        for tab in (self.tab_mensual, self.tab_ahorro, self.tab_consumo,
                    self.tab_seguidor, self.tab_cfe, self.tab_detalle):
            self._mensaje_inicial(tab)
        self.var_tipo_sistema.set("Fijo")
        self.factura_cfe = None

    def _cambiar_modo_facturacion(self):
        """Mostrar precio único o tarifa CFE según el modo."""
        self.frame_fact_simple.pack_forget()
        self.frame_fact_cfe.pack_forget()
        if self.var_modo_fact.get() == "simple":
            self.frame_fact_simple.pack(fill="x")
        else:
            self.frame_fact_cfe.pack(fill="x")

    def _actualizar_campos_pdbt(self):
        """Mostrar campos editables sólo cuando se elige PDBT."""
        if not hasattr(self, "frame_pdbt"):
            return
        if self.var_tarifa.get() == "PDBT":
            self.frame_pdbt.pack(fill="x", pady=(4, 0))
        else:
            self.frame_pdbt.pack_forget()

    def _aplicar_valores_pdbt(self):
        """Si el usuario eligió PDBT, sobreescribir precio/cargo en TARIFAS_CFE."""
        if self.var_modo_fact.get() != "cfe" or self.var_tarifa.get() != "PDBT":
            return
        try:
            precio = float(self.var_pdbt_precio.get())
            cargo = float(self.var_pdbt_cargo.get())
        except (ValueError, AttributeError):
            return
        if precio < 0 or cargo < 0:
            return
        TARIFAS_CFE["PDBT"]["bloques"] = [(float("inf"), precio)]
        TARIFAS_CFE["PDBT"]["cargo_fijo_mensual"] = cargo

    def _actualizar_costo_auto(self):
        """Recalcula el costo del sistema cuando cambia área, tipo o costos unitarios."""
        if not hasattr(self, "var_costo") or not hasattr(self, "var_auto_costo"):
            return
        if not self.var_auto_costo.get():
            return  # modo manual: no tocar el campo

        try:
            area = float(self.var_area.get())
            costo_fijo = float(self.var_costo_fijo.get())
            costo_m2 = float(self.var_costo_m2.get())
            tipo = self.var_tipo_sistema.get()
        except (ValueError, AttributeError):
            return

        costo = calcular_costo_sistema(area, tipo, costo_fijo, costo_m2)
        self.var_costo.set(f"{costo:.0f}")

    def _cambiar_modo(self):
        """Mostrar el frame que corresponde al modo seleccionado."""
        for f in (self.frame_ciudad, self.frame_manual, self.frame_nasa):
            f.pack_forget()
        modo = self.var_modo.get()
        if modo == "ciudad":
            self.frame_ciudad.pack(fill="x")
        elif modo == "manual":
            self.frame_manual.pack(fill="x")
        else:
            self.frame_nasa.pack(fill="x")

    def _descargar_nasa(self):
        """Llamar a la API en un hilo para no bloquear la UI."""
        try:
            lat = float(self.var_lat_nasa.get())
            lon = float(self.var_lon_nasa.get())
        except ValueError:
            messagebox.showerror("Datos inválidos", "Latitud y longitud deben ser números.")
            return
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            messagebox.showerror("Datos inválidos", "Rango: lat ±90, lon ±180.")
            return

        self.btn_nasa.config(state="disabled", text="Descargando...")
        self.lbl_nasa_estado.config(text="Consultando NASA POWER...")

        def _trabajo():
            try:
                anual, mensual = obtener_hsp_nasa(lat, lon)
                self.after(0, self._on_nasa_ok, anual, mensual)
            except Exception as e:
                self.after(0, self._on_nasa_error, str(e))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _on_nasa_ok(self, anual, mensual):
        self._nasa_hsp = anual
        self._nasa_mensual = mensual
        self.btn_nasa.config(state="normal", text="Descargar de NASA POWER")
        self.lbl_nasa_estado.config(
            text=f"✓ HSP anual: {anual:.2f} kWh/m²/día (rango {min(mensual):.1f}–{max(mensual):.1f})")

    def _on_nasa_error(self, mensaje):
        self.btn_nasa.config(state="normal", text="Descargar de NASA POWER")
        self.lbl_nasa_estado.config(text="✗ Error en la descarga")
        messagebox.showerror("NASA POWER",
                             f"No se pudieron descargar los datos:\n{mensaje}")

    def _leer_parametros(self):
        modo_fact = self.var_modo_fact.get()
        try:
            area = float(self.var_area.get())
            eficiencia = float(self.var_eficiencia.get())
            angulo = float(self.var_angulo.get())
            perdidas = float(self.var_perdidas.get())
            costo = float(self.var_costo.get())
            if modo_fact == "simple":
                precio = float(self.var_precio.get())
                tarifa = None
                consumo_mensual_kwh = None
            else:
                # En modo CFE, derivamos un precio "estimado" para el modelo
                # genérico, pero la lógica real usa los bloques de tarifa.
                precio = 3.50
                tarifa = self.var_tarifa.get()
                consumo_mensual_kwh = float(self.var_consumo_mes.get())
                if consumo_mensual_kwh < 0:
                    raise ValueError("El consumo no puede ser negativo.")
        except ValueError as e:
            if "could not convert" in str(e):
                raise ValueError("Todos los campos numéricos deben ser válidos.")
            raise

        if area <= 0:
            raise ValueError("El área debe ser mayor a 0.")
        if not 5 <= eficiencia <= 30:
            raise ValueError("La eficiencia debe estar entre 5% y 30%.")
        if not 0 <= angulo <= 90:
            raise ValueError("El ángulo debe estar entre 0° y 90°.")
        if not 0 <= perdidas <= 50:
            raise ValueError("Las pérdidas deben estar entre 0% y 50%.")
        if precio < 0 or costo < 0:
            raise ValueError("Los valores económicos no pueden ser negativos.")

        # Determinar HSP, latitud y meses según el modo
        modo = self.var_modo.get()
        mensual_personalizado = None

        if modo == "ciudad":
            ciudad = self.var_ciudad.get()
            datos = CIUDADES_MEXICO[ciudad]
            hsp = datos["hsp"]
            latitud = datos["latitud"]
            etiqueta = ciudad

        elif modo == "manual":
            try:
                hsp = float(self.var_hsp_manual.get())
                latitud = float(self.var_lat_manual.get())
            except ValueError:
                raise ValueError("HSP y latitud deben ser numéricos.")
            if not 1 <= hsp <= 9:
                raise ValueError("HSP típico está entre 1 y 9 kWh/m²/día.")
            if not -90 <= latitud <= 90:
                raise ValueError("Latitud entre -90 y 90.")
            etiqueta = f"Manual (HSP {hsp:.2f})"

        else:  # nasa
            if self._nasa_hsp is None:
                raise ValueError("Primero descarga los datos de NASA POWER.")
            hsp = self._nasa_hsp
            try:
                latitud = float(self.var_lat_nasa.get())
            except ValueError:
                raise ValueError("Latitud inválida.")
            mensual_personalizado = self._nasa_mensual
            etiqueta = f"NASA POWER ({latitud:.2f}, {float(self.var_lon_nasa.get()):.2f})"

        return {
            "ciudad": etiqueta,
            "hsp": hsp,
            "latitud": latitud,
            "area": area,
            "eficiencia": eficiencia,
            "angulo": angulo,
            "perdidas": perdidas,
            "precio_kwh": precio,
            "costo_sistema": costo,
            "mensual_personalizado": mensual_personalizado,
            "tipo_sistema": self.var_tipo_sistema.get(),
            "modo_facturacion": modo_fact,
            "tarifa_cfe": tarifa,
            "consumo_mensual_kwh": consumo_mensual_kwh,
        }

    # --------------------- contenido educativo -------------------------
    def _llenar_aprende(self):
        """Pestaña de aprendizaje con contenido didáctico."""
        for w in self.tab_aprende.winfo_children():
            w.destroy()

        contenedor = ttk.Frame(self.tab_aprende, style="Card.TFrame")
        contenedor.pack(fill="both", expand=True, padx=10, pady=10)

        # Texto con scroll
        canvas_scroll = tk.Canvas(contenedor, bg=COLOR_TARJETA,
                                  highlightthickness=0)
        scrollbar = ttk.Scrollbar(contenedor, orient="vertical",
                                  command=canvas_scroll.yview)
        marco_interno = ttk.Frame(canvas_scroll, style="Card.TFrame")

        marco_interno.bind("<Configure>", lambda e: canvas_scroll.configure(
            scrollregion=canvas_scroll.bbox("all")))
        canvas_scroll.create_window((0, 0), window=marco_interno, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        canvas_scroll.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Scroll con rueda del mouse (macOS y Windows)
        def _on_mousewheel(e):
            canvas_scroll.yview_scroll(int(-1 * (e.delta / 2)), "units")
        canvas_scroll.bind_all("<MouseWheel>", _on_mousewheel)

        secciones = [
            ("☀ ¿Cómo funciona un panel solar?",
             "Un panel fotovoltaico convierte la luz del sol en electricidad usando el "
             "efecto fotovoltaico: cuando los fotones de la luz golpean el silicio del panel, "
             "liberan electrones que generan una corriente eléctrica continua. Esa corriente pasa "
             "por un inversor que la transforma en corriente alterna, igual a la que usan los "
             "electrodomésticos de tu casa."),

            ("🔆 ¿Qué es la HSP (Horas Sol Pico)?",
             "La HSP indica cuántas horas equivalentes de sol a 1000 W/m² recibe un lugar en un "
             "día promedio. Es la unidad estándar para comparar el recurso solar entre ciudades.\n\n"
             "  • HSP < 4: recurso bajo (lugares nublados o templados)\n"
             "  • HSP 4–5: recurso medio (centro de México)\n"
             "  • HSP 5–6: recurso alto (norte de México, Yucatán)\n"
             "  • HSP > 6: recurso excelente (Mexicali, Sonora, BCS)"),

            ("📐 ¿Por qué importa el ángulo de inclinación?",
             "Cuando los rayos del sol caen perpendicularmente al panel, la captación es máxima. "
             "Como México está en el hemisferio norte, los paneles deben inclinarse hacia el sur "
             "con un ángulo cercano a la latitud del lugar. Si el ángulo es muy distinto, parte de "
             "la energía se pierde en reflexión.\n\n"
             "    Fórmula:  f_inclinación = cos(|ángulo_panel − latitud|)"),

            ("⚙ ¿Qué son las pérdidas del sistema?",
             "Entre el panel y el enchufe se pierde energía por varios factores:\n\n"
             "  • Inversor: 3–5% al convertir CD a CA\n"
             "  • Cableado: 1–3% por resistencia eléctrica\n"
             "  • Suciedad/polvo: 2–8%\n"
             "  • Temperatura: los paneles pierden eficiencia cuando se calientan (3–10%)\n"
             "  • Sombras parciales: hasta 20% si hay árboles o edificios cerca\n\n"
             "En total, un sistema bien instalado pierde 15–25% respecto al valor teórico. "
             "Eso es el Performance Ratio (PR): un PR de 0.80 significa que aprovechas el 80% "
             "del potencial."),

            ("🌎 ¿Cuánto CO₂ evitas?",
             "En México, generar 1 kWh de electricidad emite en promedio 0.494 kg de CO₂ al ambiente "
             "(factor publicado por la CRE). Si tu panel produce 3,000 kWh al año, evitas que se "
             "emitan casi 1.5 toneladas de CO₂. En 20 años son ~30 toneladas, el equivalente a "
             "plantar más de 1,000 árboles."),

            ("💰 ¿Cuándo se recupera la inversión?",
             "El periodo de recuperación (payback) se calcula así:\n\n"
             "    Payback = Costo del sistema ÷ Ahorro anual en electricidad\n\n"
             "En México, los sistemas residenciales suelen recuperarse en 4 a 7 años, y el panel "
             "sigue funcionando 25–30 años, así que el resto es ganancia neta."),

            ("🇲🇽 El acantilado DAC — clave para México",
             "CFE clasifica a los hogares en 8 tarifas según el clima local. Cada tarifa tiene un\n"
             "LÍMITE DE ALTO CONSUMO mensual. Si el promedio anual lo rebasa, te reclasifican\n"
             "como DAC (Doméstica de Alto Consumo) y pierdes todo subsidio: pagas ~$6 MXN/kWh\n"
             "sobre TODOS tus kWh, no solo los excedentes.\n\n"
             "Ejemplo en Tarifa 1 (templada, límite 250 kWh/mes):\n"
             "  • Consumo 200 kWh/mes (normal): factura ≈ $350/mes\n"
             "  • Consumo 400 kWh/mes → DAC: factura ≈ $2,500/mes (¡7×!)\n\n"
             "Por qué importa para solar: si un sistema solar reduce el consumo neto por\n"
             "debajo del límite, el hogar SALE de DAC y el ahorro real es mucho mayor que\n"
             "el simple 'kWh × precio'. Selecciona el modo 'Tarifa CFE' para verlo en la\n"
             "pestaña 🇲🇽 Factura CFE."),

            ("🔁 Seguidores solares (solar trackers)",
             "Un seguidor solar es un mecanismo que orienta el panel hacia el sol durante todo el día, "
             "como un girasol. Hay dos tipos principales:\n\n"
             "  • Un eje (este-oeste): rota durante el día siguiendo la trayectoria del sol.\n"
             "    Ganancia típica: +25 a +35% de energía vs panel fijo.\n\n"
             "  • Dos ejes (azimut + altitud): además ajusta la inclinación según la estación.\n"
             "    Ganancia típica: +35 a +45% de energía vs panel fijo.\n\n"
             "El costo del seguidor es mayor (1 eje: ~25% más; 2 ejes: ~50% más), pero a largo plazo "
             "suele compensar — sobre todo en latitudes altas o granjas solares grandes."),

            ("🔧 Cómo construir un seguidor (proyecto del club)",
             "Materiales recomendados:\n\n"
             "  • Arduino UNO o ESP32 (~$150 MXN)\n"
             "  • 1 o 2 servomotores SG90 / MG996R (~$60–200 MXN)\n"
             "  • 4 fotorresistencias LDR en cruz (~$10 MXN)\n"
             "  • 4 resistencias de 10kΩ para divisor de tensión\n"
             "  • Panel solar pequeño 6V / 1W para pruebas\n"
             "  • Estructura: madera, perfil de aluminio o impresión 3D\n\n"
             "Lógica de control: el Arduino lee las 4 LDR (arriba, abajo, izquierda, derecha). "
             "Si una recibe más luz que la otra, mueve el servo hacia ese lado hasta que las cuatro "
             "miden lo mismo — eso significa que el panel está apuntando al sol.\n\n"
             "Alternativa más precisa: calcular la posición del sol con una ecuación astronómica "
             "según hora, fecha, latitud y longitud (algoritmo SPA de NREL)."),

            ("💼 Caso de estudio — Negocio en Hermosillo (PDBT)",
             "Hermosillo es una de las ciudades con MEJOR recurso solar de México\n"
             "(HSP = 6.00 kWh/m²/día). Combinado con la tarifa comercial PDBT\n"
             "(~$5.00/kWh sin subsidio), el payback es muy corto.\n\n"
             "Escenario: negocio con consumo ~1,000 kWh/mes, latitud 29.1°,\n"
             "panel a 30°, 20% eficiencia, pérdidas 20%, precio luz $5.00/kWh\n\n"
             "  Sistema                  kWh/año   Ahorro/año     Costo     Payback\n"
             "  ───────────────────────  ───────   ──────────   ────────   ────────\n"
             "  20 m² Fijo                 6,964      $34,818   $105,000    3.0 años\n"
             "  30 m² Fijo                10,445      $52,227   $150,000    2.9 años\n"
             "  50 m² Fijo                17,409      $87,044   $240,000    2.8 años\n"
             "  30 m² Seguidor 1 eje      13,267      $66,336   $187,500    2.8 años\n"
             "  30 m² Seguidor 2 ejes     14,416      $72,082   $225,000    3.1 años\n\n"
             "Conclusiones:\n"
             "  • Payback en Hermosillo con PDBT: menor a 3 años en casi todos\n"
             "    los escenarios\n"
             "  • Paneles fijos bien orientados (ángulo ≈ latitud) ya rinden excelente\n"
             "  • El seguidor de 1 eje produce 27% más energía con el mismo payback\n"
             "  • El seguidor de 2 ejes tiene mayor producción absoluta pero el\n"
             "    extra costo alarga el payback\n"
             "  • Después del payback, el panel funciona 22-27 años más = ganancia neta\n\n"
             "Para replicar: elige ciudad 'Hermosillo, SON', modo 'Precio único'\n"
             "con $5.00/kWh, y ajusta el área en la sección de Panel solar."),

            ("🧪 Experimentos para el club",
             "  • Compara la HSP de tu ciudad con la de Mexicali — ¿qué tanto más produce un panel allá?\n"
             "  • Cambia el ángulo de 0° a 90° y observa cómo varía el factor de inclinación\n"
             "  • Usa el modo NASA POWER para descargar datos reales de tu casa o tu escuela\n"
             "  • Compara dos sistemas: uno barato con paneles de 15% vs uno caro de 22%\n"
             "    — ¿cuál se paga primero?\n"
             "  • Cambia el 'Tipo de sistema' a Seguidor 1 eje y 2 ejes — ¿cuántos años antes\n"
             "    se recupera la inversión gracias a la ganancia extra?\n"
             "  • Construye un seguidor real con Arduino y compara la energía medida vs la\n"
             "    estimada por la calculadora"),
        ]

        for titulo, cuerpo in secciones:
            ttk.Label(marco_interno, text=titulo,
                      background=COLOR_TARJETA,
                      foreground=COLOR_PRIMARIO,
                      font=("Helvetica", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
            ttk.Label(marco_interno, text=cuerpo,
                      background=COLOR_TARJETA,
                      foreground=COLOR_TEXTO,
                      font=("Helvetica", 10),
                      wraplength=720,
                      justify="left").pack(anchor="w", padx=18, pady=(0, 6))

    def _llenar_biblio(self):
        """Pestaña con fórmulas, fuentes de datos y bibliografía."""
        for w in self.tab_biblio.winfo_children():
            w.destroy()

        contenedor = ttk.Frame(self.tab_biblio, style="Card.TFrame")
        contenedor.pack(fill="both", expand=True, padx=10, pady=10)

        canvas_scroll = tk.Canvas(contenedor, bg=COLOR_TARJETA,
                                  highlightthickness=0)
        scrollbar = ttk.Scrollbar(contenedor, orient="vertical",
                                  command=canvas_scroll.yview)
        marco_interno = ttk.Frame(canvas_scroll, style="Card.TFrame")
        marco_interno.bind("<Configure>", lambda e: canvas_scroll.configure(
            scrollregion=canvas_scroll.bbox("all")))
        canvas_scroll.create_window((0, 0), window=marco_interno, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        canvas_scroll.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        secciones = [
            ("📐 Fórmulas usadas en la calculadora",
             "Energía diaria del panel (kWh/día):\n"
             "    E = A × η × HSP × PR × f_inclinación × G_seguidor\n\n"
             "Donde:\n"
             "  • A = área del panel (m²)\n"
             "  • η = eficiencia del panel (decimal, ej: 0.20 = 20%)\n"
             "  • HSP = horas sol pico (kWh/m²/día)\n"
             "  • PR = Performance Ratio = 1 − pérdidas (ej: 0.80)\n"
             "  • f_inclinación = cos(|ángulo − latitud|) para paneles fijos;\n"
             "                    1.0 para sistemas con seguidor solar\n"
             "  • G_seguidor = ganancia por seguir al sol:\n"
             "        Fijo: 1.00   ·   Seguidor 1 eje: 1.27   ·   Seguidor 2 ejes: 1.38\n\n"
             "Producción mensual:\n"
             "    E_mes = E × factor_mes × días_mes\n\n"
             "El factor mensual varía entre 0.80 (diciembre) y 1.15 (mayo) para el hemisferio "
             "norte. Cuando se usan datos de NASA POWER, se reemplaza por la HSP real de cada mes.\n\n"
             "CO₂ evitado:\n"
             "    CO₂ (kg) = E_anual × 0.494\n\n"
             "Periodo de recuperación:\n"
             "    Payback (años) = Costo sistema ÷ (E_anual × precio_kWh)"),

            ("📊 Fuentes de datos",
             "  • HSP por ciudad en México: SENER — Secretaría de Energía, Atlas Nacional de\n"
             "    Zonas con Alto Potencial de Energías Limpias (AZEL).\n\n"
             "  • Datos satelitales globales: NASA POWER — Prediction of Worldwide Energy\n"
             "    Resources, parámetro ALLSKY_SFC_SW_DWN (irradiación de onda corta en\n"
             "    superficie con cielo abierto). https://power.larc.nasa.gov\n\n"
             "  • Factor de emisión CO₂: CRE — Comisión Reguladora de Energía, Factor de\n"
             "    Emisión del Sistema Eléctrico Nacional 2023 (0.494 kg CO₂/kWh).\n\n"
             "  • Tarifas CFE 1, 1A-1F, DAC: CFE — https://app.cfe.mx/aplicaciones/ccfe/\n"
             "    tarifas/tarifas/Tarifas.asp\n"
             "    PRECIOS REFERENCIALES 2024–2025. CFE ajusta cada mes; para uso profesional\n"
             "    actualiza los valores en el diccionario TARIFAS_CFE del código.\n\n"
             "  • Consumo promedio del hogar: CFE — Comisión Federal de Electricidad,\n"
             "    ~250 kWh/mes (tarifa doméstica básica)."),

            ("📖 Bibliografía recomendada",
             "  • Duffie, J. A. & Beckman, W. A. (2013). Solar Engineering of Thermal\n"
             "    Processes. 4ª edición, Wiley.\n\n"
             "  • Sandia National Laboratories (2014). PV Performance Modeling Methods and\n"
             "    Practices.\n\n"
             "  • SENER (2023). Balance Nacional de Energía. Gobierno de México.\n\n"
             "  • IEA-PVPS (2024). Snapshot of Global PV Markets. International Energy Agency.\n\n"
             "  • Masters, G. M. (2013). Renewable and Efficient Electric Power Systems.\n"
             "    2ª edición, Wiley.\n\n"
             "  • Reda, I. & Andreas, A. (2008). Solar Position Algorithm for Solar Radiation\n"
             "    Applications. NREL/TP-560-34302 — referencia para construir seguidores\n"
             "    solares precisos por cálculo astronómico."),

            ("🔗 Recursos en línea",
             "  • NASA POWER — irradiación solar global\n"
             "    https://power.larc.nasa.gov\n\n"
             "  • PVGIS (Comisión Europea) — simulador profesional fotovoltaico\n"
             "    https://re.jrc.ec.europa.eu/pvg_tools/en/\n\n"
             "  • SENER México — datos oficiales\n"
             "    https://www.gob.mx/sener\n\n"
             "  • Global Solar Atlas — mapa interactivo\n"
             "    https://globalsolaratlas.info"),

            ("⚠ Aviso importante",
             "Esta calculadora es un modelo didáctico diseñado para clubes de ciencia. Los "
             "valores son estimaciones razonables pero no sustituyen un estudio profesional. "
             "Para una instalación real, consulta a un instalador certificado por ANCE o "
             "conforme a la norma NMX-J-643."),
        ]

        for titulo, cuerpo in secciones:
            ttk.Label(marco_interno, text=titulo,
                      background=COLOR_TARJETA,
                      foreground=COLOR_PRIMARIO,
                      font=("Helvetica", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
            ttk.Label(marco_interno, text=cuerpo,
                      background=COLOR_TARJETA,
                      foreground=COLOR_TEXTO,
                      font=("Courier New", 9) if "Fórmulas" in titulo or "Fuentes" in titulo or "Bibliografía" in titulo or "Recursos" in titulo else ("Helvetica", 10),
                      wraplength=720,
                      justify="left").pack(anchor="w", padx=18, pady=(0, 6))

    # ----------------------------- gráficas ----------------------------
    def _nueva_figura(self, tab):
        for w in tab.winfo_children():
            w.destroy()
        fig = Figure(figsize=(8, 4.5), dpi=100, facecolor=COLOR_TARJETA)
        ax = fig.add_subplot(111)
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        return fig, ax, canvas

    def _graficar_mensual(self):
        fig, ax, canvas = self._nueva_figura(self.tab_mensual)
        valores = self.resultado["produccion_mensual"]
        barras = ax.bar(MESES, valores, color=COLOR_PRIMARIO, edgecolor="white")
        for b, v in zip(barras, valores):
            ax.text(b.get_x() + b.get_width() / 2, v + max(valores) * 0.01,
                    f"{v:.0f}", ha="center", va="bottom", fontsize=8)
        ax.set_title(f"Producción mensual estimada — {self.parametros_actuales['ciudad']}",
                     color=COLOR_TEXTO, fontsize=12)
        ax.set_ylabel("kWh / mes")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        fig.tight_layout()
        canvas.draw()

    def _graficar_ahorro(self):
        fig, ax, canvas = self._nueva_figura(self.tab_ahorro)
        anios = list(range(0, 21))
        ahorro = [self.resultado["ahorro_anual"] * a -
                  self.parametros_actuales["costo_sistema"] for a in anios]
        ax.plot(anios, ahorro, color=COLOR_PRIMARIO, linewidth=2.5, marker="o", markersize=4)
        ax.axhline(0, color="#888", linestyle="--", linewidth=1)
        ax.fill_between(anios, ahorro, 0,
                        where=[a >= 0 for a in ahorro],
                        color=COLOR_EXITO, alpha=0.2)
        ax.fill_between(anios, ahorro, 0,
                        where=[a < 0 for a in ahorro],
                        color="#E74C3C", alpha=0.15)
        ax.set_title("Ahorro económico acumulado", color=COLOR_TEXTO, fontsize=12)
        ax.set_xlabel("Años")
        ax.set_ylabel("Ahorro neto ($)")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(linestyle="--", alpha=0.4)
        fig.tight_layout()
        canvas.draw()

    def _graficar_consumo(self):
        fig, ax, canvas = self._nueva_figura(self.tab_consumo)
        produccion = self.resultado["produccion_mensual"]
        consumo = [CONSUMO_HOGAR_PROMEDIO] * 12
        x = range(12)
        ancho = 0.4
        ax.bar([i - ancho/2 for i in x], produccion, ancho,
               label="Tu producción", color=COLOR_PRIMARIO)
        ax.bar([i + ancho/2 for i in x], consumo, ancho,
               label="Consumo hogar promedio", color=COLOR_PRIMARIO)
        ax.set_xticks(list(x))
        ax.set_xticklabels(MESES)
        ax.set_title(f"Producción vs consumo de un hogar promedio  "
                     f"(cobertura: {self.resultado['cobertura']:.0f}%)",
                     color=COLOR_TEXTO, fontsize=12)
        ax.set_ylabel("kWh / mes")
        ax.legend()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        fig.tight_layout()
        canvas.draw()

    def _mostrar_factura_cfe(self):
        """Pestaña con desglose de facturación CFE antes/después de solar."""
        for w in self.tab_cfe.winfo_children():
            w.destroy()

        if self.factura_cfe is None:
            tk.Label(self.tab_cfe,
                     text="Selecciona 'Tarifa CFE (México)' en el modo de facturación\n"
                          "y vuelve a calcular para ver el desglose detallado.",
                     bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE,
                     font=("Helvetica", 11, "italic"),
                     justify="center").pack(pady=40)
            return

        f = self.factura_cfe
        info = TARIFAS_CFE[self.parametros_actuales["tarifa_cfe"]]

        # Encabezado
        cab = tk.Frame(self.tab_cfe, bg=COLOR_TARJETA)
        cab.pack(fill="x", padx=20, pady=(15, 10))
        tk.Label(cab,
                 text=f"💡 Análisis con {info['nombre']}",
                 bg=COLOR_TARJETA, fg=COLOR_PRIMARIO,
                 font=("Helvetica", 14, "bold")).pack(anchor="w")
        tk.Label(cab,
                 text=f"Consumo: {self.parametros_actuales['consumo_mensual_kwh']:.0f} kWh/mes  "
                      f"·  Producción solar: {f['produccion_anual']/12:.0f} kWh/mes",
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE,
                 font=("Helvetica", 10)).pack(anchor="w", pady=(2, 0))

        # Tarjeta DAC si aplica
        if f["dac_antes"] or f["dac_despues"]:
            marco_dac = tk.Frame(self.tab_cfe, bg="#FFF8E1",
                                 highlightbackground=COLOR_NARANJA,
                                 highlightthickness=2)
            marco_dac.pack(fill="x", padx=20, pady=(0, 10), ipady=8, ipadx=10)
            if f["dac_antes"] and not f["dac_despues"]:
                msg = ("⚡ Antes de solar: en DAC ($6.07/kWh sin subsidio).\n"
                       "✓ Con solar SALE de DAC y vuelve a tarifa normal — "
                       "esto multiplica el ahorro.")
                color_msg = COLOR_EXITO
            elif f["dac_antes"] and f["dac_despues"]:
                msg = ("⚠ El sistema solar no es suficiente para salir de DAC.\n"
                       "Considera aumentar el área de paneles o reducir consumo.")
                color_msg = "#F57C00"
            else:
                msg = "⚡ Después de solar entras en DAC. Revisa el cálculo."
                color_msg = "#F57C00"
            tk.Label(marco_dac, text=msg,
                     bg="#FFF8E1", fg=color_msg,
                     font=("Helvetica", 10, "bold"),
                     justify="left").pack(anchor="w", padx=8)

        # Comparativa de facturas
        comp = tk.Frame(self.tab_cfe, bg=COLOR_TARJETA)
        comp.pack(fill="x", padx=20, pady=10)
        for i in range(3):
            comp.columnconfigure(i, weight=1)

        def card(parent, col, titulo, valor, color, sub=""):
            m = tk.Frame(parent, bg=COLOR_GRIS_BG,
                         highlightbackground=color, highlightthickness=0)
            m.grid(row=0, column=col, sticky="nsew", padx=5, ipady=10)
            tk.Frame(m, bg=color, width=4).pack(side="left", fill="y")
            cont = tk.Frame(m, bg=COLOR_GRIS_BG)
            cont.pack(side="left", fill="both", expand=True, padx=10, pady=4)
            tk.Label(cont, text=titulo.upper(),
                     bg=COLOR_GRIS_BG, fg=COLOR_TEXTO_SUAVE,
                     font=("Helvetica", 9, "bold")).pack(anchor="w")
            tk.Label(cont, text=valor,
                     bg=COLOR_GRIS_BG, fg=COLOR_TEXTO,
                     font=("Helvetica", 15, "bold")).pack(anchor="w")
            if sub:
                tk.Label(cont, text=sub,
                         bg=COLOR_GRIS_BG, fg=COLOR_TEXTO_SUAVE,
                         font=("Helvetica", 9)).pack(anchor="w")

        card(comp, 0, "Factura SIN solar",
             f"${f['factura_sin_solar']:,.0f}/año",
             "#E74C3C",
             "Tarifa: " + f['tarifa_aplicada_antes'])
        card(comp, 1, "Factura CON solar",
             f"${f['factura_con_solar']:,.0f}/año",
             COLOR_EXITO,
             "Tarifa: " + f['tarifa_aplicada_despues'])
        card(comp, 2, "Ahorro real",
             f"${f['ahorro_anual_real']:,.0f}/año",
             COLOR_PRIMARIO,
             f"${f['precio_efectivo_kwh']:.2f}/kWh efectivo")

        # Tabla mensual
        tk.Label(self.tab_cfe,
                 text="Desglose mensual",
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_2,
                 font=("Helvetica", 12, "bold")).pack(anchor="w", padx=20, pady=(15, 4))

        tabla_marco = tk.Frame(self.tab_cfe, bg=COLOR_TARJETA)
        tabla_marco.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        cols = ("mes", "consumo", "produccion", "neto", "fact_antes", "fact_despues", "ahorro")
        tree = ttk.Treeview(tabla_marco, columns=cols, show="headings", height=14)
        encabezados = [
            ("mes", "Mes", 60), ("consumo", "Consumo kWh", 100),
            ("produccion", "Producción kWh", 110), ("neto", "Neto kWh", 90),
            ("fact_antes", "Sin solar $", 100), ("fact_despues", "Con solar $", 100),
            ("ahorro", "Ahorro $", 100),
        ]
        for c, t, w in encabezados:
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="e")
        tree.column("mes", anchor="center")

        consumo_mes = self.parametros_actuales["consumo_mensual_kwh"]
        prod_mensual = self.resultado["produccion_mensual"]
        tarifa_antes = f["tarifa_aplicada_antes"]
        tarifa_despues = f["tarifa_aplicada_despues"]

        for m in range(12):
            consumo_m = consumo_mes
            prod_m = prod_mensual[m]
            neto_m = max(0, consumo_m - prod_m)
            costo_antes = costo_factura_mes(consumo_m, tarifa_antes, m + 1)
            costo_despues = costo_factura_mes(neto_m, tarifa_despues, m + 1)
            tree.insert("", "end", values=(
                MESES[m],
                f"{consumo_m:.0f}",
                f"{prod_m:.0f}",
                f"{neto_m:.0f}",
                f"${costo_antes:,.0f}",
                f"${costo_despues:,.0f}",
                f"${costo_antes - costo_despues:,.0f}",
            ))
        tree.pack(fill="both", expand=True)

        # Nota
        tk.Label(self.tab_cfe,
                 text="Nota: precios CFE referenciales 2024–2025. Para cálculo de proyecto real, "
                      "actualiza los valores en TARIFAS_CFE con la tarifa vigente del mes.",
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE,
                 font=("Helvetica", 8, "italic"),
                 wraplength=720, justify="left").pack(anchor="w", padx=20, pady=(0, 10))

    def _graficar_seguidor(self):
        """Comparativa de los 3 sistemas: Fijo, Seguidor 1 eje, Seguidor 2 ejes."""
        fig, ax, canvas = self._nueva_figura(self.tab_seguidor)

        # Calcular los tres sistemas con los mismos parámetros base
        comparacion = comparar_sistemas(self.parametros_actuales)

        nombres = list(comparacion.keys())
        anuales = [comparacion[n]["produccion_anual"] for n in nombres]
        ahorros = [comparacion[n]["ahorro_anual"] for n in nombres]

        colores = [COLOR_PRIMARIO, COLOR_NARANJA, COLOR_EXITO]
        x = range(len(nombres))

        barras = ax.bar(x, anuales, color=colores, edgecolor="white", width=0.5)
        for i, (b, v, a) in enumerate(zip(barras, anuales, ahorros)):
            ax.text(b.get_x() + b.get_width() / 2,
                    v + max(anuales) * 0.015,
                    f"{v:.0f} kWh\n${a:,.0f}/año",
                    ha="center", va="bottom",
                    fontsize=10, fontweight="bold", color=COLOR_TEXTO_2)
            # Mostrar % vs fijo
            if i > 0:
                pct = (v / anuales[0] - 1) * 100
                ax.text(b.get_x() + b.get_width() / 2,
                        v / 2,
                        f"+{pct:.0f}%", ha="center", va="center",
                        fontsize=14, fontweight="bold", color="white")

        ax.set_xticks(list(x))
        ax.set_xticklabels(nombres, fontsize=11)
        ax.set_title("Producción anual: Fijo vs Seguidores solares",
                     color=COLOR_TEXTO, fontsize=13, fontweight="bold")
        ax.set_ylabel("kWh / año", color=COLOR_TEXTO_SUAVE)
        ax.set_ylim(0, max(anuales) * 1.20)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        fig.tight_layout()
        canvas.draw()

    def _tabla_detalle(self):
        for w in self.tab_detalle.winfo_children():
            w.destroy()

        cols = ("Concepto", "Valor")
        tree = ttk.Treeview(self.tab_detalle, columns=cols, show="headings", height=14)
        tree.heading("Concepto", text="Concepto")
        tree.heading("Valor", text="Valor")
        tree.column("Concepto", width=320, anchor="w")
        tree.column("Valor", width=200, anchor="e")

        r = self.resultado
        p = self.parametros_actuales

        filas = [
            ("Ciudad", p["ciudad"]),
            ("Irradiación solar (HSP)", f"{p['hsp']:.2f} kWh/m²/día"),
            ("Latitud", f"{p['latitud']:.1f}°"),
            ("Área de paneles", f"{p['area']:.1f} m²"),
            ("Eficiencia del panel", f"{p['eficiencia']:.1f} %"),
            ("Ángulo de inclinación", f"{p['angulo']:.0f}°"),
            ("Factor de inclinación", f"{r['factor_inclinacion']:.3f}"),
            ("Pérdidas del sistema", f"{p['perdidas']:.0f} %"),
            ("─" * 30, "─" * 18),
            ("Producción diaria promedio", f"{r['energia_diaria']:.2f} kWh"),
            ("Producción anual", f"{r['produccion_anual']:.0f} kWh"),
            ("Cobertura del hogar promedio", f"{r['cobertura']:.0f} %"),
            ("Ahorro económico anual", f"${r['ahorro_anual']:,.0f}"),
            ("CO₂ evitado al año", f"{r['co2_evitado']:.0f} kg"),
            ("CO₂ evitado en 20 años", f"{r['co2_evitado'] * 20 / 1000:.1f} toneladas"),
            ("Periodo de recuperación",
                f"{r['payback']:.1f} años" if r["payback"] != float("inf") else "—"),
        ]
        for c, v in filas:
            tree.insert("", "end", values=(c, v))

        tree.pack(fill="both", expand=True, padx=10, pady=10)

    # ---------------------------- exportar -----------------------------
    def exportar_csv(self):
        if not self.resultado:
            messagebox.showwarning("Sin datos", "Primero realiza un cálculo.")
            return

        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"energia_solar_{datetime.now():%Y%m%d_%H%M}.csv")
        if not ruta:
            return

        r = self.resultado
        p = self.parametros_actuales
        try:
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Calculadora de Energía Solar - Reporte"])
                w.writerow(["Generado", datetime.now().strftime("%Y-%m-%d %H:%M")])
                w.writerow([])
                w.writerow(["PARÁMETROS"])
                w.writerow(["Ciudad", p["ciudad"]])
                w.writerow(["HSP (kWh/m²/día)", p["hsp"]])
                w.writerow(["Área (m²)", p["area"]])
                w.writerow(["Eficiencia (%)", p["eficiencia"]])
                w.writerow(["Ángulo (°)", p["angulo"]])
                w.writerow(["Pérdidas (%)", p["perdidas"]])
                w.writerow(["Precio luz ($/kWh)", p["precio_kwh"]])
                w.writerow(["Costo sistema ($)", p["costo_sistema"]])
                w.writerow([])
                w.writerow(["RESULTADOS"])
                w.writerow(["Producción anual (kWh)", round(r["produccion_anual"], 1)])
                w.writerow(["Ahorro anual ($)", round(r["ahorro_anual"], 2)])
                w.writerow(["CO2 evitado (kg/año)", round(r["co2_evitado"], 1)])
                w.writerow(["Cobertura hogar (%)", round(r["cobertura"], 1)])
                w.writerow(["Recuperación (años)",
                            round(r["payback"], 2) if r["payback"] != float("inf") else "N/A"])
                w.writerow([])
                w.writerow(["PRODUCCIÓN MENSUAL"])
                w.writerow(["Mes", "kWh"])
                for m, v in zip(MESES, r["produccion_mensual"]):
                    w.writerow([m, round(v, 1)])

            messagebox.showinfo("Exportado", f"Archivo guardado en:\n{ruta}")
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo guardar el archivo: {e}")

    def exportar_pdf(self):
        if not self.resultado:
            messagebox.showwarning("Sin datos", "Primero realiza un cálculo.")
            return

        ruta = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"reporte_solar_{datetime.now():%Y%m%d_%H%M}.pdf")
        if not ruta:
            return

        try:
            self._construir_pdf(ruta)
            messagebox.showinfo("Exportado", f"Reporte PDF guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF: {e}")

    def _construir_pdf(self, ruta):
        r = self.resultado
        p = self.parametros_actuales

        with PdfPages(ruta) as pdf:
            # Página 1: portada con resumen
            fig = plt.figure(figsize=(8.5, 11))
            fig.suptitle("Reporte: Producción de Energía Solar",
                         fontsize=18, fontweight="bold", color=COLOR_PRIMARIO, y=0.96)

            texto = (
                f"Generado: {datetime.now():%Y-%m-%d %H:%M}\n\n"
                f"PARÁMETROS DE ENTRADA\n"
                f"  • Ciudad: {p['ciudad']}\n"
                f"  • Irradiación (HSP): {p['hsp']:.2f} kWh/m²/día\n"
                f"  • Área de paneles: {p['area']:.1f} m²\n"
                f"  • Eficiencia: {p['eficiencia']:.1f} %\n"
                f"  • Ángulo de inclinación: {p['angulo']:.0f}°\n"
                f"  • Pérdidas del sistema: {p['perdidas']:.0f} %\n"
                f"  • Precio luz: ${p['precio_kwh']:.2f} / kWh\n"
                f"  • Costo del sistema: ${p['costo_sistema']:,.0f}\n\n"
                f"RESULTADOS\n"
                f"  • Producción diaria: {r['energia_diaria']:.2f} kWh\n"
                f"  • Producción anual: {r['produccion_anual']:.0f} kWh\n"
                f"  • Ahorro anual: ${r['ahorro_anual']:,.0f}\n"
                f"  • CO₂ evitado/año: {r['co2_evitado']:.0f} kg\n"
                f"  • CO₂ evitado en 20 años: {r['co2_evitado'] * 20 / 1000:.1f} toneladas\n"
                f"  • Cobertura del hogar promedio: {r['cobertura']:.0f} %\n"
                f"  • Periodo de recuperación: "
                f"{r['payback']:.1f} años\n"
            )

            fig.text(0.1, 0.85, texto, fontsize=11, va="top", family="monospace")
            fig.text(0.1, 0.05,
                     "Club de Ciencias — Proyecto de 5 sábados\n"
                     "Modelo didáctico. Para una instalación real, consulta a un especialista.",
                     fontsize=8, color="#888")
            pdf.savefig(fig)
            plt.close(fig)

            # Página 2: gráfica mensual
            fig, ax = plt.subplots(figsize=(8.5, 5.5))
            ax.bar(MESES, r["produccion_mensual"], color=COLOR_PRIMARIO)
            ax.set_title(f"Producción mensual — {p['ciudad']}")
            ax.set_ylabel("kWh / mes")
            ax.grid(axis="y", linestyle="--", alpha=0.4)
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

            # Página 3: ahorro acumulado
            fig, ax = plt.subplots(figsize=(8.5, 5.5))
            anios = list(range(0, 21))
            ahorro = [r["ahorro_anual"] * a - p["costo_sistema"] for a in anios]
            ax.plot(anios, ahorro, color=COLOR_PRIMARIO, linewidth=2.5, marker="o")
            ax.axhline(0, color="#888", linestyle="--")
            ax.fill_between(anios, ahorro, 0, where=[a >= 0 for a in ahorro],
                            color=COLOR_EXITO, alpha=0.2)
            ax.fill_between(anios, ahorro, 0, where=[a < 0 for a in ahorro],
                            color="#E74C3C", alpha=0.15)
            ax.set_title("Ahorro económico acumulado (20 años)")
            ax.set_xlabel("Años")
            ax.set_ylabel("$")
            ax.grid(linestyle="--", alpha=0.4)
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)


# =====================================================================
#  ENTRADA PRINCIPAL
# =====================================================================
def main():
    app = CalculadoraSolarApp()
    app.mainloop()


if __name__ == "__main__":
    main()
