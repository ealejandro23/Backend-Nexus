# Nexo Recommender System - EP2 + EP3

Sistema de recomendación de productos con arquitectura de microservicios para el caso Nexus Retail.

**Equipo:** 2  
**Curso:** ITY1102 - Arquitectura de Sistemas de Inteligencia Artificial  
**Evaluación:** Evaluaciones Parciales 2 y 3

---

## Novedades EP3 (infraestructura, worker del LLM y pipeline)

La EP3 agrega el worker de campañas personalizadas con LLM y el despliegue en
AWS. La parte de Esteban Gamboa incluye:

| Pieza | Ubicación |
|---|---|
| Servicio de campañas + worker | `servicio-campanas/` |
| Cola RabbitMQ y worker con timeout, reintentos 429 y modo degradado | `servicio-campanas/app/queue.py`, `app/llm.py` |
| Anonimización antes del LLM | `servicio-campanas/app/anonymizer.py` |
| `POST /api/campanas/{usuario}` y `GET /api/health` | `servicio-campanas/app/main.py` |
| Borde TLS 80/443 | `edge/` |
| EC2, S3, security group, Elastic IP y scripts de despliegue | `infra/` |
| Pipeline con tests antes de publicar y tag `ep3` | `.github/workflows/ci.yml` |
| Informe EP3 (apartados 3 y 5 + anexos A/B/C) | `docs/arc42-ep3.md` |

Inicio rápido:

```bash
# No requiere clonar el repositorio ni docker login: las imágenes son públicas.
curl -fsSLO https://raw.githubusercontent.com/ealejandro23/Backend-Nexus/ep3/docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/ealejandro23/Backend-Nexus/ep3/.env.example -o .env
# completar NVIDIA_API_KEY, DB_PASSWORD, RABBITMQ_PASSWORD y ANONYMIZATION_SALT
docker compose -p equipo02 pull
docker compose -p equipo02 up -d
curl -k https://localhost/api/health
```

Guía completa de AWS en [`infra/README.md`](infra/README.md).


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

### Opción 1: Desde GHCR (recomendado, sin clonar el repositorio)

Las siete imágenes `:ep3` son públicas, así que **no se necesita `docker login`
ni token**. El compose no compila nada (`build:`): sólo descarga imágenes. Basta
con el `docker-compose.yml` y el `.env` en una carpeta vacía.

1. **Descargar sólo el compose y la plantilla de variables**
   ```bash
   mkdir nexo-ep3 && cd nexo-ep3
   curl -fsSLO https://raw.githubusercontent.com/ealejandro23/Backend-Nexus/ep3/docker-compose.yml
   curl -fsSL https://raw.githubusercontent.com/ealejandro23/Backend-Nexus/ep3/.env.example -o .env
   ```
   En Windows PowerShell:
   ```powershell
   New-Item -ItemType Directory nexo-ep3 -Force | Out-Null; Set-Location nexo-ep3
   curl.exe -fsSLO https://raw.githubusercontent.com/ealejandro23/Backend-Nexus/ep3/docker-compose.yml
   curl.exe -fsSL https://raw.githubusercontent.com/ealejandro23/Backend-Nexus/ep3/.env.example -o .env
   ```

2. **Editar `.env`** con `DB_PASSWORD`, `RABBITMQ_PASSWORD`, `NVIDIA_API_KEY` y
   `ANONYMIZATION_SALT`. No se versiona ni se comparte.

3. **Preparar los datos** (si no los tienes ya):
   Los CSV crudos no están en este repositorio. Las dos copias idénticas del
   equipo están en:
   - `ealejandro23/Microservicio-IA`, rama `main`, carpeta `datos/crudos/`
   - `ealejandro23/Microservicio-Nexus`, rama `feat/dominio-nexus`, carpeta `carga/datos/`

   ```bash
   mkdir -p datos/crudos
   cd datos/crudos
   for f in productos usuarios transacciones clickstream; do
     curl -fsSLO "https://raw.githubusercontent.com/ealejandro23/Microservicio-IA/main/datos/crudos/$f.csv"
   done
   cd ../..
   python datos/preparar.py   # genera datos/datos_tratados/*.csv
   ```

   El servicio `carga` monta `datos/datos_tratados/` en sólo lectura y lo que
   inserta son `productos_limpios.csv`, `usuarios_limpios.csv` y
   `transacciones_limpias.csv`. No se versionan porque contienen datos
   personales. Si la carpeta está vacía, el contenedor termina con error y
   `POST /api/campanas/{usuario}` responde `404`.

4. **Levantar el sistema** (sin `docker login`, las imágenes son públicas)
   ```bash
   docker compose -p equipo02 pull
   docker compose -p equipo02 up -d
   ```

5. **Verificar que funciona**
   ```bash
   curl -k https://localhost/api/health
   # Navegador: https://localhost
   ```

6. **Detener el sistema**
   ```bash
   docker compose -p equipo02 down -v
   ```

> Si algún `pull` responde `denied`, ese paquete quedó privado: haz
> `docker login ghcr.io` con un PAT que tenga `read:packages`, o cambia su
> visibilidad a pública en GitHub → Packages. Con la entrega actual no ocurre.

### Opción 1b: Desarrollo (clonar el repositorio)

Sólo necesitas clonar si vas a modificar código, ejecutar los tests o
reconstruir imágenes localmente:

```bash
git clone https://github.com/ealejandro23/Backend-Nexus.git
cd Backend-Nexus
cp .env.example .env
docker compose -p equipo02 up -d --build
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

## EP3: Worker de campañas con LLM

### Componentes nuevos

| Componente | Descripción |
|---|---|
| `servicio-campanas` (API) | FastAPI en `:8090`; encola jobs y expone health |
| `servicio-campanas-worker` | Consume RabbitMQ y llama a SageMaker + NVIDIA |
| `rabbitmq` | Cola durable `campanas` + DLQ `campanas.dlq` |
| `edge` | Nginx con TLS, publica 80/443, enruta `/api/campanas` y `/api/health` |

### Flujo de una campaña

1. `POST /api/campanas/{usuario}` valida que el usuario exista y publica un job.
2. El worker consume el job, lee perfil y predicciones desde PostgreSQL.
3. Anonimiza el perfil (elimina PII y seudonimiza `usuario_id`).
4. Consulta SageMaker (si está configurado) o usa las predicciones de la BD.
5. Arma el prompt y llama a NVIDIA con timeout y reintentos ante 429.
6. Guarda la campaña en `campanas` y, si hay bucket, la exporta a S3.
7. Si el LLM falla, guarda una campaña de respaldo con `degradado=true`.

### Variables de entorno

Ver [`.env.example`](.env.example). Las mínimas para EP3:

```env
NVIDIA_API_KEY=nvapi-...
ANONYMIZATION_SALT=<valor aleatorio largo>
DB_PASSWORD=<clave>
RABBITMQ_PASSWORD=<clave>
SAGEMAKER_ENDPOINT_NAME=nexo-propension-ep3   # opcional
S3_BUCKET=nexo-ep3-campanas-equipo2            # opcional
```

### Tests EP3

```bash
cd servicio-campanas
pip install -r requirements-dev.txt
pytest -v --cov=app
```

| Test | Qué valida |
|---|---|
| `test_anonymization.py` (Prueba 5) | No se filtra PII al prompt del LLM |
| `test_llm_down.py` (Prueba 6) | 429/timeout/401 generan modo degradado sin caer |
| `test_health.py` (propia) | Health independiente de DB, SageMaker, cola y LLM |
| `test_campaigns_api.py` | Encolado, fallback en línea y consulta de campañas |

### Pipeline EP3

El workflow `.github/workflows/ci.yml`:

1. Ejecuta tests de campañas y de datos **antes** de publicar.
2. Construye y publica `backend`, `campanas` y `edge` en GHCR (`sha-` y `latest`).
3. Al crear el tag `ep3`, publica el tag estable `:ep3` que usa el compose.

Para publicar una entrega:

```bash
git tag -f ep3
git push origin ep3 --force
```

### Seguridad

- `.env` sólo existe en el servidor, con permisos `600` (nunca se versiona).
- El LLM recibe únicamente datos agregados y un hash del usuario.
- El security group expone 80/443 a Internet y 22 sólo a la IP del administrador.
- Las imágenes se ejecutan como usuario no root (`appuser`, UID 10001).
- El bucket S3 bloquea acceso público y exige TLS.

---

## Licencia

Proyecto académico - DUOC UC
