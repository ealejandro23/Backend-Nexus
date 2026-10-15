"""
=============================================================================
TESTS - TRATAMIENTO DE DATOS
=============================================================================
Verifica que el tratamiento de datos genere resultados correctos.

Autor: Equipo 2 - ITY1102 Arquitectura de Sistemas IA
Fecha: 2026
=============================================================================
"""

import pytest
import pandas as pd
import os
import sys

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from preparar import (
    limpiar_productos, limpiar_transacciones, limpiar_usuarios,
    limpiar_clickstream, crear_variables_modelo, separar_train_test
)

def test_productos_sin_duplicados():
    """Verifica que los productos tratados no tengan duplicados."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\productos.csv")
    df_limpio = limpiar_productos(df)
    
    # No debe haber SKUs duplicados
    assert df_limpio['sku'].duplicated().sum() == 0

def test_productos_sin_nulos_categoria():
    """Verifica que los productos tratados no tengan nulos en categoría."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\productos.csv")
    df_limpio = limpiar_productos(df)
    
    # No debe haber nulos en categoría
    assert df_limpio['categoria'].isnull().sum() == 0

def test_productos_categorias_normalizadas():
    """Verifica que las categorías estén normalizadas a minúsculas."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\productos.csv")
    df_limpio = limpiar_productos(df)
    
    # Todas las categorías deben estar en minúsculas
    assert all(df_limpio['categoria'] == df_limpio['categoria'].str.lower())

def test_productos_stock_no_negativo():
    """Verifica que el stock no tenga valores negativos."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\productos.csv")
    df_limpio = limpiar_productos(df)
    
    # No debe haber stock negativo
    assert (df_limpio['stock'] >= 0).all()

def test_transacciones_sin_nulos_descuento():
    """Verifica que las transacciones tratadas no tengan nulos en descuento."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\transacciones.csv")
    df_limpio = limpiar_transacciones(df)
    
    # No debe haber nulos en descuento
    assert df_limpio['descuento'].isnull().sum() == 0

def test_transacciones_cantidad_positiva():
    """Verifica que la cantidad no tenga valores negativos."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\transacciones.csv")
    df_limpio = limpiar_transacciones(df)
    
    # No debe haber cantidad negativa
    assert (df_limpio['cantidad'] >= 0).all()

def test_usuarios_edad_valida():
    """Verifica que la edad esté en rango válido."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\usuarios.csv")
    df_limpio = limpiar_usuarios(df)
    
    # La edad debe estar entre 0 y 120
    assert ((df_limpio['edad'] >= 0) & (df_limpio['edad'] <= 120)).all()

def test_usuarios_sin_duplicados():
    """Verifica que los usuarios tratados no tengan duplicados."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\usuarios.csv")
    df_limpio = limpiar_usuarios(df)
    
    # No debe haber usuario_id duplicados
    assert df_limpio['usuario_id'].duplicated().sum() == 0

def test_clickstream_sin_duplicados():
    """Verifica que el clickstream tratado no tenga duplicados."""
    df = pd.read_csv(r"C:\Users\esteb\Downloads\caso-nexus\caso\datos\clickstream.csv")
    df_limpio = limpiar_clickstream(df)
    
    # No debe haber duplicados
    assert df_limpio.duplicated().sum() == 0

def test_variables_modelo_columnas():
    """Verifica que las variables del modelo tengan las columnas correctas."""
    # Crear datos de prueba con la estructura correcta
    transacciones = pd.DataFrame({
        'usuario_id': ['U1', 'U1', 'U2', 'U2'],
        'sku': ['NX-1', 'NX-2', 'NX-1', 'NX-2'],
        'pedido_id': ['P1', 'P2', 'P3', 'P4'],
        'total': [100000, 50000, 75000, 25000],
        'fecha': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']
    })
    
    clickstream = pd.DataFrame({
        'usuario_id': ['U1', 'U1', 'U2', 'U2'],
        'sku': ['NX-1', 'NX-2', 'NX-1', 'NX-2'],
        'tipo_evento': ['vista', 'clic', 'vista', 'clic']
    })
    
    productos = pd.DataFrame({
        'sku': ['NX-1', 'NX-2'],
        'categoria': ['notebooks', 'monitores']
    })
    
    usuarios = pd.DataFrame({
        'usuario_id': ['U1', 'U2'],
        'edad': [30, 25],
        'acepta_marketing': [1, 0]
    })
    
    variables = crear_variables_modelo(transacciones, clickstream, productos, usuarios)
    
    # Verificar que tiene las columnas esperadas
    columnas_esperadas = [
        'num_compras_categoria', 'num_vistas_categoria', 'num_clics_categoria',
        'total_gastado_categoria', 'dias_ultima_compra', 'frecuencia_compra',
        'ticket_promedio', 'edad', 'acepta_marketing', 'propension_compra'
    ]
    
    for col in columnas_esperadas:
        assert col in variables.columns, f"Falta la columna: {col}"

def test_separacion_train_test():
    """Verifica que la separación train/test sea correcta."""
    # Crear datos de prueba con suficientes muestras para estratificación
    variables = pd.DataFrame({
        'num_compras_categoria': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'num_vistas_categoria': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        'num_clics_categoria': [5, 10, 15, 20, 25, 30, 35, 40, 45, 50],
        'total_gastado_categoria': [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
        'dias_ultima_compra': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        'frecuencia_compra': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'ticket_promedio': [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
        'edad': [25, 30, 35, 40, 45, 50, 55, 60, 65, 70],
        'acepta_marketing': [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        'propension_compra': [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
    })
    
    X_train, X_test, y_train, y_test, feature_cols = separar_train_test(variables)
    
    # Verificar que la separación es 80/20
    assert len(X_train) == 8
    assert len(X_test) == 2
    
    # Verificar que las features son correctas
    assert len(feature_cols) == 9

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
