-- =============================================================================
-- INICIALIZACIÓN DE BASE DE DATOS - NEXO RECOMMENDER SYSTEM
-- =============================================================================
-- Este script crea las tablas necesarias para el sistema de recomendación.
-- Se ejecuta automáticamente al levantar el contenedor de PostgreSQL.
-- =============================================================================

-- Tabla de productos
CREATE TABLE IF NOT EXISTS productos (
    sku VARCHAR(50) PRIMARY KEY,
    nombre VARCHAR(200),
    categoria VARCHAR(100) NOT NULL,
    marca VARCHAR(100),
    precio_lista FLOAT,
    costo FLOAT,
    stock INTEGER DEFAULT 0,
    activo BOOLEAN DEFAULT TRUE,
    fecha_alta DATE
);

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id VARCHAR(50) PRIMARY KEY,
    fecha_registro DATE,
    region VARCHAR(100),
    comuna VARCHAR(100),
    canal_captacion VARCHAR(50),
    email_valido BOOLEAN DEFAULT FALSE,
    acepta_marketing INTEGER DEFAULT 0,
    edad INTEGER
);

-- Tabla de transacciones
CREATE TABLE IF NOT EXISTS transacciones (
    id SERIAL PRIMARY KEY,
    pedido_id VARCHAR(50),
    linea INTEGER,
    usuario_id VARCHAR(50),
    sku VARCHAR(50),
    fecha TIMESTAMP,
    cantidad INTEGER,
    precio_unitario FLOAT,
    descuento FLOAT,
    total FLOAT,
    canal VARCHAR(50),
    estado VARCHAR(50)
);

-- Tabla de predicciones
CREATE TABLE IF NOT EXISTS predicciones (
    id SERIAL PRIMARY KEY,
    usuario_id VARCHAR(50) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    prediccion FLOAT NOT NULL,
    propension VARCHAR(20) NOT NULL,
    version_modelo VARCHAR(20) NOT NULL,
    tiempo_ms FLOAT NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_transacciones_usuario ON transacciones(usuario_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_sku ON transacciones(sku);
CREATE INDEX IF NOT EXISTS idx_predicciones_usuario ON predicciones(usuario_id);
CREATE INDEX IF NOT EXISTS idx_predicciones_fecha ON predicciones(fecha);
