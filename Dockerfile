FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    flask>=3.0.0 \
    cryptography>=43.0.0 \
    pyotp>=2.9.0 \
    "qrcode[pil]>=8.0.0" \
    pypng>=0.20220715.0 \
    rich>=13.8.0 \
    google-auth>=2.35.0 \
    google-auth-oauthlib>=1.2.0 \
    google-auth-httplib2>=0.2.0 \
    google-api-python-client>=2.149.0 \
    APScheduler>=3.10.4

COPY src/__init__.py src/__init__.py
COPY src/vault.py    src/vault.py
COPY vault/ui.py     vault/ui.py
COPY vault/backup.py vault/backup.py

# vault/data/ is mounted as a volume — not baked into the image
VOLUME ["/app/vault/data"]

EXPOSE 5111

ENV VAULT_UI_PORT=5111
ENV PYTHONPATH=/app

CMD ["python", "vault/ui.py"]
