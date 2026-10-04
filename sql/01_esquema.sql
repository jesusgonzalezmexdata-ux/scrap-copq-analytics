-- Esquema para PostgreSQL (probado en la versión 16).
-- Uso desde la raíz del repositorio:
--   createdb planta
--   psql -d planta -f sql/01_esquema.sql -f sql/02_carga.sql
DROP TABLE IF EXISTS scrap_por_defecto, reclamos_cliente, mantenimientos, altas_operadores,
                     produccion_turnos, catalogo_productos;

CREATE TABLE catalogo_productos (
    producto             VARCHAR(10) PRIMARY KEY,
    descripcion          VARCHAR(60)   NOT NULL,
    linea                VARCHAR(4)    NOT NULL,
    costo_material_mxn   NUMERIC(10,2) NOT NULL,
    costo_conversion_mxn NUMERIC(10,2) NOT NULL,
    costo_retrabajo_mxn  NUMERIC(10,2) NOT NULL,
    precio_venta_mxn     NUMERIC(10,2) NOT NULL
);

CREATE TABLE produccion_turnos (
    run_id             VARCHAR(8) PRIMARY KEY,
    fecha              DATE         NOT NULL,
    linea              VARCHAR(4)   NOT NULL,
    proceso            VARCHAR(30)  NOT NULL,
    turno              VARCHAR(12)  NOT NULL CHECK (turno IN ('Matutino', 'Vespertino', 'Nocturno')),
    producto           VARCHAR(10)  NOT NULL REFERENCES catalogo_productos,
    piezas_producidas  INTEGER      NOT NULL CHECK (piezas_producidas > 0),
    piezas_scrap       INTEGER      NOT NULL CHECK (piezas_scrap >= 0),
    piezas_retrabajo   INTEGER      NOT NULL CHECK (piezas_retrabajo >= 0),
    horas_desde_mantto NUMERIC(6,1) NOT NULL,
    cambio_modelo      SMALLINT     NOT NULL,
    proveedor_material CHAR(1)      NOT NULL,
    operadores_nuevos  SMALLINT     NOT NULL,
    humedad_rel_pct    NUMERIC(5,1) NOT NULL,
    paro_min           INTEGER      NOT NULL,
    CHECK (piezas_scrap <= piezas_producidas)
);

CREATE TABLE scrap_por_defecto (
    run_id  VARCHAR(8)  NOT NULL REFERENCES produccion_turnos,
    defecto VARCHAR(30) NOT NULL,
    piezas  INTEGER     NOT NULL CHECK (piezas > 0),
    PRIMARY KEY (run_id, defecto)
);

CREATE TABLE reclamos_cliente (
    reclamo_id          VARCHAR(8) PRIMARY KEY,
    fecha               DATE          NOT NULL,
    producto            VARCHAR(10)   NOT NULL REFERENCES catalogo_productos,
    linea               VARCHAR(4)    NOT NULL,
    defecto             VARCHAR(30)   NOT NULL,
    piezas_afectadas    INTEGER       NOT NULL,
    costo_seleccion_mxn NUMERIC(12,2) NOT NULL,
    costo_flete_mxn     NUMERIC(12,2) NOT NULL,
    penalizacion_mxn    NUMERIC(12,2) NOT NULL,
    costo_total_mxn     NUMERIC(12,2) NOT NULL
);

CREATE TABLE mantenimientos (
    fecha            DATE         NOT NULL,
    linea            VARCHAR(4)   NOT NULL,
    turno            VARCHAR(12)  NOT NULL,
    horas_acumuladas NUMERIC(6,1) NOT NULL
);

CREATE TABLE altas_operadores (
    fecha DATE        NOT NULL,
    linea VARCHAR(4)  NOT NULL,
    turno VARCHAR(12) NOT NULL
);

CREATE INDEX ON produccion_turnos (linea, fecha);
