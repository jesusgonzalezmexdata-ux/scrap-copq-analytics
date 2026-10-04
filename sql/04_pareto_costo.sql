-- Pareto de defectos por costo: scrap valorizado + reclamos atribuidos al defecto.
WITH costo AS (
    SELECT d.defecto,
           SUM(d.piezas * (c.costo_material_mxn + c.costo_conversion_mxn)) AS valor
    FROM scrap_por_defecto d
    JOIN produccion_turnos p USING (run_id)
    JOIN catalogo_productos c ON c.producto = p.producto
    GROUP BY d.defecto
    UNION ALL
    SELECT defecto, SUM(costo_total_mxn)
    FROM reclamos_cliente
    GROUP BY defecto
), por_defecto AS (
    SELECT defecto, SUM(valor) AS costo_mxn
    FROM costo
    GROUP BY defecto
)
SELECT defecto,
       costo_mxn,
       ROUND(100 * costo_mxn / SUM(costo_mxn) OVER (), 2) AS pct,
       ROUND(100 * SUM(costo_mxn) OVER (ORDER BY costo_mxn DESC ROWS UNBOUNDED PRECEDING)
             / SUM(costo_mxn) OVER (), 2)                AS pct_acum
FROM por_defecto
ORDER BY costo_mxn DESC;
