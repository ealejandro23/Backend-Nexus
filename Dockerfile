# =============================================================================
# DOCKERFILE - BACKEND NEXUS
# =============================================================================
# Imagen para el pipeline CI/CD de EP2
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY carga/requirements.txt ./ 2>/dev/null || true
RUN pip install --no-cache-dir pandas numpy scikit-learn joblib psycopg2-binary || true

# Copiar archivos del proyecto
COPY . .

# Variables de entorno
ENV DB_HOST=db \
    DB_PORT=5432 \
    DB_NAME=nexo \
    DB_USER=nexo \
    DB_PASSWORD=nexo123

# Comando por defecto
CMD ["echo", "Backend Nexus - EP2 Ready"]
