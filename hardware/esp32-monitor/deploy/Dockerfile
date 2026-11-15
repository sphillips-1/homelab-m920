FROM python:3.12-slim
RUN python -m pip install --no-cache-dir esptool==5.6.0
COPY scripts/deploy-esp32-firmware.py scripts/esp32_profiles.py /app/
ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-B", "/app/deploy-esp32-firmware.py"]
