FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# tools/video_analyzer 패키지를 컨테이너에 복사 — main.py가 in-process로 사용
# (build context는 repo 루트 — docker-compose.yml context: ../..)
COPY tools/video_analyzer /app/tools/video_analyzer
RUN touch /app/tools/__init__.py

COPY infrastructure/notebook-gateway/services/incident-mcp/main.py /app/main.py

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
