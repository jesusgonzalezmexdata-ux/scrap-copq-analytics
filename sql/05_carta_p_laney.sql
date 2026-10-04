-- Carta p diaria por línea, clásica y p′ de Laney.
-- p′: los límites se multiplican por σ_z = promedio del rango móvil de z / 1.128.
WITH diario AS (
    SELECT linea, fecha,
           SUM(piezas_producidas)                                      AS n,
           SUM(piezas_scrap)                                           AS x,
           CAST(SUM(piezas_scrap) AS NUMERIC(18,10)) / SUM(piezas_producidas) AS p
    FROM produccion_turnos
    GROUP BY linea, fecha
), centro AS (
    SELECT linea, CAST(SUM(x) AS NUMERIC(18,10)) / SUM(n) AS p_barra
    FROM diario
    GROUP BY linea
), estandar AS (
    SELECT d.*, c.p_barra,
           SQRT(c.p_barra * (1 - c.p_barra) / d.n)                     AS sigma,
           (d.p - c.p_barra) / SQRT(c.p_barra * (1 - c.p_barra) / d.n) AS z
    FROM diario d
    JOIN centro c USING (linea)
), rango_movil AS (
    SELECT *, ABS(z - LAG(z) OVER (PARTITION BY linea ORDER BY fecha)) AS rm
    FROM estandar
), laney AS (
    SELECT linea, AVG(rm) / 1.128 AS sigma_z
    FROM rango_movil
    GROUP BY linea
)
SELECT r.linea, r.fecha, r.n, r.x,
       ROUND(r.p, 6)                                              AS p,
       ROUND(r.p_barra, 6)                                        AS lc,
       ROUND(r.p_barra + 3 * r.sigma, 6)                          AS lsc_p,
       ROUND(r.p_barra + 3 * r.sigma * l.sigma_z, 6)              AS lsc_laney,
       ROUND(GREATEST(r.p_barra - 3 * r.sigma * l.sigma_z, 0), 6) AS lic_laney,
       ROUND(l.sigma_z, 3)                                        AS sigma_z,
       ABS(r.z) > 3                                          AS fuera_p,
       ABS(r.z) > 3 * l.sigma_z                              AS fuera_laney
FROM rango_movil r
JOIN laney l USING (linea)
ORDER BY r.linea, r.fecha;
