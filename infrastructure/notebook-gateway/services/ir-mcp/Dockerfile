FROM python:3.12-slim

# adb 백엔드용 android-tools + curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl android-tools-adb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py keyevents.py rdk_keymap.py ./
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
