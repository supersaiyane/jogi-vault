# Quick Start Guide

Get the vault running and storing secrets in 5 minutes.

---

## 1. Start the vault

```bash
# Local Python
make -f vault/Makefile up

# Or Docker
docker-compose up vault-ui -d
```

## 2. Complete setup wizard

Open `http://localhost:5111` → set password → scan QR → save keys.

## 3. Add your first secret

**Web UI:** Secrets tab → "+ Add key" → enter key name + value → Save

**CLI:**
```bash
make -f vault/Makefile set P=yourpassword K=ANTHROPIC_API_KEY V=sk-ant-api03-xxxxx
```

## 4. Generate a machine token

Web UI → API tab → "Generate Machine Token" → copy VLT-...

```bash
export VAULT_PASSWORD=VLT-xxxxxxxxxxxxxxxxxxx
```

## 5. Use in your code

```python
from src.vault_client import vault

api_key = vault.get("ANTHROPIC_API_KEY")
```

## 6. Verify everything works

```bash
make -f vault/Makefile status
make -f vault/Makefile list P=xxx
```

---

## What's next?

| Want to... | Go to |
|-----------|-------|
| Add more secrets | [Secret Management](Secret-Management) |
| Separate keys by project | [Namespaces](Namespaces) |
| Set up backups | [Backup & Restore](Backup-&-Restore) |
| Use from curl/JS/Go | [REST API](REST-API) |
| Run in Docker | [Docker Deployment](Docker-Deployment) |
