FROM python:3.12-alpine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=6099 DB_PATH=/data/vault.sqlite3
WORKDIR /app
COPY db.py manage.py server.py ./
COPY public ./public
RUN addgroup -S vault && adduser -S vault -G vault && mkdir -p /data && chown vault:vault /data
USER vault
EXPOSE 6099
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:6099/api/v1/health',timeout=2)"
CMD ["python","server.py"]
