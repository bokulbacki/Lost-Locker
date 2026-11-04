FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lostlocker ./lostlocker
COPY wsgi.py .

# Run as an unprivileged user; uploaded photos go in a volume it can write to.
RUN useradd --system --uid 10001 app \
    && mkdir -p /data/uploads \
    && chown -R app /data
USER app
ENV UPLOAD_FOLDER=/data/uploads
VOLUME /data/uploads

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "wsgi:app"]
