# Jogi Vault

A self-contained encrypted secret manager.
Stores API keys and credentials in an AES-encrypted file — safe to commit to git.
Exposes a web UI, a CLI, and a REST API so any language can read secrets without touching `.env` files.

---

## Features

| Feature | Description |
|---|---|
| AES-128 + HMAC-SHA256 | Authenticated encryption — tamper is detected automatically |
| PBKDF2-SHA256 | 480 000 iterations — brute-force resistant |
| TOTP 2FA | YubiKey, Google Authenticator, Authy, 1Password, or any TOTP app |
| Recovery key | `JOGI-…` resets master password if forgotten |
| Emergency key | `EMRG-…` one-time TOTP bypass — auto-regenerates after use |
| Machine token | `VLT-…` hides real password from config files |
| Key tags | Label secrets: API Key, Password, RSA Private/Public, Access Token… |
| Namespaces | Separate encrypted store per project, same password |
| REST API | `GET /api/v1/secret/KEY` — fetch individual keys from any language |
| Google Drive backup | Auto-backup every N hours, email-verified restore |
| Web UI | http://localhost:5111 |
| CLI | `vault/cli.py` |
| Docker | `docker-compose up vault-ui` |

---

## Quick start

```bash
# Docker (recommended)
docker-compose up vault-ui
# Open http://localhost:5111 — setup wizard appears on first visit

# Local Python
make -f vault/Makefile up
```

---

## First-time setup (web wizard)

1. Open `http://localhost:5111`
2. **Set master password** — choose something strong (16+ chars)
3. **Scan QR code** — open any TOTP app, scan, confirm with the 6-digit code
4. **Save your keys** — shown once, store in a password manager:
   ```
   JOGI-XXXXX-XXXXX-XXXXX-XXXXX   ← recovery key (password reset)
   EMRG-XXXXX-XXXXX-XXXXX-XXXXX   ← emergency key (TOTP bypass)
   ```
5. **Generate a machine token** — API tab → Generate Machine Token → copy `VLT-…`
6. Put the machine token in your `.env`:
   ```
   VAULT_PASSWORD=VLT-xxxxxxxxxxxxxxxxxxx
   ```

---

## Machine token — why and how

Your real password never goes in any config file.
A machine token (`VLT-…`) resolves to the real password internally.

```
Real password  →  PBKDF2  →  encrypts vault.enc        (stays in your head)
Machine token  →  PBKDF2  →  decrypts real password    (safe for config files)
```

```bash
# Generate from CLI
make -f vault/Makefile generate-token P=your_real_password

# Revoke (instantly blocks all automated access)
make -f vault/Makefile revoke-token P=your_real_password
```

**Security:** If someone reads your `.env` they get the `VLT-…` token.
Without `vault/data/vault.token` on disk the token is useless.
Changing your master password auto-revokes all machine tokens.

---

## Using vault in Python code

### Option A — Direct (same Python project, fastest)

No HTTP. No vault UI needed. Reads `VAULT_PASSWORD` from env automatically.

```python
# Import once at the top of any file
from src.vault_client import vault

# Get a single key
api_key  = vault.get("ANTHROPIC_API_KEY")
voice_id = vault.get("ELEVENLABS_VOICE_ID")

# Get multiple keys at once → returns a dict
keys = vault.get_many("ANTHROPIC_API_KEY", "ELEVENLABS_KEY", "PEXELS_API_KEY")
anthropic = keys["ANTHROPIC_API_KEY"]

# Get from a specific namespace
stripe  = vault.get("STRIPE_KEY",   ns="payments")
db_pass = vault.get("DB_PASSWORD",  ns="internal")

# Get everything in a namespace
all_keys = vault.all(ns="payments")

# List key names only (no values)
names = vault.keys()
names = vault.keys(ns="payments")

# List all namespaces
spaces = vault.namespaces()

# Force re-read from disk (clears in-memory cache)
vault.clear_cache()
vault.clear_cache(ns="payments")
```

Caching behaviour: the first `vault.get("KEY")` decrypts from disk and caches in memory.
Every subsequent call returns from memory instantly — no re-auth, no re-decrypt.

```python
# Custom instance (explicit password, no caching)
from src.vault_client import VaultClient

v = VaultClient(password="VLT-abc123", cache_values=False)
key = v.get("MY_KEY")
```

### Option B — HTTP API (any language, separate service)

Requires the vault UI to be running. Uses the REST API token.

```python
from src.vault_client import VaultHTTPClient

# Reads VAULT_URL and VAULT_API_TOKEN from env
http = VaultHTTPClient()

key  = http.get("ANTHROPIC_API_KEY")
keys = http.get_many("ANTHROPIC_API_KEY", "ELEVENLABS_KEY")
all  = http.all(ns="payments")
```

**curl:**
```bash
# Single key
curl http://localhost:5111/api/v1/secret/ANTHROPIC_API_KEY \
     -H "Authorization: Bearer YOUR_API_TOKEN"

# From a namespace
curl "http://localhost:5111/api/v1/secret/STRIPE_KEY?ns=payments" \
     -H "Authorization: Bearer YOUR_API_TOKEN"

# List all keys
curl http://localhost:5111/api/v1/secrets \
     -H "Authorization: Bearer YOUR_API_TOKEN"

# List namespaces
curl http://localhost:5111/api/v1/namespaces \
     -H "Authorization: Bearer YOUR_API_TOKEN"
```

**JavaScript / Node:**
```js
const VAULT = "http://localhost:5111/api/v1";
const TOKEN = process.env.VAULT_API_TOKEN;

async function getSecret(key, ns = "default") {
  const r = await fetch(`${VAULT}/secret/${key}?ns=${ns}`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  const { value } = await r.json();
  return value;
}

const apiKey = await getSecret("ANTHROPIC_API_KEY");
const stripe = await getSecret("STRIPE_KEY", "payments");
```

---

## docker-compose integration

### .env file (gitignored)
```bash
# Machine token — generated from API tab in vault UI
VAULT_PASSWORD=VLT-xxxxxxxxxxxxxxxxxxx

# REST API token — generated from API tab in vault UI
VAULT_API_TOKEN=xxxxxxxxxxxxxxxxxxxx

# Vault base URL — for HTTP mode
VAULT_URL=http://localhost:5111
```

### docker-compose.yml
```yaml
services:

  vault-ui:
    build:
      context: .
      dockerfile: vault/Dockerfile
    image: jogi-vault-ui
    container_name: jogi-vault-ui
    restart: unless-stopped
    ports:
      - "5111:5111"
    volumes:
      - ./vault/data:/app/vault/data
    environment:
      - VAULT_UI_PORT=5111
      - VAULT_PASSWORD=${VAULT_PASSWORD}   # pre-unlocks vault for API on startup

  my-app:
    build: .
    depends_on:
      - vault-ui
    environment:
      - VAULT_PASSWORD=${VAULT_PASSWORD}   # machine token — for direct Python access
      - VAULT_API_TOKEN=${VAULT_API_TOKEN} # REST API token — for HTTP access
      - VAULT_URL=http://vault-ui:5111     # internal Docker network URL
```

When `VAULT_PASSWORD` is set in the vault-ui container, the API is pre-unlocked on startup — no UI login required. Any service in the same Docker network can call `/api/v1/secret/KEY`.

---

## Namespaces — one vault, multiple projects

```bash
# Create namespaces from the web UI (API tab → New Namespace)
# or from the CLI:
make -f vault/Makefile new-namespace P=xxx NS=payments
make -f vault/Makefile new-namespace P=xxx NS=internal

# Each namespace is a separate .enc file, same password
# vault/data/vault.enc          → default
# vault/data/vault-payments.enc → payments
# vault/data/vault-internal.enc → internal
```

In code:
```python
from src.vault_client import vault

default_key = vault.get("ANTHROPIC_API_KEY")              # default namespace
stripe_key  = vault.get("STRIPE_SECRET", ns="payments")
db_pass     = vault.get("DB_PASSWORD",   ns="internal")
```

---

## Makefile reference

```bash
# UI
make up                          # start locally → http://localhost:5111
make docker-up                   # start via docker-compose
make docker-build                # rebuild image + restart
make docker-logs                 # tail container logs
make docker-down                 # stop container

# Secrets   (P=password or VLT-token)
make list        P=xxx
make set         P=xxx K=MY_KEY V=my_value
make get         P=xxx K=MY_KEY
make delete      P=xxx K=MY_KEY
make import-env  P=xxx           # import from ../.env

# Namespaces
make namespaces  P=xxx
make new-namespace   P=xxx NS=payments
make delete-namespace P=xxx NS=payments

# Password / 2FA
make change-password             # prompts interactively
make forgot-password             # reset with recovery key
make save-password               # verify + save to ~/.zshrc
make setup-totp   P=xxx
make disable-totp P=xxx
make new-emergency-key P=xxx

# Machine token
make generate-token P=real_password   # generates VLT-… token
make revoke-token   P=xxx

# Backup
make backup P=xxx                # manual Google Drive backup

# Info
make status                      # health check
make help                        # full command list
```

---

## Security model

```
Normal login        →  password  +  TOTP code
Lost authenticator  →  password  +  Emergency key (EMRG-…)
Forgot password     →  Recovery key (JOGI-…)
Automated access    →  Machine token (VLT-…) in VAULT_PASSWORD env var
API access          →  REST API token in Authorization: Bearer header
Vault corrupted     →  Restore from Google Drive backup (email-verified)
```

| What gets stored | Where | Encrypted? |
|---|---|---|
| Secrets | `vault/data/vault.enc` | AES-128 + HMAC |
| TOTP secret | `vault/data/vault.totp` | AES-128 |
| Recovery bundle | `vault/data/vault.recovery` | AES-128 |
| Emergency key | `vault/data/vault.emergency` | PBKDF2 hash only |
| Machine token bundle | `vault/data/vault.token` | AES-128 |
| Drive backup oauth | `vault/data/backup-oauth.json` | plaintext client creds |
| Real password | nowhere | never stored |

---

## What to commit to git

| File | Commit? |
|---|---|
| `vault/data/vault.enc` | ✅ encrypted |
| `vault/data/vault.salt` | ✅ not sensitive |
| `vault/data/vault.totp` | ✅ encrypted |
| `vault/data/vault.recovery` | ✅ encrypted |
| `vault/data/vault.emergency` | ✅ hash only |
| `vault/data/vault.token` | ✅ encrypted |
| `vault/data/backup-oauth.json` | ✅ not sensitive |
| `VAULT_PASSWORD` / real password | ❌ never |
| Recovery key plaintext | ❌ store in password manager |
| Emergency key plaintext | ❌ store in password manager |
| `.env` | ❌ gitignored |
