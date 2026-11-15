FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY hardware/esp32-audiobook/tools/audiobookshelf_host.py /app/server.py
USER 1000:1000
ENTRYPOINT ["python", "-B", "/app/server.py"]
