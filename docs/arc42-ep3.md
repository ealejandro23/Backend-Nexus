# Nexo Recommender System - Informe EP3

**Equipo:** 2  
**Curso:** ITY1102 - Arquitectura de Sistemas de Inteligencia Artificial  
**Evaluación:** Evaluación Parcial 3  
**Integrante responsable de esta parte:** Esteban Gamboa  
**Alcance:** infraestructura en AWS, worker del LLM, cola RabbitMQ y pipeline CI/CD.

---

## Historial de Versiones

| Fecha | Versión | Autor | Qué cambió y por qué |
|-------|---------|-------|----------------------|
| 11/11/2026 | 3.0.0 | Esteban Gamboa | EP3: EC2, S3, RabbitMQ, worker NVIDIA, anonimización, health y pipeline `ep3` |

---

## 1. Resumen Ejecutivo

La EP3 extiende el sistema Nexo Recommender con un **worker de campañas
personalizadas**. El flujo es:

1. La API recibe `POST /api/campanas/{usuario}` y publica un job en RabbitMQ.
2. El worker consume el job y obtiene el perfil del cliente y sus predicciones.
3. El perfil se **anonimiza** antes de salir del perímetro.
4. El worker consulta SageMaker (si está configurado) y luego a la API de
   **NVIDIA** para redactar la campaña.
5. La campaña se guarda en PostgreSQL y, opcionalmente, se exporta a S3.
6. Si el LLM falla, se genera una campaña de respaldo y se marca `degradado`.

Todo corre en una instancia **EC2 t3.medium** en `us-east-1`, con IP elástica,
`LabInstanceProfile`, security group 80/443 y SSH restringido a la IP del
administrador. El compose descarga imágenes `:ep3` y se apoya en un archivo
`.env` que sólo existe en el servidor.

---

## 2. Requisitos Cubiertos

| Requisito EP3 | Evidencia |
|---|---|
| EC2 t3.medium us-east-1, IP elástica, LabInstanceProfile, SG 80/443 y 22 restringido | `infra/cloudformation.yaml`, `infra/README.md` |
| Compose con imágenes `:ep3`, `.env` en servidor y `.env.example` en repo | `docker-compose.yml`, `.env.example`, `infra/deploy.sh` |
| RabbitMQ + worker NVIDIA con tiempo máximo, reintentos 429 y modo degradado | `servicio-campanas/app/queue.py`, `app/llm.py` |
| Anonimización antes del LLM y ruta `POST /api/campanas/{usuario}` | `app/anonymizer.py`, `app/main.py` |
| `GET /api/health` con DB, SageMaker, cola y LLM por separado | `app/health.py` |
| Pipeline con tests antes de publicar, tag `ep3` e imágenes `:ep3` | `.github/workflows/ci.yml` |
| Pruebas 5, 6 y propia | `servicio-campanas/tests/` |
| Informe: apartado 3, apartado 5 y anexos A/B/C | Este documento |

---

## 3. Infraestructura y Despliegue

### 3.1 Instancia EC2

| Atributo | Valor |
|---|---|
| Región | `us-east-1` |
| Tipo | `t3.medium` (2 vCPU, 4 GB RAM) |
| Sistema operativo | Amazon Linux 2023 |
| Perfil IAM | `LabInstanceProfile` (AWS Academy) |
| Almacenamiento | 30 GB gp3 cifrado |
| IP | Elástica, asociada a la instancia |
| Docker | Instalado por UserData, con Compose v2 |

**Security group:**

| Puerto | Protocolo | Origen | Uso |
|---|---|---|---|
| 80 | TCP | `0.0.0.0/0` | HTTP, redirige a HTTPS |
| 443 | TCP | `0.0.0.0/0` | HTTPS público |
| 22 | TCP | `MiIP/32` | SSH administrativo |

El puerto 22 no se abre a Internet: el parámetro `AllowedSSHCIDR` exige la IP
del administrador con máscara `/32`.

**Justificación del tipo de instancia:** t3.medium entrega 4 GB de RAM,
suficientes para PostgreSQL, RabbitMQ, cinco microservicios, el worker y el
borde TLS sin swap. t3.small (2 GB) queda justo y puede provocar OOM con las réplicas de
dominio; t3.large duplica el costo sin aportar al volumen del piloto.

### 3.2 Bucket S3

| Atributo | Valor |
|---|---|
| Nombre | `nexo-ep3-campanas-<equipo>` |
| Región | `us-east-1` |
| Cifrado | AES256 (SSE-S3) |
| Versionado | Habilitado |
| Acceso público | Bloqueado (ACL y policy) |
| Lifecycle | Borra objetos a los 365 días; aborta multipart a los 7 días |
| Uso | Exportar cada campaña a `campanas/<hash_usuario>/<job_id>.json` |

La exportación es **secundaria**: si S3 falla, la campaña igual se guarda en
PostgreSQL y el worker no se cae. El nombre del objeto usa el hash del usuario,
no su identificador real.

### 3.3 Cola RabbitMQ

| Elemento | Configuración |
|---|---|
| Imagen | `rabbitmq:3.13-management-alpine` |
| Usuario | `RABBITMQ_USER` (desde `.env`) |
| Cola principal | `campanas`, durable |
| Cola de errores | `campanas.dlq`, durable |
| Exchange DLX | `campanas.dlx`, tipo direct |
| Prefetch | 1 mensaje por worker |
| Persistencia | `DeliveryMode.PERSISTENT` |
| Reintentos | 3, con header `x-retry` |
| Mensaje | JSON con `job_id`, `usuario_id`, `canal`, `tono`, `incluir_descuento` |

**Política de fallos:**

1. Si el worker falla, el mensaje se reencola con `x-retry + 1`.
2. Tras 3 reintentos, se rechaza y RabbitMQ lo envía a `campanas.dlq`.
3. Si la cola no está disponible al crear la campaña, la API procesa el job
   **en línea** (fallback controlado) y responde `procesado_en_linea`.

### 3.4 Worker del LLM

**Pipeline interno:**

```
job RabbitMQ
   │
   ▼
PostgreSQL: perfil + predicciones
   │
   ▼
Anonimización (SHA-256 con sal, edad por rango, PII fuera)
   │
   ▼
SageMaker (opcional) ──falla──► predicciones de PostgreSQL
   │
   ▼
Prompt + NVIDIA API
   │
   ├── 200 → campaña normal
   ├── 429 → backoff exponencial y reintento
   ├── timeout/5xx → reintento
   └── agotado → campaña de respaldo (degradado=true)
   │
   ▼
INSERT en campanas + export S3
```

**Control de tiempo y reintentos:**

| Parámetro | Default | Efecto |
|---|---|---|
| `LLM_TIMEOUT_SECONDS` | 20 s | Timeout por intento |
| `LLM_MAX_WAIT_SECONDS` | 30 s | Tiempo máximo total del job |
| `LLM_MAX_RETRIES` | 3 | Reintentos ante 429/5xx/timeout |
| `LLM_BACKOFF_SECONDS` | 0.5 s | Base del backoff exponencial |
| `SAGEMAKER_TIMEOUT_SECONDS` | 4 s | Corte de la llamada a SageMaker |
| `RABBITMQ_MAX_RETRIES` | 3 | Reintentos antes de DLQ |

El backoff respeta `Retry-After` cuando NVIDIA lo envía y nunca excede el
tiempo máximo de espera. Un error 401/403 no se reintenta: se degrada de
inmediato para no gastar cuota.

**Modo degradado:** la campaña de respaldo se construye sólo con categorías y
señales anonimizadas. No inventa precios, stock ni plazos. Se guarda con
`degradado=true` y `motivo_degradado` para auditoría.

**Anonimización:**

| Dato | Tratamiento |
|---|---|
| `usuario_id` | SHA-256 con sal → `u_<16 hex>` |
| Nombre, apellido | Se elimina |
| Email, teléfono, RUT | Se elimina o reemplaza por token |
| Dirección, comuna, región | Se elimina |
| Edad | Se convierte en rango (`25-34`, `35-44`, …) |
| Comportamiento | Se conserva agregado (frecuencia, ticket, categorías) |

### 3.5 Health check

`GET /api/health` ejecuta las cuatro verificaciones en paralelo con timeout
independiente:

| Check | Cómo se verifica | Estados |
|---|---|---|
| `base_datos` | `SELECT 1` con pool asyncpg | `ok` / `error` |
| `sagemaker` | `DescribeEndpoint` con boto3 | `ok` / `degradado` / `no_configurado` / `error` |
| `cola` | `declare_queue(passive=True)` y cuenta mensajes | `ok` / `error` |
| `llm` | `GET /v1/models` en NVIDIA | `ok` / `degradado` (429) / `no_configurado` / `error` |

El estado global es `error` sólo si PostgreSQL no responde. Si falla el LLM,
SageMaker o la cola, el estado es `degradado` y el servicio sigue operando con
sus respaldos. `GET /health` es un liveness barato para Docker y no depende de
servicios externos.

### 3.6 Diagrama de despliegue

```
                        Internet
                           │ 80/443
                           ▼
        ┌─────────────────────────────────────────────┐
        │ EC2 t3.medium · us-east-1 · Elastic IP      │
        │ LabInstanceProfile · SG 80/443 + 22 MiIP    │
        │                                             │
        │  ┌───────────────────────────────────────┐  │
        │  │ edge (Nginx TLS) :80/:443             │  │
        │  └───────┬───────────────────────┬───────┘  │
        │          │ /                     │ /api/*  │
        │          ▼                       ▼         │
        │  ┌──────────────┐        ┌──────────────┐   │
        │  │ gateway:8080 │        │ campanas:8090│   │
        │  └──┬────┬────┬─┘        └──────┬───────┘   │
        │     │    │    │                 │           │
        │     ▼    ▼    ▼                 ▼           │
        │  front   ia  dominio x2     PostgreSQL      │
        │                             (volumen)       │
        │                                 │           │
        │                    ┌────────────▼────────┐  │
        │                    │ RabbitMQ            │  │
        │                    │ campanas / DLQ      │  │
        │                    └────────────┬────────┘  │
        │                                 │ consume   │
        │                    ┌────────────▼────────┐  │
        │                    │ worker LLM          │  │
        │                    │ (misma imagen)      │  │
        │                    └───┬─────────────┬───┘  │
        │                        │             │      │
        │                        ▼             ▼      │
        │                  SageMaker       NVIDIA API │
        │                  (opcional)                 │
        │                                             │
        │  S3: campañas/<hash>/<job>.json             │
        └─────────────────────────────────────────────┘
```

### 3.7 Costos

Supuestos: 730 horas/mes, 1.000 campañas/mes, ~1.500 tokens por campaña,
10 GB de campañas en S3.

| Recurso | Cálculo | USD/mes |
|---|---|---|
| EC2 t3.medium on-demand | 0,0416 USD/h × 730 h | 30,37 |
| EBS gp3 30 GB | 0,08 USD/GB-mes × 30 GB | 2,40 |
| Elastic IP asociada | 0,005 USD/h × 730 h | 3,65 |
| S3 almacenamiento + requests | 10 GB + ~2.000 PUT/GET | 0,50 |
| NVIDIA API | 1.000 × 1.500 tokens (entrada+salida) | 0,30 |
| **Total** | | **37,22** |

Notas:
- Dentro de AWS Academy el costo se cubre con créditos del laboratorio.
- SageMaker no se incluye porque el endpoint puede estar apagado; si se deja
  activo, se cobra por hora según el tipo de instancia del endpoint.
- El costo dominante es la EC2; bajar a t3.small ahorra ~15 USD/mes pero
  arriesga OOM con las réplicas de dominio.

---

## 4. Modelo de Datos de Campañas

```sql
CREATE TABLE campanas (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL UNIQUE,
    usuario_id VARCHAR(50) NOT NULL,
    canal VARCHAR(50) NOT NULL,
    asunto VARCHAR(200) NOT NULL,
    mensaje TEXT NOT NULL,
    recomendaciones JSONB NOT NULL DEFAULT '[]'::jsonb,
    degradado BOOLEAN NOT NULL DEFAULT FALSE,
    motivo_degradado VARCHAR(300),
    modelo_llm VARCHAR(100),
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

La tabla la crea el propio servicio (`ensure_schema`) al arrancar, sin montar
archivos de inicialización. El `job_id` es idempotente: si RabbitMQ reentrega
el mensaje, el `UPSERT` no duplica la campaña.

---

## 5. Pruebas y Optimizaciones

### 5.1 Estrategia de pruebas

| Nivel | Qué se prueba | Herramienta |
|---|---|---|
| Unitario | Anonimización, parseo de prompt, fallback | pytest |
| Integración | API + servicio + cola falsa + LLM falso | pytest-asyncio + httpx ASGI |
| Resiliencia | 429, timeout, 401, cola caída | `httpx.MockTransport` |
| Datos | Limpieza e integración de CSV | pytest + pandas |
| Humo | `/health` y `/api/health` | curl / httpx |

### 5.2 Pruebas obligatorias

#### Prueba 5 - Anonimización

**Objetivo:** demostrar que ningún dato personal llega al LLM.

**Casos:**
- Perfil con nombre, email, teléfono, RUT, dirección, comuna y región.
- Se verifica que ninguno de esos valores aparezca en el JSON anonimizado ni
  en el prompt.
- Se verifica que la edad exacta se transforme en rango.
- Se verifica que el hash sea estable con la misma sal y distinto con otra sal.
- Se verifica que el texto libre elimine email, teléfono, RUT y dirección.

**Resultado:** `4 passed` en `tests/test_anonymization.py`.

#### Prueba 6 - LLM caído

**Objetivo:** demostrar que el worker no se cae y genera una campaña degradada.

**Casos:**
- NVIDIA responde **429** en todos los intentos.
- NVIDIA produce **timeout** de lectura.
- NVIDIA responde **401** (no reintentable).
- Pipeline completo: el job se procesa, la campaña se guarda con
  `degradado=true` y `motivo_degradado` incluye el error.
- `GET /api/health` reporta `llm: degradado` sin devolver 500.

**Resultado:** `5 passed` en `tests/test_llm_down.py`.

#### Prueba propia - Health por dependencia

**Objetivo:** demostrar que el health no oculta fallas.

**Casos:**
- Las cuatro dependencias aparecen siempre como claves separadas.
- LLM caído → estado global `degradado`.
- SageMaker no configurado → no degrada el sistema.
- PostgreSQL caído → estado global `error`.
- `/health` (liveness) sigue en `ok` aunque las dependencias estén caídas.

**Resultado:** `5 passed` en `tests/test_health.py`.

### 5.3 Resultados de la suite

```text
$ cd servicio-campanas
$ pytest -v --cov=app

tests/test_anonymization.py ....                          [ 20%]
tests/test_campaigns_api.py ......                        [ 50%]
tests/test_health.py .....                                [ 75%]
tests/test_llm_down.py .....                              [100%]

20 passed
```

Cobertura de los módulos críticos:

| Módulo | Cobertura |
|---|---|
| `anonymizer.py` | 79% |
| `campaigns.py` | 83% |
| `health.py` | 97% |
| `main.py` | 88% |
| `prompts.py` | 93% |
| `schemas.py` | 100% |

Los módulos con menor cobertura (`database.py`, `queue.py`, `sagemaker.py`)
requieren servicios reales; se validan en el humo de EC2 y en los tests de
integración manuales del despliegue.

### 5.4 Optimizaciones aplicadas

| Optimización | Dónde | Efecto |
|---|---|---|
| Timeout por intento + deadline total | `llm.py` | Ningún job queda colgado más de 30 s |
| Backoff exponencial + `Retry-After` | `llm.py` | No satura a NVIDIA ante 429 |
| Modo degradado determinista | `llm.py` | La campaña sale aunque el LLM esté caído |
| Prefetch 1 y ACK manual | `queue.py` | Un worker no acumula jobs lentos |
| DLQ con 3 reintentos | `queue.py` | No se pierden jobs fallidos |
| Fallback en línea si la cola cae | `campaigns.py` | La API sigue respondiendo |
| Pool asyncpg (1-5 conexiones) | `database.py` | Reutiliza conexiones y evita handshakes |
| Health en paralelo | `health.py` | La suma de latencias no castiga el endpoint |
| Truncado de prompt a 2.500 caracteres | `prompts.py` | Controla tokens y costo |
| Hash de usuario en objetos S3 | `campaigns.py` | No expone el ID real en el bucket |
| Exportación S3 en thread | `campaigns.py` | No bloquea el event loop |
| Imagen única para API y worker | `Dockerfile` | Menos capas, menos superficie |
| Usuario no root UID 10001 | `Dockerfile` | Menor impacto ante RCE |
| Cache de capas en CI | `ci.yml` | Builds más rápidos y reproducibles |
| Límites de CPU/memoria | `docker-compose.yml` | Un servicio no consume el host |

### 5.5 Pipeline

| Etapa | Job | Condición |
|---|---|---|
| 1 | `test-campanas` | PR, push main/dev, tag ep3 |
| 2 | `test-datos` | PR, push main/dev, tag ep3 |
| 3 | `build-and-push-backend` | push main o tag ep3, después de tests |
| 4 | `build-and-push-campanas` | push main o tag ep3, después de tests |
| 5 | `build-and-push-edge` | push main o tag ep3, después de tests |
| 6 | `tag-ep3` | tag `ep3`, matriz backend/campanas/edge |

Reglas cumplidas:
- Ninguna imagen se publica si fallan los tests (`needs: [test-*]`).
- Las imágenes se construyen en `linux/amd64`.
- Cada imagen lleva tag `sha-`, `latest` y, al crear el tag, `ep3`.
- El workflow usa `GHCR_PAT` si existe y cae a `GITHUB_TOKEN` si no.
- `concurrency` cancela ejecuciones viejas de la misma rama.

---

## Anexo A: Referencias

1. Starke, G. (2023). *arc42: Template for architecture documentation*. https://arc42.org/
2. AWS (2024). *Amazon EC2 User Guide for Linux Instances*. AWS Documentation.
3. AWS (2024). *Amazon SageMaker Developer Guide*. AWS Documentation.
4. AWS (2024). *Amazon S3 User Guide*. AWS Documentation.
5. RabbitMQ (2024). *RabbitMQ Documentation: Reliability and Dead Lettering*. https://www.rabbitmq.com/docs/
6. NVIDIA (2024). *NVIDIA API Catalog*. https://build.nvidia.com/
7. Docker (2024). *Docker Compose Specification*. https://docs.docker.com/compose/
8. GitHub (2024). *GitHub Actions Documentation*. https://docs.github.com/en/actions
9. Ley 19.628 y Ley 21.719 sobre protección de datos personales (Chile).

---

## Anexo B: Declaración de Uso de IA Generativa

| Herramienta | Uso | Verificación |
|---|---|---|
| Claude / asistente de código | Redacción de documentación, estructura del worker, tests y scripts de despliegue | Revisión de cifras, ejecución de pytest y prueba de humo en EC2 |
| GitHub Copilot | Sugerencias de código en Python y YAML | Revisión de pares y pruebas automatizadas |

**Declaración:** el integrante entiende el contenido de este documento y puede
explicar y justificar cada decisión de infraestructura, cola, worker y
pipeline. La IA se usó como apoyo de redacción y borrador; el código fue
verificado con tests, revisión manual y mediciones antes de integrarse.

---

## Anexo C: Repositorios, Imágenes y Endpoints

| Repositorio | URL | Imagen `:ep3` |
|---|---|---|
| Backend-Nexus (infra, worker, pipeline) | https://github.com/ealejandro23/Backend-Nexus | `ghcr.io/ealejandro23/backend:ep3` |
| Worker de campañas | https://github.com/ealejandro23/Backend-Nexus/tree/main/servicio-campanas | `ghcr.io/ealejandro23/campanas:ep3` |
| Borde TLS | https://github.com/ealejandro23/Backend-Nexus/tree/main/edge | `ghcr.io/ealejandro23/edge:ep3` |
| Microservicio-IA | https://github.com/ealejandro23/Microservicio-IA | `ghcr.io/ealejandro23/ia:ep3` |
| Microservicio-Nexus (dominio) | https://github.com/ealejandro23/Microservicio-Nexus | `ghcr.io/ealejandro23/dominio:ep3` |
| Frontend-Nexus | https://github.com/ealejandro23/Frontend-Nexus | `ghcr.io/ealejandro23/front:ep3` |
| Gateway | https://github.com/FranAlarcon24/gateway-nexus | `ghcr.io/franalarcon24/gateway:ep3` |

**Compose:** https://github.com/ealejandro23/Backend-Nexus/blob/main/docker-compose.yml  
**Pipeline:** https://github.com/ealejandro23/Backend-Nexus/actions  
**Infraestructura:** https://github.com/ealejandro23/Backend-Nexus/tree/main/infra

**Endpoints:**

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/campanas/{usuario}` | Encola una campaña personalizada |
| GET | `/api/campanas/{usuario}` | Última campaña generada |
| GET | `/api/campanas/jobs/{job_id}` | Campaña por job |
| GET | `/api/health` | Estado de DB, SageMaker, cola y LLM |
| GET | `/health` | Liveness para Docker |

**Comandos de operación:**

```bash
docker compose -p equipo02 ps
docker compose -p equipo02 logs -f campanas campanas-worker
docker compose -p equipo02 exec rabbitmq rabbitmqctl list_queues name messages
docker compose -p equipo02 exec campanas curl -s localhost:8090/api/health
```

**Integrantes:**

| Nombre | GitHub | Piezas |
|---|---|---|
| Francisca Alarcón | @francisca-alarcon | Front, Gateway |
| Benjamín Trujillo | @benjamin-trujillo | IA, Modelo |
| Esteban Gamboa | @esteban-gamboa | Infraestructura, worker del LLM, pipeline, documentación |
