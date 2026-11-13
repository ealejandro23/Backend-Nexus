# Infraestructura EP3 - Nexo Recommender

Esta carpeta contiene todo lo necesario para desplegar la parte de
**Esteban Gamboa**: EC2, bucket S3, cola RabbitMQ, worker del LLM y pipeline.

## 1. Arquitectura de despliegue

```
Internet
   │ 80/443
   ▼
┌──────────────────────────────────────────────────────────────┐
│ EC2 t3.medium (us-east-1) + Elastic IP                       │
│ LabInstanceProfile                                           │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │ edge (Nginx) │───►│ gateway:8080 │───►│ front / ia /   │  │
│  │ TLS 80/443   │    └──────────────┘    │ dominio x2     │  │
│  │              │───►┌──────────────┐    └────────────────┘  │
│  │              │    │ campanas:8090│───► PostgreSQL        │
│  └──────────────┘    └──────┬───────┘                        │
│                             │ publica job                    │
│                      ┌──────▼───────┐                        │
│                      │ RabbitMQ     │                        │
│                      │ cola campanas│                        │
│                      └──────┬───────┘                        │
│                             │ consume                        │
│                      ┌──────▼───────┐   ┌─────────────────┐  │
│                      │ worker LLM   │──►│ NVIDIA API      │  │
│                      │ (misma img)  │   └─────────────────┘  │
│                      └──────┬───────┘                        │
│                             │ invoca                         │
│                      ┌──────▼───────┐   ┌─────────────────┐  │
│                      │ SageMaker    │   │ S3 (campañas)   │  │
│                      │ endpoint     │   └─────────────────┘  │
│                      └──────────────┘                        │
└──────────────────────────────────────────────────────────────┘
```

## 2. Crear la infraestructura

### Opción A: CloudFormation (recomendado)

1. En AWS Academy, abrir **CloudFormation** en `us-east-1`.
2. Crear stack con el archivo `infra/cloudformation.yaml`.
3. Parámetros:
   - `KeyName`: par de llaves existente en la cuenta.
   - `AllowedSSHCIDR`: tu IP pública con `/32` (por ejemplo `200.1.2.3/32`).
   - `InstanceType`: `t3.medium`.
   - `BucketName`: nombre único global, por ejemplo `nexo-ep3-campanas-equipo2`.
4. Crear el stack y esperar `CREATE_COMPLETE`.
5. Anotar los outputs: `PublicIP`, `InstanceId`, `BucketName`, `HealthURL`.

El stack crea:
- Security group con **80 y 443 abiertos** a Internet y **22 sólo desde tu IP**.
- Instancia **t3.medium** con `LabInstanceProfile` y disco gp3 cifrado de 30 GB.
- **IP elástica** asociada a la instancia.
- Bucket S3 con versionado, cifrado AES256, bloqueo de acceso público y
  lifecycle de 365 días.

### Opción B: Consola (si CloudFormation no está permitido)

1. **EC2 → Launch instance**:
   - AMI Amazon Linux 2023, tipo `t3.medium`, región `us-east-1`.
   - Key pair propio.
   - **IAM instance profile: `LabInstanceProfile`**.
   - Security group: 80 y 443 `0.0.0.0/0`; 22 `MiIP/32`.
   - Disco gp3 30 GB cifrado.
2. **Elastic IP → Allocate → Associate** con la instancia.
3. **S3 → Create bucket** en `us-east-1`, bloquear acceso público, cifrado AES256.
4. Ejecutar `infra/bootstrap.sh` en la instancia (o pegarlo como User data).

## 3. Configurar el servidor

```bash
# En la instancia (Amazon Linux 2023)
sudo dnf install -y docker git awscli
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
# Volver a entrar por SSH para aplicar el grupo docker
```

El bucket S3 y el endpoint de SageMaker se configuran en `.env`:

```env
AWS_REGION=us-east-1
S3_BUCKET=nexo-ep3-campanas-equipo2
SAGEMAKER_ENDPOINT_NAME=nexo-propension-ep3
NVIDIA_API_KEY=nvapi-...
```

En AWS Academy **no** se configuran credenciales: `LabInstanceProfile` las
entrega automáticamente al SDK (boto3).

## 4. Desplegar

Desde tu computador, en la raíz del repositorio:

```bash
export EC2_HOST=54.1.2.3
export SSH_KEY=~/.ssh/nexo.pem
export DB_PASSWORD='...'
export RABBITMQ_PASSWORD='...'
export NVIDIA_API_KEY='nvapi-...'
export ANONYMIZATION_SALT="$(openssl rand -hex 24)"
export SAGEMAKER_ENDPOINT_NAME=nexo-propension-ep3
export S3_BUCKET=nexo-ep3-campanas-equipo2

./infra/deploy.sh
```

En Windows:

```powershell
$env:EC2_HOST="54.1.2.3"
$env:SSH_KEY="$HOME\.ssh\nexo.pem"
$env:DB_PASSWORD="..."
$env:RABBITMQ_PASSWORD="..."
$env:NVIDIA_API_KEY="nvapi-..."
$env:ANONYMIZATION_SALT="..."
$env:SAGEMAKER_ENDPOINT_NAME="nexo-propension-ep3"
$env:S3_BUCKET="nexo-ep3-campanas-equipo2"

.\infra\deploy.ps1
```

El script:
1. Genera `.env` desde `.env.example` (sin versionarlo).
2. Copia **sólo** `docker-compose.yml` y `.env` a `/opt/nexo` con permisos `600`.
3. Hace `docker compose pull` de las imágenes `:ep3` desde GHCR.
4. Levanta los servicios con `docker compose up -d`.

> El servidor **no necesita clonar el repositorio**. El compose usa únicamente
> imágenes publicadas; el código sólo se clona si se va a desarrollar o
> reconstruir imágenes. Como los paquetes son públicos, el `pull` funciona sin
> `GHCR_PAT`; la variable existe sólo como respaldo si algún paquete vuelve a
> quedar privado.

## 5. Verificar

```bash
# Health público (DB, SageMaker, cola y LLM por separado)
curl -k https://<IP>/api/health

# Encolar una campaña
curl -k -X POST https://<IP>/api/campanas/U100000 \
  -H "Content-Type: application/json" \
  -d '{"canal":"email","tono":"cercano"}'

# Consultar el resultado
curl -k https://<IP>/api/campanas/U100000
```

Respuesta esperada de health:

```json
{
  "estado": "ok",
  "checks": {
    "base_datos": {"estado": "ok", "detalle": "PostgreSQL responde", "latencia_ms": 2.1},
    "sagemaker": {"estado": "ok", "detalle": "endpoint ... InService", "latencia_ms": 120.0},
    "cola": {"estado": "ok", "detalle": "0 mensajes en cola", "latencia_ms": 4.3},
    "llm": {"estado": "ok", "detalle": "API de NVIDIA responde", "latencia_ms": 80.0}
  }
}
```

Si el LLM no está disponible, el health queda `degradado` y las campañas se
generan igual con el mensaje de respaldo (`"degradado": true`).

## 6. Costos estimados (us-east-1)

| Recurso | Cálculo | USD/mes |
|---|---|---|
| EC2 t3.medium on-demand | 0,0416 USD/h × 730 h | 30,37 |
| EBS gp3 30 GB | 0,08 USD/GB-mes × 30 | 2,40 |
| Elastic IP asociada | 0,005 USD/h × 730 h | 3,65 |
| S3 (10 GB + requests) | almacenamiento + PUT/GET | 0,50 |
| NVIDIA API (1.000 campañas) | ~1.500 tokens/campaña | 0,30 |
| **Total** | | **~37,22** |

Notas:
- AWS Academy entrega créditos; el costo real puede ser 0 dentro del laboratorio.
- SageMaker se cobra por hora del endpoint si está siempre activo; si se usa
  el modelo local de EP2, el health queda `no_configurado` y no hay costo.
- El bucket lifecycle borra las campañas a los 365 días.

## 7. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker compose pull` falla con `denied` | Imagen privada | `docker login ghcr.io` con un PAT `read:packages` |
| Paquete nuevo en GHCR privado | Los paquetes nuevos nacen privados | GitHub → Packages → `campanas`/`edge` → Package settings → Change visibility → Public |
| `health` con `base_datos: error` | PostgreSQL aún iniciando | Esperar 30 s y reintentar |
| `health` con `cola: error` | RabbitMQ sin memoria | Revisar `docker compose logs rabbitmq` |
| `health` con `llm: no_configurado` | Falta `NVIDIA_API_KEY` | Completar `.env` y `docker compose up -d` |
| `health` con `sagemaker: no_configurado` | Falta endpoint | Configurar `SAGEMAKER_ENDPOINT_NAME` o dejar el fallback local |
| `502` en `/api/campanas` | Worker/API caídos | `docker compose logs campanas campanas-worker` |
| Certificado inválido | Certificado autofirmado | Reemplazar `/etc/nginx/certs` por Let's Encrypt o usar `curl -k` |
