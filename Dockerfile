FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system --gid 10001 swiftdeploy \
    && adduser --system --uid 10001 --ingroup swiftdeploy --home /app swiftdeploy

COPY app/main.py /app/main.py
COPY app/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt \
    && chown -R swiftdeploy:swiftdeploy /app

USER 10001:10001

EXPOSE 5000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${APP_PORT:-5000}"]
