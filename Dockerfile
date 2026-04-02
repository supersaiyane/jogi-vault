FROM python:3.11-slim

LABEL maintainer="Gurpreet Sandhu <garryexplains.yt@gmail.com>"
LABEL description="Jogi Vault — AES-256-GCM encrypted secret manager"
LABEL version="2.0"

WORKDIR /app

# Install Python dependencies (pinned ranges)
RUN pip install --no-cache-dir \
    "flask>=3.0,<4.0" \
    "cryptography>=43.0,<44.0" \
    "pyotp>=2.9,<3.0" \
    "qrcode[pil]>=8.0,<9.0" \
    "pypng>=0.20220715,<1.0" \
    "rich>=13.8,<14.0" \
    "google-auth>=2.35,<3.0" \
    "google-auth-oauthlib>=1.2,<2.0" \
    "google-auth-httplib2>=0.2,<1.0" \
    "google-api-python-client>=2.149,<3.0" \
    "APScheduler>=3.10,<4.0"

# Copy only the files needed at runtime
COPY src/__init__.py     src/__init__.py
COPY src/vault.py        src/vault.py
COPY vault/__init__.py   vault/__init__.py
COPY vault/app.py        vault/app.py
COPY vault/helpers.py    vault/helpers.py
COPY vault/ui.py         vault/ui.py
COPY vault/services/     vault/services/
COPY vault/routes/       vault/routes/
COPY vault/middleware/    vault/middleware/
COPY vault/templates/    vault/templates/
COPY vault/static/       vault/static/

# vault/data/ is mounted as a volume — never baked into the image
VOLUME ["/app/vault/data"]

EXPOSE 5111

ENV VAULT_UI_PORT=5111
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=20s --timeout=5s --start-period=8s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5111')" || exit 1

CMD ["python", "vault/ui.py"]
