# =============================================================================
# Despliegue de Nexo EP3 en EC2 desde Windows (PowerShell + OpenSSH).
# Uso:
#   $env:EC2_HOST="54.1.2.3"; $env:SSH_KEY="$HOME\.ssh\nexo.pem"
#   $env:DB_PASSWORD="..."; $env:RABBITMQ_PASSWORD="..."
#   $env:NVIDIA_API_KEY="..."; $env:ANONYMIZATION_SALT="..."
#   .\infra\deploy.ps1
# =============================================================================
[CmdletBinding()]
param(
    [string]$Ec2Host = $env:EC2_HOST,
    [string]$SshKey = $env:SSH_KEY,
    [string]$SshUser = $(if ($env:SSH_USER) { $env:SSH_USER } else { "ec2-user" }),
    [string]$RemoteDir = $(if ($env:REMOTE_DIR) { $env:REMOTE_DIR } else { "/opt/nexo" }),
    [string]$ImageTag = $(if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "ep3" }),
    [string]$Domain = $(if ($env:DOMAIN) { $env:DOMAIN } else { "nexo.local" })
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not $Ec2Host) { throw "Define EC2_HOST o -Ec2Host" }
if (-not $SshKey) { throw "Define SSH_KEY o -SshKey" }
if (-not (Test-Path $SshKey)) { throw "No existe la llave SSH: $SshKey" }

$requeridos = @{
    DB_PASSWORD          = $env:DB_PASSWORD
    RABBITMQ_PASSWORD    = $env:RABBITMQ_PASSWORD
    NVIDIA_API_KEY       = $env:NVIDIA_API_KEY
    ANONYMIZATION_SALT   = $env:ANONYMIZATION_SALT
}
foreach ($clave in $requeridos.Keys) {
    if ([string]::IsNullOrWhiteSpace($requeridos[$clave])) {
        throw "Falta la variable de entorno $clave"
    }
}

$sshOpts = @("-i", $SshKey, "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15")
$destino = "$SshUser@$Ec2Host"

# Generar .env local desde .env.example sin exponer secretos en el repositorio.
$lineas = Get-Content -Path ".env.example" -Encoding UTF8
$reemplazos = @{
    "IMAGE_TAG"                = $ImageTag
    "DOMAIN"                   = $Domain
    "DB_PASSWORD"              = $env:DB_PASSWORD
    "RABBITMQ_PASSWORD"        = $env:RABBITMQ_PASSWORD
    "NVIDIA_API_KEY"           = $env:NVIDIA_API_KEY
    "ANONYMIZATION_SALT"       = $env:ANONYMIZATION_SALT
    "SAGEMAKER_ENDPOINT_NAME"  = $(if ($env:SAGEMAKER_ENDPOINT_NAME) { $env:SAGEMAKER_ENDPOINT_NAME } else { "" })
    "S3_BUCKET"                = $(if ($env:S3_BUCKET) { $env:S3_BUCKET } else { "" })
}
$nuevas = foreach ($linea in $lineas) {
    if ($linea -match "^([A-Z0-9_]+)=") {
        $clave = $Matches[1]
        if ($reemplazos.ContainsKey($clave)) {
            "$clave=$($reemplazos[$clave])"
            continue
        }
    }
    $linea
}
$tmpEnv = Join-Path $env:TEMP "nexo-ep3.env"
$nuevas | Set-Content -Path $tmpEnv -Encoding UTF8

try {
    Write-Host "==> Preparando $RemoteDir en $Ec2Host"
    & ssh @sshOpts $destino "mkdir -p '$RemoteDir'"

    Write-Host "==> Copiando compose y .env"
    & scp @sshOpts "docker-compose.yml" "${destino}:${RemoteDir}/docker-compose.yml"
    & scp @sshOpts $tmpEnv "${destino}:${RemoteDir}/.env"
    & ssh @sshOpts $destino "chmod 600 '$RemoteDir/.env'"

    if ($env:GHCR_PAT) {
        Write-Host "==> Login en GHCR"
        $env:GHCR_PAT | & ssh @sshOpts $destino "docker login ghcr.io -u '$($env:GHCR_USER)' --password-stdin"
    }

    Write-Host "==> Descargando imágenes :$ImageTag y levantando servicios"
    & ssh @sshOpts $destino "cd '$RemoteDir' && docker compose pull && docker compose up -d --remove-orphans && docker compose ps"

    Write-Host "==> Despliegue completado"
    Write-Host "    Health:   https://$Ec2Host/api/health"
    Write-Host "    Campañas: POST https://$Ec2Host/api/campanas/{usuario}"
}
finally {
    Remove-Item $tmpEnv -Force -ErrorAction SilentlyContinue
}
