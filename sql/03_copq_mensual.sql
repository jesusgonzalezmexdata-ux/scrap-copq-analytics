-- Costo de no calidad (COPQ) por mes: scrap (material + conversión) + retrabajo + reclamos.
WITH scrap AS (
    SELECT CAST(date_trunc('month', p.fecha) AS DATE)                    AS mes,
           SUM(p.piezas_scrap * (c.costo_material_mxn + c.costo_conversion_mxn)) AS costo_scrap_mxn,
           SUM(p.piezas_retrabajo * c.costo_retrabajo_mxn)                AS costo_retrabajo_mxn
    FROM produccion_turnos p
    JOIN catalogo_productos c USING (producto)
    GROUP BY 1
), reclamos AS (
    SELECT CAST(date_trunc('month', fecha) AS DATE) AS mes,
           SUM(costo_total_mxn)                     AS costo_reclamos_mxn
    FROM reclamos_cliente
    GROUP BY 1
)
SELECT s.mes,
       s.costo_scrap_mxn,
       s.costo_retrabajo_mxn,
       COALESCE(r.costo_reclamos_mxn, 0)                                         AS costo_reclamos_mxn,
       s.costo_scrap_mxn + s.costo_retrabajo_mxn + COALESCE(r.costo_reclamos_mxn, 0) AS copq_mxn
FROM scrap s
LEFT JOIN reclamos r USING (mes)
ORDER BY s.mes;
