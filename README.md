# Nexo Recommender System - EP2

Sistema de recomendación de productos con arquitectura de microservicios para el caso Nexus Retail.

**Equipo:** 2  
**Curso:** ITY1102 - Arquitectura de Sistemas de Inteligencia Artificial  
**Evaluación:** Evaluación Parcial 2

---

## Tabla de Contenidos

1. [Descripción del Sistema](#descripción-del-sistema)
2. [Arquitectura](#arquitectura)
3. [Estructura del Proyecto](#estructura-del-proyecto)
4. [Requisitos](#requisitos)
5. [Instalación y Ejecución](#instalación-y-ejecución)
6. [Uso del Sistema](#uso-del-sistema)
7. [API](#api)
8. [Tests](#tests)
9. [Modelo de IA](#modelo-de-ia)
10. [Tratamiento de Datos](#tratamiento-de-datos)

---

## Descripción del Sistema

Nexo Recommender es un sistema de recomendación de productos que utiliza inteligencia artificial (red neuronal PyTorch) para predecir la propensión de compra de los usuarios en diferentes categorías de productos.

### Características principales

- **Predicción de propensión de compra**: Modelo de red neuronal entrenado con datos históricos
- **Arquitectura de microservicios**: Servicios independientes y escalables
- **Alta disponibilidad**: Réplicas con balanceo de carga
- **API REST**: Interfaz estándar para integración
- **Front web**: Interfaz de usuario intuitiva con Streamlit

---

## Arquitectura

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTE (Navegador)                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GATEWAY (Nginx)                                    │
│                           Puerto 8080                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  /              → Front (Streamlit)                                     │ │
│  │  /api/ia/*      → Microservicio de IA                                   │ │
│  │  /api/dominio/* → Microservicio de Dominio                              │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
          │                    │                      │
          ▼                    ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────┐
│   FRONT         │  │  MICROSERVICIO  │  │  MICROSERVICIO DE DOMINIO       │
│   (Streamlit)   │  │  DE IA          │  │  ┌─────────────┐ ┌────────────┐ │
│                 │  │  (PyTorch)      │  │  │ Réplica 1   │ │ Réplica 2  │ │
│                 │  │                 │  │  └─────────────┘ └────────────┘ │
└─────────────────┘  └─────────────────┘  └─────────────────────────────────┘
                              │                        │
                              ▼                        ▼
                    ┌─────────────────┐      ┌─────────────────┐
                    │  MODELO         │      │  BASE DE DATOS  │
                    │  ENTRENADO      │      │  (PostgreSQL)   │
                    │  (.pkl)         │      │                 │
                    └─────────────────┘      └─────────────────┘
```

### Patrones Arquitectónicos

1. **API Gateway**: Nginx como único punto de entrada
2. **Microservicios**: Servicios independientes por dominio
3. **Balanceo de carga**: Réplicas del microservicio de dominio
4. **Health checks**: Verificación de salud de cada servicio

---

## Estructura del Proyecto

```
EP2_Nexo/
├── docker-compose.yml          # Orquestación de contenedores
├── .env.example                # Variables de entorno de ejemplo
├── .gitignore                  # Archivos ignorados por Git
├── README.md                   # Este archivo
│
├── datos/                      # Tratamiento de datos
│   ├── preparar.py             # Script de limpieza y transformación
│   ├── tests/                  # Tests del tratamiento
│   └── datos_tratados/         # Datos generados (se crean al ejecutar)
│
├── ia/                         # Microservicio de IA
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                  # API REST (FastAPI)
│   ├── modelo.py               # Definición del modelo PyTorch
│   ├── modelo_entrenado.pkl    # Modelo serializado
│   ├── metricas.json           # Métricas de evaluación
│   └── tests/                  # Tests del microservicio
│
├── dominio/                    # Microservicio de dominio
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                  # API REST (FastAPI)
│   └── tests/                  # Tests del microservicio
│
├── front/                      # Interfaz de usuario
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                  # Aplicación Streamlit
│
├── gateway/                    # Gateway Nginx
│   ├── Dockerfile
│   └── nginx.conf              # Configuración del gateway
│
├── carga/                      # Servicio de carga de datos
│   ├── Dockerfile
│   ├── requirements.txt
│   └── cargar.py               # Script de carga
│
├── db/                         # Base de datos
│   └── init.sql                # Inicialización (opcional)
│
├── docs/                       # Documentación
│   └── arc42-ep2.md            # Documentación arc42
│
└── .github/
    └── workflows/
        └── ci.yml              # Pipeline CI/CD
```

---

## Requisitos

### Para desarrollo local

- Python 3.11+
- pip
- Docker Desktop (opcional, para pruebas con contenedores)

### Para ejecución con Docker

- Docker Desktop
- Docker Compose

### Dependencias Python principales

- **PyTorch**: Framework de deep learning
- **FastAPI**: Framework web para APIs REST
- **Streamlit**: Framework para aplicaciones web
- **Pandas**: Manipulación de datos
- **scikit-learn**: Utilidades de machine learning
- **SQLAlchemy**: ORM para base de datos

---

## Instalación y Ejecución

### Opción 1: Con Docker (Recomendado)

1. **Clonar el repositorio**
   ```bash
   git clone <url-del-repositorio>
   cd EP2_Nexo
   ```

2. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env si es necesario
   ```

3. **Levantar el sistema**
   ```bash
   docker compose -p equipo02 pull
   docker compose -p equipo02 up -d
   ```

4. **Verificar que funciona**
   ```
   Abrir http://localhost:8080 en el navegador
   ```

5. **Detener el sistema**
   ```bash
   docker compose -p equipo02 down -v
   ```

### Opción 2: Desarrollo local (sin Docker)

1. **Crear entorno virtual**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

2. **Instalar dependencias**
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   pip install -r ia/requirements.txt
   pip install -r dominio/requirements.txt
   pip install -r front/requirements.txt
   ```

3. **Ejecutar tratamiento de datos**
   ```bash
   python datos/preparar.py
   ```

4. **Entrenar el modelo**
   ```bash
   python ia/modelo.py
   ```

5. **Levantar servicios** (en terminales separadas)
   ```bash
   # Terminal 1: Microservicio de IA
   cd ia
   uvicorn app:app --host 0.0.0.0 --port 8000
   
   # Terminal 2: Microservicio de Dominio
   cd dominio
   uvicorn app:app --host 0.0.0.0 --port 8001
   
   # Terminal 3: Front
   cd front
   streamlit run app.py
   ```

---

## Uso del Sistema

### Interfaz Web

1. Abrir `http://localhost:8080` en el navegador
2. En la pestaña "Predicción":
   - Ingresar datos del usuario (edad, frecuencia de compra, etc.)
   - Ingresar datos del producto (categoría, compras previas, etc.)
   - Hacer clic en "Realizar Predicción"
3. Ver el resultado con la probabilidad y clasificación de propensión

### Predicción por API

```bash
curl -X POST http://localhost:8080/api/ia/predict \
  -H "Content-Type: application/json" \
  -d '{
    "num_compras_categoria": 5,
    "num_vistas_categoria": 20,
    "num_clics_categoria": 10,
    "total_gastado_categoria": 150000,
    "dias_ultima_compra": 15,
    "frecuencia_compra": 10,
    "ticket_promedio": 75000,
    "edad": 35,
    "acepta_marketing": 1
  }'
```

---

## API

### Microservicio de IA

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/predict` | Predicción individual |
| POST | `/predict/batch` | Predicción por lotes |
| GET | `/modelo/info` | Información del modelo |

### Microservicio de Dominio

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/prediccion` | Registrar predicción |
| GET | `/prediccion/{id}` | Obtener predicción |
| GET | `/predicciones` | Listar predicciones |
| GET | `/estadisticas` | Estadísticas del sistema |
| GET | `/productos` | Listar productos |
| GET | `/productos/{sku}` | Obtener producto |

---

## Tests

### Ejecutar todos los tests

```bash
# Tests del microservicio de IA
pytest ia/tests/ -v

# Tests del microservicio de dominio
pytest dominio/tests/ -v

# Tests del tratamiento de datos
pytest datos/tests/ -v
```

### Cobertura

```bash
pytest --cov=ia --cov=dominio --cov=datos --cov-report=html
```

---

## Modelo de IA

### Arquitectura

```
Input (9 features)
    │
    ▼
┌─────────────────┐
│  Dense (64)     │
│  ReLU           │
│  Dropout (0.3)  │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Dense (32)     │
│  ReLU           │
│  Dropout (0.3)  │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Dense (16)     │
│  ReLU           │
│  Dropout (0.3)  │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Dense (1)      │
│  Sigmoid        │
└─────────────────┘
    │
    ▼
Output (probabilidad 0-1)
```

### Features de entrada

1. `num_compras_categoria`: Número de compras previas en la categoría
2. `num_vistas_categoria`: Número de vistas previas en la categoría
3. `num_clics_categoria`: Número de clics previos en la categoría
4. `total_gastado_categoria`: Total gastado en la categoría
5. `dias_ultima_compra`: Días desde la última compra
6. `frecuencia_compra`: Frecuencia de compra del usuario
7. `ticket_promedio`: Ticket promedio del usuario
8. `edad`: Edad del usuario
9. `acepta_marketing`: Si acepta marketing (0 o 1)

### Métricas de evaluación

| Métrica | Valor |
|---------|-------|
| Accuracy | 97.08% |
| Precision | 97.05% |
| Recall | 99.37% |
| F1-Score | 98.19% |
| ROC-AUC | 93.88% |

### Hiperparámetros

- **Optimizador**: Adam
- **Learning rate**: 0.001
- **Batch size**: 64
- **Epochs**: 50 (con early stopping)
- **Dropout**: 0.3
- **Función de pérdida**: BCEWithLogitsLoss (con pesos para balancear clases)

---

## Tratamiento de Datos

### Perfilado inicial

| Archivo | Filas | Columnas | Duplicados | Nulos |
|---------|-------|----------|------------|-------|
| productos.csv | 1,531 | 9 | 31 | 207 |
| transacciones.csv | 22,187 | 11 | 186 | 9,175 |
| usuarios.csv | 4,026 | 8 | 26 | 1,487 |
| clickstream.csv | 29,340 | 9 | 263 | 46,993 |

### Reglas de limpieza aplicadas

1. **Productos**:
   - Categorías normalizadas a minúsculas
   - `precio_lista`: eliminado "$" y convertido a numérico
   - `activo`: normalizado a booleano
   - `stock`: valores negativos corregidos a 0
   - `costo`: nulos imputados con mediana
   - SKUs duplicados eliminados

2. **Transacciones**:
   - `precio_unitario`: convertido a numérico
   - `descuento`: nulos imputados con 0
   - `cantidad`: negativas marcadas como devolución
   - `total`: recalculado
   - Filtradas solo transacciones con estado válido

3. **Usuarios**:
   - `edad`: valores fuera de rango corregidos
   - `region`: normalizada a minúsculas
   - `email_valido`: normalizado a booleano
   - `acepta_marketing`: nulos imputados con 0

4. **Clickstream**:
   - `timestamp`: formatos mixtos manejados
   - `tipo_evento`: normalizado a minúsculas
   - Duplicados eliminados

### Resultado final

| Archivo | Filas después |
|---------|---------------|
| productos | 1,500 |
| transacciones | 19,011 |
| usuarios | 4,000 |
| clickstream | 29,077 |

---

## Licencia

Proyecto académico - DUOC UC
