# MVP «Diagnóstico de scrap en pesos»: protocolo de piloto

**Para quién:** gerente de calidad o de planta en un proveedor de autopartes (Tier 1 o 2) u otra manufactura con scrap registrado por corrida.
**Qué decide:** qué palanca de reducción de scrap financiar primero y con qué ahorro esperado.
**Qué recibe:** un reporte de una página con el costo de no calidad, las palancas con efecto demostrado y la acción propuesta en formato 8D.

## 1. Datos que se piden

| Hoja | Obligatorio | Opcional (cada columna habilita un análisis) |
|---|---|---|
| `produccion` (una fila por corrida) | fecha, línea, turno, producto, piezas producidas, piezas de scrap | retrabajo; horas desde el último preventivo (palanca de mantenimiento); proveedor del material (palanca de proveedor); operadores nuevos (palanca de inducción); una columna `scrap_<defecto>` por defecto (Pareto) |
| `costos` (por número de parte) | material y conversión por pieza | retrabajo por pieza, precio de venta |
| `reclamos` | — | fecha, línea, defecto y costo total de cada reclamo de cliente |

Mínimo 3 meses de corridas; ideal 12. La plantilla descargable trae las instrucciones y un ejemplo lleno.

**Lo que más cuesta conseguir** no es el modelo, sino unir el registro de scrap (MES o Excel de calidad) con el de mantenimiento por línea y fecha. Si la planta no registra las horas desde el preventivo, se puede reconstruir a partir de las fechas de las órdenes de mantenimiento.

## 2. Privacidad

- En la demo publicada, el archivo se procesa dentro del navegador del usuario (Python en WebAssembly). No se envía a ningún servidor ni queda guardado.
- Para el piloto se recomiendan identificadores codificados: líneas, operadores y proveedores sin nombres reales.
- El caso solo se publica con autorización escrita y sin datos que identifiquen a la empresa.

## 3. Fases

| Fase | Duración | Actividad | Entregable |
|---|---|---|---|
| 0 · Acuerdo | 1 semana | Carta de confidencialidad, responsable del lado de la planta, extracción de datos | Archivo con la plantilla llena |
| 1 · Retrospectiva | 1–2 semanas | Diagnóstico sobre el histórico; revisión de errores de datos con el responsable | Reporte de una página y lista de correcciones de datos |
| 2 · Confirmación en piso | 1 semana | D4 del 8D con el equipo: 5 porqués o Ishikawa sobre la palanca principal | Causa confirmada o descartada |
| 3 · Acción controlada | 8 semanas | Aplicar la palanca en una línea o grupo piloto; otro comparable queda como control | Cartas p′ de piloto y control |
| 4 · Cierre | 1 semana | Comparar piloto contra control; actualizar plan de control, AMEF y plan de mantenimiento | Caso de estudio con el resultado y sus límites |

## 4. Criterios definidos antes de empezar

**Pasa de fase 1 a 2 si:**
- el modelo le gana al promedio por línea en la prueba fuera de muestra (el reporte lo indica), y
- hay al menos una palanca con ahorro neto P10 > 0.

**Éxito en fase 3:** la tasa de scrap de la línea piloto baja de forma sostenida en su carta p′ (racha de puntos bajo la línea central o salida por el límite inferior), y la del control no.

**Abandono:**
- menos de 3 meses de datos, o no se pueden unir scrap y mantenimiento por línea y fecha;
- el modelo no supera al promedio por línea;
- la causa no se confirma en piso.

Un abandono también se documenta: indica qué dato tendría que empezar a registrar la planta.

## 5. Qué hace y qué no hace el diagnóstico

- **Hace:** cuantifica el costo de no calidad, separa variación real de falsas alarmas con la carta p′ de Laney y estima cuánto scrap se asocia a cada factor registrado, con intervalo.
- **No hace:** demostrar causalidad. La asociación se confirma en piso (D4) y con la acción controlada (D6). Tampoco ve factores que no estén en el archivo (método, material de otra fuente, condiciones ambientales no registradas).
- **Supuesto de la palanca de mantenimiento:** el scrap por encima del umbral de horas vuelve al nivel previo al umbral si el preventivo se hace a tiempo. El costo considera solo los preventivos adicionales, al precio que capture el usuario.

## 6. Referencias normativas

| Requisito | Cómo se atiende |
|---|---|
| IATF 16949 · 8.5.1.5 Mantenimiento productivo total | Frecuencia del preventivo fijada con datos de desempeño |
| IATF 16949 · 9.1.1.2 Técnicas estadísticas | Carta p′ de Laney y modelo binomial documentados |
| IATF 16949 · 10.2.3 Solución de problemas | Acción en formato 8D con verificación de eficacia |
| ISO 9001 · 9.1.3 Análisis y evaluación | Costo de no calidad y Pareto por costo |
| ISO 9001 · 10.2 No conformidad y acción correctiva | D4–D7 del reporte |
