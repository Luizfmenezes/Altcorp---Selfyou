# ==========================================================================
#  Background Remover — wrapper web (Flask) sobre a CLI 'backgroundremover'
# ==========================================================================
FROM python:3.10-slim

# Dependências de sistema exigidas por opencv/ffmpeg (usadas pela lib)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsm6 \
        libxext6 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# torch (CPU) é grande — instala primeiro para aproveitar cache de camada
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Diretórios de trabalho para uploads/resultados
RUN mkdir -p /app/uploads /app/results

EXPOSE 5000

# gunicorn = servidor de produção. 1 worker (modelo de IA pesado), timeout alto.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "600", "app:app"]
