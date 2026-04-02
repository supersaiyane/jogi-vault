# Docker Deployment

## Two Compose Files

| File | Location | Purpose |
|------|----------|---------|
| `docker-compose.yml` | Project root | Full pipeline (vault + video + review) |
| `vault/docker-compose.yml` | vault/ folder | Vault standalone |

---

## Option A: Vault Standalone

Run the vault independently, without the video pipeline.

```bash
cd vault/
docker-compose up -d
open http://localhost:5111
```

### docker-compose.yml (vault/docker-compose.yml)

```yaml
services:
  vault:
    build:
      context: ..
      dockerfile: vault/Dockerfile
    image: jogi-vault
    container_name: jogi-vault
    restart: unless-stopped
    ports:
      - "${VAULT_UI_PORT:-5111}:5111"
    volumes:
      - ./data:/app/vault/data
    environment:
      - VAULT_UI_PORT=5111
      - VAULT_PASSWORD=${VAULT_PASSWORD:-}
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:5111')"]
      interval: 20s
      timeout: 5s
      retries: 3
      start_period: 8s
```

### .env file (create in vault/ folder)

```bash
VAULT_PASSWORD=VLT-xxxxxxxxxxx    # machine token from API tab
VAULT_UI_PORT=5111                # optional, change port
```

---

## Option B: Full Pipeline

Run the vault alongside the video pipeline and review UI.

```bash
# From project root
docker-compose up vault-ui -d                       # vault only
docker-compose --profile pipeline up -d             # vault + pipeline
docker-compose --profile review up -d               # vault + review UI
docker-compose --profile pipeline --profile review up -d  # everything
```

### Architecture

```
Your machine
┌───────────────────────────────────────────────────────┐
│  docker-compose                                       │
│  ┌─────────────────┐     ┌──────────────────────┐     │
│  │  vault-ui        │     │  jogi (pipeline)     │     │
│  │  Port 5111       │◀────│  VAULT_PASSWORD=VLT  │     │
│  │  Flask app       │     │  Python scripts      │     │
│  │  ┌────────────┐  │     │                      │     │
│  │  │ vault/data/ │  │     │  Direct: vault.get() │     │
│  │  │ (volume)    │  │     │  HTTP: /api/v1/...   │     │
│  │  └────────────┘  │     └──────────────────────┘     │
│  └─────────────────┘                                   │
│         ▲                 ┌──────────────────────┐     │
│    ./vault/data/          │  reviewer (nginx)    │     │
│    (mounted from host)    │  Port 8080           │     │
│                           └──────────────────────┘     │
└───────────────────────────────────────────────────────┘

Browser → http://localhost:5111 (vault)
Browser → http://localhost:8080 (video review)
```

---

## Environment Variables

| Variable | Used By | Required | Purpose |
|----------|---------|----------|---------|
| `VAULT_PASSWORD` | vault-ui, jogi | Yes | Machine token (VLT-...) — pre-unlocks vault |
| `VAULT_NAMESPACE` | jogi | No | Which namespace to load (default: `jogiexplains-yt`) |
| `VAULT_API_TOKEN` | jogi | No | REST API token (only for HTTP mode) |
| `VAULT_URL` | jogi | No | Internal vault URL (only for HTTP mode) |
| `VAULT_UI_PORT` | vault | No | Port to listen on (default: 5111) |

> Your pipeline uses **direct mode** (`VaultClient`), so `VAULT_API_TOKEN` and `VAULT_URL` are optional. They're only needed if you add a non-Python service that reads secrets over HTTP.

---

## Common Commands

```bash
# Standalone (from vault/)
docker-compose up -d
docker-compose up --build -d
docker-compose logs -f
docker-compose stop
docker-compose down
docker-compose down -v              # DANGER: removes volumes

# Full pipeline (from project root)
docker-compose up vault-ui -d
docker-compose up vault-ui --build -d
docker-compose logs -f vault-ui
docker-compose logs -f jogi
docker-compose stop
```

---

## Important Notes

- `vault/data/` is mounted as a volume — NOT baked into the image
- Never put your real password in the Dockerfile or compose file
- Use a machine token (`VLT-...`) in `VAULT_PASSWORD`
- The `jogi` container waits for `vault-ui` to be healthy before starting
- The backup scheduler only runs while the vault UI container is running
