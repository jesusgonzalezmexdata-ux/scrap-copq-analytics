# Analítica de scrap y costo de no calidad (COPQ)

*[English](README.md) · Español*

**[Demo en vivo](https://huggingface.co/spaces/JesusRLGonzalez/scrap-copq-analytics)** | **[Página del proyecto](https://jesusgonzalezmexdata-ux.github.io/scrap-copq-analytics/)**

**Cómo encontrar las palancas que reducen el scrap en una planta de autopartes, cuantificarlas en pesos y validarlas con estadística.**

Python (pandas, statsmodels) · SQL (PostgreSQL) · control estadístico de procesos · GLM binomial · Streamlit

> **Datos sintéticos.** La planta, sus líneas y sus cifras son ficticias. Los datos se generan con `scrap_copq/generate.py` (semilla fija) e imitan problemas reales de manufactura: desgaste entre mantenimientos, rotación de personal, lotes de un proveedor, humedad y una falla de fixture.

## Resumen ejecutivo

**La no calidad costó 8.46 millones de MXN en 2025 (1.85 % de las ventas). Tres palancas recortan 1.23 millones al año (14.5 % del COPQ), y más del 80 % de ese ahorro viene de una sola: ajustar el mantenimiento preventivo de la línea de soldadura robotizada.**

| Hallazgo | Evidencia |
|---|---|
| El desgaste entre mantenimientos de L2 es la mayor fuga | L2 genera el 49 % del costo de scrap. Su tasa se mantiene en ~1.9 % hasta ~170 h desde el preventivo y llega a 6 % a las 310 h; hoy el intervalo es de 320 h |
| El volumen engaña | La *falta de fusión* es el 5 % de las piezas desechadas pero el 16 % del costo, y originó 6 de los 8 reclamos de cliente |
| El problema del turno nocturno es la rotación | Las 10 altas del año entraron de noche. Cada operador nuevo en soldadura manual multiplica por 1.34 los momios de scrap |
| El proveedor barato no es barato | El proveedor C surte el 15 % del material de L1 pero causa el 42 % de las grietas; su descuento de 2 % se va en scrap y reclamos |

| Palanca | Ahorro neto anual (mediana) | Intervalo P10–P90 |
|---|---|---|
| Mantenimiento preventivo de L2 cada 170–180 h | **1.03 M MXN** | 1.00 – 1.06 M |
| Reasignar los lotes del proveedor C al A | 0.12 M MXN | 0.12 – 0.13 M |
| Inducción por competencias para operadores nuevos | 0.08 M MXN | 0.06 – 0.09 M |

![Pareto por piezas frente a Pareto por costo](reports/figures/pareto_piezas_vs_costo.png)

## Método

```
MES (crudo) → limpieza y validación → COPQ y Pareto → cartas p / p′ → exploración → GLM binomial → simulación de ahorro
```

1. **Limpieza** (`scrap_copq/clean.py`). Normaliza turnos, quita duplicados y excluye corridas imposibles (scrap mayor a lo producido o que no cuadra con el desglose por defecto). La humedad faltante se imputa con la lectura del mismo turno en otra línea. Cada corrección queda registrada en `data/processed/reporte_calidad_datos.json`.
2. **Costo de no calidad.** Scrap (material más conversión), retrabajo y reclamos de cliente (selección, flete urgente y penalización).
3. **Pareto doble.** Por piezas y por costo, con los reclamos atribuidos a su defecto.
4. **Control estadístico.** La carta p clásica marca 47 % de los días de L2 como fuera de control: con miles de piezas por día, cualquier variación real los dispara. La **carta p′ de Laney** corrige esa sobredispersión y deja 32 días. Todos ocurren con más de 170 h desde el mantenimiento, y la firma del defecto separa dos causas: desgaste (porosidad) y una falla de fixture (dimensional).
5. **Modelo explicativo.** Regresión logística sobre proporciones (GLM binomial ponderado por piezas), con escala cuasi-binomial por la sobredispersión (χ²/gl = 1.78). El umbral de mantenimiento se estima por mínima devianza. Fuera de muestra (entrenado con ene–sep, evaluado en oct–dic) supera a dos modelos base:

   | Predicción de la tasa diaria de scrap | Error absoluto medio (pp) |
   |---|---:|
   | Base: promedio por línea | 1.18 |
   | Base: promedio por línea × banda de 50 h desde el mantenimiento | 1.04 |
   | **GLM binomial** | **0.65** |

   El segundo modelo base ya sabe que el desgaste importa; el GLM aún reduce su error en un tercio porque también usa operadores, lotes de proveedor y humedad.
6. **Simulación de ahorro.** El modelo predice el scrap con y sin cada palanca, valora la diferencia a costo y resta lo que cuesta implementarla. La incertidumbre se propaga con 2,000 simulaciones de los coeficientes.

<p>
  <img src="reports/figures/carta_p_vs_laney_L2.png" width="49%" alt="Carta p clásica frente a carta p′ de Laney">
  <img src="reports/figures/scrap_vs_mantenimiento.png" width="49%" alt="Tasa de scrap según horas desde el mantenimiento">
</p>
<p>
  <img src="reports/figures/curva_mantenimiento_L2.png" width="49%" alt="Ahorro neto según el intervalo de mantenimiento">
  <img src="reports/figures/razones_de_momios.png" width="49%" alt="Razones de momios del modelo">
</p>

El análisis completo, con la explicación de cada paso, está en [`notebooks/analisis_scrap_copq.ipynb`](notebooks/analisis_scrap_copq.ipynb).

## Tablero interactivo

`streamlit_app.py` tiene filtros de periodo, línea y turno, y cinco pestañas:
- **Costo por mes:** COPQ mensual por componente.
- **Pareto:** por costo o por piezas.
- **Control estadístico:** cartas p y p′ por línea.
- **Causas:** factores que elevan el scrap.
- **Simulador de ahorro:** mueve el intervalo de mantenimiento y la eficacia de la inducción, y ve el ahorro.

![Tablero: simulador de ahorro](reports/figures/tablero.png)

## Úsalo con los datos de tu planta (MVP)

El modo **«Tus datos»** del tablero aplica el mismo diagnóstico al Excel de una planta real, sin suponer nombres de líneas, turnos ni proveedores.

1. Descarga la plantilla (tres hojas: `produccion`, una fila por corrida; `costos`, por número de parte; `reclamos`, opcional). Viene llena con la planta sintética como ejemplo.
2. Sube tu archivo, o usa el botón del archivo de ejemplo con errores de captura. Las filas con error se excluyen y se listan con su número de fila de Excel (más scrap que producción, número de parte desconocido, fechas inválidas, duplicados).
3. Lee el resultado: costo de no calidad, cartas p′ de Laney por línea y solo las palancas con efecto estadísticamente distinto de cero, cada una con su ahorro anual P10–P90 y una prueba fuera de muestra contra el promedio por línea.
4. Descarga un reporte de una página con la acción propuesta en formato 8D y sus referencias IATF 16949 / ISO 9001.

**Privacidad:** en la demo publicada el archivo se procesa dentro del navegador del visitante (Python en WebAssembly) y no se envía a ningún servidor. Sobre la planta sintética, el modelo genérico encuentra la misma palanca principal sin que se le indique: preventivo de L2 cada 160 h en lugar de ≈ 320 h, 1.07 M MXN netos al año. Protocolo de piloto y criterios de éxito y de abandono: [`docs/MVP_PILOTO.md`](docs/MVP_PILOTO.md).

## Cómo ejecutarlo

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows · en macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

python -m scrap_copq.generate      # opcional: regenera los datos sintéticos
python -m scrap_copq.clean         # limpieza y validación
python -m scrap_copq.intake plantilla_scrap.xlsx   # plantilla de Excel para una planta real
pytest                             # 24 pruebas: métricas, limpieza, modelo, SQL y entrada del MVP
streamlit run streamlit_app.py     # tablero
jupyter lab notebooks/analisis_scrap_copq.ipynb
```

**SQL en PostgreSQL.** Esquema con restricciones de integridad, carga de los CSV limpios y tres consultas: COPQ mensual con CTE, Pareto con funciones de ventana, y carta p′ de Laney con `LAG`.

```bash
createdb planta
psql -d planta -f sql/01_esquema.sql -f sql/02_carga.sql
psql -d planta -f sql/05_carta_p_laney.sql
```

Las pruebas comparan el resultado de cada consulta con el de Python. En el repositorio corren en DuckDB, para no requerir servidor; también se verificaron en PostgreSQL 16.

## Estructura

```
├── scrap_copq/
│   ├── config.py      # catálogo de la planta y supuestos de costo
│   ├── generate.py    # datos sintéticos con patrones sembrados
│   ├── clean.py       # limpieza y validación
│   ├── metrics.py     # COPQ, Pareto, cartas p y p′, reglas de Western Electric
│   ├── intake.py      # MVP: plantilla de Excel y validación por fila
│   ├── diagnose.py    # MVP: diagnóstico genérico con palancas filtradas por significancia
│   ├── report.py      # MVP: reporte de una página con la acción 8D
│   ├── ui_diagnostico.py  # MVP: modo «Tus datos» del tablero
│   ├── model.py       # GLM binomial, umbral, validación y simulación de ahorro
│   └── plots.py       # gráficas del notebook y del README
├── sql/               # esquema, carga y consultas para PostgreSQL
├── notebooks/         # análisis narrado
├── data/raw/          # exportación "sucia" del MES
├── data/processed/    # datos limpios
├── reports/figures/
├── tests/
└── streamlit_app.py
```

## Datos

`produccion_turnos.csv`: una fila por línea, turno y día (2,751 corridas limpias en 2025).

| Columna | Descripción |
|---|---|
| `piezas_producidas`, `piezas_scrap`, `piezas_retrabajo` | Volumen de la corrida |
| `horas_desde_mantto` | Horas de operación desde el último mantenimiento preventivo de la línea |
| `operadores_nuevos` | Operadores de la cuadrilla con menos de 6 meses de antigüedad (0–4) |
| `proveedor_material` | Proveedor del lote de lámina o alambre (A, B o C) |
| `humedad_rel_pct` | Humedad relativa ambiente |
| `cambio_modelo` | 1 si la corrida empezó con cambio de número de parte |
| `paro_min` | Minutos de paro no planeado |

Además: `scrap_por_defecto.csv`, `reclamos_cliente.csv`, `mantenimientos.csv`, `altas_operadores.csv` y `catalogo_productos.csv` (costos y precios por pieza).

## Supuestos y limitaciones

- **Datos sintéticos:** los efectos se sembraron para demostrar el método. En una planta real, cada causa se confirma en piso, por ejemplo con un Ishikawa o 5 porqués por hallazgo.
- **Modelo observacional:** el ahorro asume que los efectos estimados son causales. Un piloto con carta p′ antes y después es la prueba definitiva.
- **Costos:** los de las palancas (`scrap_copq/config.py`) son supuestos y deben reemplazarse con datos de la planta. Son 4,500 MXN por preventivo adicional, 15,000 MXN por operador capacitado y un descuento de 2 % del proveedor C.

---

**Jesús R. L. González**: Analista y Científico de Datos · Operaciones y Calidad en manufactura · [LinkedIn](https://www.linkedin.com/in/jesus-r-l-gonzalez)
