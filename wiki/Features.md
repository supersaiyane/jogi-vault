# Features — Complete Overview

One-shot reference of everything Jogi Vault can do.

> **Version:** 2.0 (AES-256-GCM upgrade) | **Last updated:** 2026-04-02

---

## 1. Encryption

### AES-256-GCM (Galois/Counter Mode)

The gold standard for authenticated encryption. Replaced the earlier AES-128 Fernet implementation.

| Property | Value |
|----------|-------|
| Algorithm | AES-256-GCM |
| Key size | 256 bits (32 bytes) |
| Nonce | 12 bytes, random per write |
| Auth tag | Built-in (GCM) — detects tampering |
| Format | `JV01` (4B magic) + nonce (12B) + ciphertext + tag |

- Same plaintext never produces the same ciphertext (fresh nonce each time)
- Legacy Fernet data auto-detected and transparently migrated on next write
- Zero-downtime migration — no manual steps

### PBKDF2-SHA256 Key Derivation

| Property | Value |
|----------|-------|
| Hash | SHA-256 |
| Iterations | 480,000 |
| Salt | 16 bytes, random per namespace |
| Output | 32 bytes (used as AES-256 key) |

- Your password is never used directly — always derived through PBKDF2
- Random salt per namespace — same password produces different keys
- Salt stored in `vault.salt` (safe to commit)

---

## 2. Authentication

### Master Password
- Primary auth factor — derives the encryption key
- Never stored anywhere — only in your memory and RAM during a session

### TOTP Two-Factor Authentication
- Works with: YubiKey, Google Authenticator, Microsoft Authenticator, Authy, 1Password
- 30-second rolling codes, ±1 window tolerance
- TOTP secret encrypted with AES-256-GCM in `vault.totp`
- Enable: `make setup-totp P=xxx` | Disable: `make disable-totp P=xxx`

### Emergency Key (`EMRG-XXXXX-XXXXX-XXXXX-XXXXX`)
- One-time TOTP bypass when you lose your authenticator
- Single use — consumed on use, new key auto-generated
- Stored as PBKDF2 hash (not reversible) in `vault.emergency`
- Rotate: `make new-emergency-key P=xxx`

### Recovery Key (`JOGI-XXXXX-XXXXX-XXXXX-XXXXX`)
- Resets master password if forgotten (your last resort)
- Encrypts a copy of your current password
- Does NOT bypass TOTP
- Shown once during setup — store in password manager

### Machine Token (`VLT-xxxxxxxxx...`)
- Hides real password from config files / env vars
- Two-part security: need both `VLT-...` token AND `vault.token` file on disk
- Password change auto-revokes all tokens
- Instant revocation without password change
- Usage: `export VAULT_PASSWORD=VLT-xxxxxxxxxxxxxxxxxxx`

---

## 3. Secret Management

### Key-Value Store
- Secrets stored as key-value pairs (keys auto-uppercased)
- Values can be any string: API keys, JSON blobs, URLs, certificates
- Operations: `set`, `get`, `delete`, `list`, `import-env`

### Key Tags / Types

| Tag | Label | Color |
|-----|-------|-------|
| `api_key` | API Key | Blue |
| `password` | Password | Red |
| `rsa_private` | RSA Private Key | Dark Red |
| `rsa_public` | RSA Public Key | Green |
| `access_token` | Access Token | Yellow |
| `secret` | Secret | Purple |
| `url` | URL / Endpoint | Teal |
| `email` | Email | Gray |
| `certificate` | Certificate | Orange |
| `other` | Other | Dim |

Color-coded badges in web UI, filterable by type.

### Secret Expiry / TTL
- Optional expiry timestamp on any secret
- Track when API keys need rotation
- Advisory only — expired keys still return values (won't break your pipeline)
- Expiry metadata auto-cleaned on delete

```python
vault.set_with_expiry("KEY", "value", "2026-12-31T00:00:00+00:00")
vault.is_expired("KEY")              # True/False
vault.list_expiring(within_days=30)  # [("KEY", "2026-12-31T...")]
```

```bash
make set-expiry P=xxx K=KEY V=value E=2026-12-31
make expiring P=xxx DAYS=30
```

### Namespaces
- Separate encrypted store per project — same password, isolated secrets
- Each namespace gets its own `.enc` + `.salt` files
- Shared: master password, TOTP, recovery/emergency keys

```
vault/data/vault.enc              → default
vault/data/vault-payments.enc     → "payments"
vault/data/vault-staging.enc      → "staging"
```

```python
vault.get("KEY", ns="payments")
vault.all(ns="staging")
```

```bash
make new-namespace P=xxx NS=payments
make delete-namespace P=xxx NS=payments
make namespaces
```

---

## 4. Access Methods

### Web UI (`http://localhost:5111`)
- Setup wizard (password → TOTP → recovery/emergency keys)
- Login with password + TOTP
- **Secrets tab:** add, edit, delete, show/hide values, filter by tag
- **Backup tab:** Google Drive backup, restore, scheduling
- **API tab:** machine token, REST API token, namespace management
- Dark theme, mobile-friendly
- Identity guard: edit/delete requires re-authentication

### CLI (`vault/cli.py`)
```bash
python vault/cli.py set KEY VALUE
python vault/cli.py get KEY
python vault/cli.py list
python vault/cli.py delete KEY
python vault/cli.py import-env .env
python vault/cli.py change-password
python vault/cli.py forgot-password
```

### Makefile (`vault/Makefile`)
```bash
make set P=xxx K=KEY V=value
make get P=xxx K=KEY
make list P=xxx
make delete P=xxx K=KEY
make status
make help                    # full target list
```

### REST API
```
GET /api/v1/secret/<KEY>         → single secret
GET /api/v1/secret/<KEY>?ns=work → from namespace
GET /api/v1/secrets              → list key names
GET /api/v1/namespaces           → list namespaces
```
Auth: `Authorization: Bearer <token>` header

```bash
curl localhost:5111/api/v1/secret/MY_KEY -H "Authorization: Bearer TOKEN"
```

### Python Client (`src/vault_client.py`)

**Direct mode** (fastest, no HTTP):
```python
from src.vault_client import vault
key = vault.get("ANTHROPIC_API_KEY")
keys = vault.get_many("KEY1", "KEY2", "KEY3")
everything = vault.all(ns="payments")
```

**HTTP mode** (any service, needs vault UI running):
```python
from src.vault_client import VaultHTTPClient
http = VaultHTTPClient()
key = http.get("ANTHROPIC_API_KEY")
```

Both cache values in memory. Call `.clear_cache()` to re-read.

---

## 5. Backup & Recovery

### Google Drive Backup
- OAuth2 authentication with Google Drive API
- Configurable schedule: every 1, 2, 4, 8, 12, or 24 hours
- Auto-pruning: keeps 10 most recent backups
- Manual backup: web UI button or `make backup P=xxx`
- Format: zip of all `vault/data/` files (encrypted at rest)

### Restore with Email Verification
1. Click "Restore" next to a backup
2. 6-digit code sent to configured email
3. Enter code to confirm
4. Vault data replaced with backup contents

Prevents unauthorized restores. Requires Gmail + App Password.

---

## 6. Security Features

### Session Encryption
- Vault password in Flask session cookie encrypted with AES-256-GCM
- Derived from server's random secret key
- Even if cookie intercepted, password cannot be extracted

### CSRF Protection
- Cryptographic CSRF token per session
- Auto-injected into every POST form via `after_request` hook
- Validated on every POST (except API routes)

### Login Rate Limiting
- Max 5 attempts per IP per 5-minute window
- Prevents online brute-force attacks

### Audit Log (`vault/data/audit.log`)
- Append-only JSON lines
- Logs: logins, CRUD ops, password changes, token ops, namespace ops
- Never blocks vault operations (fails silently)

```bash
make audit                # last 20 entries
make audit-failures       # failed operations only
```

### Zip Path Traversal Protection
- Backup restore validates all zip paths before extraction
- Rejects paths that escape `vault/data/` (e.g., `../../etc/crontab`)

### Identity Guard
- Edit/delete in web UI requires re-entering password + TOTP
- Prevents damage from session hijacking or unlocked browser

### Constant-Time Comparisons
- `secrets.compare_digest()` for all token/code checks
- Prevents timing attacks

### Pinned Dependencies
- Docker: `>=X.Y,<X+1.0` ranges prevent breaking upgrades

### macOS Keychain
- `make save-password` stores to Keychain, not `~/.zshrc`
- `make load-password` shows the retrieval command

---

## 7. Docker Support

### Dockerfile (`vault/Dockerfile`)
- Python 3.11-slim base
- All deps installed at build time
- `vault/data/` mounted as volume (not baked in)
- Port 5111

### Two Compose Files

| File | Location | Purpose |
|------|----------|---------|
| `docker-compose.yml` | Project root | Full pipeline (vault + video + review) |
| `vault/docker-compose.yml` | vault/ | Vault standalone |

```bash
# Standalone
cd vault/ && docker-compose up -d

# Full pipeline
docker-compose --profile pipeline up -d
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `VAULT_PASSWORD` | Machine token — pre-unlocks vault |
| `VAULT_NAMESPACE` | Namespace for pipeline (e.g., `jogiexplains-yt`) |
| `VAULT_API_TOKEN` | REST API token (HTTP mode only) |
| `VAULT_URL` | Vault URL (HTTP mode only) |
| `VAULT_UI_PORT` | Port to listen on (default: 5111) |

---

## 8. File Reference

### Code

| File | Purpose |
|------|---------|
| `vault/ui.py` | Web UI (Flask) |
| `vault/cli.py` | CLI |
| `vault/backup.py` | Google Drive backup |
| `vault/Dockerfile` | Container |
| `vault/Makefile` | Make targets |
| `vault/docker-compose.yml` | Standalone compose |
| `src/vault.py` | Core encryption engine |
| `src/vault_client.py` | Python clients |

### Data (`vault/data/`)

| File | Encrypted | Content |
|------|-----------|---------|
| `vault.enc` | AES-256-GCM | Secrets (default namespace) |
| `vault.salt` | No | Password salt |
| `vault.totp` | AES-256-GCM | TOTP secret |
| `vault.recovery` | AES-256 (Fernet) | Recovery key bundle |
| `vault.emergency` | PBKDF2 hash | Emergency key (not reversible) |
| `vault.token` | AES-256 (Fernet) | Machine token bundle |
| `audit.log` | No | Security audit log |
| `backup-oauth.json` | No | Google Drive OAuth creds |
| `vault-<ns>.enc` | AES-256-GCM | Namespace secrets |
| `vault-<ns>.salt` | No | Namespace salt |

### Documentation

| File | Content |
|------|---------|
| `README.md` | Project docs |
| `wiki/` | Full documentation wiki (23 pages) |
