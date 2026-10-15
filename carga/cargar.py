"""
=============================================================================
SERVICIO DE CARGA DE DATOS - NEXO RECOMMENDER SYSTEM
=============================================================================
Carga los datos tratados en la base de datos PostgreSQL.
Se ejecuta una sola vez al levantar el sistema.

Autor: Equipo 2 - ITY1102 Arquitectura de Sistemas IA
Fecha: 2026
=============================================================================
"""

import pandas as pd
import psycopg2
import os
import time
import logging

# =============================================================================
# CONFIGURACIÓN DE LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nexo")
DB_USER = os.getenv("DB_USER", "nexo")
DB_PASSWORD = os.getenv("DB_PASSWORD", "nexo123")

DATOS_DIR = os.path.join(os.path.dirname(__file__), "..", "datos", "datos_tratados")

# =============================================================================
# FUNCIONES
# =============================================================================
def get_db_connection():
    """Establece conexión con PostgreSQL."""
    max_retries = 30
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            logger.info("Conexión a PostgreSQL establecida")
            return conn
        except Exception as e:
            logger.warning(f"Intento {attempt+1}/{max_retries}: {e}")
            time.sleep(retry_delay)
    
    raise Exception("No se pudo conectar a PostgreSQL después de varios intentos")

def crear_tablas(conn):
    """Crea las tablas necesarias si no existen."""
    cur = conn.cursor()
    
    # Tabla de productos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            sku VARCHAR(50) PRIMARY KEY,
            nombre VARCHAR(200),
            categoria VARCHAR(100),
            marca VARCHAR(100),
            precio_lista FLOAT,
            costo FLOAT,
            stock INTEGER,
            activo BOOLEAN,
            fecha_alta DATE
        )
    """)
    
    # Tabla de usuarios
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario_id VARCHAR(50) PRIMARY KEY,
            fecha_registro DATE,
            region VARCHAR(100),
            comuna VARCHAR(100),
            canal_captacion VARCHAR(50),
            email_valido BOOLEAN,
            acepta_marketing INTEGER,
            edad INTEGER
        )
    """)
    
    # Tabla de transacciones
    cur.execute("""
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
        )
    """)
    
    # Tabla de predicciones
    cur.execute("""
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
        )
    """)
    
    conn.commit()
    cur.close()
    logger.info("Tablas creadas/verificadas correctamente")

def cargar_productos(conn):
    """Carga los productos desde el CSV tratado."""
    filepath = os.path.join(DATOS_DIR, "productos_limpios.csv")
    if not os.path.exists(filepath):
        logger.warning(f"Archivo no encontrado: {filepath}")
        return 0
    
    df = pd.read_csv(filepath)
    cur = conn.cursor()
    
    # Limpiar tabla
    cur.execute("TRUNCATE TABLE productos")
    
    # Insertar datos
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO productos (sku, nombre, categoria, marca, precio_lista, costo, stock, activo, fecha_alta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sku) DO NOTHING
        """, (
            row['sku'], row['nombre'], row['categoria'], row['marca'],
            float(row['precio_lista']), float(row['costo']), int(row['stock']),
            bool(row['activo']), row['fecha_alta']
        ))
    
    conn.commit()
    cur.close()
    logger.info(f"Productos cargados: {len(df)} registros")
    return len(df)

def cargar_usuarios(conn):
    """Carga los usuarios desde el CSV tratado."""
    filepath = os.path.join(DATOS_DIR, "usuarios_limpios.csv")
    if not os.path.exists(filepath):
        logger.warning(f"Archivo no encontrado: {filepath}")
        return 0
    
    df = pd.read_csv(filepath)
    cur = conn.cursor()
    
    # Limpiar tabla
    cur.execute("TRUNCATE TABLE usuarios")
    
    # Insertar datos
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO usuarios (usuario_id, fecha_registro, region, comuna, canal_captacion, email_valido, acepta_marketing, edad)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (usuario_id) DO NOTHING
        """, (
            row['usuario_id'], row['fecha_registro'], row['region'],
            row['comuna'], row['canal_captacion'], bool(row['email_valido']),
            int(row['acepta_marketing']), int(row['edad'])
        ))
    
    conn.commit()
    cur.close()
    logger.info(f"Usuarios cargados: {len(df)} registros")
    return len(df)

def cargar_transacciones(conn):
    """Carga las transacciones desde el CSV tratado."""
    filepath = os.path.join(DATOS_DIR, "transacciones_limpias.csv")
    if not os.path.exists(filepath):
        logger.warning(f"Archivo no encontrado: {filepath}")
        return 0
    
    df = pd.read_csv(filepath)
    cur = conn.cursor()
    
    # Limpiar tabla
    cur.execute("TRUNCATE TABLE transacciones")
    
    # Insertar datos
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO transacciones (pedido_id, linea, usuario_id, sku, fecha, cantidad, precio_unitario, descuento, total, canal, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row['pedido_id'], int(row['linea']), row['usuario_id'],
            row['sku'], row['fecha'], int(row['cantidad']),
            float(row['precio_unitario']), float(row['descuento']),
            float(row['total']), row['canal'], row['estado']
        ))
    
    conn.commit()
    cur.close()
    logger.info(f"Transacciones cargadas: {len(df)} registros")
    return len(df)

def main():
    logger.info("="*60)
    logger.info("CARGA DE DATOS - NEXO RECOMMENDER")
    logger.info("="*60)
    
    # Conectar a la base de datos
    conn = get_db_connection()
    
    try:
        # Crear tablas
        crear_tablas(conn)
        
        # Cargar datos
        total_productos = cargar_productos(conn)
        total_usuarios = cargar_usuarios(conn)
        total_transacciones = cargar_transacciones(conn)
        
        logger.info("="*60)
        logger.info("CARGA COMPLETADA EXITOSAMENTE")
        logger.info(f"  Productos: {total_productos}")
        logger.info(f"  Usuarios: {total_usuarios}")
        logger.info(f"  Transacciones: {total_transacciones}")
        logger.info("="*60)
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
