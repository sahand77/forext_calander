FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FOREXFACTORY_CSV_PATH=/data/forex_factory_cache.csv \
    FOREXFACTORY_TZ=Asia/Tehran \
    FOREXFACTORY_API_HOST=0.0.0.0 \
    FOREXFACTORY_API_PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY scripts ./scripts

RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "-m", "src.forexfactory.api", "--host", "0.0.0.0", "--port", "8000", "--csv", "/data/forex_factory_cache.csv"]
