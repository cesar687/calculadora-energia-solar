# ☀ Calculadora de Producción de Energía Solar

**Desarrollos de Ideas Mexicanas (DIMEX) — Para aprendizaje en clubes de ciencia.**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Status](https://img.shields.io/badge/status-didáctico-orange)
![GitHub Pages](https://img.shields.io/badge/web-online-green)

Calculadora educativa que estima cuánta energía produciría un sistema fotovoltaico según ubicación, área de paneles, eficiencia, inclinación y pérdidas del sistema. Incluye datos reales de 18 ciudades de México, integración con la API de **NASA POWER** y gráficas de producción mensual, ahorro económico y comparativa contra el consumo de un hogar promedio.

🌐 **Versión web (úsala en celular o computadora):** [Abrir calculadora](https://cesar687.github.io/calculadora-energia-solar/))

> Reemplaza `USUARIO` con tu nombre de usuario de GitHub después de habilitar Pages.

---

## Características

- 📍 **Tres modos de irradiación solar:**
  - Ciudad predefinida (18 ciudades de México con datos del Atlas SENER)
  - Entrada manual de HSP y latitud
  - Descarga en vivo desde **NASA POWER** ingresando lat/lon

- 🔁 **Comparador de sistemas:**
  - Panel fijo (sin seguidor)
  - Seguidor solar de **1 eje** (+27% producción)
  - Seguidor solar de **2 ejes** (+38% producción)
  - Incluye proyecto guiado para construir un seguidor con Arduino, servomotores y LDRs

- 🇲🇽 **Modelo de tarifas CFE (México):**
  - Las 8 tarifas residenciales (1, 1A, 1B, 1C, 1D, 1E, 1F, DAC) con bloques verano/invierno
  - Cálculo en cascada por bloque (básico, intermedio, excedente)
  - **Acantilado DAC**: la calculadora detecta si el hogar entra/sale de DAC con solar — esto puede multiplicar el ahorro real 2–3× vs un modelo de precio único
  - Desglose mensual: consumo, producción, neto, factura antes/después y ahorro real
  - Precio efectivo por kWh evitado (útil para ingeniería)

- 📊 **Cinco visualizaciones:**
  - Producción mensual estimada
  - Ahorro económico acumulado a 20 años
  - Comparativa contra consumo de un hogar promedio
  - Comparativa Fijo vs Seguidor 1 eje vs Seguidor 2 ejes
  - Tabla de detalle numérico

- 📚 **Pestaña Aprende:** explicación didáctica del efecto fotovoltaico, HSP, ángulo de inclinación, pérdidas del sistema y experimentos para el club.

- 📖 **Pestaña Bibliografía:** fórmulas físicas, fuentes de datos (SENER, NASA POWER, CRE, CFE) y referencias académicas.

- 💾 **Exportación:** CSV con todos los resultados; impresión a PDF desde el navegador.

---

## Cómo usar

### Versión web (recomendada para celular)

Abre **index.html** en cualquier navegador o visita la URL de GitHub Pages.

### Versión Python (escritorio, con ventana gráfica)

```bash
pip3 install matplotlib
python3 calculadora_energia_solar.py
```

Requiere Python 3.8+ y `tkinter` (incluido en Python de python.org; en macOS con Homebrew: `brew install python-tk`).

---

## 📸 Capturas

Para agregar capturas: ejecuta la calculadora, toma screenshots y guárdalos en una carpeta `docs/` del repo. Luego inclúyelos así:

```markdown
![Pantalla principal](docs/captura-principal.png)
![Comparador de seguidores](docs/comparador-seguidor.png)
![Pestaña Aprende](docs/aprende.png)
```

---

## Fórmulas físicas

Energía diaria producida por el panel:

```
E = A × η × HSP × PR × f_inclinación × G_seguidor
```

| Variable        | Descripción                                                   |
|-----------------|---------------------------------------------------------------|
| **A**           | Área del panel (m²)                                           |
| **η**           | Eficiencia del panel (decimal, ej: 0.20 = 20%)                |
| **HSP**         | Horas sol pico (kWh/m²/día)                                   |
| **PR**          | Performance Ratio = 1 − pérdidas (ej: 0.80)                   |
| **f_inclinación** | cos(\|ángulo − latitud\|) si es fijo, 1.0 con seguidor      |
| **G_seguidor**  | Fijo: 1.00 · Seguidor 1 eje: 1.27 · Seguidor 2 ejes: 1.38     |

CO₂ evitado al año:

```
CO₂ (kg) = E_anual × 0.494
```

Periodo de recuperación:

```
Payback (años) = Costo del sistema ÷ Ahorro anual
```

---

## Fuentes de datos

- **HSP por ciudad:** SENER — Atlas Nacional de Zonas con Alto Potencial de Energías Limpias (AZEL)
- **Datos satelitales globales:** [NASA POWER](https://power.larc.nasa.gov) — parámetro `ALLSKY_SFC_SW_DWN`
- **Factor de emisión CO₂:** CRE — Factor de Emisión del Sistema Eléctrico Nacional 2023 (0.494 kg CO₂/kWh)
- **Consumo del hogar:** CFE — ~250 kWh/mes (tarifa doméstica básica)

---

## Plan sugerido para 5 sábados del club

1. **Sábado 1** — Investigar la física del recurso solar y recolectar HSP de varias ciudades
2. **Sábado 2** — Construir la fórmula y probarla en consola con casos simples
3. **Sábado 3** — Armar la interfaz Tkinter (Python) o HTML/JS con entradas y resultados
4. **Sábado 4** — Agregar gráficas con matplotlib o Chart.js
5. **Sábado 5** — Validación, exportación PDF/CSV y presentación final

---

## ⚠ Limitaciones y precisión

Esta es una herramienta **educativa**, no profesional. Su precisión típica es de **±15 a 25 %** comparada con la producción real medida en una instalación. Las causas principales de incertidumbre son:

| Fuente de error            | Magnitud típica | Por qué                                                |
|----------------------------|-----------------|--------------------------------------------------------|
| HSP de la ciudad           | ±5 %            | Es un promedio anual; tu microclima puede variar       |
| Eficiencia real del panel  | ±3 %            | Baja con la edad (~0.5 %/año) y la temperatura         |
| Pérdidas reales            | ±10 %           | Sombras, polvo, cableado dependen de cada instalación  |
| Factor de inclinación      | ±5 %            | Modelo cos() simplificado; el real usa azimut y altura |
| Ganancia del seguidor      | ±5 %            | Varía con latitud y tipo de mecanismo                  |
| Tarifa eléctrica (CFE)     | ±10 %           | Cambia trimestralmente; aquí se usan valores promedio  |

**Lo que esta calculadora SÍ hace bien:**

- Comparar **escenarios relativos** (¿Mexicali vs CDMX? ¿Fijo vs seguidor?)
- Enseñar las **variables físicas** que afectan la producción
- Dar un **orden de magnitud** del ahorro y payback (±20 %)

**Lo que NO modela:**

- Sombras parciales reales sobre el panel
- Variación de temperatura horaria
- Inversor real con su curva de eficiencia
- Sistema de baterías
- Degradación del panel a 25–30 años
- Cambios futuros en tarifas eléctricas
- Net-metering / net-billing (contrato con CFE)

**No debe usarse para:**

- Cotizar una instalación real
- Decidir el dimensionamiento de un sistema
- Calcular ROI para una inversión seria

Para esos casos, usa una herramienta profesional (ver sección siguiente) y consulta a un instalador certificado conforme a la norma **NMX-J-643/1-ANCE**.

---

## 🔬 Comparación con herramientas profesionales

Si necesitas precisión de ingeniería, usa una de estas:

| Herramienta                                                       | Precisión | Costo       | Uso recomendado                |
|-------------------------------------------------------------------|-----------|-------------|--------------------------------|
| Esta calculadora DIMEX                                            | ±15–25 %  | Gratis      | Educación, primera estimación  |
| [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/) (Comisión Europea)| ±5–10 %   | Gratis      | Estudio preliminar serio       |
| [NREL PVWatts](https://pvwatts.nrel.gov)                          | ±5–10 %   | Gratis      | Estimación rápida en EE.UU.    |
| **PVsyst**                                                        | ±2–5 %    | ~$1,000 USD | Diseño profesional certificado |
| **Helioscope**                                                    | ±2–5 %    | Suscripción | Instaladores comerciales       |

Lo que estas herramientas hacen y la nuestra no:

- Modelo hora a hora (8,760 horas/año)
- Datos meteorológicos TMY (Typical Meteorological Year)
- Simulación de sombras 3D
- Curvas reales de inversor y panel comerciales (PAN files)
- Degradación a 25 años
- Reporte certificado válido para financiamiento bancario

---

## 🤝 Contribuir

¿Tienes ideas o encontraste un error? Abre un [Issue](https://github.com/TU_USUARIO/calculadora-energia-solar/issues) o envía un Pull Request.

Ideas para mejorar:

- Agregar más ciudades de México y América Latina
- Modelar baterías de litio (capacidad, eficiencia round-trip)
- Soporte para net-metering / net-billing CFE
- Versión PWA instalable en celular
- Traducción al inglés y portugués
- Modo offline con datos cacheados

---

## 📬 Contacto

**DIMEX — Desarrollos de Ideas Mexicanas**
📧 cesar@dimexideas.com
🌐 [dimexideas.com](https://dimexideas.com)

---

## Licencia

MIT — uso libre con atribución.

---

**DIMEX — Desarrollos de Ideas Mexicanas**

