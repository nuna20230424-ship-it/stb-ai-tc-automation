FROM python:3.12-slim

# bluez (Linux BT 스택), bluetoothctl, curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez bluez-tools \
    dbus libdbus-1-dev libglib2.0-dev pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
