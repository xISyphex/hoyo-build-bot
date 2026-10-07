FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot
ENV CACHE_DIR=/app/data
VOLUME /app/data
CMD ["python", "-m", "bot"]
