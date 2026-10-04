-- Carga los CSV limpios (comandos \copy de psql; ejecutar desde la raíz del repositorio).
\copy catalogo_productos FROM 'data/processed/catalogo_productos.csv' WITH (FORMAT csv, HEADER true)
\copy produccion_turnos  FROM 'data/processed/produccion_turnos.csv'  WITH (FORMAT csv, HEADER true)
\copy scrap_por_defecto  FROM 'data/processed/scrap_por_defecto.csv'  WITH (FORMAT csv, HEADER true)
\copy reclamos_cliente   FROM 'data/processed/reclamos_cliente.csv'   WITH (FORMAT csv, HEADER true)
\copy mantenimientos     FROM 'data/processed/mantenimientos.csv'     WITH (FORMAT csv, HEADER true)
\copy altas_operadores   FROM 'data/processed/altas_operadores.csv'   WITH (FORMAT csv, HEADER true)
