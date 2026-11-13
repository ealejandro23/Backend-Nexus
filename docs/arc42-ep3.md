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

> **TODO — Responsable:** _[completar nombre del integrante]_.
>
> Esta sección debe presentar el resumen ejecutivo del sistema completo:
> problema abordado, solución propuesta en la EP3, resultados obtenidos y
> estado final de la entrega. No forma parte del alcance redactado por
> Esteban Gamboa.

---

## 2. Requisitos Cubiertos

> **TODO — Responsable:** _[completar nombre del integrante]_.
>
> Esta sección debe contener la tabla de requisitos de la EP3, su evidencia y
> la trazabilidad con los apartados 3 y 5. No forma parte del alcance redactado
> por Esteban Gamboa.

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
| `LLM_DISABLE_THINKING` | `true` | Desactiva el razonamiento de Nemotron 3 y devuelve el JSON final |
| `SAGEMAKER_TIMEOUT_SECONDS` | 4 s | Corte de la llamada a SageMaker |
| `RABBITMQ_MAX_RETRIES` | 3 | Reintentos antes de DLQ |

El modelo por defecto es **`nvidia/nemotron-3.5-lightning-30b-a3b`**. El modelo
anterior, `meta/llama-3.1-70b-instruct`, alcanzó su fin de vida el **26-08-2026**
y la API responde `410 Gone`, por lo que se migró. Como Nemotron 3 es un modelo
de razonamiento, el cliente envía `chat_template_kwargs.enable_thinking=false`:
así `content` trae el JSON final y el presupuesto de tokens no se consume
pensando. Si la respuesta no trae `content`, el worker genera el respaldo en
lugar de guardar el texto `None`.

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

### 3.7 Modelo de datos de campañas

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
el mensaje, el `UPSERT` no duplica la campaña. Los datos personales no se
persisten en esta tabla: `usuario_id` es el identificador de negocio y la
exportación a S3 usa su hash.

### 3.8 Costos

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

## 4. Modelo de Datos del Sistema

> **TODO — Responsable:** _[completar nombre del integrante]_.
>
> Esta sección debe describir el modelo de datos completo del sistema (tablas
> base de productos, usuarios y transacciones, además de las tablas de dominio
> de la EP3). El modelo de la tabla `campanas` que respalda el worker se
> documenta en §3.7 por pertenecer al alcance de Esteban Gamboa.

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
- Modelo de razonamiento sin `content` final → respaldo, sin guardar `None`.
- Health reporta `degradado` si el modelo configurado no está disponible.

**Resultado:** `8 passed` en `tests/test_llm_down.py`.

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
$ python -m pytest -v --cov=app

tests/test_anonymization.py ....                          [ 17%]
tests/test_campaigns_api.py ......                        [ 43%]
tests/test_health.py .....                                [ 65%]
tests/test_llm_down.py ........                           [100%]

23 passed
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
| `enable_thinking=false` | `llm.py` | Evita `content=null` y el gasto de tokens de razonamiento |
| Validación del modelo en health | `llm.py` | Detecta modelos EOL o no disponibles |
| Migración a Nemotron 3.5 Lightning | `config.py` | Reemplaza el modelo Llama 3.1 EOL (410) |
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
| Healthcheck del front alineado a `:8000` | `docker-compose.yml` | Evita falsos `unhealthy` y permite arrancar gateway y borde |
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

**Evidencia:** última ejecución verde del tag `ep3` en
https://github.com/ealejandro23/Backend-Nexus/actions/runs/43343991741
(commit `2fe58e4`: tests de campañas y datos, builds `backend`, `campanas` y
`edge`, y job `tag-ep3` que publica las imágenes `:ep3` en `linux/amd64`).
La imagen `ghcr.io/ealejandro23/campanas:ep3` se inspeccionó tras publicarse y
contiene el modelo `nvidia/nemotron-3.5-lightning-30b-a3b`,
`LLM_DISABLE_THINKING=true` y la validación del modelo en `/api/health`.

### 5.6 Prueba de humo end-to-end

Se levantó el stack completo con `docker compose -p equipo02` usando las nueve
imágenes `:ep3` publicadas en GHCR (`db`, `rabbitmq`, `campanas`,
`campanas-worker`, `edge`, `gateway`, `front`, `ia`, `dominio` ×2) y el
servicio one-shot `carga`, que crea las tablas base.

| Paso | Resultado |
|---|---|
| `GET https://localhost/healthz` (borde) | `200 ok` |
| `GET https://localhost/api/health` (borde → campañas) | `estado=ok`; `base_datos=ok`, `cola=ok`, `sagemaker=no_configurado`, `llm=no_configurado` |
| `GET https://localhost/health` (borde → gateway) | `{"status":"ok","servicio":"gateway"}` |
| `GET https://localhost/` (borde → gateway → front) | `200 text/html` |
| `POST https://localhost/api/campanas/U100000` | `202`, `estado=en_cola`, `job_id` UUID generado |
| RabbitMQ | Job consumido; `campanas=0`, `campanas.dlq=0` |
| Worker (log) | `Campaña ... generada para u_a1ec2af3fe0c068a` (usuario anonimizado) |
| `GET https://localhost/api/campanas/U100000` | `200`, campaña con recomendaciones `audio` (0,82) y `video` (0,55) |
| LLM sin clave | `degradado=true`, `motivo_degradado="NVIDIA_API_KEY no configurada"` |

Esto valida en contenedores reales, a través del borde TLS, el enrutamiento
`/api/*` hacia el servicio de campañas, el enrutamiento del front por el
gateway, el encolado y consumo por el worker, la anonimización previa al LLM y
el modo degradado de la prueba 6.

**Consumo puro desde GHCR:** en una carpeta vacía, con `docker logout ghcr.io`
(sin credenciales), se descargaron sólo `docker-compose.yml` y `.env.example`
desde el tag `ep3`, se completó `.env` y `docker compose pull && up -d` levantó
los diez contenedores. `https://localhost/api/health` y `https://localhost/`
respondieron `200`. Por tanto, el despliegue **no requiere clonar el
repositorio ni autenticarse en GHCR**.

### 5.7 Validación con NVIDIA real

Con una API key real se ejecutó el cliente `NvidiaLLMClient` del worker:

| Métrica | Resultado |
|---|---|
| Modelo | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| `degradado` | `false` |
| `error` | `null` |
| `intentos` | 1 |
| Latencia | 2.437 ms |
| Asunto generado | “Descubre lo último en audio y video” |
| Mensaje generado | “Hola, revisa nuestras novedades en auriculares y equipos de sonido. También tenemos opciones en video para completar tu entretenimiento.” |

La misma prueba permitió detectar que el modelo anterior
`meta/llama-3.1-70b-instruct` está EOL: la API responde `410 Gone` desde el
26-08-2026. También se comprobó que la cuenta sólo tiene habilitados algunos
modelos de NVIDIA; el health ahora valida que el modelo configurado exista en
`/v1/models` y reporta `degradado` si no está disponible.

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
| Claude / asistente de código | Redacción de documentación, estructura del worker, tests y scripts de despliegue | Revisión de cifras, ejecución de pytest y prueba de humo en contenedores reales |
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

**Visibilidad:** las siete imágenes `:ep3` son públicas. Se verificó con un
`HEAD /v2/<repo>/manifests/ep3` anónimo (sin credenciales) y las siete
respondieron `200`, por lo que `docker compose pull` funciona sin `docker login`.

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
| Francisca Alarcón | @FranAlarcon24 | Front, Gateway |
| Benjamín | @zbenja19 | IA, Modelo |
| Esteban Gamboa | @ealejandro23 | Infraestructura, worker del LLM, pipeline, documentación |
