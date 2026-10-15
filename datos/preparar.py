"""
=============================================================================
TRATAMIENTO DE DATOS - NEXO RECOMMENDER SYSTEM
=============================================================================
Este script realiza el tratamiento completo de los datos crudos del caso
Nexus Retail, aplicando reglas de limpieza, integración y transformación
para generar las variables de entrada del modelo de recomendación.

Autor: Equipo 2 - ITY1102 Arquitectura de Sistemas IA
Fecha: 2026
=============================================================================
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
import joblib

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
DATA_DIR = r"C:\Users\esteb\Downloads\caso-nexus\caso\datos"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "datos_tratados")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
# 1. PERFILADO DE DATOS
# =============================================================================
def perfilado(df, nombre):
    """Genera un reporte completo del perfil de datos."""
    reporte = {
        "archivo": nombre,
        "filas": len(df),
        "columnas": len(df.columns),
        "tipos": df.dtypes.astype(str).to_dict(),
        "nulos": df.isnull().sum().to_dict(),
        "duplicados": df.duplicated().sum(),
        "unicos": {col: df[col].nunique() for col in df.columns}
    }
    return reporte

def imprimir_perfilado(reporte, etapa="ANTES"):
    print(f"\n{'='*60}")
    print(f"PERFILADO {etapa}: {reporte['archivo']}")
    print(f"{'='*60}")
    print(f"Filas: {reporte['filas']}, Columnas: {reporte['columnas']}")
    print(f"Duplicados: {reporte['duplicados']}")
    print(f"Nulos por columna: {reporte['nulos']}")
    print(f"Valores únicos: {reporte['unicos']}")

# =============================================================================
# 2. LIMPIEZA DE DATOS
# =============================================================================
def limpiar_productos(df):
    """
    Limpieza de productos.csv
    
    Problemas identificados:
    - precio_lista como string con "$" (ej: "$19.929")
    - categoria con mayúsculas/minúsculas inconsistentes
    - activo con valores inconsistentes (0, "Si", "true")
    - stock con valores negativos
    - costo con nulos
    - SKUs duplicados
    """
    print("\n--- Limpieza de productos ---")
    filas_antes = len(df)
    
    # 2.1 Normalizar categoría a minúsculas
    df['categoria'] = df['categoria'].str.lower().str.strip()
    print(f"  [REGLA] Categorías normalizadas a minúsculas")
    
    # 2.2 Limpiar precio_lista: quitar "$" y convertir a float
    df['precio_lista'] = df['precio_lista'].astype(str).str.replace('$', '', regex=False)
    df['precio_lista'] = df['precio_lista'].str.replace('.', '', regex=False)
    df['precio_lista'] = pd.to_numeric(df['precio_lista'], errors='coerce')
    print(f"  [REGLA] precio_lista: eliminado '$' y convertido a numérico")
    
    # 2.3 Normalizar activo a booleano
    df['activo'] = df['activo'].astype(str).str.lower().map({
        'si': True, 'true': True, '1': True, '0': False, 'no': False
    }).fillna(False)
    print(f"  [REGLA] activo: normalizado a booleano (Si/true/1 -> True)")
    
    # 2.4 Corregir stock negativo (error de inventario)
    # Primero convertir a numérico (puede venir como string)
    df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0).astype(int)
    stock_negativos = (df['stock'] < 0).sum()
    df.loc[df['stock'] < 0, 'stock'] = 0
    print(f"  [REGLA] stock: {stock_negativos} valores negativos corregidos a 0")
    
    # 2.5 Manejar nulos en costo (imputar con mediana)
    nulos_costo = df['costo'].isnull().sum()
    df['costo'] = df['costo'].fillna(df['costo'].median())
    print(f"  [REGLA] costo: {nulos_costo} nulos imputados con mediana")
    
    # 2.6 Eliminar SKUs duplicados (mantener el más reciente)
    duplicados = df['sku'].duplicated().sum()
    df = df.drop_duplicates(subset=['sku'], keep='last')
    print(f"  [REGLA] sku: {duplicados} duplicados eliminados (keep='last')")
    
    # 2.7 Marcar productos inactivos
    df['activo'] = df['activo'].astype(bool)
    
    filas_despues = len(df)
    print(f"  Resultado: {filas_antes} -> {filas_despues} filas")
    
    return df

def limpiar_transacciones(df):
    """
    Limpieza de transacciones.csv
    
    Problemas identificados:
    - precio_unitario como string
    - descuento con nulos
    - cantidad negativa
    - total negativo
    - usuario_id "invitado"
    """
    print("\n--- Limpieza de transacciones ---")
    filas_antes = len(df)
    
    # 3.1 Convertir precio_unitario a numérico
    df['precio_unitario'] = pd.to_numeric(df['precio_unitario'], errors='coerce')
    print(f"  [REGLA] precio_unitario: convertido a numérico")
    
    # 3.2 Imputar descuento nulo con 0
    nulos_descuento = df['descuento'].isnull().sum()
    df['descuento'] = df['descuento'].fillna(0)
    print(f"  [REGLA] descuento: {nulos_descuento} nulos imputados con 0")
    
    # 3.3 Corregir cantidades negativas (devoluciones -> marcar)
    cant_negativas = (df['cantidad'] < 0).sum()
    df['es_devolucion'] = df['cantidad'] < 0
    df['cantidad'] = df['cantidad'].abs()
    print(f"  [REGLA] cantidad: {cant_negativas} negativas marcadas como devolución")
    
    # 3.4 Calcular total correcto
    df['total'] = df['cantidad'] * df['precio_unitario'] - df['descuento']
    print(f"  [REGLA] total: recalculado como cantidad * precio - descuento")
    
    # 3.5 Marcar usuarios invitados
    df['es_invitado'] = df['usuario_id'] == 'invitado'
    print(f"  [REGLA] usuario_id: 'invitado' marcado como es_invitado")
    
    # 3.6 Filtrar solo transacciones válidas (pagado)
    estados_validos = ['pagado', 'completado', 'entregado']
    df = df[df['estado'].isin(estados_validos)]
    print(f"  [REGLA] estado: filtrados solo estados válidos {estados_validos}")
    
    filas_despues = len(df)
    print(f"  Resultado: {filas_antes} -> {filas_despues} filas")
    
    return df

def limpiar_usuarios(df):
    """
    Limpieza de usuarios.csv
    
    Problemas identificados:
    - edad con valores fuera de rango (-38, 999)
    - regiones con nombres inconsistentes
    - comunas que no corresponden a la región
    - email_valido con valores NaN
    - acepta_marketing con NaN
    """
    print("\n--- Limpieza de usuarios ---")
    filas_antes = len(df)
    
    # 4.1 Corregir edades fuera de rango (0 < edad < 120)
    edades_invalidas = ((df['edad'] < 0) | (df['edad'] > 120)).sum()
    df.loc[(df['edad'] < 0) | (df['edad'] > 120), 'edad'] = np.nan
    df['edad'] = df['edad'].fillna(df['edad'].median())
    print(f"  [REGLA] edad: {edades_invalidas} valores fuera de rango corregidos")
    
    # 4.2 Normalizar regiones
    df['region'] = df['region'].str.lower().str.strip()
    print(f"  [REGLA] region: normalizada a minúsculas")
    
    # 4.3 Normalizar email_valido
    df['email_valido'] = df['email_valido'].astype(str).str.lower().map({
        'true': True, 'false': False, '1': True, '0': False
    }).fillna(False)
    print(f"  [REGLA] email_valido: normalizado a booleano")
    
    # 4.4 Normalizar acepta_marketing
    df['acepta_marketing'] = df['acepta_marketing'].fillna(0).astype(int)
    print(f"  [REGLA] acepta_marketing: nulos imputados con 0")
    
    # 4.5 Eliminar duplicados por usuario_id
    duplicados = df['usuario_id'].duplicated().sum()
    df = df.drop_duplicates(subset=['usuario_id'], keep='first')
    print(f"  [REGLA] usuario_id: {duplicados} duplicados eliminados")
    
    filas_despues = len(df)
    print(f"  Resultado: {filas_antes} -> {filas_despues} filas")
    
    return df

def limpiar_clickstream(df):
    """
    Limpieza de clickstream.csv
    
    Problemas identificados:
    - usuario_id con NaN (visitantes no identificados)
    - timestamps con formatos diferentes
    """
    print("\n--- Limpieza de clickstream ---")
    filas_antes = len(df)
    
    # 5.1 Manejar timestamps con formatos diferentes
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', format='mixed')
    nulos_timestamp = df['timestamp'].isnull().sum()
    df = df.dropna(subset=['timestamp'])
    print(f"  [REGLA] timestamp: {nulos_timestamp} con formato inválido eliminados")
    
    # 5.2 Marcar visitantes (sin usuario_id)
    df['es_visitante'] = df['usuario_id'].isnull()
    print(f"  [REGLA] usuario_id: {df['es_visitante'].sum()} visitantes marcados")
    
    # 5.3 Normalizar tipo_evento
    df['tipo_evento'] = df['tipo_evento'].str.lower().str.strip()
    print(f"  [REGLA] tipo_evento: normalizado a minúsculas")
    
    # 5.4 Eliminar duplicados
    duplicados = df.duplicated().sum()
    df = df.drop_duplicates()
    print(f"  [REGLA] duplicados: {duplicados} eliminados")
    
    filas_despues = len(df)
    print(f"  Resultado: {filas_antes} -> {filas_despues} filas")
    
    return df

# =============================================================================
# 3. INTEGRACIÓN DE DATOS
# =============================================================================
def integrar_datos(productos, transacciones, usuarios, clickstream):
    """
    Integra los cuatro archivos por sus claves.
    
    Reglas:
    - Transacciones se unen con productos por SKU
    - Transacciones se unen con usuarios por usuario_id
    - Clickstream se une con productos por SKU
    - Clickstream se une con usuarios por usuario_id
    """
    print("\n--- Integración de datos ---")
    
    # 6.1 Transacciones + Productos
    trans_prod = transacciones.merge(
        productos[['sku', 'categoria', 'marca', 'precio_lista', 'stock', 'activo']],
        on='sku',
        how='left'
    )
    sin_producto = trans_prod['categoria'].isnull().sum()
    print(f"  [INTEGRACIÓN] Transacciones sin producto: {sin_producto}")
    
    # 6.2 Transacciones + Usuarios
    trans_prod_usu = trans_prod.merge(
        usuarios[['usuario_id', 'region', 'acepta_marketing', 'edad']],
        on='usuario_id',
        how='left'
    )
    sin_usuario = trans_prod_usu['region'].isnull().sum()
    print(f"  [INTEGRACIÓN] Transacciones sin usuario: {sin_usuario}")
    
    # 6.3 Clickstream + Productos
    click_prod = clickstream.merge(
        productos[['sku', 'categoria', 'marca']],
        on='sku',
        how='left'
    )
    sin_producto_click = click_prod['categoria'].isnull().sum()
    print(f"  [INTEGRACIÓN] Clickstream sin producto: {sin_producto_click}")
    
    return trans_prod_usu, click_prod

# =============================================================================
# 4. VARIABLES DE ENTRADA DEL MODELO
# =============================================================================
def crear_variables_modelo(transacciones, clickstream, productos, usuarios):
    """
    Crea las variables de entrada para el modelo de recomendación.
    
    Objetivo: Predecir la propensión de compra por usuario y categoría.
    
    Variables:
    - usuario_id: identificador del usuario
    - categoria: categoría del producto
    - num_compras_categoria: número de compras previas en esa categoría
    - num_vistas_categoria: número de vistas previas en esa categoría
    - num_clics_categoria: número de clics previos en esa categoría
    - total_gastado_categoria: total gastado en esa categoría
    - dias_ultima_compra: días desde la última compra en esa categoría
    - frecuencia_compra: frecuencia de compra del usuario
    - ticket_promedio: ticket promedio del usuario
    - edad: edad del usuario
    - acepta_marketing: si acepta marketing
    - propension_compra: variable objetivo (1 si compró en esa categoría)
    """
    print("\n--- Creación de variables del modelo ---")
    
    # 7.0 Integrar transacciones con productos para obtener la categoría
    transacciones = transacciones.merge(
        productos[['sku', 'categoria']],
        on='sku',
        how='left'
    )
    # Eliminar transacciones sin categoría (producto no encontrado)
    transacciones = transacciones.dropna(subset=['categoria'])
    print(f"  [INTEGRACIÓN] Transacciones con categoría: {len(transacciones)}")
    
    # 7.1 Agregaciones por usuario y categoría (transacciones)
    agg_trans = transacciones.groupby(['usuario_id', 'categoria']).agg(
        num_compras_categoria=('pedido_id', 'count'),
        total_gastado_categoria=('total', 'sum'),
        fecha_ultima_compra=('fecha', 'max')
    ).reset_index()
    
    # 7.2 Agregaciones por usuario y categoría (clickstream)
    # Primero integrar clickstream con productos para obtener la categoría
    clickstream = clickstream.merge(
        productos[['sku', 'categoria']],
        on='sku',
        how='left'
    )
    clickstream = clickstream.dropna(subset=['categoria'])
    
    agg_click = clickstream.groupby(['usuario_id', 'categoria']).agg(
        num_vistas_categoria=('tipo_evento', lambda x: (x == 'vista').sum()),
        num_clics_categoria=('tipo_evento', lambda x: (x == 'clic').sum())
    ).reset_index()
    
    # 7.3 Unir agregaciones
    variables = agg_trans.merge(agg_click, on=['usuario_id', 'categoria'], how='outer')
    variables = variables.fillna(0)
    
    # 7.4 Calcular días desde última compra
    # Manejar formatos de fecha mixtos de forma robusta
    def parse_fecha(x):
        try:
            # Intentar parsear y remover timezone si existe
            dt = pd.to_datetime(x, dayfirst=True, utc=True)
            return dt.tz_localize(None) if dt.tz else dt
        except:
            return pd.NaT
    
    variables['fecha_ultima_compra'] = variables['fecha_ultima_compra'].apply(parse_fecha)
    ahora = pd.Timestamp.now(tz=None)
    variables['dias_ultima_compra'] = (ahora - variables['fecha_ultima_compra']).dt.days
    variables['dias_ultima_compra'] = variables['dias_ultima_compra'].fillna(999).astype(int)
    
    # 7.5 Variables globales del usuario
    user_stats = transacciones.groupby('usuario_id').agg(
        frecuencia_compra=('pedido_id', 'count'),
        ticket_promedio=('total', 'mean')
    ).reset_index()
    
    variables = variables.merge(user_stats, on='usuario_id', how='left')
    variables = variables.fillna(0)
    
    # 7.6 Unir con datos de usuarios
    variables = variables.merge(
        usuarios[['usuario_id', 'edad', 'acepta_marketing']],
        on='usuario_id',
        how='left'
    )
    # Rellenar nulos de usuarios no encontrados con valores por defecto
    variables['edad'] = variables['edad'].fillna(variables['edad'].median())
    variables['acepta_marketing'] = variables['acepta_marketing'].fillna(0)
    
    # 7.7 Variable objetivo: propensión de compra
    # 1 si el usuario compró en esa categoría, 0 si solo miró
    variables['propension_compra'] = (variables['num_compras_categoria'] > 0).astype(int)
    
    print(f"  Variables creadas: {list(variables.columns)}")
    print(f"  Total registros: {len(variables)}")
    print(f"  Distribución objetivo: {variables['propension_compra'].value_counts().to_dict()}")
    
    return variables

# =============================================================================
# 5. SEPARACIÓN ENTRENAMIENTO/PRUEBA
# =============================================================================
def separar_train_test(variables):
    """
    Separa los datos en conjuntos de entrenamiento y prueba.
    Estratificado por la variable objetivo para mantener la distribución.
    """
    print("\n--- Separación train/test ---")
    
    feature_cols = [
        'num_compras_categoria', 'num_vistas_categoria', 'num_clics_categoria',
        'total_gastado_categoria', 'dias_ultima_compra', 'frecuencia_compra',
        'ticket_promedio', 'edad', 'acepta_marketing'
    ]
    
    X = variables[feature_cols]
    y = variables['propension_compra']
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"  Train: {len(X_train)} registros")
    print(f"  Test: {len(X_test)} registros")
    print(f"  Distribución train: {y_train.value_counts().to_dict()}")
    print(f"  Distribución test: {y_test.value_counts().to_dict()}")
    
    return X_train, X_test, y_train, y_test, feature_cols

# =============================================================================
# 6. GUARDAR RESULTADOS
# =============================================================================
def guardar_resultados(productos, transacciones, usuarios, clickstream, 
                       variables, X_train, X_test, y_train, y_test, feature_cols):
    """Guarda todos los datos tratados y artefactos."""
    print("\n--- Guardando resultados ---")
    
    # Guardar datos tratados
    productos.to_csv(os.path.join(OUTPUT_DIR, "productos_limpios.csv"), index=False)
    transacciones.to_csv(os.path.join(OUTPUT_DIR, "transacciones_limpias.csv"), index=False)
    usuarios.to_csv(os.path.join(OUTPUT_DIR, "usuarios_limpios.csv"), index=False)
    clickstream.to_csv(os.path.join(OUTPUT_DIR, "clickstream_limpio.csv"), index=False)
    variables.to_csv(os.path.join(OUTPUT_DIR, "variables_modelo.csv"), index=False)
    
    # Guardar conjuntos de train/test
    X_train.to_csv(os.path.join(OUTPUT_DIR, "X_train.csv"), index=False)
    X_test.to_csv(os.path.join(OUTPUT_DIR, "X_test.csv"), index=False)
    y_train.to_csv(os.path.join(OUTPUT_DIR, "y_train.csv"), index=False)
    y_test.to_csv(os.path.join(OUTPUT_DIR, "y_test.csv"), index=False)
    
    # Guardar feature_cols
    with open(os.path.join(OUTPUT_DIR, "feature_cols.json"), "w") as f:
        json.dump(feature_cols, f)
    
    print(f"  Datos guardados en: {OUTPUT_DIR}")

# =============================================================================
# PIPELINE DE DATOS: LIMPIEZA, INGESTA Y TRANSFORMACIÓN
# =============================================================================
def pipeline_datos():
    """
    Pipeline completo de tratamiento de datos.
    
    Etapas:
    1. Perfilado - Análisis inicial de los datos
    2. Limpieza - Corrección de problemas encontrados
    3. Ingesta - Carga de datos a la base de datos
    4. Transformación - Creación de variables del modelo
    
    Returns:
        Diccionario con todos los datos tratados
    """
    print("="*60)
    print("PIPELINE DE DATOS - NEXO RECOMMENDER")
    print("="*60)
    
    # =========================================================================
    # ETAPA 1: PERFILADO
    # =========================================================================
    print("\n" + "="*60)
    print("ETAPA 1: PERFILADO DE DATOS")
    print("="*60)
    
    # Cargar datos crudos
    print("\nCargando datos crudos...")
    productos = pd.read_csv(os.path.join(DATA_DIR, "productos.csv"))
    transacciones = pd.read_csv(os.path.join(DATA_DIR, "transacciones.csv"))
    usuarios = pd.read_csv(os.path.join(DATA_DIR, "usuarios.csv"))
    clickstream = pd.read_csv(os.path.join(DATA_DIR, "clickstream.csv"))
    
    # Perfilado ANTES
    print("\n--- Perfilado ANTES del tratamiento ---")
    for df, nombre in [(productos, "productos"), (transacciones, "transacciones"),
                       (usuarios, "usuarios"), (clickstream, "clickstream")]:
        reporte = perfilado(df, nombre)
        imprimir_perfilado(reporte, "ANTES")
    
    # =========================================================================
    # ETAPA 2: LIMPIEZA
    # =========================================================================
    print("\n" + "="*60)
    print("ETAPA 2: LIMPIEZA DE DATOS")
    print("="*60)
    
    productos = limpiar_productos(productos)
    transacciones = limpiar_transacciones(transacciones)
    usuarios = limpiar_usuarios(usuarios)
    clickstream = limpiar_clickstream(clickstream)
    
    # Perfilado DESPUÉS
    print("\n--- Perfilado DESPUÉS del tratamiento ---")
    for df, nombre in [(productos, "productos"), (transacciones, "transacciones"),
                       (usuarios, "usuarios"), (clickstream, "clickstream")]:
        reporte = perfilado(df, nombre)
        imprimir_perfilado(reporte, "DESPUÉS")
    
    # =========================================================================
    # ETAPA 3: INTEGRACIÓN
    # =========================================================================
    print("\n" + "="*60)
    print("ETAPA 3: INTEGRACIÓN DE DATOS")
    print("="*60)
    
    transacciones_int, clickstream_int = integrar_datos(
        productos, transacciones, usuarios, clickstream
    )
    
    # =========================================================================
    # ETAPA 4: TRANSFORMACIÓN
    # =========================================================================
    print("\n" + "="*60)
    print("ETAPA 4: TRANSFORMACIÓN (VARIABLES DEL MODELO)")
    print("="*60)
    
    variables = crear_variables_modelo(transacciones, clickstream, productos, usuarios)
    
    # Separación train/test
    X_train, X_test, y_train, y_test, feature_cols = separar_train_test(variables)
    
    # =========================================================================
    # ETAPA 5: SALIDAS
    # =========================================================================
    print("\n" + "="*60)
    print("ETAPA 5: GUARDAR SALIDAS")
    print("="*60)
    
    guardar_resultados(productos, transacciones, usuarios, clickstream,
                       variables, X_train, X_test, y_train, y_test, feature_cols)
    
    print("\n" + "="*60)
    print("PIPELINE COMPLETADO EXITOSAMENTE")
    print("="*60)
    
    return {
        "productos": productos,
        "transacciones": transacciones,
        "usuarios": usuarios,
        "clickstream": clickstream,
        "variables": variables,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "feature_cols": feature_cols
    }

# =============================================================================
# COMPATIBILIDAD CON CÓDIGO ANTERIOR
# =============================================================================
def main():
    """Mantiene compatibilidad con llamadas existentes."""
    return pipeline_datos()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
