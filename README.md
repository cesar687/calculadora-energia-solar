# ☀ Calculadora de Producción de Energía Solar

**Desarrollos de Ideas Mexicanas (DIMEX) — Para aprendizaje en clubes de ciencia.**

Calculadora educativa que estima cuánta energía produciría un sistema fotovoltaico según ubicación, área de paneles, eficiencia, inclinación y pérdidas del sistema. Incluye datos reales de 18 ciudades de México, integración con la API de **NASA POWER** y gráficas de producción mensual, ahorro económico y comparativa contra el consumo de un hogar promedio.

🌐 **Versión web (úsala en celular o computadora):** [Abrir calculadora](https://USUARIO.github.io/calculadora-energia-solar/)

> Reemplaza `USUARIO` con tu nombre de usuario de GitHub después de habilitar Pages.

---

## Características

- 📍 **Tres modos de irradiación solar:**
  - Ciudad predefinida (18 ciudades de México con datos del Atlas SENER)
  - Entrada manual de HSP y latitud
  - Descarga en vivo desde **NASA POWER** ingresando lat/lon

- 📊 **Cuatro visualizaciones:**
  - Producción mensual estimada
  - Ahorro económico acumulado a 20 años
  - Comparativa contra consumo de un hogar promedio
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

## Fórmulas físicas

Energía diaria producida por el panel:

```
E = A × η × HSP × PR × f_inclinación
```

| Variable        | Descripción                                       |
|-----------------|---------------------------------------------------|
| **A**           | Área del panel (m²)                               |
| **η**           | Eficiencia del panel (decimal, ej: 0.20 = 20%)    |
| **HSP**         | Horas sol pico (kWh/m²/día)                       |
| **PR**          | Performance Ratio = 1 − pérdidas (ej: 0.80)       |
| **f_inclinación** | cos(\|ángulo − latitud\|)                       |

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

## Aviso

Esta calculadora es un **modelo didáctico** diseñado para clubes de ciencia. Los valores son estimaciones razonables pero **no sustituyen un estudio profesional**. Para una instalación real, consulta a un instalador certificado conforme a la norma NMX-J-643.

---

## Licencia

MIT — uso libre con atribución.

---

**DIMEX — Desarrollos de Ideas Mexicanas**
