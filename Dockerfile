FROM python:3.12-slim

# System deps: FFmpeg + build tools for whisper
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything
COPY server.py .
COPY static/ ./static/

RUN mkdir -p uploads outputs

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
