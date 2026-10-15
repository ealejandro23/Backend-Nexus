# =============================================================================
# DOCKERFILE - SERVICIO DE CARGA DE DATOS
# =============================================================================
# Servicio one-shot que carga los datos tratados en la base de datos
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar script de carga
COPY cargar.py .

# El servicio se ejecuta una sola vez y termina
CMD ["python", "cargar.py"]
