# ==========================================================================
#  PaddleOCR — wrapper web (FastAPI) sobre a biblioteca PaddleOCR
# ==========================================================================
FROM python:3.10-slim

# Dependências de sistema para PaddlePaddle / OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        ffmpeg \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# uvicorn = servidor ASGI. 1 worker (modelo pesado em memória).
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
