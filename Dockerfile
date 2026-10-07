FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot
# Railway rejects the VOLUME instruction; mount a volume at /app/data on the host instead.
ENV CACHE_DIR=/app/data PYTHONUNBUFFERED=1
CMD ["python", "-m", "bot"]
