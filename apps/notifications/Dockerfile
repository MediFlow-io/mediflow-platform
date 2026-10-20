FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --create-home appuser
USER appuser
EXPOSE 8095
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8095/healthz', timeout=2)"
# One worker process: it also runs the event listener. Threads serve the API.
CMD ["gunicorn", "app.wsgi:app", "--bind", "0.0.0.0:8095", "--workers", "1", "--threads", "8", "--access-logfile", "-"]
