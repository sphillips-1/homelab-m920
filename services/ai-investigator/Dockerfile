FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
USER 10001:10001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--limit-concurrency", "8"]
