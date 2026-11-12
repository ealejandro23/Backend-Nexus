"""
=============================================================================
TESTS - TRATAMIENTO DE DATOS
=============================================================================
Verifica las reglas de limpieza e integración con datos sintéticos, para que
el pipeline pueda ejecutarse sin depender de archivos locales ni de rutas de
Windows.

Autor: Equipo 2 - ITY1102 Arquitectura de Sistemas IA
Fecha: 2026
=============================================================================
"""

import os
import sys

import pandas as pd
import pytest

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from preparar import (  # noqa: E402
    crear_variables_modelo,
    limpiar_clickstream,
    limpiar_productos,
    limpiar_transacciones,
    limpiar_usuarios,
    separar_train_test,
)


@pytest.fixture
def productos_crudos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sku": ["A", "A", "B", "C"],
            "nombre": ["Producto A", "Producto A", "Producto B", "Producto C"],
            "categoria": ["Audio", "AUDIO", "Video", "Audio"],
            "marca": ["Marca1", "Marca1", "Marca2", "Marca1"],
            "precio_lista": ["$19.929", "$19.929", "$5.000", "$1.000"],
            "costo": [10000.0, 10000.0, None, 500.0],
            "stock": [-5, 3, 10, 2],
            "activo": ["Si", "true", "0", "1"],
            "fecha_alta": ["2024-01-01"] * 4,
        }
    )


@pytest.fixture
def transacciones_crudas() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pedido_id": ["P1", "P2", "P3", "P4"],
            "linea": [1, 1, 1, 1],
            "usuario_id": ["U1", "U1", "U2", "invitado"],
            "sku": ["A", "B", "A", "C"],
            "fecha": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "cantidad": [1, -1, 2, 1],
            "precio_unitario": ["10000", "5000", "10000", "1000"],
            "descuento": [None, 500, 0, 0],
            "total": [10000, -500, 20000, 1000],
            "canal": ["web"] * 4,
            "estado": ["pagado", "pagado", "completado", "cancelado"],
        }
    )


@pytest.fixture
def usuarios_crudos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "usuario_id": ["U1", "U2", "U2", "U3"],
            "fecha_registro": ["2024-01-01"] * 4,
            "region": ["Metropolitana", "VALPARAISO", "Valparaiso", "Biobio"],
            "comuna": ["Santiago", "Viña del Mar", "Viña del Mar", "Concepción"],
            "canal_captacion": ["web"] * 4,
            "email_valido": ["true", "0", "1", None],
            "acepta_marketing": [1, None, 0, 1],
            "edad": [30, -5, 25, 999],
        }
    )


@pytest.fixture
def clickstream_crudo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "usuario_id": ["U1", "U1", "U2", None],
            "sku": ["A", "A", "B", "C"],
            "timestamp": [
                "2024-01-01 10:00:00",
                "2024-01-01 10:00:00",
                "2024-01-02T11:00:00",
                "fecha-invalida",
            ],
            "tipo_evento": ["Vista", "Vista", "CLIC", "vista"],
        }
    )


def test_productos_sin_duplicados(productos_crudos: pd.DataFrame) -> None:
    df_limpio = limpiar_productos(productos_crudos)
    assert df_limpio["sku"].duplicated().sum() == 0


def test_productos_categorias_normalizadas(productos_crudos: pd.DataFrame) -> None:
    df_limpio = limpiar_productos(productos_crudos)
    assert all(df_limpio["categoria"] == df_limpio["categoria"].str.lower())
    assert df_limpio["categoria"].isnull().sum() == 0


def test_productos_stock_no_negativo(productos_crudos: pd.DataFrame) -> None:
    df_limpio = limpiar_productos(productos_crudos)
    assert (df_limpio["stock"] >= 0).all()


def test_productos_precio_numerico(productos_crudos: pd.DataFrame) -> None:
    df_limpio = limpiar_productos(productos_crudos)
    assert pd.api.types.is_numeric_dtype(df_limpio["precio_lista"])
    assert (df_limpio["precio_lista"] > 0).all()


def test_transacciones_sin_nulos_descuento(
    transacciones_crudas: pd.DataFrame,
) -> None:
    df_limpio = limpiar_transacciones(transacciones_crudas)
    assert df_limpio["descuento"].isnull().sum() == 0


def test_transacciones_cantidad_positiva(
    transacciones_crudas: pd.DataFrame,
) -> None:
    df_limpio = limpiar_transacciones(transacciones_crudas)
    assert (df_limpio["cantidad"] >= 0).all()
    assert "es_devolucion" in df_limpio.columns


def test_transacciones_solo_estados_validos(
    transacciones_crudas: pd.DataFrame,
) -> None:
    df_limpio = limpiar_transacciones(transacciones_crudas)
    assert set(df_limpio["estado"]).issubset({"pagado", "completado", "entregado"})


def test_usuarios_edad_valida(usuarios_crudos: pd.DataFrame) -> None:
    df_limpio = limpiar_usuarios(usuarios_crudos)
    assert ((df_limpio["edad"] >= 0) & (df_limpio["edad"] <= 120)).all()


def test_usuarios_sin_duplicados(usuarios_crudos: pd.DataFrame) -> None:
    df_limpio = limpiar_usuarios(usuarios_crudos)
    assert df_limpio["usuario_id"].duplicated().sum() == 0


def test_clickstream_sin_duplicados(clickstream_crudo: pd.DataFrame) -> None:
    df_limpio = limpiar_clickstream(clickstream_crudo)
    assert df_limpio.duplicated().sum() == 0
    assert "es_visitante" in df_limpio.columns


def test_variables_modelo_columnas() -> None:
    transacciones = pd.DataFrame(
        {
            "usuario_id": ["U1", "U1", "U2", "U2"],
            "sku": ["NX-1", "NX-2", "NX-1", "NX-2"],
            "pedido_id": ["P1", "P2", "P3", "P4"],
            "total": [100000, 50000, 75000, 25000],
            "fecha": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        }
    )
    clickstream = pd.DataFrame(
        {
            "usuario_id": ["U1", "U1", "U2", "U2"],
            "sku": ["NX-1", "NX-2", "NX-1", "NX-2"],
            "tipo_evento": ["vista", "clic", "vista", "clic"],
        }
    )
    productos = pd.DataFrame(
        {"sku": ["NX-1", "NX-2"], "categoria": ["notebooks", "monitores"]}
    )
    usuarios = pd.DataFrame(
        {
            "usuario_id": ["U1", "U2"],
            "edad": [30, 25],
            "acepta_marketing": [1, 0],
        }
    )

    variables = crear_variables_modelo(
        transacciones, clickstream, productos, usuarios
    )

    columnas_esperadas = [
        "num_compras_categoria",
        "num_vistas_categoria",
        "num_clics_categoria",
        "total_gastado_categoria",
        "dias_ultima_compra",
        "frecuencia_compra",
        "ticket_promedio",
        "edad",
        "acepta_marketing",
        "propension_compra",
    ]
    for col in columnas_esperadas:
        assert col in variables.columns, f"Falta la columna: {col}"


def test_separacion_train_test() -> None:
    variables = pd.DataFrame(
        {
            "num_compras_categoria": range(1, 11),
            "num_vistas_categoria": range(10, 110, 10),
            "num_clics_categoria": range(5, 55, 5),
            "total_gastado_categoria": range(1000, 11000, 1000),
            "dias_ultima_compra": range(10, 110, 10),
            "frecuencia_compra": range(1, 11),
            "ticket_promedio": range(1000, 11000, 1000),
            "edad": range(25, 75, 5),
            "acepta_marketing": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
            "propension_compra": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        }
    )

    X_train, X_test, y_train, y_test, feature_cols = separar_train_test(variables)

    assert len(X_train) == 8
    assert len(X_test) == 2
    assert len(feature_cols) == 9
    assert len(y_train) == 8
    assert len(y_test) == 2
